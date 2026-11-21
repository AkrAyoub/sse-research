#!/usr/bin/env python3
"""R143: read-only, role-neutral first-boot capacity and prerequisite inventory.

Run this on each NEW VM before any installation. It makes NO modifications,
requires no root privileges, reads no signer/key contents and uses no network.
Operational sizing is an explicit starting recommendation, NOT an SSE or PoS
eligibility rule or a permanent role-population limit.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys

SCHEMA = "SSE_R143_NEW_HOST_READINESS_V1"
ROLES = frozenset(("full_node", "observer", "validator",
                   "provider", "consumer", "monitor"))
NODE_ID = re.compile(r"[a-z][a-z0-9-]{2,62}\Z")
GIB = 1024 ** 3

# Advice for INITIAL experiments, not protocol-enforced minimum requirements.
# A future empirical benchmark must replace these preliminary planning margins.
SIZING = {
    "full_node": {"vcpus": 4, "memoryGiB": 10, "freeDiskGiB": 50},
    "observer": {"vcpus": 4, "memoryGiB": 10, "freeDiskGiB": 50},
    "validator": {"vcpus": 4, "memoryGiB": 10, "freeDiskGiB": 50},
    "provider": {"vcpus": 2, "memoryGiB": 4, "freeDiskGiB": 10},
    "consumer": {"vcpus": 1, "memoryGiB": 2, "freeDiskGiB": 5},
    "monitor": {"vcpus": 1, "memoryGiB": 2, "freeDiskGiB": 5},
}

class Refused(ValueError):
    pass

def check_roles(node_id, roles):
    if type(node_id) is not str or not NODE_ID.fullmatch(node_id):
        raise Refused("invalid local node identifier")
    if type(roles) is not list or not roles or len(roles) != len(set(roles)):
        raise Refused("roles must be a nonempty unique list")
    if any(type(role) is not str or role not in ROLES for role in roles):
        raise Refused("unsupported role name")
    return tuple(roles)

def parse_meminfo(text):
    if type(text) is not str:
        raise Refused("missing kernel memory report")
    matched = re.findall(r"^MemTotal:\s*([0-9]+)\s+kB$", text, re.M)
    if len(matched) != 1:
        raise Refused("invalid MemTotal kernel report")
    return int(matched[0]) * 1024

def recommend(roles, cpus, memory_bytes, free_disk_bytes):
    if not roles or any(r not in SIZING for r in roles):
        raise Refused("invalid role selection")
    if (type(cpus) is not int or cpus <= 0
            or any(type(x) is not int or x < 0
                   for x in (memory_bytes, free_disk_bytes))):
        raise Refused("invalid observed resources")
    required = {key: max(SIZING[role][key] for role in roles)
                for key in ("vcpus", "memoryGiB", "freeDiskGiB")}
    measured = {"vcpus": cpus,
                "memoryGiB": round(memory_bytes / GIB, 2),
                "freeDiskGiB": round(free_disk_bytes / GIB, 2)}
    gaps = [
        f"{key}: observed {measured[key]} < planning target {required[key]}"
        for key in required if measured[key] < required[key]
    ]
    return required, measured, gaps

def inspect(node_id, roles, *, home=None, get_cpus=os.cpu_count,
            get_mem=None, get_disk=None, which=shutil.which,
            get_os=platform.system, get_machine=platform.machine):
    roles = check_roles(node_id, roles)
    if get_os() != "Linux" or get_machine() != "x86_64":
        raise Refused("current pinned Besu/Lighthouse setup requires Linux x86_64")
    home = Path.home() if home is None else Path(home)
    if get_mem is None:
        try:
            mem = parse_meminfo(Path("/proc/meminfo").read_text("utf-8"))
        except OSError as exc:
            raise Refused("cannot inspect host physical memory") from exc
    else:
        mem = get_mem()
    try:
        disk = shutil.disk_usage(str(home)).free if get_disk is None else get_disk()
    except OSError as exc:
        raise Refused("cannot inspect local data volume free space") from exc
    cpus = get_cpus()
    required, observed, gaps = recommend(roles, cpus, mem, disk)
    tools = {name: which(name) is not None
             for name in ("python3", "git", "docker", "zerotier-cli", "ip", "curl")}
    # Only report known guarded state existence, never inspect key material.
    state = home / ".local" / "share"
    signer_present = any((state / path).exists() or (state / path).is_symlink()
                         for path in ("sse-r35-chain31340-g2-private",
                                      "sse-r27-bls-operator-private"))
    existing_r59 = (state / "sse-r59-chain31340-observer")
    existing_observer = existing_r59.exists() or existing_r59.is_symlink()
    # Existing original host should never be treated as a clean candidate.
    if signer_present or existing_observer:
        raise Refused("existing chain31340 identity present; new-host workflow refused")
    missing = sorted(name for name, present in tools.items() if not present)
    # Independent observer needs pinned archive/images, configured Docker and
    # public transport; executable presence alone is insufficient proof.
    return {
        "schema": SCHEMA, "nodeId": node_id, "requestedRoles": list(roles),
        "architecture": "linux/amd64",
        "observedResources": observed,
        "initialPlanningTarget": required,
        "initialSizingAdviceMet": not gaps,
        "sizingGaps": gaps,
        "binaryExists": tools,
        "missingBinaries": missing,
        "fullClientRoleRequested": bool(set(roles) & {"full_node", "observer", "validator"}),
        "originalChain31340ArchiveVerified": False,
        "clientImageDigestsVerified": False,
        "publicPeerDirectoriesVerified": False,
        "zeroTierMembershipVerified": False,
        "dockerDaemonReadyVerified": False,
        "newIndependentValidatorKeyExists": False,
        "realOnChainValidatorDepositVerified": False,
        "beaconValidatorActiveVerified": False,
        "roleEconomicsVerifiedOnChain": False,
        "actualResourcesLeasedVerified": False,
        "eligibleToJoinConsensusOrSseMarketplaceClaimed": False,
        "hostPackagesInstalled": False,
        "containersStarted": False,
        "networkChanged": False,
        "signingKeysReadOrCreated": False,
        "action": "INVENTORY_ONLY_NOT_INSTALLED",
    }

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--node-id", required=True)
    p.add_argument("--roles", required=True,
                   help="comma-separated initial experiment roles (not permanent permissions)")
    args = p.parse_args(argv)
    try:
        print(json.dumps(inspect(args.node_id, args.roles.split(",")),
                         indent=2, sort_keys=True))
        return 0
    except (Refused, OSError, TypeError, ValueError) as exc:
        print("R143_NEW_VM_INVENTORY_REFUSED: " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
