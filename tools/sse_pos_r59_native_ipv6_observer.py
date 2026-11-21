#!/usr/bin/env python3
"""R59: create-once genuine NON-SIGNING chain31340 Besu + Lighthouse IPv6 node.

One operator-authorized --apply deploys real pinned EL + CL clients on a
dedicated dual-stack Docker bridge; host bindings expose only *native P2P*
to the host's already-joined controllerless ZeroTier 6plane IPv6.
EL JSON-RPC and Beacon REST bind only HOST 127.0.0.1; Engine8551 is NEVER
published to host. No VC, BLS key, ETH wallet, or new genesis is created.
Restart policy is unless-stopped; no interactive passwords after launch.

--plan is read-only, does not require code checkout/private GitHub.
--apply is one-shot, operator-consented; on PARTIAL FAILURE DO NOT RETRY.
Running EL/CL without verified bootnodes will NOT synchronize chain31340.
Real native P2P, finality, remote reachability still need real measurements.
"""
from __future__ import annotations
import argparse
import hashlib
import ipaddress
import json
import os
import platform
import re
import secrets
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path.home() / ".local/share/sse-r59-chain31340-observer"
ARCHIVE = Path.home() / "chain31340-public-native-observer-v1.tar.gz"
ARCHIVE_SHA = "1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7"
PREFIX = "chain31340-public/"
EXPECTED = {
    "genesis.json": "22eb6c58288113b9c3671970967151012665137b345237b5c24060dc988b1ee8",
    "config.yaml": "3e750d7d02e3ed83747f95cc09ff3299185f56f1777dfeb1f126b17881297b6e",
    "genesis.ssz": "8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82",
    "deposit_contract_block.txt": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
}
MAX_ARCHIVE = 6_000_000
MAX_MEMBER = 3_000_000
NETWORK = "ff2328775f000000"
BRIDGE = "sse31340-r59-nonsigning-bridge"
EL = "sse31340-r59-nonsigning-el"
BN = "sse31340-r59-nonsigning-bn"
BESU_REF = "hyperledger/besu@sha256:4fd2ba40f0d65917bcb3abd9af60673946f66dee2ecb1b87f7cdfa6a30fe458d"
BESU_ID = "sha256:4fd2ba40f0d65917bcb3abd9af60673946f66dee2ecb1b87f7cdfa6a30fe458d"
LIGHTHOUSE_REF = "sigp/lighthouse@sha256:53f9063d98c3d3a2d290207873f019ea2298cfc02f8cd58d87c33b04aab856d1"
LIGHTHOUSE_ID = "sha256:53f9063d98c3d3a2d290207873f019ea2298cfc02f8cd58d87c33b04aab856d1"
ENR = re.compile(r"enr:[A-Za-z0-9_-]{75,2000}\Z")


ENODE6 = re.compile(r"enode://[a-fA-F0-9]{128}@\\[[0-9a-fA-F:]+\\]:[1-9][0-9]{1,4}(?:\\?discport=[1-9][0-9]{1,4})?\\Z")


class R59Refused(ValueError):
    pass


