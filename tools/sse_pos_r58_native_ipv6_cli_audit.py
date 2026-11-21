#!/usr/bin/env python3
"""R58: read-only/short-lived OFFLINE native IPv6 capability audit on NON-SIGNING host.

Checks actual R47 genesis hash, ad-hoc membership and R57 immutable image IDs,
then invokes ONLY Docker --help and --Xhelp in ephemeral networkless containers.
Does not launch Besu EL, Lighthouse BN/VC, new genesis, ports or validators.
Its output is capability evidence, NOT a native P2P/consensus handshake.
"""
from __future__ import annotations
import hashlib
import ipaddress
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

NETWORK = "ff2328775f000000"
ARCHIVE_SHA = "1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7"
BESU_REF = "hyperledger/besu@sha256:4fd2ba40f0d65917bcb3abd9af60673946f66dee2ecb1b87f7cdfa6a30fe458d"
BESU_ID = "sha256:4fd2ba40f0d65917bcb3abd9af60673946f66dee2ecb1b87f7cdfa6a30fe458d"
LIGHTHOUSE_REF = "sigp/lighthouse@sha256:53f9063d98c3d3a2d290207873f019ea2298cfc02f8cd58d87c33b04aab856d1"
LIGHTHOUSE_ID = "sha256:53f9063d98c3d3a2d290207873f019ea2298cfc02f8cd58d87c33b04aab856d1"
BESU_FLAGS = (
    "p2p-enabled", "p2p-host", "p2p-interface", "p2p-host-ipv6",
    "p2p-interface-ipv6", "p2p-port-ipv6", "p2p-ipv6-outbound-enabled",
    "discovery-mode", "discovery-enabled", "p2p-discovery-port",
    "nat-method", "engine-rpc-enabled", "engine-rpc-host",
    "engine-rpc-port", "engine-host-allowlist",
    "engine-jwt-secret", "rpc-http-host", "rpc-http-enabled",
    "host-allowlist", "network-id", "genesis-file",
    "Xv5-discovery-enabled",
)
LIGHTHOUSE_FLAGS = (
    "listen-address", "enr-address", "port", "port6",
    "quic-port", "quic-port6", "discovery-port6",
    "enr-tcp6-port", "enr-udp6-port", "enr-quic6-port",
    "enable-private-discovery", "disable-packet-filter",
    "disable-upnp", "disable-enr-auto-update",
    "http-address", "http-port", "execution-endpoint",
    "execution-jwt", "testnet-dir", "datadir",
    "boot-nodes", "allow-insecure-genesis-sync",
)
REQUIRED_BESU_IPV6 = (
    "p2p-host-ipv6", "p2p-interface-ipv6", "p2p-port-ipv6",
    "p2p-ipv6-outbound-enabled", "discovery-mode", "rpc-http-host",
)
REQUIRED_BESU_ENGINE = (
    "engine-rpc-port", "engine-host-allowlist", "engine-jwt-secret",
)
REQUIRED_LIGHTHOUSE = (
    "listen-address", "enr-address", "port6", "enr-tcp6-port",
    "enr-udp6-port", "enable-private-discovery",
    "http-address", "execution-endpoint", "execution-jwt",
    "allow-insecure-genesis-sync",
)


class R58Refused(ValueError):
    pass


