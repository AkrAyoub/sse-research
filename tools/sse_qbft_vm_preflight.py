#!/usr/bin/env python3
"""Read-only preflight for one independent Ubuntu Besu validator.

Hard stop on legacy Anvil listener 8545, wrong chain/genesis, missing unique
node key, unpinned image, missing Tailscale, unavailable Docker or occupied
validator ports. No Docker start, wallet signing or RPC state change occurs.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import platform
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys

from sse_qbft_validator_identity import inspect_local, IdentityError

DIGEST_IMAGE = re.compile(
    r"[a-z0-9][a-z0-9._/-]{1,100}:[a-zA-Z0-9._-]+@sha256:[0-9a-f]{64}\Z"
)
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
GITSHA = re.compile(r"[0-9a-f]{40}\Z")
OVERLAY_NET = ipaddress.IPv4Network("100.64.0.0/10")


class PreflightError(ValueError):
    pass


def _run(args, timeout=12):
    try:
        p = subprocess.run(args, capture_output=True, text=True,
                           check=True, timeout=timeout)
        return p.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise PreflightError("required local command unavailable: " + args[0]) from None


def parse_genesis(path: Path, expected_sha256: str) -> dict:
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
            or not SHA256.fullmatch(expected_sha256) or path.stat().st_size > 262144):
        raise PreflightError("invalid genesis file or trusted SHA256")
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha256:
        raise PreflightError("immutable genesis SHA256 mismatch")
    try:
        doc = json.loads(raw)
        cfg = doc["config"]
        qbft = cfg["qbft"]
        if (type(cfg["chainId"]) is not int or cfg["chainId"] != 31338
                or qbft["blockperiodseconds"] != 5
                or qbft["requesttimeoutseconds"] != 10
                or int(doc["gasLimit"], 16) != 15000000):
            raise PreflightError("genesis is not approved baseline QBFT 31338")
    except (ValueError, TypeError, KeyError) as exc:
        raise PreflightError("malformed or nonbaseline genesis") from None
    return {"genesisSha256": actual, "chainId": 31338,
            "targetBlockPeriodSeconds": 5, "blockGasLimit": 15000000}


def parse_image(value: str) -> str:
    if type(value) is not str or not DIGEST_IMAGE.fullmatch(value):
        raise PreflightError("Besu image must have full reviewed version AND sha256 digest")
    if not value.startswith("hyperledger/besu:"):
        raise PreflightError("wrong Besu image repository")
    # GHSA-p4h2-gvh4-pv6j: one Byzantine QBFT proposer could mint native
    # currency through unvalidated withdrawals when Shanghai is enabled.
    # Upstream patched QBFT withdrawals in 26.8.1; a later JVM Base64
    # security mitigation shipped in 26.11.1. This research baseline
    # therefore requires >=26.11.1 (and still needs review of later CVEs).
    version = value.split(":", 1)[1].split("@", 1)[0]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise PreflightError("Besu version must be explicit, no RC/latest")
    version_numbers = tuple(int(v) for v in version.split("."))
    if version_numbers < (26, 11, 1):
        raise PreflightError("Research baseline requires 26.11.1+ (QBFT withdrawals and 2026 JVM Base64 fixes)")
    return value


def parse_tailscale_status(raw: str, expected_ip: str) -> dict:
    try:
        doc = json.loads(raw)
        info = doc["Self"]
        address = ipaddress.IPv4Address(expected_ip)
        actual = [ipaddress.ip_address(x) for x in info["TailscaleIPs"]]
        if (doc["BackendState"] != "Running" or info["Online"] is not True
                or address not in OVERLAY_NET or address not in actual):
            raise PreflightError("tailnet not running with this VM's approved overlay IP")
    except (ValueError, KeyError, TypeError) as exc:
        raise PreflightError("invalid Tailscale status or overlay identity") from None
    return {"tailscaleOnline": True, "overlayIPv4": str(address)}


def _listening(port: int, host="127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.35)
        return s.connect_ex((host, port)) == 0


def _p2p_port_busy(port: int = 30303) -> bool:
    """Probe TCP *and* UDP bind conflicts; do not listen or publish a service."""
    for protocol in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
        with socket.socket(socket.AF_INET, protocol) as sock:
            try:
                sock.bind(("0.0.0.0", port))
            except OSError:
                return True
    return False


def assess(*, source_revision: str, current_revision: str, image: str,
           genesis: Path, genesis_sha256: str,
           private_dir: Path, public_file: Path,
           tailscale_status: str, run=_run, listening=_listening) -> dict:
    if (not GITSHA.fullmatch(source_revision) or
            not GITSHA.fullmatch(current_revision)
            or source_revision != current_revision):
        raise PreflightError("checkout not at exact reviewed GitHub source commit")
    if platform.system() != "Linux":
        raise PreflightError("run on independent Ubuntu validator machine")
    os_release = Path("/etc/os-release").read_text(encoding="utf-8")
    if "ID=ubuntu" not in os_release and 'ID="ubuntu"' not in os_release:
        raise PreflightError("validator operating system is not Ubuntu")
    if os.geteuid() == 0:
        raise PreflightError("run this check as the dedicated unprivileged validator operator")
    if listening(8545) or listening(18545) or _p2p_port_busy():
        raise PreflightError("existing/legacy RPC or P2P listener: never overwrite")
    genesis_doc = parse_genesis(genesis, genesis_sha256)
    record = inspect_local(private_dir, public_file=public_file)
    overlay = parse_tailscale_status(tailscale_status, record["overlayIPv4"])
    for args in (["docker", "version", "--format", "{{.Server.Version}}"],
                 ["docker", "compose", "version", "--short"]):
        run(args)
    return {
        "kind": "SSE_QBFT_INDEPENDENT_HOST_PREFLIGHT_V1",
        "sourceGitSha": source_revision, "besuImage": parse_image(image),
        **genesis_doc, **overlay,
        "nodeId": record["nodeId"],
        "validatorAddress": record["validatorAddress"],
        "enode": record["enode"],
        "dockerAvailable": True,
        "legacyAnvilProtected": True,
        "p2pPortReady": True,
        "localRpcPortReady": True,
        "startedDocker": False, "transactionsSent": False,
        "independentAdministratorProved": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Read-only validator readiness gate; safe on new VM")
    p.add_argument("--expected-revision", required=True)
    p.add_argument("--besu-image", required=True)
    p.add_argument("--genesis", type=Path, required=True)
    p.add_argument("--genesis-sha256", required=True)
    p.add_argument("--private-dir", type=Path, required=True)
    p.add_argument("--public-file", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        current = _run(["git", "rev-parse", "HEAD"])
        status = _run(["tailscale", "status", "--json"])
        result = assess(source_revision=a.expected_revision,
                        current_revision=current, image=a.besu_image,
                        genesis=a.genesis, genesis_sha256=a.genesis_sha256,
                        private_dir=a.private_dir, public_file=a.public_file,
                        tailscale_status=status)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (PreflightError, IdentityError, ValueError, OSError,
            KeyError, TypeError) as exc:
        print("SSE_QBFT_PREFLIGHT_REFUSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
