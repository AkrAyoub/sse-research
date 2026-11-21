#!/usr/bin/env python3
"""R49: genuine NATIVE EL+CL public bootstrap seed for unchanged chain31340.

RUN ON A SEPARATE, NETWORK-ROUTABLE Linux/amd64 edge, NEVER on owner VM4706.
No validator or BLS signer. Exact owner Step54 PUBLIC genesis TAR, same pinned
Besu+Lighthouse, new independent local Engine JWT and fresh EL+Beacon data.
Publishes ONLY genuine EL P2P TCP+UDP and Lighthouse P2P TCP+UDP+QUIC UDP.
DO NOT publish Engine RPC 8551, EL JSON-RPC, Beacon REST or validator signing.
A seed without peers cannot produce blocks or independently finalize them.

Requires real CURRENT public IPv4 endpoint at launch. Address MAY change later,
but an address change requires refreshing signed advertised ENRs/edge mapping;
never pretend DNS alone makes a NAT/CGNAT node reachable. This source does NOT
prove WAN ingress, independent administration or P2P handshake.
--plan is read-only. --apply explicitly consented create-once; NEVER retry after
partial apply, regenerate originals or start a duplicate signing client.
"""
from __future__ import annotations
import argparse
import ipaddress
import json
import os
from pathlib import Path
import platform
import secrets
import subprocess
import sys
import tarfile
import time

import sse_pos_r48_external_observer as external
import sse_pos_r47_public_observer_bundle as bundle
import sse_pos_g2_recover_r40 as owner

RUN = Path.home() / ".local/share/sse-r49-chain31340-public-native-seed"
NET = "sse31340-r49-public-seed-bridge"
EL = "sse31340-r49-public-seed-el"
BN = "sse31340-r49-public-seed-bn"
DOCKER_PUBLISH = (
    "0.0.0.0:30303:30303/tcp",
    "0.0.0.0:30303:30303/udp",
    "0.0.0.0:9000:9000/tcp",
    "0.0.0.0:9000:9000/udp",
    "0.0.0.0:9001:9001/udp",
)
DEPOSIT_SHA = "5aaa8327c5765ec883224895ca02cade2871e12dad0197bdc791efc91c7ef18d"

class SeedRefused(ValueError):
    pass

def ipv4(value: str) -> str:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError as exc:
        raise SeedRefused("advertised endpoint must be current global IPv4") from exc
    if not isinstance(ip, ipaddress.IPv4Address) or not ip.is_global:
        raise SeedRefused("advertised endpoint must be globally routable IPv4")
    return str(ip)

def bounded_public_tar(archive: Path) -> dict:
    if (archive.is_symlink() or not archive.is_file() or
            not 0 < archive.stat().st_size <= bundle.MAX_TARBALL):
        raise SeedRefused("must supply bounded regular PUBLIC real genesis tarball")
    if bundle.digest(archive.read_bytes()) != external.BUNDLE_SHA256:
        raise SeedRefused("original VM4706 public TAR hash mismatch")
    report = bundle.verify_bundle(archive)
    if report["publicGenesisFilesExact"] != 4 or report["actualBeaconSSZBytes"] != 2737436:
        raise SeedRefused("real original genesis/Beacon data mismatch")
    return report

