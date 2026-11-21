#!/usr/bin/env python3
"""R41: verify running G2 EL internally; resume original BN and VC in order.

Docker --internal bridge may prevent host-published loopback access even if
pinned Besu is actually running. Read chain identity by Docker exec over local
Bash TCP inside the existing container; never print raw API data or secrets.
No new clients/keys/genesis/JWT, no delete or duplicate validator process.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import time

import sse_pos_g2_recover_r40 as old

EL, ORIGINAL, BN, VC = old.REPLACEMENT_EL, old.ORIGINAL_EL, old.BEACON, old.VC
EXPECTED_CHAIN, EXPECTED_GENESIS = hex(31340), str(old.GENESIS_TIME)
MAX_RESPONSE = 50000

class Refuse(ValueError):
    pass

def docker(args: list[str], timeout: int = 12) -> bytes:
    try:
        result = subprocess.run(["sudo", "-n", "docker", *args], capture_output=True,
                                timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Refuse("existing Docker operation inaccessible") from exc
    if result.returncode:
        raise Refuse("reviewed Docker operation refused; no raw stderr emitted")
    return result.stdout[:MAX_RESPONSE]

def state(name: str) -> dict:
    try:
        x = json.loads(docker(["inspect", "--format", "{{json .State}}", name]))
    except (ValueError, TypeError) as exc:
        raise Refuse("unreadable existing Docker state") from exc
    if not isinstance(x, dict):
        raise Refuse("Docker state is not an object")
    return x

def inspect(name: str, fmt: str):
    return docker(["inspect", "-f", fmt, name]).decode("utf-8").strip()

def require_existing(sha: str):
    old.exact_git(sha)
    old.safe_dir(old.RUN)
    for sub in ("el", "beacon", "vc", "testnet"):
        old.safe_dir(old.RUN / sub)
    for name, expected in old.EXPECTED.items():
        old.safe_public(old.RUN / name, expected)
    jwt = old.RUN / "engine.jwt"
    if (jwt.is_symlink() or not jwt.is_file()
            or jwt.stat().st_uid != os.geteuid()
            or stat.S_IMODE(jwt.stat().st_mode) != 0o600 or jwt.stat().st_size != 64):
        raise Refuse("original Engine JWT file metadata mismatch; bytes not read")
    _, besu_id, lighthouse_id = old.image_pins()
    for name, expected in (
        (EL, besu_id), (ORIGINAL, besu_id),
        (BN, lighthouse_id), (VC, lighthouse_id)
    ):
        if (inspect(name, "{{.Image}}") != expected
                or inspect(name, "{{.HostConfig.NetworkMode}}") != old.NETWORK):
            raise Refuse("pinned original Docker image or private bridge mismatch")
    if docker(["network", "inspect", "--format", "{{.Internal}}", old.NETWORK]).strip() != b"true":
        raise Refuse("original G2 Docker bridge must remain internal")
    if (state(ORIGINAL).get("Status") != "exited"
            or state(EL).get("Running") is not True
            or state(BN).get("Status") != "exited"
            or state(VC).get("Status") != "exited"):
        raise Refuse("expected running replacement EL and three stopped original clients")
    mounts = json.loads(inspect(EL, "{{json .Mounts}}"))
    expected = {
        "/data": (str(old.RUN / "el"), True),
        "/testnet": (str(old.RUN / "testnet"), False),
        "/jwt/engine.jwt": (str(old.RUN / "engine.jwt"), False)
    }
    if not isinstance(mounts, list) or len(mounts) != len(expected):
        raise Refuse("replacement EL unexpected mounts")
    found = {m.get("Destination"): m for m in mounts if isinstance(m, dict)}
    for dest, (source, rw) in expected.items():
        m = found.get(dest)
        if not isinstance(m, dict) or m.get("Source") != source or m.get("RW") is not rw:
            raise Refuse("replacement EL not using original state/JWT/genesis")
    tmpfs = json.loads(inspect(EL, "{{json .HostConfig.Tmpfs}}"))
    if not isinstance(tmpfs, dict) or "exec" not in tmpfs.get("/tmp", "").split(","):
        raise Refuse("replacement Besu does not have reviewed JVM-native tmpfs")

def wire(method: str, port: int, path: str, body: dict | None) -> str:
    if (method, port, path) not in (
        ("POST", 8545, "/"), ("GET", 5052, "/eth/v1/beacon/genesis")
    ):
        raise Refuse("only two local read-only API queries allowed")
    data = json.dumps(body, separators=(",", ":")).encode("ascii") if body else b""
    parts = [f"{method} {path} HTTP/1.1", "Host: localhost",
             "Accept: application/json", "Connection: close"]
    if data:
        parts += ["Content-Type: application/json", f"Content-Length: {len(data)}"]
    request = "\r\n".join(parts) + "\r\n\r\n" + data.decode("ascii")
    return (f"exec 3<>/dev/tcp/127.0.0.1/{port} || exit 17\n"
            + "printf '%s' " + shlex.quote(request) + " >&3\n"
            + "timeout 5 cat <&3 || test $? -eq 124")

def parse_http(raw: bytes) -> tuple[str, dict | None]:
    headers, sep, body = raw.partition(b"\r\n\r\n")
    if not sep or not headers.startswith(b"HTTP/"):
        return "NO_VALID_HTTP", None
    first = headers.split(b"\r\n", 1)[0].split()
    if len(first) < 2 or not first[1].isdigit():
        return "INVALID_HTTP_STATUS", None
    code = int(first[1])
    if code != 200:
        return "HTTP_" + str(code), None
    try:
        if b"transfer-encoding: chunked" in headers.lower():
            size, marker, remainder = body.partition(b"\r\n")
            if not marker:
                return "BAD_CHUNK", None
            size_int = int(size.split(b";")[0], 16)
            if size_int < 1 or size_int > MAX_RESPONSE:
                return "BAD_CHUNK", None
            body = remainder[:size_int]
        result = json.loads(body)
    except (ValueError, TypeError):
        return "HTTP_200_BAD_JSON", None
    return "HTTP_200", result if isinstance(result, dict) else None

def inside(name: str) -> dict:
    if name == EL:
        request = wire("POST", 8545, "/", {
            "jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []
        })
    elif name == BN:
        request = wire("GET", 5052, "/eth/v1/beacon/genesis", None)
    else:
        raise Refuse("only original BN and currently running EL allowed")
    try:
        raw = docker(["exec", name, "/bin/bash", "-c", request])
    except Refuse:
        return {"status": "CONTAINER_EXEC_FAILED", "identityVerified": False}
    status, parsed = parse_http(raw)
    if name == EL:
        ok = (status == "HTTP_200" and isinstance(parsed, dict)
              and parsed.get("result") == EXPECTED_CHAIN)
    else:
        data = parsed.get("data") if isinstance(parsed, dict) else None
        ok = (status == "HTTP_200" and isinstance(data, dict)
              and str(data.get("genesis_time")) == EXPECTED_GENESIS)
    return {"status": status, "identityVerified": ok, "rawResponseEmitted": False}

def plan(sha: str) -> dict:
    require_existing(sha)
    el = inside(EL)
    return {
        "schema": "SSE_R41_ORIGINAL_G2_INTERNAL_API_GATE_V1",
        "sourceSha": sha,
        "replacementBesuContainerAlreadyRunning": True,
        "originalELContainerPreservedStopped": True,
        "originalBeaconAndVCBothStopped": True,
        "publicGenesisSSZAndOriginalJWTMetadataVerified": True,
        "privateDockerBridge": True,
        "insideBesuRpc": el,
        "actualBesuChain31340IdentityVerified": el["identityVerified"],
        "noContainersCreatedOrStartedByPlan": True,
        "noRawLogResponseOrValidatorSecretsEmitted": True,
    }

def wait_beacon() -> dict:
    report = {"status": "NOT_READY", "identityVerified": False}
    for _ in range(30):
        if state(BN).get("Running") is not True:
            return {"status": "BEACON_STOPPED", "identityVerified": False}
        report = inside(BN)
        if report["identityVerified"]:
            return report
        time.sleep(2)
    return report

def resume(sha: str) -> dict:
    report = plan(sha)
    if not report["actualBesuChain31340IdentityVerified"]:
        raise Refuse("Besu chain31340 identity NOT verified inside container; VC remains stopped")
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        raise Refuse("interactive owner authorization required")
    consent = input("Resume ORIGINAL ONE signing VC only if not signing elsewhere. "
                    "Type RESUME-ORIGINAL-G2-VC: ")
    if consent != "RESUME-ORIGINAL-G2-VC":
        raise Refuse("owner did not approve original signer resume")
    if state(ORIGINAL).get("Running") or state(VC).get("Running"):
        raise Refuse("duplicate signer/original EL may be active; stop")
    docker(["start", BN])
    print("R41_ORIGINAL_BEACON_RESTART_SUBMITTED=true", flush=True)
    ready = wait_beacon()
    if not ready["identityVerified"]:
        raise Refuse("Beacon not accepting expected original genesis; VC remains stopped")
    print("R41_REAL_BEACON_GENESIS_TIME_VERIFIED_INSIDE_CONTAINER=true", flush=True)
    if (state(ORIGINAL).get("Running") or state(VC).get("Running")
            or state(EL).get("Running") is not True):
        raise Refuse("unexpected signer or execution state before validator restart")
    docker(["start", VC])
    print("R41_SAME_ORIGINAL_SINGLE_VALIDATOR_RESTART_SUBMITTED=true", flush=True)
    report.update({
        "beaconVerifiedOriginalGenesisTime": True,
        "sameOriginalValidatorRestartSubmitted": True,
        "originalSlashingProtectionPreserved": True,
        "actualFinalityOrSignedBlocksProvenByResume": False,
        "publicP2PEnabled": False,
        "newContainersCreatedByR41": False,
    })
    return report

def main() -> int:
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true")
    g.add_argument("--resume", action="store_true")
    p.add_argument("--expected-commit", required=True)
    args = p.parse_args()
    try:
        result = plan(args.expected_commit) if args.plan else resume(args.expected_commit)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["actualBesuChain31340IdentityVerified"] else 2
    except (Refuse, old.RecoveryRefused, OSError, ValueError, KeyboardInterrupt) as exc:
        print("R41_REFUSED: " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
