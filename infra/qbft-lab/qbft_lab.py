#!/usr/bin/env python3
"""Manual-only isolated four-validator Besu QBFT laboratory for SSE."""
import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
STATE = ROOT / ".local" / "qbft-lab"
COMPOSE = STATE / "compose.yml"
IMAGE = "hyperledger/besu:26.6.1"
CHAIN_ID = 20261118
PORTS = (18545, 18546, 18547, 18548)


def normalize_public_key(raw):
    value = raw.strip().lower().removeprefix("0x")
    if len(value) == 130 and value.startswith("04"):
        value = value[2:]
    if len(value) != 128 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("Expected 64-byte uncompressed secp256k1 public key")
    return value


def make_compose(keys, uid, gid):
    if len(keys) != 4 or len(set(keys)) != 4:
        raise ValueError("Four distinct validator public keys required")
    result = ["services:"]
    for i in range(1, 5):
        name = "validator" + str(i)
        peers = ["enode://" + key + "@validator" + str(j) + ":30303"
                 for j, key in enumerate(keys, 1) if j != i]
        flags = ["--data-path=/data", "--genesis-file=/config/genesis.json",
                 "--network-id=" + str(CHAIN_ID), "--rpc-http-enabled=true",
                 "--rpc-http-host=0.0.0.0", "--rpc-http-api=ETH,NET,WEB3,QBFT",
                 "--host-allowlist=*", "--p2p-port=30303",
                 "--p2p-host=" + name, "--min-gas-price=0",
                 "--tx-pool-enable-balance-check=false",
                 "--bootnodes=" + ",".join(peers)]
        result.extend(["  " + name + ":", "    image: " + IMAGE,
                       '    user: "' + str(uid) + ":" + str(gid) + '"',
                       "    restart: unless-stopped", "    command:"])
        result.extend(["      - '" + flag + "'" for flag in flags])
        result.extend(["    volumes:",
                       "      - './genesis.json:/config/genesis.json:ro'",
                       "      - './" + name + "/data:/data'",
                       "    ports:",
                       '      - "127.0.0.1:' + str(PORTS[i-1]) + ':8545"',
                       "    networks: [qbft-lab]"])
    result.extend(["networks:", "  qbft-lab:", "    driver: bridge", ""])
    return "\n".join(result)


def run(*args):
    subprocess.run(list(args), check=True)


def docker_compose(*args):
    if not COMPOSE.is_file():
        raise RuntimeError("No network config. Run prepare first.")
    run("docker", "compose", "-p", "sse-qbft-lab", "-f", str(COMPOSE), *args)


def prepare():
    if STATE.exists() and any(STATE.iterdir()):
        raise RuntimeError("Existing network state; refusing to overwrite " + str(STATE))
    if shutil.which("docker") is None:
        raise RuntimeError("Docker missing: no installation will be attempted")
    if not hasattr(os, "getuid"):
        raise RuntimeError("This script requires an Ubuntu/Linux host")
    STATE.mkdir(parents=True, exist_ok=True)
    uid, gid = os.getuid(), os.getgid()
    run("docker", "run", "--rm", "--user", str(uid) + ":" + str(gid),
        "-v", str(HERE) + ":/config:ro", "-v", str(STATE) + ":/work",
        IMAGE, "operator", "generate-blockchain-config",
        "--config-file=/config/qbft-config.json", "--to=/work/generated",
        "--private-key-file-name=key")
    output = STATE / "generated"
    folders = sorted((output / "keys").glob("0x*"))
    if len(folders) != 4 or not (output / "genesis.json").is_file():
        raise RuntimeError("Besu generator did not produce four validators and a genesis")
    shutil.copy2(output / "genesis.json", STATE / "genesis.json")
    keys, accounts = [], []
    for i, folder in enumerate(folders, 1):
        destination = STATE / ("validator" + str(i)) / "data"
        destination.mkdir(parents=True, exist_ok=False)
        for filename in ("key", "key.pub"):
            shutil.copy2(folder / filename, destination / filename)
        (destination / "key").chmod(0o600)
        keys.append(normalize_public_key((folder / "key.pub").read_text()))
        accounts.append({"node": "validator" + str(i), "address": folder.name})
    COMPOSE.write_text(make_compose(keys, uid, gid), encoding="utf-8")
    (STATE / "identities.json").write_text(json.dumps(accounts, indent=2) + "\n")
    print(json.dumps({"state": str(STATE), "chainId": CHAIN_ID,
                      "validators": accounts}, indent=2))
    print("Never commit .local network keys or chain data.")