def check(commit: str, archive: Path, advertise_ip: str) -> dict:
    owner.exact_git(commit)
    address = ipv4(advertise_ip)
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SeedRefused("seed requires genuine Linux amd64")
    if (owner.RUN.exists() or owner.RUN.is_symlink()
            or (Path.home() / ".local/share/sse-r27-bls-operator-private").exists()):
        raise SeedRefused("this seed MUST NOT be installed on original signing VM4706")
    if RUN.exists() or RUN.is_symlink():
        raise SeedRefused("previous seed state exists; never overwrite")
    if (external.exists("network", NET) or
            any(external.exists("container", n)
                for n in (EL, BN, "sse31340-g2-vc", external.EL, external.BN))):
        raise SeedRefused("existing chain client/seed resources must not be overwritten")
    verified = bounded_public_tar(archive)
    images = external.client_images()
    return {
        "schema": "SSE_R49_GENUINE_EXTERNAL_PUBLIC_NATIVE_SEED_REVIEW_V1",
        "sourceExactGitSha": commit,
        "publicArchiveSha256Verified": True,
        "originalPublicBeaconGenesisBytes": verified["actualBeaconSSZBytes"],
        "pinnedBesuAndLighthouseImagesOnThisHost": len(images) == 2,
        "advertisedAddressIsCurrentGlobalIPv4BySyntax": address == ipv4(address),
        "externalGatewayAndFirewallPortMappingIndependentlyVerified": False,
        "expectedNativeExecutionP2pPorts": ["30303/tcp", "30303/udp"],
        "expectedNativeConsensusP2pPorts": ["9000/tcp", "9000/udp", "9001/udp"],
        "actualNativeExternalHandshakesVerified": False,
        "independentOperatorFaultDomainVerified": False,
        "ownerOriginalKeysOrRuntimeRead": False,
        "newGenesisOrSigningKeyGenerated": False,
        "originalRealChain31340Preserved": True,
        "publicEthChainRpcAndAuthenticatedEngineApiPublished": False,
        "noContainersOrFilesCreatedByPreflight": True,
        "publicInternetSeedReady": False,
    }

def stage_public(archive: Path) -> None:
    allowed = set(bundle.EXPECTED)
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            if member.name == bundle.PREFIX + "manifest.json":
                continue
            name = member.name.removeprefix(bundle.PREFIX)
            if member.name != bundle.PREFIX + name or name not in allowed:
                raise SeedRefused("public TAR member allowlist error")
            stream = tar.extractfile(member)
            if stream is None:
                raise SeedRefused("public TAR member absent")
            data = stream.read(bundle.MAX_FILE + 1)
            if bundle.digest(data) != bundle.EXPECTED[name]:
                raise SeedRefused("source PUBLIC genesis hash changed")
            external.create_file(RUN / "testnet" / name, data)

