#!/usr/bin/env python3
"""R97 read-only live native EL/CL peer + bootnode diagnostic for R92 nodes.

Never prints Docker environment or authenticated JWT. Never changes Docker.
Outputs bounded JSON with peer counts, configured peer-seed *presence*,
current beacon peer identity, and EL/CL availability; no misleading READY.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import urllib.request
import urllib.error

ROLES = {
    "owner": ("sse31340-g2-el-r40", "sse31340-g2-bn", 18545, 15052),
    "observer": ("sse31340-r59-nonsigning-el", "sse31340-r59-nonsigning-bn", 28545, 25052),
}

def request_json(port: int, path: str, payload: bytes | None = None) -> dict:
    url = f"http://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type":"application/json"} if payload else {},
                                 method="POST" if payload else "GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=7) as response:
        data = response.read(128_000)
        return json.loads(data)

def docker_command(name: str) -> list[str]:
    p = subprocess.run(["sudo", "-n", "docker", "inspect", "--format", "{{json .Config.Cmd}}", name],
                       check=True, text=True, capture_output=True, timeout=15)
    raw = json.loads(p.stdout)
    if not isinstance(raw, list):
        raise ValueError("unexpected Docker command metadata")
    return [x for x in raw if isinstance(x, str)]

def seeds(cmd: list[str], mode: str) -> dict:
    # Never print peer records or full command line; report only static options.
    if mode == "el":
        return {
            "explicit_bootnodes": any(s.startswith("--bootnodes=") and len(s) > 12 for s in cmd),
            "discovery_enabled": "--discovery-enabled=true" in cmd,
            "ipv6_outbound_enabled": "--p2p-ipv6-outbound-enabled=true" in cmd,
        }
    return {
        "explicit_bootnodes": any(s.startswith("--boot-nodes=") and len(s) > 13 for s in cmd),
        "private_discovery_enabled": "--enable-private-discovery" in cmd,
        "quic_ipv6_9001": "--quic-port6=9001" in cmd,
    }

def evaluate(el_result: dict, peer_result: dict, sync_result: dict, el_seed: dict, bn_seed: dict) -> dict:
    el = el_result.get("result")
    if not isinstance(el, str) or not el.startswith("0x"):
        raise ValueError("invalid EL peer count")
    el_count = int(el, 16)
    peer = peer_result.get("data", {}).get("connected")
    if not isinstance(peer, str) or not peer.isdecimal():
        raise ValueError("invalid CL peer count")
    cl_count = int(peer)
    sync = sync_result.get("data")
    if not isinstance(sync, dict):
        raise ValueError("invalid CL syncing")
    return {
        "el_peer_count": el_count,
        "cl_peer_count": cl_count,
        "beacon_syncing": sync.get("is_syncing"),
        "beacon_optimistic": sync.get("is_optimistic"),
        "beacon_el_offline": sync.get("el_offline"),
        "el_seed_configuration": el_seed,
        "cl_seed_configuration": bn_seed,
        "native_peering_verified": el_count > 0 and cl_count > 0,
        "live_consensus_verified": False,
        "readiness": "PEERING_NOT_VERIFIED" if el_count == 0 or cl_count == 0 else "P2P_PRESENT_VERIFY_FINALITY",
    }

def run(role: str) -> dict:
    el, bn, el_port, bn_port = ROLES[role]
    payload = b'{"jsonrpc":"2.0","method":"net_peerCount","params":[],"id":1}'
    el_cmd = docker_command(el)
    bn_cmd = docker_command(bn)
    el_peers = request_json(el_port, "/", payload)
    bn_peers = request_json(bn_port, "/eth/v1/node/peer_count")
    syncing = request_json(bn_port, "/eth/v1/node/syncing")
    identity = request_json(bn_port, "/eth/v1/node/identity")
    value = evaluate(el_peers, bn_peers, syncing, seeds(el_cmd,"el"), seeds(bn_cmd,"bn"))
    nodeid = identity.get("data",{}).get("peer_id")
    value["beacon_peer_id"] = nodeid if isinstance(nodeid,str) and len(nodeid) <= 120 else "unknown"
    value["role"] = role
    return value

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=tuple(ROLES), required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.role), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, urllib.error.URLError):
        print("R97_DIAGNOSTIC_FAILED: local client API or bounded Docker read unavailable",file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
