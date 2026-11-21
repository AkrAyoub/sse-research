#!/usr/bin/env python3
"""R60: read-only CURRENT owner G2 native P2P and finality inspection.

Runs only on original owner VM4706 with exact reviewed Git source.
NEVER changes Docker, OS networking, ZeroTier, signing keys or services.
Does not print raw container command arrays, JWT or keystore metadata.
Actual API readings are point-in-time observations, not independent sync.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from urllib.request import Request, ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
OWNER = Path.home() / ".local/share/sse-r35-chain31340-g2-private"
NET = "sse31340-g2-internal"
EL = "sse31340-g2-el-r40"
BN = "sse31340-g2-bn"
VC = "sse31340-g2-vc"
GENESIS_TIME = "1795219212"
GENESIS = {
    "genesis.json": "22eb6c58288113b9c3671970967151012665137b345237b5c24060dc988b1ee8",
    "genesis.ssz": "8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82",
}
COMMIT = re.compile(r"[a-f0-9]{40}\Z")
HEXNUM = re.compile(r"0x[0-9a-fA-F]{1,20}\Z")
ROOT_HASH = re.compile(r"0x[a-fA-F0-9]{64}\Z")
SAFE_FLAGS = (
    "p2p-enabled", "p2p-interface", "p2p-interface-ipv6", "p2p-host-ipv6",
    "p2p-port", "p2p-port-ipv6", "discovery-enabled", "discovery-mode",
    "listen-address", "port", "port6", "discovery-port", "discovery-port6",
    "quic-port", "quic-port6", "enable-private-discovery",
)
OPENER = build_opener(ProxyHandler({}))


class R60Refused(ValueError):
    pass


def run(args: list[str], timeout: int = 12) -> str:
    try:
        p = subprocess.run(args, capture_output=True, text=True,
                           errors="replace", check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise R60Refused("read-only owner command inaccessible or timed out") from exc
    if p.returncode != 0 or len(p.stdout) > 250_000:
        raise R60Refused("read-only owner command refused or oversized response")
    return p.stdout.strip()


def docker(args: list[str], timeout: int = 12) -> str:
    return run(["sudo", "-n", "docker", *args], timeout=timeout)


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(65536), b""):
            h.update(part)
    return h.hexdigest()


def owner_guard(commit: str) -> None:
    if not COMMIT.fullmatch(commit):
        raise R60Refused("expected pinned 40-hex Git SHA")
    if run(["git", "-C", str(ROOT), "rev-parse", "HEAD"]) != commit:
        raise R60Refused("reviewed source Git SHA does not match")
    if not OWNER.is_dir() or OWNER.is_symlink():
        raise R60Refused("this is not the original G2 owner host")
    if stat.S_IMODE(OWNER.stat().st_mode) != 0o700:
        raise R60Refused("original G2 private home directory permissions unsafe")
    for name, expected in GENESIS.items():
        p = OWNER / "testnet" / name
        if p.is_symlink() or not p.is_file() or file_digest(p) != expected:
            raise R60Refused("original existing G2 public genesis changed")
    jwt = OWNER / "engine.jwt"
    if (jwt.is_symlink() or not jwt.is_file() or jwt.stat().st_size != 64
            or stat.S_IMODE(jwt.stat().st_mode) != 0o600):
        raise R60Refused("original local JWT metadata invalid")
    # NEVER read the original JWT contents, signing key, slashing DB or wallet.


def safe_flags(args: object) -> dict[str, list[str]]:
    """Extract only allowlisted network flags; never return raw argv."""
    if not isinstance(args, list):
        raise R60Refused("container command format changed")
    result: dict[str, list[str]] = {}
    for arg in args:
        if not isinstance(arg, str):
            raise R60Refused("container command contains non-string")
        key, sep, value = arg.removeprefix("--").partition("=")
        if arg.startswith("--") and key in SAFE_FLAGS and sep:
            if len(value) > 60 or not re.fullmatch(r"[A-Za-z0-9:.,_-]{1,60}", value):
                raise R60Refused("network option value not safe for audit")
            result.setdefault(key, []).append(value)
    return result


def client(name: str) -> dict:
    state = json.loads(docker(["inspect", "--format", "{{json .State}}", name]))
    if not isinstance(state, dict):
        raise R60Refused("Docker container state unreadable")
    command = json.loads(docker(["inspect", "--format", "{{json .Config.Cmd}}", name]))
    mode = docker(["inspect", "--format", "{{.HostConfig.NetworkMode}}", name])
    image_id = docker(["inspect", "--format", "{{.Image}}", name])
    bindings = json.loads(docker(["inspect", "--format",
                                  "{{json .HostConfig.PortBindings}}", name]))
    if bindings is not None and not isinstance(bindings, dict):
        raise R60Refused("Docker host port binding structure invalid")
    # Only protocol/host bind addresses + port numbers; no secret-bearing args.
    external_p2p = []
    for cport, records in (bindings or {}).items():
        if cport in ("30303/tcp", "30303/udp", "9000/tcp",
                     "9000/udp", "9001/udp"):
            for record in records or []:
                if isinstance(record, dict):
                    external_p2p.append({
                        "containerPort": cport,
                        "boundHostIp": record.get("HostIp", ""),
                        "boundHostPort": record.get("HostPort", ""),
                    })
    return {
        "running": state.get("Running") is True,
        "status": state.get("Status") if state.get("Status") in
            ("created", "running", "exited", "restarting", "paused", "dead") else "unknown",
        "networkModeIsOriginalInternal": mode == NET,
        "actualImageIdIsSha256": bool(re.fullmatch(r"sha256:[0-9a-f]{64}", image_id)),
        "explicitNetworkFlags": safe_flags(command),
        "publishedNativeP2pHostBindings": external_p2p,
    }


def api_json(url: str, payload: dict | None = None) -> dict | None:
    try:
        body = None if payload is None else json.dumps(payload).encode()
        req = Request(url, data=body, method="GET" if body is None else "POST",
                      headers={"Content-Type": "application/json"})
        with OPENER.open(req, timeout=3) as response:
            if response.status != 200:
                return None
            data = json.loads(response.read(300_000))
            return data if isinstance(data, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def rpc(method: str) -> str | None:
    result = api_json("http://127.0.0.1:18545", {
        "jsonrpc": "2.0", "id": 1, "method": method, "params": []})
    return result.get("result") if isinstance(result, dict) and isinstance(result.get("result"), str) else None


def beacon_reading() -> dict:
    genesis = api_json("http://127.0.0.1:15052/eth/v1/beacon/genesis")
    head = api_json("http://127.0.0.1:15052/eth/v1/beacon/headers/head")
    checkpoints = api_json("http://127.0.0.1:15052/eth/v1/beacon/states/head/finality_checkpoints")
    g = genesis.get("data", {}) if isinstance(genesis, dict) else {}
    d = head.get("data", {}) if isinstance(head, dict) else {}
    m = d.get("header", {}).get("message", {}) if isinstance(d, dict) else {}
    root = d.get("root") if isinstance(d, dict) else None
    f = checkpoints.get("data", {}).get("finalized", {}) if isinstance(checkpoints, dict) else {}
    slot = m.get("slot") if isinstance(m, dict) else None
    epoch = f.get("epoch") if isinstance(f, dict) else None
    finalized_root = f.get("root") if isinstance(f, dict) else None
    return {
        "genesisTimeMatchesOriginal": isinstance(g, dict) and str(g.get("genesis_time")) == GENESIS_TIME,
        "headSlot": int(slot) if isinstance(slot, str) and slot.isdecimal() else None,
        "headRoot": root if isinstance(root, str) and ROOT_HASH.fullmatch(root) else None,
        "finalizedEpoch": int(epoch) if isinstance(epoch, str) and epoch.isdecimal() else None,
        "finalizedRoot": finalized_root if isinstance(finalized_root, str) and ROOT_HASH.fullmatch(finalized_root) else None,
        "beaconRestGaveBothHeadAndFinalizedCheckpoint": (
            isinstance(slot, str) and slot.isdecimal() and
            isinstance(epoch, str) and epoch.isdecimal() and
            isinstance(root, str) and bool(ROOT_HASH.fullmatch(root)) and
            isinstance(finalized_root, str) and bool(ROOT_HASH.fullmatch(finalized_root))
        ),
    }


def audit(commit: str) -> dict:
    owner_guard(commit)
    mode = docker(["network", "inspect", "--format", "{{.Internal}}", NET])
    ipv6 = docker(["network", "inspect", "--format", "{{.EnableIPv6}}", NET])
    if mode not in ("true", "false") or ipv6 not in ("true", "false"):
        raise R60Refused("original Docker network inspect invalid")
    el, bn, vc = client(EL), client(BN), client(VC)
    chainid = rpc("eth_chainId")
    block = rpc("eth_blockNumber")
    peers = rpc("net_peerCount")
    return {
        "schema": "SSE_R60_ACTUAL_OWNER_CHAIN31340_READONLY_NATIVE_P2P_AND_HEALTH_V1",
        "sourceGitExactSha": commit,
        "originalGenesisSha256Verified": True,
        "originalJwtMetadataVerifiedWithoutReadingItsContents": True,
        "originalDockerNetwork": NET,
        "originalDockerNetworkInternal": mode == "true",
        "originalDockerNetworkIpv6Enabled": ipv6 == "true",
        "originalExecutionClient": el,
        "originalBeaconNode": bn,
        "originalValidatorClient": {
            "running": vc["running"],
            "networkModeIsOriginalInternal": vc["networkModeIsOriginalInternal"],
            "noSignerSecretOrSlashingDbReadByTool": True,
        },
        "ownerZeroTierCliInstalled": shutil.which("zerotier-cli") is not None,
        "ownerZeroTierOverlayActuallyJoinedByThisAudit": False,
        "realExecutionRpcChainId31340": chainid == hex(31340),
        "realExecutionBlockNumber": int(block, 16) if isinstance(block, str) and HEXNUM.fullmatch(block) else None,
        "realExecutionPeerCount": int(peers, 16) if isinstance(peers, str) and HEXNUM.fullmatch(peers) else None,
        "realBeacon": beacon_reading(),
        "originalExecutionP2pExplicitlyDisabled": el["explicitNetworkFlags"].get("p2p-enabled") == ["false"],
        "originalSignerOrServicesStoppedOrChanged": False,
        "nativeP2pHostExposurePerformed": False,
        "nativeSecondPeerOrIndependentFinalityProven": False,
        "needsReviewedExistingStatePreservingP2pMaintenance": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only owner G2 P2P and finality audit")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--expected-commit", required=True)
    a = parser.parse_args()
    if not a.audit:
        print("R60_REFUSED: only --audit is supported", file=sys.stderr)
        return 2
    try:
        print(json.dumps(audit(a.expected_commit), sort_keys=True, indent=2))
        return 0
    except (R60Refused, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print("R60_OWNER_READONLY_AUDIT_REFUSED: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