def apply(commit: str, archive: Path, advertise_ip: str, operator_verified: bool):
    report = check(commit, archive, advertise_ip)
    address = ipv4(advertise_ip)
    if operator_verified is not True:
        raise SeedRefused("external operator must first verify actual TCP+UDP edge ingress")
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        raise SeedRefused("interactive independent seed operator authorization required")
    answer = input(
        "This will start real PUBLIC P2P (EL 30303 TCP+UDP; CL 9000 TCP+UDP,"
        " 9001 UDP) but NO validator, public RPC, or Engine API."
        " Only authorize on a real publicly routable edge with reviewed firewall."
        " Type CREATE-31340-NONSIGNING-PUBLIC-SEED: "
    )
    if answer != "CREATE-31340-NONSIGNING-PUBLIC-SEED":
        raise SeedRefused("external operator did not authorize public native P2P seed")
    images = external.client_images()
    RUN.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    RUN.mkdir(mode=0o700)
    for sub in ("el", "beacon", "testnet"):
        (RUN / sub).mkdir(mode=0o700)
    stage_public(archive)
    external.create_file(RUN / "engine.jwt", secrets.token_hex(32).encode())
    external.docker(["network", "create", "--driver", "bridge", NET])
    print("R49_REAL_EXTERNAL_SEED_DOCKER_BRIDGE_CREATED=true", flush=True)
    uidgid = f"{os.geteuid()}:{os.getegid()}"
    common = [
        "--init", "--network", NET, "--user", uidgid,
        "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--mount", f"type=bind,source={RUN / 'testnet'},target=/testnet,readonly",
        "--mount", f"type=bind,source={RUN / 'engine.jwt'},target=/jwt/engine.jwt,readonly",
    ]
    external.docker([
        "run", "-d", "--pull", "never", "--platform", "linux/amd64",
        "--name", EL, "--hostname", EL, *common,
        "--publish", DOCKER_PUBLISH[0], "--publish", DOCKER_PUBLISH[1],
        "--tmpfs", "/tmp:rw,nosuid,exec,size=256m",
        "--cpus", "2", "--memory", "4g", "--pids-limit", "384",
        "--mount", f"type=bind,source={RUN / 'el'},target=/data",
        images["besu"],
        "--network-id=31340", "--genesis-file=/testnet/genesis.json",
        "--data-path=/data", "--p2p-enabled=true",
        "--discovery-enabled=true", "--discovery-mode=BOTH",
        "--p2p-interface=0.0.0.0", "--nat-method=NONE",
        "--p2p-host=" + address, "--p2p-port=30303",
        "--p2p-discovery-port=30303",
        "--rpc-http-enabled", "--rpc-http-host=127.0.0.1",
        "--rpc-http-port=8545", "--rpc-http-api=ETH,NET,WEB3",
        "--host-allowlist=localhost,127.0.0.1",
        "--engine-rpc-enabled", "--engine-rpc-port=8551",
        "--engine-host-allowlist=" + EL,
        "--engine-jwt-secret=/jwt/engine.jwt",
    ], timeout=30)
    print("R49_EXTERNAL_PUBLIC_SEED_BESU_SUBMITTED=true", flush=True)
    external.docker([
        "run", "-d", "--pull", "never", "--platform", "linux/amd64",
        "--name", BN, "--hostname", BN, *common,
        "--publish", DOCKER_PUBLISH[2], "--publish", DOCKER_PUBLISH[3],
        "--publish", DOCKER_PUBLISH[4],
        "--tmpfs", "/tmp:rw,nosuid,noexec,size=256m",
        "--cpus", "1.5", "--memory", "4g", "--pids-limit", "384",
        "--mount", f"type=bind,source={RUN / 'beacon'},target=/data",
        "--entrypoint", "lighthouse", images["lighthouse"],
        "--testnet-dir=/testnet", "--datadir=/data", "bn",
        "--execution-endpoint=http://" + EL + ":8551",
        "--execution-jwt=/jwt/engine.jwt",
        "--http", "--http-address=127.0.0.1", "--http-port=5052",
        "--listen-address=0.0.0.0",
        "--port=9000", "--discovery-port=9000", "--quic-port=9001",
        "--enr-address=" + address,
        "--enr-tcp-port=9000", "--enr-udp-port=9000",
        "--enr-quic-port=9001", "--disable-upnp",
        # A fresh non-signing node on the 2026-11-21 custom chain without a
        # trusted checkpoint has genesis weak-subjectivity risk. TEST ONLY;
        # require independent canonical finalized-checkpoint comparison later.
        "--allow-insecure-genesis-sync",
    ], timeout=30)
    print("R49_EXTERNAL_PUBLIC_SEED_LIGHTHOUSE_SUBMITTED=true", flush=True)
    report.update({
        "mode": "one_time_new_public_seed_non_signing",
        "noContainersOrFilesCreatedByPreflight": False,
        "publicP2pDockerPortBindingsSubmitted": list(DOCKER_PUBLISH),
        "operatorClaimedExternalTcpUdpForwardingWasReviewed": True,
        "actualExternalTcpUdpReachabilityStillUnverified": True,
        "newOwnerExternalLocalEngineJwtGeneratedNotShared": True,
        "noValidatorClientOrSignerStarted": True,
        "genesisWeakSubjectivityRiskAcceptedForResearchObserver": True,
        "originalOwnerVM4706Unaffected": True,
    })
    return report

def main() -> int:
    p = argparse.ArgumentParser(description="Non-signing native chain31340 public seed on a separate edge host only")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    p.add_argument("--expected-commit", required=True)
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--advertise-ip", required=True)
    p.add_argument("--external-tcp-udp-forwarding-reviewed", action="store_true")
    args = p.parse_args()
    try:
        if args.plan:
            report = check(args.expected_commit, args.bundle, args.advertise_ip)
            report["mode"] = "read_only_plan"
        else:
            report = apply(
                args.expected_commit, args.bundle, args.advertise_ip,
                args.external_tcp_udp_forwarding_reviewed
            )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (SeedRefused, external.ExternalObserverRefused,
            owner.RecoveryRefused, bundle.ArtifactRefused, OSError,
            ValueError, KeyError, tarfile.TarError, KeyboardInterrupt):
        print("R49_PUBLIC_NATIVE_SEED_REFUSED", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