def rpc(port, method, params=None):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                          "params": params if params is not None else []})
    request = urllib.request.Request(
        "http://127.0.0.1:" + str(port), payload.encode(),
        {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=4) as response:
        message = json.load(response)
    if "error" in message:
        raise RuntimeError(str(message["error"]))
    return message["result"]


def inspect():
    result = []
    for i, port in enumerate(PORTS, 1):
        item = {"node": "validator" + str(i), "rpcPort": port}
        try:
            item["chainId"] = int(rpc(port, "eth_chainId"), 16)
            item["height"] = int(rpc(port, "eth_blockNumber"), 16)
            item["peers"] = int(rpc(port, "net_peerCount"), 16)
            item["genesisHash"] = rpc(port, "eth_getBlockByNumber",
                                      ["0x0", False])["hash"]
            item["validators"] = rpc(port, "qbft_getValidatorsByBlockNumber",
                                     ["latest"])
        except Exception as exc:
            item["error"] = str(exc)
        result.append(item)
    return result


def verify(rows):
    good = [r for r in rows if "error" not in r]
    if len(good) != 4:
        raise RuntimeError("Four responding validators required")
    if any(r["chainId"] != CHAIN_ID for r in good):
        raise RuntimeError("Incorrect chain ID")
    if len({r["genesisHash"] for r in good}) != 1:
        raise RuntimeError("Genesis mismatch")
    if any(len(r["validators"]) != 4 for r in good):
        raise RuntimeError("Unexpected QBFT validator set")
    if any(r["peers"] < 2 for r in good):
        raise RuntimeError("Insufficient peer connections")
    if min(r["height"] for r in good) < 2:
        raise RuntimeError("No observed block production")
    if max(r["height"] for r in good) - min(r["height"] for r in good) > 2:
        raise RuntimeError("Chain-head divergence")
    return good


def sample(seconds):
    if seconds < 10 or seconds > 3600:
        raise ValueError("Sampling requires 10..3600 seconds")
    start = inspect()
    verify(start)
    t0 = time.monotonic()
    time.sleep(seconds)
    elapsed = time.monotonic() - t0
    end = inspect()
    verify(end)
    increase = {row["node"]: row["height"] - start[i]["height"]
                for i, row in enumerate(end)}
    top = end[0]["height"]
    blocks = [rpc(PORTS[0], "eth_getBlockByNumber", [hex(i), False])
              for i in range(max(1, top - 63), top + 1)]
    stamps = [int(block["timestamp"], 16) for block in blocks]
    intervals = [b-a for a, b in zip(stamps, stamps[1:])]
    output = {
        "experiment": "local QBFT idle-block observational sample",
        "timeSeconds": round(elapsed, 3), "start": start, "end": end,
        "newBlocks": increase,
        "observedSecondsPerBlock": round(elapsed / increase["validator1"], 3)
        if increase["validator1"] else None,
        "recentBlockPeriodMedian": statistics.median(intervals) if intervals else None,
        "recentBlockPeriodP95": sorted(intervals)[int(0.95 * (len(intervals)-1))]
        if intervals else None,
        "transactionThroughputMeasured": False,
        "limitation": "One host, no application tx, no real distributed fault isolation"
    }
    destination = STATE / ("sample-" + str(int(time.time())) + ".json")
    destination.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"file": str(destination), **output}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    for name in ("prepare", "up", "down", "status", "verify", "logs"):
        subs.add_parser(name)
    measure = subs.add_parser("sample")
    measure.add_argument("--seconds", type=int, default=30)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "up":
        docker_compose("up", "-d")
    elif args.action == "down":
        docker_compose("down")  # Does not delete state or keys.
    elif args.action == "logs":
        docker_compose("logs", "--tail=100")
    elif args.action in ("status", "verify"):
        rows = inspect()
        print(json.dumps(rows, indent=2))
        if args.action == "verify":
            verify(rows)
            print("QBFT_LAB_VERIFIED")
    elif args.action == "sample":
        sample(args.seconds)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as err:
        print("QBFT_LAB_ERROR:", err, file=sys.stderr)
        sys.exit(1)
