#!/usr/bin/env python3
"""R206: verify real finalized SSE Adaptive V2 market+ledger on chain31340.

No signing, keys, deployments or Docker changes. Requires a PUBLIC manifest
from actual deployment receipts with separately pinned runtime SHA-256.
Never substitutes contract creation on a local simulator for live proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request

GENESIS = "0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf"
CHAIN = 31340
RPC_URLS = {"http://127.0.0.1:18545", "http://127.0.0.1:28545"}
ADDR = re.compile(r"0x[0-9a-fA-F]{40}\Z")
HASH = re.compile(r"0x[0-9a-fA-F]{64}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
DEC = re.compile(r"[1-9][0-9]*\Z")


class Refused(ValueError):
    pass


def _addr(a):
    if type(a) is not str or not ADDR.fullmatch(a) or int(a, 16) == 0:
        raise Refused("invalid nonzero Ethereum address")
    return a.lower()


def _hash(x):
    if type(x) is not str or not HASH.fullmatch(x):
        raise Refused("invalid 32-byte hash")
    return x.lower()


def _num(x):
    if type(x) is not str or not re.fullmatch(r"0x[0-9a-fA-F]+\Z", x):
        raise Refused("invalid hexadecimal JSON-RPC quantity")
    return int(x, 16)


def validate(m):
    if type(m) is not dict or set(m) != {
        "schema", "chainId", "executionGenesisHash", "deployer",
        "deploymentTxHash", "minimumBondWei", "market", "ledger"
    }:
        raise Refused("unrecognized manifest fields")
    if (m["schema"] != "SSE_R206_ADAPTIVE_MARKET_V2_DEPLOYMENT_V1"
            or type(m["chainId"]) is not int or m["chainId"] != CHAIN
            or _hash(m["executionGenesisHash"]) != GENESIS):
        raise Refused("manifest wrong original blockchain")
    _addr(m["deployer"])
    _hash(m["deploymentTxHash"])
    if type(m["minimumBondWei"]) is not str or not DEC.fullmatch(m["minimumBondWei"]):
        raise Refused("invalid immutable minimum bond")
    for name in ("market", "ledger"):
        record = m[name]
        if type(record) is not dict or set(record) != {"address", "runtimeSha256"}:
            raise Refused("missing complete runtime attestation for " + name)
        _addr(record["address"])
        if type(record["runtimeSha256"]) is not str or not SHA.fullmatch(record["runtimeSha256"]):
            raise Refused("missing immutable runtime digest")
        if int(record["runtimeSha256"], 16) == 0:
            raise Refused("zero runtime digest")
    if m["market"]["address"].lower() == m["ledger"]["address"].lower():
        raise Refused("market and ledger cannot be the same address")
    return m


def load(path):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 8192:
        raise Refused("manifest must be small regular non-symlink file")
    return validate(json.loads(path.read_text("utf-8")))


def rpc(url, method, params):
    if url not in RPC_URLS:
        raise Refused("only approved localhost node RPCs accepted")
    payload = json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode()
    request = urllib.request.Request(url, data=payload,
                headers={"Content-Type":"application/json"}, method="POST")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=8) as res:
        if res.status != 200:
            raise Refused("RPC HTTP not 200")
        raw = res.read(131073)
    if len(raw) > 131072:
        raise Refused("RPC oversized")
    value = json.loads(raw)
    if type(value) is not dict or value.get("jsonrpc") != "2.0" or value.get("id") != 1 or "error" in value or "result" not in value:
        raise Refused("malformed or failed RPC response")
    return value["result"]


# Independently computed using official OpenSSL KECCAK-256, not
# hashlib.sha3_256 (which uses incompatible NIST SHA3 domain separation).
# Fixed audited ABI surface: never process arbitrary user-provided methods.
ABI_SELECTORS = {
    "votes()": "0xe168c3ec",
    "settlement()": "0x51160630",
    "minimumBond()": "0xaa7517e1",
}

def selector(signature):
    try:
        return ABI_SELECTORS[signature]
    except KeyError as exc:
        raise Refused("unknown V2 immutable getter ABI") from exc


def _read_address(raw):
    if type(raw) is not str or not HASH.fullmatch(raw) or int(raw[2:26], 16) != 0:
        raise Refused("malformed ABI address result")
    return _addr("0x" + raw[-40:])


def verify(m, url, transport=rpc):
    validate(m)
    if url not in RPC_URLS:
        raise Refused("local RPC must be reviewed")
    ask = lambda method, params: transport(url, method, params)
    if ask("eth_chainId", []) != hex(CHAIN):
        raise Refused("RPC chain ID mismatch")
    genesis = ask("eth_getBlockByNumber", ["0x0", False])
    if type(genesis) is not dict or _hash(genesis.get("hash")) != GENESIS:
        raise Refused("original genesis mismatch")
    finalized = ask("eth_getBlockByNumber", ["finalized", False])
    if type(finalized) is not dict or _num(finalized.get("number")) <= 0:
        raise Refused("finalized execution state unavailable")
    height = _num(finalized["number"])
    _hash(finalized.get("hash"))

    txid = m["deploymentTxHash"]
    tx = ask("eth_getTransactionByHash", [txid])
    receipt = ask("eth_getTransactionReceipt", [txid])
    if type(tx) is not dict or type(receipt) is not dict:
        raise Refused("creation transaction or receipt missing")
    if (_hash(tx.get("hash")) != _hash(txid) or
        _hash(receipt.get("transactionHash")) != _hash(txid) or
        _addr(tx.get("from")) != _addr(m["deployer"]) or
        tx.get("to") is not None or
        receipt.get("status") != "0x1" or
        _addr(receipt.get("contractAddress")) != _addr(m["market"]["address"])):
        raise Refused("wrong deployer, creation target, receipt or failed deployment")
    receiptHeight = _num(receipt.get("blockNumber"))
    if receiptHeight <= 0 or receiptHeight > height:
        raise Refused("deployment not included in finalized execution height")
    canonical = ask("eth_getBlockByNumber", [hex(receiptHeight), False])
    if type(canonical) is not dict or _hash(canonical.get("hash")) != _hash(receipt.get("blockHash")):
        raise Refused("deployment tx noncanonical or wrong block hash")
    if tx.get("chainId") is not None and _num(tx["chainId"]) != CHAIN:
        raise Refused("deployment signer chain ID mismatch")

    observed = {}
    for name in ("market", "ledger"):
        address = m[name]["address"]
        code = ask("eth_getCode", [address, hex(height)])
        if type(code) is not str or not re.fullmatch(r"0x(?:[0-9a-fA-F]{2})+", code):
            raise Refused(name + " runtime missing")
        actual = hashlib.sha256(bytes.fromhex(code[2:])).hexdigest()
        if actual != m[name]["runtimeSha256"]:
            raise Refused(name + " runtime code not pinned")
        observed[name] = {"address":address,"runtimeSha256Verified":True}

    market = m["market"]["address"]
    ledger = m["ledger"]["address"]
    marketVotes = ask("eth_call", [{"to":market,"data":selector("votes()")},hex(height)])
    ledgerParent = ask("eth_call", [{"to":ledger,"data":selector("settlement()")},hex(height)])
    bondRaw = ask("eth_call", [{"to":market,"data":selector("minimumBond()")},hex(height)])
    if (_read_address(marketVotes) != _addr(ledger) or
        _read_address(ledgerParent) != _addr(market) or
        type(bondRaw) is not str or not HASH.fullmatch(bondRaw) or
        int(bondRaw,16) != int(m["minimumBondWei"])):
        raise Refused("market/ledger immutable binding or actual bond mismatch")

    return {
        "schema":"SSE_R206_FINALIZED_ADAPTIVE_MARKET_DEPLOYMENT_AUDIT_V1",
        "originalGenesisVerified":True,
        "chainId":CHAIN,
        "deploymentReceiptSuccessfulAndFinalized":True,
        "deploymentTxHash":txid,
        "deploymentBlock":receiptHeight,
        "finalizedExecutionHeight":height,
        "runtimeCodeSha256Verified":True,
        "mutualMarketLedgerBindingsVerified":True,
        "minimumBondWei":m["minimumBondWei"],
        "contracts":observed,
        "signedTransactionsSubmittedByThisTool":False,
        "independentPhysicalSlaVerified":False,
        "unbiasedVrFVerified":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--rpc",required=True,choices=sorted(RPC_URLS))
    a=p.parse_args()
    try:
        print(json.dumps(verify(load(a.manifest),a.rpc),sort_keys=True,indent=2))
        return 0
    except (Refused,OSError,TypeError,ValueError,KeyError,UnicodeError) as exc:
        print("R206_FINALIZED_ADAPTIVE_V2_AUDIT_REFUSED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
