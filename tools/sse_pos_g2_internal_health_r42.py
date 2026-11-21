#!/usr/bin/env python3
"""R42: authentic chain31340 EL/CL/VC health from inside private Docker.

G2 --internal bridge host published 127.0.0.1 ports do not necessarily work.
Use strict read-only, localhost-only RPC within the existing client containers.
No raw logs, credentials, keystore data or JSON-RPC bytecode emitted. Never
create, start, stop or delete any container, and never claim BLS key proof
merely because VC is running.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import sse_pos_g2_recover_r40 as old
import sse_pos_g2_lighthouse_config_r42 as config
import sse_pos_g2_resume_r41 as internal

DEPOSIT = "0x00000000219ab540356cbb839cbe05303d7705fa"
CODE_SHA = "5aaa8327c5765ec883224895ca02cade2871e12dad0197bdc791efc91c7ef18d"
EXPECTED_CHAIN = "0x7a6c"

def require_actual_source(commit: str) -> None:
    old.exact_git(commit)
    old.safe_dir(old.RUN)
    old.safe_dir(old.RUN / "testnet")
    for name, h in old.EXPECTED.items():
        if name != "testnet/config.yaml":
            old.safe_public(old.RUN / name, h)
    old.safe_public(config.BACKUP, config.PUBLIC_HASH)
    base = config.BASELINE.read_bytes()
    if config.upstream_git_blob(base) != config.BASELINE_GIT_BLOB:
        raise ValueError("official Lighthouse config pinned Git blob mismatch")
    rendered, _ = config.synthesize(base.decode("utf-8"), config.BACKUP.read_text("utf-8"))
    old.safe_public(old.RUN / "testnet/config.yaml", hashlib.sha256(rendered.encode()).hexdigest())

def in_docker(name: str, method: str, path: str, payload: dict | None) -> tuple[str, dict | None]:
    if name == internal.EL and method == "POST" and path == "/":
        cmd = internal.wire(method, 8545, path, payload)
    elif name == internal.BN and method == "GET":
        cmd = internal.wire(method, 5052, path, None)
    else:
        raise ValueError("client/read-only endpoint not allowlisted")
    try:
        raw = internal.docker(["exec", name, "/bin/bash", "-c", cmd])
    except internal.Refuse:
        return "DOCKER_EXEC_FAILED", None
    return internal.parse_http(raw)

def rpc(method: str, params: list | None = None):
    status, parsed = in_docker(
        internal.EL, "POST", "/", {
            "jsonrpc": "2.0", "id": 1, "method": method, "params": params or []
        },
    )
    return (parsed.get("result") if status == "HTTP_200" and isinstance(parsed, dict)
            else None)

def beacon(path: str):
    status, parsed = in_docker(internal.BN, "GET", path, None)
    return (parsed.get("data") if status == "HTTP_200" and isinstance(parsed, dict)
            else None)

def intval(value: object, *, radix: int = 10):
    if not isinstance(value, str) or len(value) > 24:
        return None
    try:
        return int(value, radix)
    except ValueError:
        return None

def observe(commit: str) -> dict:
    require_actual_source(commit)
    states = {}
    expected = (internal.ORIGINAL, internal.EL, internal.BN, internal.VC)
    for name in expected:
        s = internal.state(name)
        states[name] = {
            "running": s.get("Running") is True,
            "exitCode": s.get("ExitCode") if isinstance(s.get("ExitCode"), int) else None,
            "oomKilled": s.get("OOMKilled") is True,
        }
    if states[internal.ORIGINAL]["running"]:
        raise ValueError("original Besu unexpectedly running: refuse double EL DB")
    chain = rpc("eth_chainId") if states[internal.EL]["running"] else None
    block = rpc("eth_blockNumber") if states[internal.EL]["running"] else None
    code = rpc("eth_getCode", [DEPOSIT, "latest"]) if states[internal.EL]["running"] else None
    gen = beacon("/eth/v1/beacon/genesis") if states[internal.BN]["running"] else None
    head = beacon("/eth/v1/beacon/headers/head") if states[internal.BN]["running"] else None
    final = beacon("/eth/v1/beacon/states/head/finality_checkpoints") if states[internal.BN]["running"] else None
    sync = beacon("/eth/v1/node/syncing") if states[internal.BN]["running"] else None
    execution_ok = chain == EXPECTED_CHAIN
    block_height = intval(block, radix=16) if isinstance(block, str) and block.startswith("0x") else None
    try:
        deposit_code_ok = (
            isinstance(code, str) and code.startswith("0x")
            and hashlib.sha256(bytes.fromhex(code[2:])).hexdigest() == CODE_SHA
        )
    except ValueError:
        deposit_code_ok = False
    genesis_time = gen.get("genesis_time") if isinstance(gen, dict) else None
    genesis_ok = str(genesis_time) == str(old.GENESIS_TIME)
    message = head.get("header", {}).get("message", {}) if isinstance(head, dict) else {}
    head_slot = intval(message.get("slot")) if isinstance(message, dict) else None
    checkpoint = final.get("finalized", {}) if isinstance(final, dict) else {}
    finalized_epoch = intval(checkpoint.get("epoch")) if isinstance(checkpoint, dict) else None
    beacon_sync = sync.get("is_syncing") if isinstance(sync, dict) else None
    return {
        "schema": "SSE_R42_NATIVE_G2_INTERNAL_REAL_HEALTH_V1",
        "sourceExactGitSha": commit,
        "observationUnixUtc": int(time.time()),
        "containerStatuses": states,
        "elChain31340VerifiedInsideDocker": execution_ok,
        "elBlockHeightObserved": block_height,
        "canonicalDepositRuntimeCodeVerified": bool(deposit_code_ok),
        "beaconGenesisTimeMatchesOriginalSSZ": genesis_ok,
        "beaconHeadSlotObserved": head_slot,
        "beaconFinalizedEpochObserved": finalized_epoch,
        "beaconSyncing": beacon_sync if type(beacon_sync) is bool else None,
        "beaconAndOriginalVCBothRunning": (states[internal.BN]["running"]
                                          and states[internal.VC]["running"]),
        "realExecutionPostGenesisBlockObserved": (
            execution_ok and block_height is not None and block_height > 0
        ),
        "realPositiveBeaconFinalityObserved": (
            execution_ok and genesis_ok and finalized_epoch is not None and finalized_epoch > 0
        ),
        "independentBLSPrivateKeyPossessionNotYetProven": True,
        "publicInternetP2PNotYetVerified": True,
        "independentPhysicalOperators": 1,
        "sourceOfMetrics": "read_only_json_rpc_inside_existing_pinned_docker_clients",
        "rawRpcResponseOrPrivateKeysEmitted": False,
        "servicesCreatedOrStartedByThisProgram": False,
    }

def main() -> int:
    p = argparse.ArgumentParser(description="True existing G2 Docker internal EL/CL JSON-RPC health only")
    p.add_argument("--expected-commit", required=True)
    args = p.parse_args()
    try:
        print(json.dumps(observe(args.expected_commit), sort_keys=True, indent=2))
        return 0
    except (ValueError, old.RecoveryRefused, internal.Refuse, OSError) as exc:
        # Never output arbitrary errors (could contain untrusted Docker output).
        print("R42_INTERNAL_HEALTH_REFUSED: " + type(exc).__name__, file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