def run(args: list[str], timeout: int = 75) -> str:
    try:
        p = subprocess.run(args, capture_output=True, text=True,
                           errors="replace", timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise R58Refused("reviewed read-only command inaccessible or timed out") from exc
    if p.returncode:
        # stderr can contain host paths: print no unreviewed raw subprocess output.
        raise R58Refused("reviewed read-only command failed")
    if len(p.stdout) > 800_000:
        raise R58Refused("CLI output exceeded bounded size")
    return p.stdout


def flag_present(help_text: str, flag: str) -> bool:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", flag):
        raise R58Refused("invalid inspected CLI flag")
    return re.search(r"(?<![A-Za-z0-9-])--" + re.escape(flag)
                     + r"(?![A-Za-z0-9-])", help_text) is not None


def flags_in_help(help_text: str, names: tuple[str, ...]) -> dict[str, bool]:
    return {name: flag_present(help_text, name) for name in names}


def signer_guard() -> None:
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise R58Refused("only non-signing Linux amd64 participant supported")
    for name in ("sse-r35-chain31340-g2-private", "sse-r27-bls-operator-private"):
        directory = Path.home() / ".local/share" / name
        if directory.exists() or directory.is_symlink():
            raise R58Refused("original signing state detected; refuse")


def archive_guard() -> int:
    archive = Path.home() / "chain31340-public-native-observer-v1.tar.gz"
    if archive.is_symlink() or not archive.is_file():
        raise R58Refused("original public genesis archive absent")
    size = archive.stat().st_size
    if not 0 < size < 6_000_000:
        raise R58Refused("public genesis archive size invalid")
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise R58Refused("public genesis archive SHA differs from owner observed hash")
    return size


def membership() -> tuple[str, str]:
    nets = json.loads(run(["sudo", "-n", "zerotier-cli", "-j", "listnetworks"], 12))
    if not isinstance(nets, list):
        raise R58Refused("ZeroTier JSON network list invalid")
    matches = [n for n in nets if isinstance(n, dict) and n.get("nwid") == NETWORK]
    if len(matches) != 1 or matches[0].get("type") != "PUBLIC" or matches[0].get("status") != "OK":
        raise R58Refused("exact public ad-hoc ZeroTier membership absent")
    m = matches[0]
    interface = m.get("portDeviceName")
    if not isinstance(interface, str) or not re.fullmatch(r"zt[A-Za-z0-9]{4,15}", interface):
        raise R58Refused("invalid ZeroTier interface")
    iplist = m.get("assignedAddresses")
    if not isinstance(iplist, list):
        raise R58Refused("no real assigned ZeroTier IPv6")
    selected = []
    for value in iplist:
        try:
            ip = ipaddress.ip_interface(str(value)).ip
        except ValueError:
            continue
        if ip.version == 6 and ip in ipaddress.ip_network("fca0::/16"):
            selected.append(str(ip))
    if len(selected) != 1:
        raise R58Refused("requires exactly one assigned 6plane IPv6")
    addr = selected[0]
    output = run(["ip", "-6", "addr", "show", "dev", interface], 10)
    if addr not in output:
        raise R58Refused("ZeroTier assigned IPv6 not bound on host interface")
    return interface, addr


def verify_image(ref: str, required_id: str) -> None:
    image_id = run(["sudo", "-n", "docker", "image", "inspect",
                    "--format", "{{.Id}}", ref], 15).strip()
    arch = run(["sudo", "-n", "docker", "image", "inspect",
                "--format", "{{.Os}}/{{.Architecture}}", ref], 15).strip()
    if image_id != required_id or arch != "linux/amd64":
        raise R58Refused("immutable client image identity/platform differs from pinned source")


def offline_help(ref: str, *, lighthouse: bool = False,
                 experimental: bool = False) -> str:
    base = [
        "sudo", "-n", "docker", "run", "--rm", "--pull", "never",
        "--platform", "linux/amd64", "--network", "none", "--read-only",
        "--tmpfs", "/tmp:rw,nosuid,exec,size=64m", "--user", "65534:65534",
        "--cpus", "1", "--memory", "1g", "--pids-limit", "128",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--hostname", "sse-r58-audit", "--add-host", "sse-r58-audit:127.0.0.1",
    ]
    if lighthouse:
        base.extend(["--entrypoint", "lighthouse"])
    base.append(ref)
    base.extend(["bn", "--help"] if lighthouse else ["--Xhelp" if experimental else "--help"])
    return run(base, 90)


def audit() -> dict:
    signer_guard()
    archive_bytes = archive_guard()
    interface, addr = membership()
    run(["sudo", "-n", "docker", "info", "--format", "{{.ServerVersion}}"], 12)
    names = run(["sudo", "-n", "docker", "ps", "-a", "--format", "{{.Names}}"], 12).splitlines()
    if "sse31340-g2-vc" in names:
        raise R58Refused("owner's original VC container detected")
    verify_image(BESU_REF, BESU_ID)
    verify_image(LIGHTHOUSE_REF, LIGHTHOUSE_ID)
    besu_help = offline_help(BESU_REF)
    lighthouse_help = offline_help(LIGHTHOUSE_REF, lighthouse=True)
    # Besu early-access flags may exist only under --Xhelp.
    xhelp_available = True
    try:
        besu_help += "\n" + offline_help(BESU_REF, experimental=True)
    except R58Refused:
        xhelp_available = False
    besu = flags_in_help(besu_help, BESU_FLAGS)
    lighthouse = flags_in_help(lighthouse_help, LIGHTHOUSE_FLAGS)
    return {
        "schema": "SSE_R58_ACTUAL_PINNED_NATIVE_IPV6_CLI_CAPABILITY_AUDIT_V1",
        "originalChain31340PublicArchiveSha256Verified": True,
        "publicArchiveBytes": archive_bytes,
        "originalSigningNodeProtected": True,
        "controllerlessZeroTierNetwork": NETWORK,
        "zeroTierInterface": interface,
        "observedHost6planeIpv6": addr,
        "verifiedBesuImageId": BESU_ID,
        "verifiedLighthouseImageId": LIGHTHOUSE_ID,
        "besuExtendedHelpAvailable": xhelp_available,
        "besuP2pCliFlagsPresent": besu,
        "lighthouseBeaconCliFlagsPresent": lighthouse,
        "requiredBesuIpv6OptionsPresent": all(besu[n] for n in REQUIRED_BESU_IPV6),
        "besuEngineJwtAndHeaderAllowlistOptionsPresent": all(besu[n] for n in REQUIRED_BESU_ENGINE),
        "besuEngineExplicitBindHostOptionObserved": besu["engine-rpc-host"],
        "engineHostAllowlistIsNotNetworkAccessControl": True,
        "engineApiIPv6HostNetworkIsolationVerified": False,
        "requiredLighthouseIpv6OptionsPresent": all(lighthouse[n] for n in REQUIRED_LIGHTHOUSE),
        "dockerHelpRunsUsedNetworkNone": True,
        "newGenesisOrSignerCreated": False,
        "actualELCLServiceOrP2pStarted": False,
        "actualEthereumPeerHandshakeObserved": False,
        "actualOriginalFinalitySyncedByThisAudit": False,
        "readyToExecuteNativeNodeWithoutDesignReview": False,
    }


def main() -> int:
    if sys.argv[1:] != ["--audit"]:
        print("R58_REFUSED: use --audit (no deployment mode)", file=sys.stderr)
        return 2
    try:
        print(json.dumps(audit(), sort_keys=True, indent=2))
        return 0
    except (R58Refused, OSError, ValueError, TypeError) as exc:
        print("R58_AUDIT_REFUSED: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
