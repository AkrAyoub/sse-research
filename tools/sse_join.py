#!/usr/bin/env python3
"""SSE unified role-selection and onboarding planner for a FRESH Ubuntu host.

Single source repository, single entry point. This version implements safe
selection, read-only host inventory and a nonmutating native EL/CL installer
preflight. It DOES NOT silently install packages, fund roles, deploy contracts,
generate a validator key or claim economic/consensus activation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import sse_pos_r143_new_vm_readiness as readiness
import sse_pos_r137_independent_observer_create_once as observer

CHOICES = (
    ("full_node", "Verify the complete chain using Besu + Lighthouse"),
    ("observer", "Nonsigning full blockchain verification / audit"),
    ("validator", "Locally keyed staking validator (deposit required)"),
    ("provider", "Serve real leased compute/resources"),
    ("consumer", "Buy real resources under funded SLA/escrow"),
    ("monitor", "Bond and independently probe selected leases"),
)
ROLE_NAMES = {r for r, _ in CHOICES}
FULL = {"full_node", "observer", "validator"}
STATE = {
    "full_node": "R137_NON_SIGNING_EL_CL_INSTALLER_REQUIRES_LOCAL_AUTHORIZATION_AND_PINNED_ARTIFACTS",
    "observer": "R137_NON_SIGNING_EL_CL_INSTALLER_REQUIRES_LOCAL_AUTHORIZATION_AND_PINNED_ARTIFACTS",
    "validator": "NOT_IMPLEMENTED_IN_UNIFIED_INSTALLER_FRESH_BLS_DEPOSIT_AND_ACTIVATION_REQUIRED",
    "provider": "NOT_IMPLEMENTED_IN_UNIFIED_INSTALLER_LIVE_RESOURCE_SERVICE_AND_ONCHAIN_BID_REQUIRED",
    "consumer": "NOT_IMPLEMENTED_IN_UNIFIED_INSTALLER_WALLET_ESCROW_AND_REAL_REQUEST_REQUIRED",
    "monitor": "NOT_IMPLEMENTED_IN_UNIFIED_INSTALLER_BOND_SELECTION_AND_INDEPENDENCE_REQUIRED",
}

class Refused(ValueError):
    pass

def choose(input_fn=input, output=print):
    output("SSE chain31340 — select all roles for this host.")
    output("These are preferences, NOT network permissions or activated roles.")
    for i, (role, description) in enumerate(CHOICES, 1):
        output(f"  {i}. {role}: {description}")
    raw = input_fn("Role numbers separated by commas (example 1,3,6): ")
    if type(raw) is not str:
        raise Refused("invalid role input")
    indices = [i.strip() for i in raw.split(",")]
    if not indices or any(not i.isdigit() or not 1 <= int(i) <= len(CHOICES)
                          for i in indices):
        raise Refused("invalid selected role number")
    selected = [CHOICES[int(i)-1][0] for i in indices]
    if len(set(selected)) != len(selected):
        raise Refused("duplicate role selection")
    return selected

def normalize_roles(roles):
    if type(roles) is not list or not roles or any(
            type(role) is not str or role not in ROLE_NAMES for role in roles):
        raise Refused("invalid roles; choose from listed public roles")
    if len(roles) != len(set(roles)):
        raise Refused("duplicate roles")
    # Validator requires consensus infrastructure. We automatically ADD the
    # full_node install dependency; this does not grant staking eligibility.
    selected = list(roles)
    dependencies = []
    if "validator" in selected and not FULL.intersection(selected - {"validator"}):
        selected.insert(0, "full_node")
        dependencies.append("validator_requires_local_full_node_consensus_clients")
    return selected, dependencies

def plan(node_id, roles, inventory=readiness.inspect):
    roles, dependencies = normalize_roles(roles)
    machine = inventory(node_id, roles)
    return {
        "schema": "SSE_UNIFIED_JOIN_PLAN_V1",
        "network": "chain31340_original_genesis",
        "nodeId": node_id,
        "selectedRoles": roles,
        "automaticallyIncludedDependencies": dependencies,
        "localHostInventory": machine,
        "components": {role: STATE[role] for role in roles},
        "requiresOwnerAuthorizationForInstall": True,
        "rolesActivatedByThisPlan": [],
        "operatorOrValidatorIndependenceCertified": False,
        "packagesInstalled": False,
        "networkJoined": False,
        "nativeClientsStarted": False,
        "walletsOrValidatorKeysGenerated": False,
        "transactionsBroadcast": False,
        "allSelectedRolesInstalled": False,
        "canProceedToFullNodePreflight": bool(set(roles) & FULL)
            and machine["initialSizingAdviceMet"]
            and not machine["missingBinaries"],
        "next": (
            "VERIFY_PUBLIC_CHAIN_ARCHIVE_DOCKER_IMAGES_OVERLAY_AND_PEER_HINTS_THEN_RUN_R137_PLAN"
            if set(roles) & FULL else
            "APPLICATION_RUNTIME_INSTALLER_NOT_YET_INTEGRATED_REQUIRE_REAL_CONTRACTS_AND_KEYS"
        ),
    }

def main(argv=None, *, inventory=readiness.inspect, input_fn=input, output=print):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--node-id", required=True, help="local unique host label")
    p.add_argument("--roles", help="comma-separated roles; omit for interactive menu")
    p.add_argument("--plan", action="store_true", help="show nonmutating readiness and role plan")
    p.add_argument("--observer-plan", action="store_true",
                   help="invoke existing R137 read-only Besu+Lighthouse preflight")
    p.add_argument("--manifest", type=Path,
                   help="operator-owned R136 signed-off manifest for observer plan")
    p.add_argument("--archive", type=Path,
                   help="exact verified original public chain archive")
    p.add_argument("--discovery-source", action="append",
                   help="repeatable existing public HTTPS peer hint URL")
    args = p.parse_args(argv)
    try:
        selected = args.roles.split(",") if args.roles is not None else choose(input_fn, output)
        selected, _ = normalize_roles(selected)
        if args.observer_plan:
            if not set(selected) & FULL:
                raise Refused("full node/observer role required for native EL/CL plan")
            if not args.manifest or not args.archive or not args.discovery_source:
                raise Refused("R137 plan requires manifest, archive, and public directories")
            if len(args.discovery_source) < 2:
                raise Refused("at least two independently published peer-hint URLs needed")
            # Delegates to existing reviewed R137 plan. Never delegates to apply.
            other = [
                "--plan", "--manifest", str(args.manifest),
                "--archive", str(args.archive),
            ]
            for url in args.discovery_source:
                other += ["--discovery-source", url]
            return observer.main(other)
        if args.manifest or args.archive or args.discovery_source:
            raise Refused("manifest/archive/discovery flags valid only for --observer-plan")
        result = plan(args.node_id, selected, inventory)
        output(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (Refused, readiness.Refused, ValueError, TypeError, OSError) as exc:
        print("SSE_UNIFIED_JOIN_REFUSED: " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
