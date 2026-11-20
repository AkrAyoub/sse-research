#!/usr/bin/env python3
"""R38: one-time PUBLIC Lighthouse testnet filename repair. NO service restart.

Pinned Lighthouse v8.3.3 source Eth2NetworkConfig::load requires
deposit_contract_block.txt; our R35 staging wrote deploy_block.txt instead.
Correct only that name by an exclusive new PUBLIC file. Never alter existing
EL/CL genesis, SSZ, JWT, validator keystores or slashing protection.
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

ROOT = Path(__file__).resolve().parents[1]
R35_ROOT = Path.home() / ".local/share/sse-r35-chain31340-g2-private"
EXPECTED_FILES = {
    "testnet/deploy_block.txt": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
    "testnet/genesis.json": "22eb6c58288113b9c3671970967151012665137b345237b5c24060dc988b1ee8",
    "testnet/config.yaml": "839072fe3d4b2092b4867010ad01254145872969d89f66ecc86610700f381b13",
    "testnet/genesis.ssz": "8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82",
}
REQUIRED_BLOCK = "testnet/deposit_contract_block.txt"
CONTAINERS = ("sse31340-g2-el", "sse31340-g2-bn", "sse31340-g2-vc")
NET = "sse31340-g2-internal"
SHA_RE = re.compile(r"[a-f0-9]{40}\Z")

class PublicLighthouseStagingError(ValueError):
    pass

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while data := stream.read(65536):
            h.update(data)
    return h.hexdigest()

def safe_file(path: Path) -> None:
    if (path.is_symlink() or not path.is_file() or path.stat().st_uid != os.geteuid()
            or stat.S_IMODE(path.stat().st_mode) & 0o022):
        raise PublicLighthouseStagingError("required immutable PUBLIC genesis file unsafe")

def safe_directory(path: Path) -> None:
    if (path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.geteuid()
            or stat.S_IMODE(path.stat().st_mode) != 0o700):
        raise PublicLighthouseStagingError("existing owner G2 data directory must be mode 0700")

def docker_state(name: str) -> str:
    try:
        result = subprocess.run(
            ["sudo", "-n", "docker", "inspect", "-f", "{{.State.Status}}", name],
            capture_output=True, check=False, timeout=8, text=True,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PublicLighthouseStagingError("unable to inspect existing pinned G2 containers") from exc
    if result.returncode:
        raise PublicLighthouseStagingError("expected original G2 container missing/inaccessible")
    return result.stdout.strip()

def ensure_exact_checkout(commit: str) -> None:
    if not SHA_RE.fullmatch(commit) or os.geteuid() == 0:
        raise PublicLighthouseStagingError("owner and immutable 40-char GitHub SHA required")
    try:
        current = subprocess.check_output(
            ["git", "rev-parse", "--verify", "HEAD^{commit}"],
            cwd=ROOT, text=True, timeout=6).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=ROOT, text=True, timeout=6).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise PublicLighthouseStagingError("cannot verify checked out clean GitHub source") from exc
    if current != commit or dirty:
        raise PublicLighthouseStagingError("G2 public alias repair requires exact clean GitHub SHA")

def review(root: Path) -> dict:
    safe_directory(root)
    safe_directory(root / "testnet")
    for name, expected_hash in EXPECTED_FILES.items():
        source = root / name
        safe_file(source)
        if sha256(source) != expected_hash:
            raise PublicLighthouseStagingError("existing immutable PUBLIC genesis/SSZ/hash mismatched")
    jwt = root / "engine.jwt"
    if (jwt.is_symlink() or not jwt.is_file() or jwt.stat().st_uid != os.geteuid()
            or stat.S_IMODE(jwt.stat().st_mode) != 0o600
            or jwt.stat().st_size != 64):
        raise PublicLighthouseStagingError("original 0600 Engine JWT metadata mismatch; content never read")
    for name in ("el", "beacon", "vc"):
        safe_directory(root / name)
    statuses = {name: docker_state(name) for name in CONTAINERS}
    if set(statuses.values()) != {"exited"}:
        raise PublicLighthouseStagingError("all three original G2 containers must be stopped before public repair")
    try:
        net_info = subprocess.run(
            ["sudo", "-n", "docker", "network", "inspect", "--format", "{{.Internal}}", NET],
            capture_output=True, text=True, check=False, timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PublicLighthouseStagingError("cannot check original isolated G2 network") from exc
    if net_info.returncode or net_info.stdout.strip() != "true":
        raise PublicLighthouseStagingError("original G2 private Docker network is not internal-only")
    alias = root / REQUIRED_BLOCK
    if alias.exists() or alias.is_symlink():
        raise PublicLighthouseStagingError("required public block alias already exists; never overwrite")
    return {
        "exactOriginalImmutablePublicArtifactsVerified": len(EXPECTED_FILES),
        "allExistingDockerContainersExited": True,
        "existingEngineJwtMetadataSafeAndNotRead": True,
        "g2IsolatedDockerBridgeStillInternal": True,
        "requiredLighthouseFileAbsent": True,
        "originalPublicFileStillPresentAndHasExactObservedHash": True,
        "existingPrivateValidatorFilesReadOrChanged": False,
    }

def create_only_public_alias(root: Path) -> None:
    path = root / REQUIRED_BLOCK
    data = (root / "testnet/deploy_block.txt").read_bytes()
    if not 0 < len(data) < 64:
        raise PublicLighthouseStagingError("unexpected original PUBLIC deploy block content size")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        raise
    if sha256(path) != EXPECTED_FILES["testnet/deploy_block.txt"]:
        raise PublicLighthouseStagingError("new public Lighthouse alias checksum mismatch; preserve evidence")

def main() -> int:
    parser = argparse.ArgumentParser(description="Exact existing G2 public-only Lighthouse mandatory file-name fix")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--plan", action="store_true")
    modes.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    try:
        ensure_exact_checkout(args.expected_commit)
        report = review(R35_ROOT)
        report.update({
            "schema": "SSE_R38_EXISTING_G2_PUBLIC_LIGHTHOUSE_FILENAME_FIX_V1",
            "readOnlyInspectionBeforeAnyWrite": True,
            "allClientsStillStopped": True,
            "noClientsStartedOrRestarted": True,
            "noGenesisSSZKeyOrWalletRegenerated": True,
            "mode": "apply_public_filename_only" if args.apply else "plan_only",
        })
        if args.apply:
            create_only_public_alias(R35_ROOT)
            report["lighthouseRequiredPublicBlockFilenameNowCreated"] = True
        else:
            report["lighthouseRequiredPublicBlockFilenameNowCreated"] = False
        print(json.dumps(report, sort_keys=True, indent=2))
        return 0
    except (PublicLighthouseStagingError, OSError, ValueError) as exc:
        print("R38_PUBLIC_LIGHTHOUSE_ALIAS_REFUSED: " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
