#!/usr/bin/env python3
"""R48: TRUE external NON-SIGNING chain31340 Besu + Lighthouse observer.

Operates on a DIFFERENT Linux x86_64 host from owner VM4706. Consumes the
exact owner-observed public-only genesis archive, never owner EL/CL runtime,
validator keystore, wallet, password, slashing database or Engine JWT.
Creates a new JWT only between THIS observer's own EL and CL. No VC at all.
Real native devp2p and discv5/libp2p bootstrap uses signed ENRs; mere ENR
strings/containers are NOT proof of connectivity or independence.

--plan is strictly read-only. --apply is create-once with interactive consent.
No cleanup, retries or second signer after a partial launch.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import platform
import re
import secrets
import stat
import subprocess
import sys
import tarfile

from sse_pos_client_pins import load_pins
import sse_pos_g2_recover_r40 as source_gate
import sse_pos_r47_public_observer_bundle as bundle

RUN = Path.home() / ".local/share/sse-r48-external-nonsigning-observer"
NETWORK = "sse31340-r48-observer-outbound"
EL = "sse31340-r48-observer-el"
BN = "sse31340-r48-observer-bn"
BUNDLE_SHA256 = "1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7"
ENR = re.compile(r"enr:[A-Za-z0-9_-]{75,2000}\Z")
ORIGINAL_OWNER_DIR = source_gate.RUN

class ExternalObserverRefused(ValueError):
    pass

def docker(args: list[str], timeout: int = 20) -> str:
    try:
        result = subprocess.run(
            ["sudo", "-n", "docker", *args],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ExternalObserverRefused("independent host Docker command inaccessible") from exc
    if result.returncode:
        # NEVER expose raw Docker output, commands or local paths in error text.
        raise ExternalObserverRefused("reviewed Docker operation refused")
    return result.stdout.strip()

def exists(kind: str, name: str) -> bool:
    if kind not in ("network", "container"):
        raise ExternalObserverRefused("unexpected Docker resource kind")
    try:
        result = subprocess.run(
            ["sudo", "-n", "docker", kind, "inspect", name],
            capture_output=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ExternalObserverRefused("cannot inspect original Docker resource") from exc
    return result.returncode == 0

def client_images() -> dict:
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ExternalObserverRefused("pinned Docker clients require an independent Linux x86_64 host")
    pins = load_pins()
    if pins["intendedChainId"] != 31340:
        raise ExternalObserverRefused("client image pins do not match real chain31340")
    refs = {}
    for role in ("besu", "lighthouse"):
        pin = pins["images"][role]
        if docker(["image", "inspect", "--format", "{{.Id}}", pin["ref"]]) != pin["imageId"]:
            raise ExternalObserverRefused("external host client image differs from pinned digest")
        refs[role] = pin["ref"]
    return refs

def validate_bootstrap(el_enr: str | None, bn_enr: str | None) -> bool:
    if (el_enr is None) != (bn_enr is None):
        raise ExternalObserverRefused("execution and consensus bootstraps must be supplied together")
    if el_enr is None:
        return False
    if (not ENR.fullmatch(el_enr) or not ENR.fullmatch(bn_enr)
            or el_enr == bn_enr):
        raise ExternalObserverRefused("two distinct real EL/CL ENR strings are required")
    return True

def preflight(archive: Path, commit: str,
              el_enr: str | None, bn_enr: str | None) -> dict:
    source_gate.exact_git(commit)
    if (ORIGINAL_OWNER_DIR.exists() or ORIGINAL_OWNER_DIR.is_symlink()
            or (Path.home() / ".local/share/sse-r27-bls-operator-private").exists()):
        raise ExternalObserverRefused("cannot stage external observer on original signing owner host")
    if RUN.exists() or RUN.is_symlink():
        raise ExternalObserverRefused("observer state already exists; never overwrite or duplicate")
    if (exists("network", NETWORK)
            or any(exists("container", n) for n in (EL, BN, "sse31340-g2-vc"))):
        raise ExternalObserverRefused("observer Docker state exists or original signer present")
    if (archive.is_symlink() or not archive.is_file()
            or not 0 < archive.stat().st_size <= bundle.MAX_TARBALL):
        raise ExternalObserverRefused("original public genesis tarball must be a bounded regular file")
    if bundle.digest(archive.read_bytes()) != BUNDLE_SHA256:
        raise ExternalObserverRefused("transferred public archive differs from real owner Step54 SHA256")
    checked = bundle.verify_bundle(archive)
    client_images()
    seeds = validate_bootstrap(el_enr, bn_enr)
    return {
        "schema": "SSE_R48_REAL_EXTERNAL_NONSIGNING_OBSERVER_PREFLIGHT_V1",
        "sourceExactGitSha": commit,
        "originalPublicArchiveSha256Verified": True,
        "originalGenesisSszBytes": checked["actualBeaconSSZBytes"],
        "originalFourPublicELCLFilesVerified": checked["publicGenesisFilesExact"] == 4,
        "realBesuAndLighthousePinnedImagesInstalled": True,
        "noOriginalValidatorSignerOrPrivateCredentialsUsed": True,
        "noObserverStateOrContainerOverwritten": True,
        "distinctExecutionAndBeaconBootstrapEnrsSupplied": seeds,
        "enrSignaturesOrReachabilityVerifiedByThisTool": False,
        "authenticatedInternetPeerHandshakesObserved": False,
        "realExternalFinalityVerified": False,
        "physicalIndependenceOfOperatorVerifiedByTool": False,
        "noServicesCreatedOrChanged": True,
        "operatorMayReviewApplyAfterSeparateSeedReachabilityEvidence": seeds,
        "actualSeedReachabilityWasVerifiedByPreflight": False,
    }

def create_file(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())

def stage_public_archive(archive: Path) -> None:
    allowed = set(bundle.EXPECTED)
    with tarfile.open(archive, "r:gz") as tar:
        for info in tar:
            if info.name == bundle.PREFIX + "manifest.json":
                continue
            name = info.name.removeprefix(bundle.PREFIX)
            if name not in allowed or info.name != bundle.PREFIX + name:
                raise ExternalObserverRefused("unexpected public genesis archive member")
            stream = tar.extractfile(info)
            if stream is None:
                raise ExternalObserverRefused("public archive member missing")
            content = stream.read(bundle.MAX_FILE + 1)
            if bundle.digest(content) != bundle.EXPECTED[name]:
                raise ExternalObserverRefused("public original genesis artifact checksum mismatch")
            create_file(RUN / "testnet" / name, content)

def apply(archive: Path, commit: str, el_enr: str, bn_enr: str) -> dict:
    result = preflight(archive, commit, el_enr, bn_enr)
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        raise ExternalObserverRefused("actual separate operator interactive consent required")
    approval = input(
        "Start NEW NON-SIGNING Besu+Lighthouse observer on THIS EXTERNAL HOST, "
        "with PUBLIC original chain31340 genesis and fresh local JWT only. "
        "No validator key. Type START-EXTERNAL-31340-OBSERVER: "
    )
    if approval != "START-EXTERNAL-31340-OBSERVER":
        raise ExternalObserverRefused("external operator did not authorize")
    refs = client_images()
    RUN.parent.mkdir(parents=True, exist_ok=True)
    RUN.mkdir(mode=0o700)
    for part in ("testnet", "el", "beacon"):
        (RUN / part).mkdir(mode=0o700)
    stage_public_archive(archive)
    # NEW independent local EL/CL Engine token, NOT owner's private JWT.
    create_file(RUN / "engine.jwt", secrets.token_hex(32).encode("ascii"))
    docker(["network", "create", "--driver", "bridge", NETWORK])
    print("R48_GENUINE_EXTERNAL_OUTBOUND_DOCKER_NETWORK_CREATED=true", flush=True)
    uidgid = str(os.geteuid()) + ":" + str(os.getegid())
    common = [
        "--init", "--network", NETWORK, "--user", uidgid,
        "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--mount", f"type=bind,source={RUN / 'testnet'},target=/testnet,readonly",
        "--mount", f"type=bind,source={RUN / 'engine.jwt'},target=/jwt/engine.jwt,readonly",
    ]
    docker([
        "run", "-d", "--pull", "never", "--platform", "linux/amd64",
        "--name", EL, "--hostname", EL, *common,
        "--publish", "127.0.0.1:28545:8545/tcp",
        "--tmpfs", "/tmp:rw,nosuid,exec,size=256m",
        "--cpus", "2", "--memory", "4g", "--pids-limit", "384",
        "--mount", f"type=bind,source={RUN / 'el'},target=/data",
        refs["besu"],
        "--network-id=31340", "--genesis-file=/testnet/genesis.json",
        "--data-path=/data", "--p2p-enabled=true",
        "--discovery-enabled=true", "--discovery-mode=BOTH",
        "--p2p-port=30303", "--bootnodes=" + el_enr,
        "--rpc-http-enabled", "--rpc-http-host=0.0.0.0",
        "--rpc-http-port=8545", "--rpc-http-api=ETH,NET,WEB3",
        "--host-allowlist=localhost,127.0.0.1",
        "--engine-rpc-enabled", "--engine-rpc-port=8551",
        "--engine-host-allowlist=" + EL,
        "--engine-jwt-secret=/jwt/engine.jwt",
    ], timeout=30)
    print("R48_REAL_INDEPENDENT_NONSIGNING_BESU_SUBMITTED=true", flush=True)
    docker([
        "run", "-d", "--pull", "never", "--platform", "linux/amd64",
        "--name", BN, "--hostname", BN, *common,
        "--publish", "127.0.0.1:25052:5052/tcp",
        "--tmpfs", "/tmp:rw,nosuid,noexec,size=256m",
        "--cpus", "1.5", "--memory", "4g", "--pids-limit", "384",
        "--mount", f"type=bind,source={RUN / 'beacon'},target=/data",
        "--entrypoint", "lighthouse", refs["lighthouse"],
        "--testnet-dir=/testnet", "--datadir=/data", "bn",
        "--execution-endpoint=http://" + EL + ":8551",
        "--execution-jwt=/jwt/engine.jwt",
        "--http", "--http-address=0.0.0.0", "--http-port=5052",
        "--listen-address=0.0.0.0", "--port=9000", "--quic-port=9001",
        "--boot-nodes=" + bn_enr,
    ], timeout=30)
    print("R48_REAL_INDEPENDENT_NONSIGNING_LIGHTHOUSE_SUBMITTED=true", flush=True)
    result.update({
        "mode": "one_time_external_operator_apply",
        "newIndependentObserverOnlyClientsSubmitted": [EL, BN],
        "noServicesCreatedOrChanged": False,
        "independentLocalEngineJwtGeneratedWithoutDisclosure": True,
        "noOriginalSignerOrValidatorClientCreated": True,
        "noPublicEngineApiOrSignerApiExposed": True,
        "onlyOutboundNativeP2pRequiredForThisObserver": True,
        "realNativeP2pAndConsensusFinalityStillNeedIndependentObservation": True,
        "sourceOnlyEnrSyntaxNotCryptographicVerification": True,
    })
    return result

def main() -> int:
    p = argparse.ArgumentParser(description="Original chain31340 independent non-signing native observer")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true")
    g.add_argument("--apply", action="store_true")
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--expected-commit", required=True)
    p.add_argument("--execution-seed-enr")
    p.add_argument("--beacon-seed-enr")
    args = p.parse_args()
    try:
        if args.plan:
            result = preflight(args.bundle, args.expected_commit,
                               args.execution_seed_enr, args.beacon_seed_enr)
            result["mode"] = "read_only_plan"
        else:
            if not args.execution_seed_enr or not args.beacon_seed_enr:
                raise ExternalObserverRefused("two real publicly reachable EL/CL seed ENRs required")
            result = apply(args.bundle, args.expected_commit,
                           args.execution_seed_enr, args.beacon_seed_enr)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ExternalObserverRefused, source_gate.RecoveryRefused,
            bundle.ArtifactRefused, OSError, ValueError,
            KeyError, tarfile.TarError, KeyboardInterrupt) as exc:
        # No raw error/log output ever.
        print("R48_EXTERNAL_OBSERVER_REFUSED: " + type(exc).__name__, file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
