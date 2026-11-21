#!/usr/bin/env python3
"""R40: guarded recovery of EXISTING one-owner real chain31340 G2 clients.

Preserves original failed Besu container, EL DB, JWT, CL and VC state, EIP-2335
signing key and slashing protection. Replaces ONLY the incorrectly noexec /tmp
container with a second isolated EL process (original must remain EXITED).
Starts EXISTING Lighthouse BN and VC in sequence only after actual RPC checks.
No genesis regeneration, keygen, new P2P, public Engine API or fake finality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from urllib.request import Request, ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
RUN = Path.home() / ".local/share/sse-r35-chain31340-g2-private"
ORIGINAL_EL = "sse31340-g2-el"
REPLACEMENT_EL = "sse31340-g2-el-r40"
BEACON = "sse31340-g2-bn"
VC = "sse31340-g2-vc"
NETWORK = "sse31340-g2-internal"
FEE_EOA = "0x13fb73aace8A11Be2899D047635A757a224Ce00B"
GENESIS_TIME = 1795219212
EXPECTED = {
    "testnet/genesis.json": "22eb6c58288113b9c3671970967151012665137b345237b5c24060dc988b1ee8",
    "testnet/config.yaml": "839072fe3d4b2092b4867010ad01254145872969d89f66ecc86610700f381b13",
    "testnet/genesis.ssz": "8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82",
    "testnet/deposit_contract_block.txt": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
    "testnet/deploy_block.txt": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
}
SHA_PATTERN = re.compile(r"[a-f0-9]{40}\Z")
OPENER = build_opener(ProxyHandler({}))

class RecoveryRefused(ValueError):
    pass

def get_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while part := stream.read(65536):
            h.update(part)
    return h.hexdigest()

def safe_dir(path: Path) -> None:
    if (path.is_symlink() or not path.is_dir()
            or path.stat().st_uid != os.geteuid()
            or stat.S_IMODE(path.stat().st_mode) != 0o700):
        raise RecoveryRefused("owner G2 private directory mismatch; preserve existing data")

def safe_public(path: Path, expected: str) -> None:
    if (path.is_symlink() or not path.is_file() or path.stat().st_uid != os.geteuid()
            or stat.S_IMODE(path.stat().st_mode) & 0o022
            or get_digest(path) != expected):
        raise RecoveryRefused("immutable PUBLIC G2 genesis/deployment-block hash mismatch")

def exact_git(commit: str) -> None:
    if not SHA_PATTERN.fullmatch(commit) or os.geteuid() == 0:
        raise RecoveryRefused("exact reviewed Git commit and unprivileged VM owner required")
    try:
        actual = subprocess.check_output(
            ["git", "rev-parse", "--verify", "HEAD^{commit}"],
            cwd=ROOT, text=True, timeout=6).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=ROOT, text=True, timeout=6).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise RecoveryRefused("unable to verify checked out Git source") from exc
    if actual != commit or dirty:
        raise RecoveryRefused("must use exact GitHub SHA with no tracked VM edits")

def run_docker(args: list[str], *, timeout: int = 15) -> str:
    try:
        result = subprocess.run(
            ["sudo", "-n", "docker", *args], capture_output=True,
            text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RecoveryRefused("authorized Docker operation not accessible") from exc
    if result.returncode:
        # Docker errors can contain paths/tokens. Do NOT reproduce stderr.
        raise RecoveryRefused("reviewed Docker operation failed; preserve existing client state")
    return result.stdout.strip()

def maybe_docker(args: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["sudo", "-n", "docker", *args], capture_output=True,
            text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    return result.returncode == 0, result.stdout.strip() if result.returncode == 0 else ""

def docker_state(name: str) -> dict:
    result = run_docker(["inspect", "--format", "{{json .State}}", name])
    try:
        state = json.loads(result)
    except (ValueError, TypeError) as exc:
        raise RecoveryRefused("Docker container state cannot be parsed") from exc
    if type(state) is not dict:
        raise RecoveryRefused("existing Docker state is invalid")
    return state

def image_pins() -> tuple[str, str, str]:
    try:
        refs = subprocess.check_output(
            [sys.executable, "-B", "tools/sse_pos_client_pins.py", "--refs"],
            cwd=ROOT, text=True, timeout=8).strip().splitlines()
        ids = subprocess.check_output(
            [sys.executable, "-B", "tools/sse_pos_client_pins.py", "--image-ids"],
            cwd=ROOT, text=True, timeout=8).strip().splitlines()
    except (OSError, subprocess.SubprocessError) as exc:
        raise RecoveryRefused("immutable client image manifest invalid") from exc
    if len(refs) != 2 or len(ids) != 2:
        raise RecoveryRefused("must have exact pinned Besu and Lighthouse images")
    return refs[0], ids[0], ids[1]

def review(commit: str) -> dict:
    exact_git(commit)
    safe_dir(RUN)
    for folder in ("testnet", "el", "beacon", "vc"):
        safe_dir(RUN / folder)
    for name, digest in EXPECTED.items():
        safe_public(RUN / name, digest)
    jwt = RUN / "engine.jwt"
    if (jwt.is_symlink() or not jwt.is_file()
            or jwt.stat().st_uid != os.geteuid()
            or stat.S_IMODE(jwt.stat().st_mode) != 0o600
            or jwt.stat().st_size != 64):
        raise RecoveryRefused("original local 256-bit owner-only Engine JWT metadata wrong")
    el_ref, el_id, lh_id = image_pins()
    if run_docker(["image", "inspect", "--format", "{{.Id}}", el_ref]) != el_id:
        raise RecoveryRefused("pinned Besu immutable Docker image identity changed")
    statuses = {}
    for name in (ORIGINAL_EL, BEACON, VC):
        s = docker_state(name)
        if (s.get("Status") != "exited" or s.get("Running") is not False
                or s.get("OOMKilled") is not False):
            raise RecoveryRefused("all three original clients must be safely exited")
        image = run_docker(["inspect", "-f", "{{.Image}}", name])
        if image != (el_id if name == ORIGINAL_EL else lh_id):
            raise RecoveryRefused("original client image differs from immutable pin")
        net = run_docker(["inspect", "-f", "{{.HostConfig.NetworkMode}}", name])
        if net != NETWORK:
            raise RecoveryRefused("original container is not on R35 isolated network")
        statuses[name] = "exited"
    exists, _ = maybe_docker(["container", "inspect", REPLACEMENT_EL])
    if exists:
        raise RecoveryRefused("replacement Besu container already exists; no duplicate EL")
    internal = run_docker(["network", "inspect", "--format", "{{.Internal}}", NETWORK])
    if internal != "true":
        raise RecoveryRefused("existing Docker network must remain internal-only")
    raw_tmpfs = run_docker(
        ["inspect", "-f", "{{json .HostConfig.Tmpfs}}", ORIGINAL_EL]
    )
    try:
        tmpfs = json.loads(raw_tmpfs)
    except (TypeError, ValueError) as exc:
        raise RecoveryRefused("cannot verify original Besu native /tmp mount") from exc
    if (type(tmpfs) is not dict or "/tmp" not in tmpfs
            or "noexec" not in tmpfs["/tmp"].split(",")):
        raise RecoveryRefused("original Besu must have reviewed erroneous noexec /tmp")
    return {
        "schema": "SSE_R40_G2_PRESERVE_ORIGINAL_CHAIN31340_RECOVERY_REVIEW_V1",
        "exactGitSHA": commit,
        "originalThreeContainersExited": statuses,
        "originalELHadNoexecTmpfs": True,
        "originalClientImageDigestsMatchPinned": True,
        "originalEngineJwtMetadataValidatedWithoutReading": True,
        "originalPublicGenesisAndLighthouseFilenameHashesVerified": len(EXPECTED),
        "originalIsolatedBridgeInternal": True,
        "newELContainerDoesNotAlreadyExist": True,
        "singleOwnerFaultDomain": True,
        "noAdditionalValidatorKeystoreCreated": True,
    }

def local_api(url: str, payload: dict | None = None) -> dict | None:
    try:
        body = json.dumps(payload).encode() if payload is not None else None
        req = Request(url, data=body,
                      headers={"Content-Type": "application/json"},
                      method="POST" if body is not None else "GET")
        with OPENER.open(req, timeout=3) as res:
            if res.status != 200:
                return None
            parsed = json.loads(res.read(300_000))
            return parsed if type(parsed) is dict else None
    except (OSError, ValueError, TypeError):
        return None

def wait_execution() -> bool:
    for _ in range(30):
        if docker_state(REPLACEMENT_EL).get("Running") is not True:
            return False
        value = local_api("http://127.0.0.1:18545",
                          {"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []})
        if (isinstance(value, dict) and value.get("result") == hex(31340)):
            return True
        time.sleep(2)
    return False

def wait_beacon() -> bool:
    for _ in range(30):
        if docker_state(BEACON).get("Running") is not True:
            return False
        value = local_api("http://127.0.0.1:15052/eth/v1/beacon/genesis")
        data = value.get("data", {}) if isinstance(value, dict) else {}
        if isinstance(data, dict) and str(data.get("genesis_time")) == str(GENESIS_TIME):
            return True
        time.sleep(2)
    return False

def recover(commit: str) -> dict:
    report = review(commit)
    el_ref, _, _ = image_pins()
    response = input(
        "Existing one-owner chain31340 signing will resume if recovery succeeds. "
        "Confirm no other VC is signing this key. Type RECOVER-CHAIN31340-G2: "
    )
    if response != "RECOVER-CHAIN31340-G2":
        raise RecoveryRefused("owner has not authorized genuine G2 service restart")
    # A deliberate replacement PROCESS, not a replacement GENESIS/KEY/DB/JWT.
    # A stopped original container remains intact for forensic comparison.
    uidgid = str(os.geteuid()) + ":" + str(os.getegid())
    args = [
        "run", "-d", "--pull", "never", "--platform", "linux/amd64",
        "--name", REPLACEMENT_EL,
        "--hostname", REPLACEMENT_EL,
        "--init", "--network", NETWORK,
        "--network-alias", ORIGINAL_EL,
        "--publish", "127.0.0.1:18545:8545/tcp",
        "--user", uidgid, "--read-only",
        # Java Besu native JNI/JNA libs need executable-backed temporary files.
        # Restrict exec to this 256MiB temporary mount, NOT the host or EL DB.
        "--tmpfs", "/tmp:rw,nosuid,exec,size=256m",
        "--cpus", "2", "--memory", "4g", "--pids-limit", "384",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--mount", "type=bind,source=" + str(RUN / "testnet") + ",target=/testnet,readonly",
        "--mount", "type=bind,source=" + str(RUN / "el") + ",target=/data",
        "--mount", "type=bind,source=" + str(RUN / "engine.jwt") + ",target=/jwt/engine.jwt,readonly",
        el_ref,
        "--network-id=31340",
        "--genesis-file=/testnet/genesis.json",
        "--data-path=/data",
        "--p2p-enabled=false",
        "--rpc-http-enabled",
        "--rpc-http-host=0.0.0.0",
        "--rpc-http-port=8545",
        "--rpc-http-api=ETH,NET,WEB3",
        "--host-allowlist=localhost,127.0.0.1",
        "--engine-rpc-enabled",
        "--engine-rpc-port=8551",
        "--engine-host-allowlist=" + ORIGINAL_EL,
        "--engine-jwt-secret=/jwt/engine.jwt",
    ]
    run_docker(args, timeout=30)
    print("R40_EXISTING_BESU_EL_DATA_AND_JWT_REUSED=true", flush=True)
    print("R40_ORIGINAL_FAILED_BESU_CONTAINER_PRESERVED=true", flush=True)
    if not wait_execution():
        raise RecoveryRefused(
            "new EL did not serve authenticated chain31340 identity; "
            "original files/containers preserved; no Beacon or VC start attempted"
        )
    print("R40_REAL_BESU_EXECUTION_CHAIN31340_RPC_OBSERVED=true", flush=True)
    if docker_state(ORIGINAL_EL).get("Running") or docker_state(VC).get("Running"):
        raise RecoveryRefused("duplicate EL or VC became active; refuse signing")
    run_docker(["start", BEACON], timeout=20)
    print("R40_EXISTING_LIGHTHOUSE_BEACON_RESTART_SUBMITTED=true", flush=True)
    if not wait_beacon():
        raise RecoveryRefused(
            "Beacon did not accept original real genesis, leave original VC STOPPED"
        )
    print("R40_REAL_BEACON_GENESIS_TIME_ACCEPTED=true", flush=True)
    if docker_state(VC).get("Running") is True:
        raise RecoveryRefused("unexpected active VC, do not start a second signer")
    run_docker(["start", VC], timeout=20)
    print("R40_EXISTING_ORIGINAL_LIGHTHOUSE_VC_RESTART_SUBMITTED=true", flush=True)
    report.update({
        "recoveryApplied": True,
        "newBesuOnlyExecutableTmpfs": True,
        "newBesuReusesExactOriginalExecutionStateAndJWT": True,
        "originalStoppedBesuContainerPreserved": True,
        "newELNetworkDNSAliasForExistingBeacon": ORIGINAL_EL,
        "realExecutionChainId31340ActuallyResponded": True,
        "realBeaconGenesisTimeActuallyResponded": True,
        "sameOriginalSingleValidatorClientRestarted": True,
        "finalityAndSignedBlocksObservedByThisScript": False,
        "publicNativeP2PVerified": False,
    })
    return report

def main() -> int:
    p = argparse.ArgumentParser(description="G2 real existing-chain recovery without genesis or signer regeneration")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    p.add_argument("--expected-commit", required=True)
    args = p.parse_args()
    try:
        if args.plan:
            report = review(args.expected_commit)
            report["mode"] = "read_only_plan"
            report["anyDockerContainerStarted"] = False
        else:
            if not sys.stdin.isatty() or not sys.stderr.isatty():
                raise RecoveryRefused("owner TTY required before resuming original validator")
            report = recover(args.expected_commit)
            report["mode"] = "explicit_owner_authorized_recovery"
        print(json.dumps(report, sort_keys=True, indent=2))
        return 0
    except (RecoveryRefused, OSError, ValueError, KeyboardInterrupt) as exc:
        # Print only our own controlled refusal reasons, never Docker stderr.
        print("R40_RECOVERY_REFUSED: " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
