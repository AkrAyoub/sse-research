#!/usr/bin/env python3
"""R141: real read-only arbitrary-size PoS node observations and fleet comparison.

Capture is executed independently on EACH real node; never remotely invokes
SSH/Docker or controls a validator. Aggregate is offline and does not treat
nodeId/operator labels, JSON files, or a shared VM provider as proofs of
physical independence, cryptographic authorship, or public Internet access.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import re
import sys
import urllib.request

SCHEMA = "SSE_R141_LOCAL_NODE_V1"
FLEET_SCHEMA = "SSE_R141_FLEET_COMPARISON_V1"
MAX_INPUT_BYTES = 16384
MAX_RESPONSE_BYTES = 65536
MAX_REPORTS = 256  # bounded *audit batch*, not a chain/role/committee cap
HEX32 = re.compile(r"0x[0-9a-fA-F]{64}\Z")
ID = re.compile(r"[a-z][a-z0-9-]{2,62}\Z")
API = (
    ("el", "/"), ("beacon", "/eth/v1/beacon/genesis"),
    ("beacon", "/eth/v1/beacon/headers/head"),
    ("beacon", "/eth/v1/beacon/states/head/finality_checkpoints"),
    ("beacon", "/eth/v1/node/syncing"), ("beacon", "/eth/v1/node/peer_count"),
)

class Refused(ValueError):
    pass

def positive_integer(value, label, *, allow_zero=True):
    if type(value) is not int or value < (0 if allow_zero else 1):
        raise Refused("invalid " + label)
    return value

def dec(value, label):
    if type(value) is not str or not re.fullmatch(r"[0-9]{1,20}", value):
        raise Refused("invalid " + label)
    return int(value)

def hx(value, label):
    if type(value) is not str or not re.fullmatch(r"0x[0-9a-fA-F]{1,16}", value):
        raise Refused("invalid " + label)
    return int(value, 16)

def root(value, label):
    if type(value) is not str or not HEX32.fullmatch(value):
        raise Refused("invalid " + label)
    return value.lower()

def checked_id(value):
    if type(value) is not str or not ID.fullmatch(value):
        raise Refused("invalid node ID")
    return value

def local_url(url):
    # No remote RPC or arbitrary URL input; run capture on its owner host.
    if type(url) is not str or not re.fullmatch(r"http://127\.0\.0\.1:[0-9]{2,5}", url):
        raise Refused("only loopback numeric IPv4 HTTP RPC/REST endpoints allowed")
    port = int(url.rsplit(":", 1)[1])
    if not 1 <= port <= 65535:
        raise Refused("invalid local port")
    return url

def http_json(url, method="GET", rpc_method=None, max_size=MAX_RESPONSE_BYTES):
    if method not in ("GET", "POST"):
        raise Refused("unapproved HTTP method")
    body = None
    if method == "POST":
        if rpc_method not in ("eth_chainId", "eth_getBlockByNumber",
                              "eth_blockNumber", "net_peerCount", "eth_syncing"):
            raise Refused("unapproved read-only ETH RPC method")
        params = ["0x0", False] if rpc_method == "eth_getBlockByNumber" else []
        body = json.dumps({"jsonrpc": "2.0", "id": 1,
                           "method": rpc_method, "params": params}).encode()
    request = urllib.request.Request(
        url, data=body, method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=8) as response:
            if response.status != 200:
                raise Refused("local client HTTP status not 200")
            raw = response.read(max_size + 1)
    except (OSError, ValueError) as exc:
        raise Refused("local client API inaccessible") from exc
    if len(raw) > max_size:
        raise Refused("oversized client API response")
    try:
        result = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise Refused("invalid local client response JSON") from exc
    if type(result) is not dict:
        raise Refused("local API returned invalid object")
    if method == "POST":
        if (result.get("jsonrpc") != "2.0" or result.get("id") != 1
                or "error" in result or "result" not in result):
            raise Refused("invalid ETH RPC result")
        return result["result"]
    if type(result.get("data")) is not dict:
        raise Refused("invalid Beacon API data")
    return result["data"]

def capture(node_id, el_url, bn_url, transport=http_json):
    checked_id(node_id)
    el_url = local_url(el_url)
    bn_url = local_url(bn_url)
    if el_url == bn_url:
        raise Refused("EL and CL REST must have distinct local ports")
    call = lambda method: transport(el_url, "POST", method)
    if hx(call("eth_chainId"), "chain id") != 31340:
        raise Refused("not SSE chain31340")
    block0 = call("eth_getBlockByNumber")
    if type(block0) is not dict:
        raise Refused("no execution genesis block")
    el_genesis = root(block0.get("hash"), "EL genesis block hash")
    height = hx(call("eth_blockNumber"), "EL height")
    peers_el = hx(call("net_peerCount"), "EL native peer count")
    syncing_el = call("eth_syncing")
    if syncing_el is not False:
        raise Refused("EL still syncing or status not proven")
    bn = lambda path: transport(bn_url + path, "GET", None)
    genesis = bn("/eth/v1/beacon/genesis")
    header = bn("/eth/v1/beacon/headers/head")
    checkpoints = bn("/eth/v1/beacon/states/head/finality_checkpoints")
    sync = bn("/eth/v1/node/syncing")
    peers = bn("/eth/v1/node/peer_count")
    if (sync.get("is_syncing") is not False or
            sync.get("is_optimistic") is not False or
            sync.get("el_offline") is not False or
            dec(sync.get("sync_distance"), "sync distance") != 0):
        raise Refused("BN syncing, optimistic, or EL offline")
    if dec(sync.get("head_slot"), "sync head slot") != dec(
            header.get("header", {}).get("message", {}).get("slot"), "header slot"):
        raise Refused("BN syncing/head readings disagree")
    final = checkpoints.get("finalized")
    if type(final) is not dict:
        raise Refused("missing finalized checkpoint")
    finalized_epoch = dec(final.get("epoch"), "finalized epoch")
    if finalized_epoch < 1:
        raise Refused("genesis-only finality does not establish live chain")
    head = dec(sync["head_slot"], "head slot")
    if finalized_epoch > head // 32:
        raise Refused("future finalized epoch")
    return {
        "schema": SCHEMA, "nodeId": node_id, "chainId": 31340,
        "capturedAtUtc": datetime.now(timezone.utc).isoformat(),
        "executionGenesisHash": el_genesis,
        "beaconGenesisValidatorsRoot": root(
            genesis.get("genesis_validators_root"), "beacon validators root"),
        "executionBlockNumber": height, "beaconHeadSlot": head,
        "executionNativePeers": peers_el,
        "beaconNativePeers": dec(peers.get("connected"), "beacon peers"),
        "finalizedEpoch": finalized_epoch,
        "finalizedRoot": root(final.get("root"), "finalized root"),
        "executionSyncing": False, "beaconSyncing": False,
        "executionOffline": False, "optimistic": False,
        "localClientApisRead": True, "validatorKeyRead": False,
        "transactionSubmitted": False, "dockerChanged": False,
        "independentOperatorVerified": False,
        "publicInternetNativeP2pVerified": False,
        "remotePhysicalResourceVerified": False,
    }

KEYS = frozenset((
    "schema", "nodeId", "chainId", "capturedAtUtc",
    "executionGenesisHash", "beaconGenesisValidatorsRoot",
    "executionBlockNumber", "beaconHeadSlot",
    "executionNativePeers", "beaconNativePeers",
    "finalizedEpoch", "finalizedRoot",
    "executionSyncing", "beaconSyncing", "executionOffline",
    "optimistic", "localClientApisRead", "validatorKeyRead",
    "transactionSubmitted", "dockerChanged",
    "independentOperatorVerified", "publicInternetNativeP2pVerified",
    "remotePhysicalResourceVerified",
))

def validate_report(obj):
    if type(obj) is not dict or set(obj) != KEYS or obj["schema"] != SCHEMA:
        raise Refused("invalid or unreviewed node report schema")
    checked_id(obj["nodeId"])
    if type(obj["chainId"]) is not int or obj["chainId"] != 31340:
        raise Refused("wrong chain ID")
    for field in ("executionGenesisHash", "beaconGenesisValidatorsRoot", "finalizedRoot"):
        root(obj[field], field)
    for field in ("executionBlockNumber", "beaconHeadSlot",
                  "executionNativePeers", "beaconNativePeers", "finalizedEpoch"):
        positive_integer(obj[field], field)
    if obj["finalizedEpoch"] < 1 or obj["finalizedEpoch"] > obj["beaconHeadSlot"] // 32:
        raise Refused("invalid finalized epoch versus head")
    for name, expected in (
        ("executionSyncing", False), ("beaconSyncing", False),
        ("executionOffline", False), ("optimistic", False),
        ("localClientApisRead", True), ("validatorKeyRead", False),
        ("transactionSubmitted", False), ("dockerChanged", False),
        ("independentOperatorVerified", False),
        ("publicInternetNativeP2pVerified", False),
        ("remotePhysicalResourceVerified", False)):
        if obj[name] is not expected:
            raise Refused("invalid safety or evidence status: " + name)
    if type(obj["capturedAtUtc"]) is not str:
        raise Refused("missing capture time")
    try:
        when = datetime.fromisoformat(obj["capturedAtUtc"])
    except ValueError as exc:
        raise Refused("invalid UTC capture time") from exc
    if when.tzinfo is None or when.utcoffset().total_seconds() != 0:
        raise Refused("capture time must be UTC")
    return obj

def load_report(path):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_INPUT_BYTES:
        raise Refused("absent, linked or oversized report")
    return validate_report(json.loads(path.read_text("utf-8")))

def compare(reports, *, max_skew_seconds=180):
    if type(reports) is not list or not 2 <= len(reports) <= MAX_REPORTS:
        raise Refused("comparison needs at least two actual local reports per audit batch")
    if type(max_skew_seconds) is not int or not 0 <= max_skew_seconds <= 3600:
        raise Refused("invalid collection time skew allowance")
    parsed = [validate_report(report) for report in reports]
    ids = [r["nodeId"] for r in parsed]
    if len(ids) != len(set(ids)):
        raise Refused("duplicate node IDs do not count as independent reports")
    capture_times = [datetime.fromisoformat(r["capturedAtUtc"]) for r in parsed]
    skew = (max(capture_times) - min(capture_times)).total_seconds()
    el_roots = {r["executionGenesisHash"].lower() for r in parsed}
    cl_roots = {r["beaconGenesisValidatorsRoot"].lower() for r in parsed}
    finals = {(r["finalizedEpoch"], r["finalizedRoot"].lower()) for r in parsed}
    epoch_count = len({r["finalizedEpoch"] for r in parsed})
    sufficient_peers = all(r["executionNativePeers"] > 0
                           and r["beaconNativePeers"] > 0 for r in parsed)
    same_genesis = len(el_roots) == len(cl_roots) == 1
    same_finalized = len(finals) == 1
    # Different epoch roots are not automatically a fork; stop at INCONCLUSIVE.
    all_agree = (same_genesis and same_finalized and
                 skew <= max_skew_seconds and sufficient_peers)
    return {
        "schema": FLEET_SCHEMA, "observedReportCount": len(parsed),
        "reportNodeIds": sorted(ids), "maxCaptureSkewSeconds": skew,
        "sameExecutionGenesis": len(el_roots) == 1,
        "sameBeaconGenesisValidatorsRoot": len(cl_roots) == 1,
        "sameFinalizedEpoch": epoch_count == 1,
        "sameFinalizedEpochAndRoot": same_finalized,
        "allObservedNodesHaveNativeElAndClPeers": sufficient_peers,
        "operatorSignedReportsVerified": False,
        "independentOperatorsOrIspsVerified": False,
        "permissionlessExternalAdmissionVerified": False,
        "unboundedNetworkSizeProven": False,
        "result": "OBSERVED_CONSISTENT_CHECKPOINTS" if all_agree
                  else "INCONCLUSIVE_OR_DIVERGENT_REQUIRES_REVIEW",
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--capture", action="store_true")
    modes.add_argument("--compare", nargs="+", type=Path)
    parser.add_argument("--node-id")
    parser.add_argument("--el")
    parser.add_argument("--bn")
    args = parser.parse_args(argv)
    try:
        if args.capture:
            if not all((args.node_id, args.el, args.bn)):
                raise Refused("local capture requires node-id, el and bn")
            report = capture(args.node_id, args.el, args.bn)
        else:
            if any((args.node_id, args.el, args.bn)):
                raise Refused("offline fleet compare cannot query network")
            report = compare([load_report(path) for path in args.compare])
        print(json.dumps(report, sort_keys=True, indent=2))
        return 0
    except (Refused, OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        print("R141_FLEET_AUDIT_REFUSED: " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
