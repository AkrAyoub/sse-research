#!/usr/bin/env python3
"""Read-only, source-testable first-boot inventory for ANY prospective SSE host.

This is deliberately NOT an installer, validator admission mechanism,
network probe, role activation, or proof that an external node joined.
It has no network I/O, writes no files, reads no secrets and needs no sudo.
A remote PC/VM is eligible to *attempt* joining regardless of provider,
IPv4 address, local node owner, or whether the machine uses SSE VM hosting.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import sys
from typing import Any

ROLES = ("observer", "full_node", "validator", "consumer", "provider", "monitor")
TOOLS = ("python3", "git", "curl", "docker", "besu", "lighthouse", "caddy", "systemctl")
SCHEMA = "SSE_FRESH_HOST_INVENTORY_V1"


class FreshHostError(ValueError):
    pass


def parse_roles(value: str) -> tuple[str, ...]:
    """Role choice is the only mandatory operator-specific input."""
    if type(value) is not str:
        raise FreshHostError("roles must be a comma-separated string")
    chosen = value.split(",")
    if not chosen or any(x != x.strip() or not x for x in chosen):
        raise FreshHostError("roles must be nonempty, comma-separated, and without surrounding whitespace")
    if len(chosen) != len(set(chosen)) or any(x not in ROLES for x in chosen):
        raise FreshHostError("unknown or duplicate role; choose from " + ",".join(ROLES))
    return tuple(chosen)


def _read_os_release(path: Path = Path("/etc/os-release")) -> tuple[str, str]:
    try:
        rows = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return ("unknown", "unknown")
    pairs: dict[str, str] = {}
    for row in rows:
        if "=" not in row or row.startswith("#"):
            continue
        key, value = row.split("=", 1)
        if key in ("ID", "VERSION_ID"):
            pairs[key] = value.strip().strip('"').strip("'")[:80]
    return (pairs.get("ID", "unknown"), pairs.get("VERSION_ID", "unknown"))


def _read_mem_mib(path: Path = Path("/proc/meminfo")) -> int | None:
    """Report actual kernel MemTotal; do not invent a minimum for our new chain."""
    try:
        for row in path.read_text(encoding="ascii").splitlines():
            if row.startswith("MemTotal:"):
                fields = row.split()
                if len(fields) == 3 and fields[2] == "kB":
                    kib = int(fields[1])
                    return kib // 1024 if kib > 0 else None
    except (OSError, ValueError, UnicodeError):
        return None
    return None


def gather_facts() -> dict[str, Any]:
    """No sockets, cloud metadata queries, local secrets, or privileged commands."""
    distro, version = _read_os_release()
    disk = shutil.disk_usage("/")
    return {
        "system": platform.system(),
        "architecture": platform.machine(),
        "distribution": distro,
        "distributionVersion": version,
        "logicalCPUs": os.cpu_count(),
        "memoryMiB": _read_mem_mib(),
        "rootDiskFreeGiB": round(disk.free / (1024 ** 3), 2),
        "rootDiskTotalGiB": round(disk.total / (1024 ** 3), 2),
        "pythonVersion": platform.python_version(),
        "executablesPresent": {name: shutil.which(name) is not None for name in TOOLS},
    }


def build_report(roles: tuple[str, ...], facts: dict[str, Any]) -> dict[str, Any]:
    """No observed hardware value is turned into a fabricated network pass."""
    if type(roles) is not tuple or not roles or any(r not in ROLES for r in roles):
        raise FreshHostError("invalid selected roles")
    if len(roles) != len(set(roles)):
        raise FreshHostError("duplicate selected roles")
    if type(facts) is not dict or set(facts) != {
        "system", "architecture", "distribution", "distributionVersion",
        "logicalCPUs", "memoryMiB", "rootDiskFreeGiB", "rootDiskTotalGiB",
        "pythonVersion", "executablesPresent"
    }:
        raise FreshHostError("invalid inventory facts")
    tools = facts["executablesPresent"]
    if type(tools) is not dict or set(tools) != set(TOOLS) or any(type(v) is not bool for v in tools.values()):
        raise FreshHostError("invalid executable inventory")
    for key in ("system", "architecture", "distribution", "distributionVersion", "pythonVersion"):
        if type(facts[key]) is not str:
            raise FreshHostError("invalid host metadata")
    for key in ("logicalCPUs", "memoryMiB"):
        if facts[key] is not None and (type(facts[key]) is not int or facts[key] <= 0):
            raise FreshHostError("invalid measured CPU/memory value")
    for key in ("rootDiskFreeGiB", "rootDiskTotalGiB"):
        v = facts[key]
        if type(v) not in (int, float) or not 0 <= v < float("inf"):
            raise FreshHostError("invalid measured disk space")
    if facts["rootDiskFreeGiB"] > facts["rootDiskTotalGiB"]:
        raise FreshHostError("free disk exceeds total disk")
    requires_el_cl = "validator" in roles or "full_node" in roles
    notes = []
    if requires_el_cl:
        notes.append("EL+CL must be independently installed, peered and synchronized; a selected validator also requires a local VC/BLS key, 32 valueless TEST ETH deposit and Beacon activation")
    if "monitor" in roles:
        notes.append("A monitor must post a real on-chain bond, be selected, and must not attest its own consumer/provider lease")
    if "provider" in roles:
        notes.append("A provider must prove real available capacity and serve authenticated live compute, not a mocked endpoint")
    if "consumer" in roles:
        notes.append("A consumer needs its own signing wallet, funded real test-ETH escrow and a live lease")
    if "observer" in roles and not requires_el_cl:
        notes.append("An observer may read verified public data, but this inventory does not establish independent chain verification")
    return {
        "schema": SCHEMA,
        "requestedRoles": list(roles),
        "activatedRoles": [],
        "host": {key: facts[key] for key in (
            "system", "architecture", "distribution", "distributionVersion",
            "logicalCPUs", "memoryMiB", "rootDiskFreeGiB", "rootDiskTotalGiB",
            "pythonVersion", "executablesPresent")},
        "bootstrapUbuntu2404Detected": (
            facts["system"] == "Linux" and facts["distribution"] == "ubuntu"
            and facts["distributionVersion"] == "24.04"
        ),
        "roleRuntimeRequirementsNotVerified": notes,
        "network": {
            "staticPublicIPRequired": False,
            "publicIPObserved": False,
            "publicTCPIngressVerified": False,
            "publicUDPIngressVerified": False,
            "natOrCGNATDetermined": False,
            "externalPeerConnected": False,
            "dynamicDNSConfigured": False,
            "bootstrapDiscoveryVerified": False,
        },
        "funding": {
            "nativeCurrency": "valueless_test_eth",
            "realEthereumMainnetEthRequired": False,
            "sseAdministratorApprovalForbidden": True,
            "independentWalletsGenerated": False,
            "faucetReservesVerified": False,
            "independentGasSponsorAvailable": False,
            "onchainGrantFinalized": False,
            "validatorDepositsFunded": False,
            "monitorBondsFunded": False,
            "consumerEscrowFunded": False,
        },
        "acceptance": {
            "publicSignedReleaseVerified": False,
            "freshPoS31340Joined": False,
            "elClGenesisAndFinalityVerified": False,
            "validatorDepositAndActivationVerified": False,
            "publicHTTPSNodeUIVerified": False,
            "realCrossHostSLAObserved": False,
        },
        "readsPrivateKeys": False,
        "writesHostConfiguration": False,
        "sendsNetworkRequests": False,
        "roleSelectionIsAdmission": False,
        "status": "HOST_INVENTORY_ONLY_NOT_AN_ONBOARDED_NODE",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SSE new-VM/external-PC read-only resource inventory")
    parser.add_argument("--roles", required=True,
                        help="comma-separated roles: " + ",".join(ROLES))
    args = parser.parse_args(argv)
    try:
        result = build_report(parse_roles(args.roles), gather_facts())
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (FreshHostError, OSError, ValueError) as exc:
        print("SSE_FRESH_HOST_PROBE_FAILED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
