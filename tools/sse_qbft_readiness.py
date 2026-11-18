#!/usr/bin/env python3
"""Read-only SSE multi-node QBFT identity / genesis / head-consistency gate.

Only standard eth/net/qbft read methods are used. No wallets, signing,
account unlock, validator vote, SSH, transactions, or chain mutation.
"""
from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from sse_network_peers import verify, PeerCatalogError, _read, MAX_MANIFEST_BYTES


class QBFTReadinessError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise QBFTReadinessError("RPC redirect forbidden")


def safe_rpc(url: str) -> str:
    if type(url) is not str or any(c.isspace() for c in url):
        raise QBFTReadinessError("invalid RPC URL")
    u = urlsplit(url)
    try:
        port = u.port
    except ValueError:
        raise QBFTReadinessError("invalid RPC port") from None
    if (u.scheme not in ("https", "http") or not u.hostname or
            u.username or u.password or u.query or u.fragment or
            u.path not in ("", "/") or
            (u.scheme == "http" and u.hostname not in ("127.0.0.1", "localhost", "::1")) or
            (port is not None and not 1 <= port <= 65535)):
        raise QBFTReadinessError("RPC requires HTTPS or localhost HTTP without credentials")
    return url


def rpc(url: str, method: str, params: list) -> object:
    safe_rpc(url)
    allowed = {"eth_chainId", "eth_blockNumber", "eth_getBlockByNumber",
               "net_peerCount", "qbft_getValidatorsByBlockNumber"}
    if method not in allowed:
        raise QBFTReadinessError("mutating/unknown RPC method forbidden")
    data = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "method": method, "params": params}).encode("utf-8")
    req = Request(url, data=data, method="POST",
                  headers={"Content-Type": "application/json"})
    try:
        with build_opener(NoRedirect()).open(req, timeout=8) as response:
            if response.status != 200:
                raise QBFTReadinessError("RPC returned non-200")
            result = response.read(131073)
    except (OSError, TimeoutError) as exc:
        raise QBFTReadinessError("RPC unavailable") from None
    if len(result) > 131072:
        raise QBFTReadinessError("oversized RPC")
    try:
        doc = json.loads(result)
    except (ValueError, UnicodeError) as exc:
        raise QBFTReadinessError("malformed RPC response") from None
    if (type(doc) is not dict or doc.get("jsonrpc") != "2.0" or
            doc.get("id") != 1 or "error" in doc or "result" not in doc
            or doc["result"] is None):
        raise QBFTReadinessError("RPC returned error or missing result")
    return doc["result"]


def _hex_number(value) -> int:
    if (type(value) is not str or not value.startswith("0x")
            or not 1 <= len(value) <= 66):
        raise QBFTReadinessError("invalid RPC hex quantity")
    try:
        return int(value[2:], 16)
    except ValueError:
        raise QBFTReadinessError("invalid RPC quantity") from None


def inspect(url: str, *, expected_chain_id: int, expected_genesis_hash: str,
            expected_validators: int, call=rpc) -> dict:
    safe_rpc(url)
    chain = _hex_number(call(url, "eth_chainId", []))
    if chain != expected_chain_id:
        raise QBFTReadinessError("wrong chain ID at " + url)
    genesis = call(url, "eth_getBlockByNumber", ["0x0", False])
    if (type(genesis) is not dict or type(genesis.get("hash")) is not str
            or genesis["hash"].lower() != expected_genesis_hash.lower()):
        raise QBFTReadinessError("genesis mismatch at " + url)
    head = _hex_number(call(url, "eth_blockNumber", []))
    peers = _hex_number(call(url, "net_peerCount", []))
    validators = call(url, "qbft_getValidatorsByBlockNumber", ["latest"])
    if (type(validators) is not list or len(validators) != expected_validators
            or len({str(v).lower() for v in validators}) != len(validators)):
        raise QBFTReadinessError("validator list differs from signed catalog size")
    return {"url": url, "chainId": chain, "genesisHash": genesis["hash"].lower(),
            "head": head, "peerCount": peers, "validatorCount": len(validators),
            "validators": [str(v).lower() for v in validators]}


def inspect_many(urls: list[str], *, chain_id: int, genesis_hash: str,
                 expected_validators: int, call=rpc, require_four=False) -> dict:
    if not urls or len(urls) != len(set(urls)) or len(urls) > 16:
        raise QBFTReadinessError("requires unique 1-16 RPC endpoints")
    if require_four and len(urls) != 4:
        raise QBFTReadinessError("distributed 4-validator acceptance requires 4 endpoints")
    nodes = [inspect(url, expected_chain_id=chain_id,
                     expected_genesis_hash=genesis_hash,
                     expected_validators=expected_validators, call=call)
             for url in urls]
    heights = [item["head"] for item in nodes]
    common_height = min(heights)
    common = []
    for item in nodes:
        block = call(item["url"], "eth_getBlockByNumber", [hex(common_height), False])
        if type(block) is not dict or type(block.get("hash")) is not str:
            raise QBFTReadinessError("missing common-height block")
        common.append(block["hash"].lower())
    if len(set(common)) != 1:
        raise QBFTReadinessError("consensus head divergence at common height")
    lists = {tuple(sorted(item["validators"])) for item in nodes}
    if len(lists) != 1:
        raise QBFTReadinessError("validator views disagree")
    if require_four and (common_height < 1 or any(item["peerCount"] < 2 for item in nodes)):
        raise QBFTReadinessError("insufficient produced blocks or multi-peer connectivity")
    return {
        "kind": "SSE_QBFT_READONLY_AGREEMENT",
        "chainId": chain_id, "genesisHash": genesis_hash.lower(),
        "commonBlockNumber": common_height, "commonBlockHash": common[0],
        "rpcNodes": len(nodes), "validatorSetSize": expected_validators,
        "peers": [{"url": item["url"], "head": item["head"],
                   "peerCount": item["peerCount"]} for item in nodes],
        "transactionsSent": False, "validatorVotesSent": False,
        "provedPhysicalIndependence": False, "provedConsensusFinality": False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only live QBFT peer/chain gate")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--public-key", required=True)
    ap.add_argument("--genesis-hash", required=True)
    ap.add_argument("--rpc-url", action="append", required=True)
    ap.add_argument("--require-four", action="store_true")
    a = ap.parse_args(argv)
    try:
        from pathlib import Path
        envelope = json.loads(_read(Path(a.manifest), MAX_MANIFEST_BYTES))
        trusted = _read(Path(a.public_key), 8192)
        catalog = verify(envelope, trusted, chain_id=31338,
                         genesis_hash=a.genesis_hash)
        report = inspect_many(a.rpc_url, chain_id=31338,
                              genesis_hash=catalog["genesisHash"],
                              expected_validators=catalog["validators"],
                              require_four=a.require_four)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (PeerCatalogError, QBFTReadinessError, OSError, ValueError,
            UnicodeError) as exc:
        print("SSE_QBFT_READINESS_REFUSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
