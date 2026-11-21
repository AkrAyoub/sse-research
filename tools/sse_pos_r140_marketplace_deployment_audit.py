#!/usr/bin/env python3
"""R140: read-only SSE marketplace contract deployment verifier on chain 31340.

This verifier does not deploy, fund, sign, or submit transactions. Its manifest
records ACTUAL deployment addresses and independently pinned runtime bytecode
SHA256 hashes. A nonempty code response alone is not provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request

ADDR = re.compile(r"0x[0-9a-fA-F]{40}\Z")
HASH = re.compile(r"0x[0-9a-fA-F]{64}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
FIELDS = frozenset(("schema", "chainId", "executionGenesisHash",
                    "contracts"))
NAMES = frozenset(("committee", "settlement", "board"))
ALLOWED_RPC = frozenset(("http://127.0.0.1:18545", "http://127.0.0.1:28545"))
ABI = {"committee": "settlement()", "settlement": "resourceBoard()",
       "board": "approvedSettlement()"}

class Refused(ValueError):
    pass

def validate(obj):
    if type(obj) is not dict or set(obj) != FIELDS:
        raise Refused("unknown/missing chain manifest keys")
    if obj["schema"] != "SSE_R140_CHAIN31340_DEPLOYMENT_V1" or (
            type(obj["chainId"]) is not int or obj["chainId"] != 31340):
        raise Refused("wrong chain identity")
    if type(obj["executionGenesisHash"]) is not str or not HASH.fullmatch(
            obj["executionGenesisHash"]) or int(obj["executionGenesisHash"], 16) == 0:
        raise Refused("expected independently pinned execution genesis hash")
    contracts = obj["contracts"]
    if type(contracts) is not dict or set(contracts) != NAMES:
        raise Refused("all three SSE contract records required")
    seen = set()
    for name in sorted(NAMES):
        entry = contracts[name]
        if type(entry) is not dict or set(entry) != {"address", "runtimeSha256"}:
            raise Refused("contract must have address and pinned runtime digest")
        address, digest = entry["address"], entry["runtimeSha256"]
        if (type(address) is not str or not ADDR.fullmatch(address)
                or int(address, 16) == 0 or address.lower() in seen):
            raise Refused("invalid/duplicate contract address")
        if type(digest) is not str or not SHA.fullmatch(digest) or int(digest, 16) == 0:
            raise Refused("missing independent runtime-code hash pin")
        seen.add(address.lower())
    return obj

def load(path):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 4096:
        raise Refused("manifest absent, symlinked or oversized")
    return validate(json.loads(path.read_text("utf-8")))

def rpc(url, method, params):
    if url not in ALLOWED_RPC:
        raise Refused("RPC must be one of the two reviewed local node endpoints")
    body = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "method": method, "params": params}).encode()
    request = urllib.request.Request(url, body, method="POST",
                                     headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=8) as response:
        if response.status != 200:
            raise Refused("local RPC error")
        raw = response.read(131073)
    if len(raw) > 131072:
        raise Refused("oversized RPC response")
    result = json.loads(raw)
    if (type(result) is not dict or result.get("jsonrpc") != "2.0"
            or result.get("id") != 1 or "error" in result
            or "result" not in result):
        raise Refused("RPC malformed or returned an error")
    return result["result"]

def selector(signature):
    # Ethereum uses Keccak-256, not Python hashlib.sha3_256.
    from Crypto.Hash import keccak
    h = keccak.new(digest_bits=256)
    h.update(signature.encode("ascii"))
    return "0x" + h.digest()[:4].hex()

def decoded_address(value):
    if (type(value) is not str
            or not re.fullmatch(r"0x[0-9a-fA-F]{64}\Z", value)
            or int(value[:26], 16) != 0):
        raise Refused("contract address-return ABI malformed")
    address = "0x" + value[-40:]
    if int(address, 16) == 0:
        raise Refused("missing contract binding")
    return address.lower()

def verify(manifest, url, transport=rpc):
    obj = validate(manifest)
    if url not in ALLOWED_RPC:
        raise Refused("unreviewed RPC endpoint")
    if transport(url, "eth_chainId", []) != "0x7a6c":
        raise Refused("RPC not chain 31340")
    genesis = transport(url, "eth_getBlockByNumber", ["0x0", False])
    if (type(genesis) is not dict or type(genesis.get("hash")) is not str
            or genesis["hash"].lower() != obj["executionGenesisHash"].lower()):
        raise Refused("genesis hash mismatch")
    # Every query is against the finalized EL state, not the pending head.
    finalized = transport(url, "eth_getBlockByNumber", ["finalized", False])
    if (type(finalized) is not dict or type(finalized.get("number")) is not str
            or type(finalized.get("hash")) is not str
            or not HASH.fullmatch(finalized["hash"])):
        raise Refused("finalized block unavailable or unsupported")
    try:
        height = int(finalized["number"], 16)
    except ValueError as exc:
        raise Refused("invalid finalized execution height") from exc
    if height <= 0:
        raise Refused("no finalized execution blocks")
    tag = hex(height)
    observed = {}
    for name in sorted(NAMES):
        item = obj["contracts"][name]
        address = item["address"]
        code = transport(url, "eth_getCode", [address, tag])
        if (type(code) is not str or not re.fullmatch(r"0x(?:[0-9a-fA-F]{2})+", code)
                or code == "0x"):
            raise Refused(name + ": missing deployed runtime")
        digest = hashlib.sha256(bytes.fromhex(code[2:])).hexdigest()
        if digest != item["runtimeSha256"]:
            raise Refused(name + ": deployed runtime differs from pinned artifact")
        observed[name] = {"address": address, "runtimeSha256Verified": True}
    for name, destination in (("committee", "settlement"),
                              ("settlement", "board"), ("board", "settlement")):
        result = transport(url, "eth_call",
                           [{"to": obj["contracts"][name]["address"],
                             "data": selector(ABI[name])}, tag])
        if decoded_address(result) != obj["contracts"][destination]["address"].lower():
            raise Refused(name + ": incorrect immutable/one-time contract wiring")
    return {
        "schema": "SSE_R140_CHAIN31340_FINALIZED_APPLICATION_AUDIT_V1",
        "rpc": url, "chainId": 31340,
        "executionGenesisVerified": True,
        "finalizedExecutionHeight": height,
        "finalizedExecutionBlockHash": finalized["hash"].lower(),
        "runtimeCodePinnedAndVerified": True,
        "mutualBindingsVerified": True,
        "contracts": observed,
        "contractsDeployedByThisTool": False,
        "walletsOrTransactionsUsed": False,
        "fundedLeaseExecuted": False,
        "adaptiveQuorumVerified": False,
        "physicalSLAFulfillmentVerified": False,
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--rpc", choices=sorted(ALLOWED_RPC), required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(verify(load(args.manifest), args.rpc), indent=2,
                         sort_keys=True))
        return 0
    except (Refused, OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        print("R140_MARKETPLACE_DEPLOYMENT_REFUSED: " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