def run(args: list[str], *, timeout: int = 20) -> str:
    try:
        p = subprocess.run(args, capture_output=True, text=True,
                           errors="replace", timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise R59Refused("reviewed host operation unavailable or timed out") from exc
    if p.returncode:
        # Do not display arbitrary output (could reveal file paths / local data).
        raise R59Refused("reviewed host operation failed; preserve partial state")
    return p.stdout.strip()


def docker(args: list[str], *, timeout: int = 25) -> str:
    return run(["sudo", "-n", "docker", *args], timeout=timeout)


def resource_exists(kind: str, name: str) -> bool:
    if kind not in ("network", "container"):
        raise R59Refused("unexpected resource type")
    try:
        result = subprocess.run(["sudo", "-n", "docker", kind, "inspect", name],
                                capture_output=True, timeout=12, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise R59Refused("cannot inspect candidate Docker resource") from exc
    if result.returncode not in (0, 1):
        raise R59Refused("Docker resource inspection inconclusive")
    return result.returncode == 0


def guard_owner() -> None:
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise R59Refused("non-signing Linux x86_64 host required")
    for directory in ("sse-r35-chain31340-g2-private", "sse-r27-bls-operator-private"):
        p = Path.home() / ".local/share" / directory
        if p.exists() or p.is_symlink():
            raise R59Refused("original owner signer state detected")
    if ROOT.exists() or ROOT.is_symlink():
        raise R59Refused("existing R59 state; no overwrites or second launch")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def inspect_archive() -> dict[str, bytes]:
    if ARCHIVE.is_symlink() or not ARCHIVE.is_file() or not 0 < ARCHIVE.stat().st_size <= MAX_ARCHIVE:
        raise R59Refused("original PUBLIC archive missing or oversized")
    if sha256(ARCHIVE.read_bytes()) != ARCHIVE_SHA:
        raise R59Refused("original chain31340 PUBLIC archive hash mismatch")
    contents: dict[str, bytes] = {}
    try:
        with tarfile.open(ARCHIVE, "r:gz") as tar:
            for item in tar:
                if (not item.isfile() or item.name not in
                    {PREFIX + n for n in (*EXPECTED, "manifest.json")} or
                    item.size < 0 or item.size > MAX_MEMBER or item.name in contents):
                    raise R59Refused("invalid, duplicate, symlinked or oversized public tar member")
                f = tar.extractfile(item)
                if f is None:
                    raise R59Refused("public member not readable")
                body = f.read(MAX_MEMBER + 1)
                if len(body) != item.size or len(body) > MAX_MEMBER:
                    raise R59Refused("unbounded public genesis member")
                contents[item.name] = body
    except (OSError, tarfile.TarError) as exc:
        raise R59Refused("cannot read original verified public archive") from exc
    if set(contents) != {PREFIX + n for n in (*EXPECTED, "manifest.json")}:
        raise R59Refused("wrong chain31340 public genesis members")
    for name, expect in EXPECTED.items():
        if sha256(contents[PREFIX + name]) != expect:
            raise R59Refused("original genesis member checksum mismatch")
    if len(contents[PREFIX + "genesis.ssz"]) != 2_737_436:
        raise R59Refused("unexpected real Beacon genesis state size")
    try:
        manifest = json.loads(contents[PREFIX + "manifest.json"])
        genesis = json.loads(contents[PREFIX + "genesis.json"])
    except (ValueError, UnicodeError) as exc:
        raise R59Refused("invalid public chain31340 JSON") from exc
    if (not isinstance(manifest, dict) or manifest.get("chainId") != 31340
        or manifest.get("filesSha256") != EXPECTED
        or not isinstance(genesis, dict)
        or not isinstance(genesis.get("config"), dict)
        or genesis["config"].get("chainId") != 31340):
        raise R59Refused("original public chain identity differs")
    return contents


def overlay_ip() -> tuple[str, str]:
    raw = run(["sudo", "-n", "zerotier-cli", "-j", "listnetworks"])
    try:
        networks = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise R59Refused("ZeroTier membership JSON invalid") from exc
    if not isinstance(networks, list):
        raise R59Refused("ZeroTier membership must be an actual list")
    matches = [n for n in networks if isinstance(n, dict) and n.get("nwid") == NETWORK]
    if len(matches) != 1 or matches[0].get("status") != "OK" or matches[0].get("type") != "PUBLIC":
        raise R59Refused("expected actual public controllerless network membership")
    n = matches[0]
    iface = n.get("portDeviceName")
    if not isinstance(iface, str) or not re.fullmatch(r"zt[A-Za-z0-9]{4,15}", iface):
        raise R59Refused("invalid actual overlay interface")
    assigned = n.get("assignedAddresses")
    if not isinstance(assigned, list):
        raise R59Refused("no overlay address from ZeroTier")
    ips = []
    for value in assigned:
        try:
            ip = ipaddress.ip_interface(str(value)).ip
        except ValueError:
            continue
        if ip.version == 6 and ip in ipaddress.ip_network("fca0::/16"):
            ips.append(str(ip))
    if len(ips) != 1:
        raise R59Refused("expected one real 6plane host IPv6")
    actual = run(["ip", "-6", "addr", "show", "dev", iface])
    if ips[0] not in actual:
        raise R59Refused("assigned overlay IPv6 absent from host interface")
    return iface, ips[0]


def images() -> None:
    for image, expected in ((BESU_REF, BESU_ID), (LIGHTHOUSE_REF, LIGHTHOUSE_ID)):
        actual = docker(["image", "inspect", "--format", "{{.Id}}", image])
        arch = docker(["image", "inspect", "--format", "{{.Os}}/{{.Architecture}}", image])
        if actual != expected or arch != "linux/amd64":
            raise R59Refused("pinned R57 immutable Docker client image ID/platform differs")


def bootnodes(el_enode: str | None, bn_enr: str | None) -> bool:
    if (el_enode is None) != (bn_enr is None):
        raise R59Refused("execution and beacon bootnodes must be supplied together")
    if el_enode is None:
        return False
    if not (ENODE6.fullmatch(el_enode) and ENR.fullmatch(bn_enr)):
        raise R59Refused("execution enodeV6 and Beacon ENR syntax required")
    host = el_enode.split("@[",1)[1].split("]",1)[0]
    try:
        address = ipaddress.IPv6Address(host)
    except ValueError as exc:
        raise R59Refused("execution enode IPv6 invalid") from exc
    if address not in ipaddress.ip_network("fca0::/16"):
        raise R59Refused("execution bootstrap cannot use private-LAN IPv4 or nonoverlay IP")
    # Valid ENR syntax != validated signature, provenance or accessibility.
    return True


def port_bindings(ip: str, is_el: bool) -> list[str]:
    validated = ipaddress.IPv6Address(ip)
    if validated not in ipaddress.ip_network("fca0::/16"):
        raise R59Refused("P2P port publication requires assigned 6plane IPv6")
    if is_el:
        return [f"[{ip}]:30404:30404/tcp", f"[{ip}]:30404:30404/udp",
                "127.0.0.1:28545:8545/tcp"]
    return [f"[{ip}]:9000:9000/tcp", f"[{ip}]:9000:9000/udp",
            f"[{ip}]:9001:9001/udp", "127.0.0.1:25052:5052/tcp"]


def no_conflicting_clients() -> None:
    names = docker(["ps", "-a", "--format", "{{.Names}}"]).splitlines()
    if ("sse31340-g2-vc" in names or
        any(name in names for name in (EL, BN)) or
        resource_exists("network", BRIDGE)):
        raise R59Refused("existing owner signer or R59 Docker resources; no overwrite")
    for name in (EL, BN):
        if resource_exists("container", name):
            raise R59Refused("existing R59 container cannot be overwritten")


def preflight(el_enode: str | None = None, bn_enr: str | None = None) -> dict:
    guard_owner()
    public = inspect_archive()
    iface, ip = overlay_ip()
    docker(["info", "--format", "{{.ServerVersion}}"])
    images()
    no_conflicting_clients()
    has_bootnodes = bootnodes(el_enode, bn_enr)
    return {
        "schema": "SSE_R59_GENUINE_NONSIGNING_IPV6_OBSERVER_CREATE_ONCE_PREFLIGHT_V1",
        "realOriginalChain31340ArchiveSha256": ARCHIVE_SHA,
        "publicGenesisFilesVerified": len(EXPECTED),
        "originalBeaconGenesisBytes": len(public[PREFIX + "genesis.ssz"]),
        "clientImagesMatchPinnedBesuAndLighthouse": True,
        "zeroTierInterface": iface,
        "host6planeIpv6": ip,
        "nativeExecutionHostPortBindings": port_bindings(ip, True),
        "nativeConsensusHostPortBindings": port_bindings(ip, False),
        "plannedEngineRpc8551HostPublication": False,
        "plannedElJsonRpcHostBindingOnlyLoopback": True,
        "plannedBeaconRestHostBindingOnlyLoopback": True,
        "dockerNetworkDesign": "dedicated_ipv6_enabled_user_defined_bridge_not_host_network",
        "ipv6DockerPublishAndNativeClientHandshakeAlreadyVerified": False,
        "executionEnodeV6AndBeaconEnrProvidedSyntaxOnly": has_bootnodes,
        "actualBootnodesAuthenticatedOrReachableByPreflight": False,
        "originalOwnerP2pReachabilityVerifiedByThisTool": False,
        "noLocalOrRemoteSignerCreatedOrUsed": True,
        "noNewConsensusFinalityOrSynchronizationClaimed": True,
        "noServicesOrFilesCreatedByPreflight": True,
        "autoRestartPlannedAfterOperatorApprovedInstall": True,
        "unattendedRebootRecoveryVerified": False,
    }


def create_file(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def stage_genesis(public: dict[str, bytes]) -> None:
    for name in EXPECTED:
        create_file(ROOT / "testnet" / name, public[PREFIX + name])


def run_container(image: str, name: str, common: list[str],
                  bindings: list[str], args: list[str],
                  *, lighthouse: bool = False) -> None:
    cmd = ["run", "-d", "--pull", "never", "--platform", "linux/amd64",
           "--name", name, "--hostname", name,
           "--restart", "unless-stopped",
           "--stop-timeout", "60",
           "--init", "--network", BRIDGE,
           "--user", f"{os.geteuid()}:{os.getegid()}",
           "--read-only", "--cap-drop", "ALL",
           "--security-opt", "no-new-privileges",
           "--cpus", "1.5" if lighthouse else "2",
           "--memory", "4g", "--pids-limit", "384",
           "--tmpfs", "/tmp:rw,nosuid," + ("noexec" if lighthouse else "exec") + ",size=256m",
           *common]
    for binding in bindings:
        cmd.extend(["--publish", binding])
    if lighthouse:
        cmd.extend(["--entrypoint", "lighthouse"])
    cmd.append(image)
    cmd.extend(args)
    docker(cmd, timeout=45)


def inspect_published(name: str, expected: list[str], image_id: str) -> None:
    image = docker(["container", "inspect", "--format", "{{.Image}}", name])
    if image != image_id:
        raise R59Refused("running container image identity mismatch")
    published = json.loads(docker(["container", "inspect",
                                   "--format", "{{json .HostConfig.PortBindings}}", name]))
    observed: set[str] = set()
    for key, entries in published.items():
        for binding in entries:
            ip = binding.get("HostIp", "")
            port = binding.get("HostPort", "")
            observed.add((f"[{ip}]" if ":" in ip else ip) + ":" + port + ":" + key)
    if observed != set(expected):
        raise R59Refused("unexpected host Docker port publication; inspect immediately")


def apply(el_enode: str | None, bn_enr: str | None) -> dict:
    result = preflight(el_enode, bn_enr)
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        raise R59Refused("interactive local operator approval required")
    print("This creates TWO REAL NON-SIGNING native chain31340 clients; "
          "no new validator or genesis. Docker bridge IPv6 maps only P2P "
          "to your ZeroTier address; privileged API not published. "
          "Bootstraps absent = no syncing. "
          "Partial failure must be inspected; NEVER rerun automatically.", file=sys.stderr)
    response = input("Type CREATE-REAL-R59-NONSIGNING-OBSERVER: ")
    if response != "CREATE-REAL-R59-NONSIGNING-OBSERVER":
        raise R59Refused("operator approval absent")
    public = inspect_archive()
    ip = result["host6planeIpv6"]
    ROOT.parent.mkdir(parents=True, exist_ok=True)
    ROOT.mkdir(mode=0o700)
    for name in ("testnet", "el", "beacon"):
        (ROOT / name).mkdir(mode=0o700)
    stage_genesis(public)
    create_file(ROOT / "engine.jwt", secrets.token_hex(32).encode("ascii"))
    # Dual-stack user-defined bridge. No host-network namespace and NO --internal:
    # CL and EL must have routed real peer traffic after true bootstrap exists.
    docker(["network", "create", "--driver", "bridge", "--ipv6", BRIDGE], timeout=35)
    print("R59_REAL_OBSERVER_DOCKER_IPV6_BRIDGE_CREATED=true", flush=True)
    common = [
        "--mount", f"type=bind,source={ROOT / 'testnet'},target=/testnet,readonly",
        "--mount", f"type=bind,source={ROOT / 'engine.jwt'},target=/jwt/engine.jwt,readonly",
    ]
    el_args = [
        "--network-id=31340", "--genesis-file=/testnet/genesis.json",
        "--data-path=/data", "--p2p-enabled=true",
        "--discovery-enabled=true", "--discovery-mode=BOTH",
        "--p2p-interface=0.0.0.0", "--p2p-interface-ipv6=::",
        "--p2p-host-ipv6=" + ip, "--p2p-port=30303", "--p2p-port-ipv6=30404",
        "--p2p-ipv6-outbound-enabled=true",
        "--nat-method=NONE",
        "--rpc-http-enabled", "--rpc-http-host=0.0.0.0",
        "--rpc-http-port=8545", "--rpc-http-api=ETH,NET,WEB3",
        "--host-allowlist=localhost,127.0.0.1",
        "--engine-rpc-enabled", "--engine-rpc-port=8551",
        "--engine-host-allowlist=" + EL,
        "--engine-jwt-secret=/jwt/engine.jwt",
    ]
    if el_enode:
        el_args.append("--bootnodes=" + el_enode)
    run_container(BESU_REF, EL,
                  [*common, "--mount", f"type=bind,source={ROOT / 'el'},target=/data"],
                  port_bindings(ip, True), el_args)
    print("R59_REAL_NONSIGNING_BESU_EL_SUBMITTED=true", flush=True)
    inspect_published(EL, port_bindings(ip, True), BESU_ID)
    bn_args = [
        "--testnet-dir=/testnet", "--datadir=/data", "bn",
        "--execution-endpoint=http://" + EL + ":8551",
        "--execution-jwt=/jwt/engine.jwt",
        "--http", "--http-address=0.0.0.0", "--http-port=5052",
        "--listen-address=::", "--port6=9000", "--discovery-port6=9000",
        "--quic-port6=9001", "--enr-address=" + ip,
        "--enr-tcp6-port=9000", "--enr-udp6-port=9000",
        "--enr-quic6-port=9001", "--enable-private-discovery",
        "--disable-upnp", "--allow-insecure-genesis-sync",
    ]
    if bn_enr:
        bn_args.extend(["--boot-nodes=" + bn_enr])
    run_container(LIGHTHOUSE_REF, BN,
                  [*common, "--mount", f"type=bind,source={ROOT / 'beacon'},target=/data"],
                  port_bindings(ip, False), bn_args, lighthouse=True)
    print("R59_REAL_NONSIGNING_LIGHTHOUSE_BN_SUBMITTED=true", flush=True)
    inspect_published(BN, port_bindings(ip, False), LIGHTHOUSE_ID)
    return {
        **result,
        "mode": "operator_authorized_one_time_create",
        "noServicesOrFilesCreatedByPreflight": False,
        "actualNonsigningBesuAndBeaconContainerStartsSubmitted": True,
        "dockerAutoRestartUnlessStoppedConfigured": True,
        "noNewValidatorClientOrSigningKeysCreated": True,
        "actualNativeRemotePeerHandshakeStillNeedsIndependentEvidence": True,
        "actualOriginalChainHeadAndFinalityStillNeedIndependentObservation": True,
        "overlayIpv6TcpUdpPortPublicationNeedsActualExternalVerification": True,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Original chain31340 NON-SIGNING EL+CL native IPv6 observer")
    x = p.add_mutually_exclusive_group(required=True)
    x.add_argument("--plan", action="store_true")
    x.add_argument("--apply", action="store_true")
    p.add_argument("--execution-seed-enode-v6")
    p.add_argument("--beacon-seed-enr")
    args = p.parse_args()
    try:
        report = preflight(args.execution_seed_enode_v6, args.beacon_seed_enr) if args.plan else apply(
            args.execution_seed_enr, args.beacon_seed_enr)
        if args.plan:
            report["mode"] = "read_only"
        print(json.dumps(report, sort_keys=True, indent=2))
        return 0
    except (R59Refused, OSError, ValueError, TypeError, KeyError, tarfile.TarError, KeyboardInterrupt) as exc:
        print("R59_NONSIGNING_OBSERVER_REFUSED: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
