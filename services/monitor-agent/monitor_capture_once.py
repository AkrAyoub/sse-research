#!/usr/bin/env python3
"""Operator-approved, role-scoped chain-bound monitor evidence capture.

One-shot R4 capture on the monitor's own Ubuntu VM. Dry-run by default.
Explicit --capture verifies a pinned admitted lease, selected committee,
local multi-role conflict policy and both EIP-712 signatures, then archives
raw positive challenge bytes with monitor-signed block provenance. It NEVER
submits a Solidity vote, qualifies a negative timeout as physical failure,
releases escrow or starts Docker.

This initial adapter supports LOOPBACK provider challenge HTTP only. Cross-VM
authenticated Tailscale Serve HTTPS needs a reviewed transport extension.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools"))
sys.path.insert(0,str(ROOT/"services"/"monitor-agent"))

from sse_node_marketplace import RPC, _load_signer
from sse_node_role_policy import role_manifest,authorize_selected_monitor
from sse_chain_read import inspect_chain
from sse_sla_manifest import policy_hash, validate_policy
from sse_resource_profile_v2 import resource_hash, compare_policy, validate_profile
from sse_evidence_wire_v1 import EvidenceScope
from sse_wp08c_chain_binding import bind_capture_to_chain
from sse_http_signed_delivery_v1 import EvidenceArchive,capture_response
from typed_evidence import Domain


def _read_small(path):
    p=Path(path)
    if not p.is_absolute() or p.is_symlink() or not p.is_file() or p.stat().st_size > 8192:
        raise ValueError("expected small existing local manifest")
    return json.loads(p.read_text("utf-8"))


def main(argv=None):
    parser=argparse.ArgumentParser(description="R4 chain-bound monitor observation (no on-chain vote)")
    parser.add_argument("--node-roles-file",type=Path,required=True)
    parser.add_argument("--policy",type=Path,required=True)
    parser.add_argument("--resource-profile",type=Path,required=True)
    parser.add_argument("--endpoint",required=True)
    parser.add_argument("--lease-id",type=int,required=True)
    parser.add_argument("--epoch-id",type=int,required=True)
    parser.add_argument("--rpc-url",required=True)
    parser.add_argument("--archive",type=Path,required=True)
    parser.add_argument("--signer-file",type=Path,
                        help="required only for --capture, owner-local monitor key")
    parser.add_argument("--capture",action="store_true",
                        help="actually probe, sign and archive; never an Ethereum transaction")
    args=parser.parse_args(argv)
    try:
        node=role_manifest(_read_small(args.node_roles_file))
        profile=validate_profile(_read_small(args.resource_profile))
        policy=validate_policy(_read_small(args.policy))
        compare_policy(profile,policy)
        if "monitor" not in node["roles"]:
            raise ValueError("VM has no configured monitor role")
        if profile["endpoint"] != args.endpoint:
            raise ValueError("endpoint not the committed resource origin")
        if type(args.lease_id) is not int or args.lease_id < 1 or args.epoch_id < 0:
            raise ValueError("invalid lease or epoch index")
        if not args.endpoint.startswith("http://127.0.0.1:"):
            raise ValueError("R4 capture transport currently requires loopback HTTP; Tailscale HTTPS pending")
        if not args.capture:
            print(json.dumps({
                "kind":"SSE_MONITOR_CHAIN_BOUND_CAPTURE_PLAN",
                "nodeId":node["nodeId"],"monitor":node["wallets"]["monitor"],
                "serviceKind":policy["serviceKind"],"leaseId":args.lease_id,
                "epochId":args.epoch_id,"slaPolicyHash":policy_hash(policy),
                "resourceProfileHash":resource_hash(profile),
                "chainVerified":False,"probePerformed":False,
                "monitorVoteSubmitted":False,"physicalSlaVerified":False
            },sort_keys=True,indent=2))
            return 0
        if args.signer_file is None:
            raise ValueError("--capture requires local monitor signer file")
        monitor=_load_signer(str(args.signer_file))
        if monitor.address.lower()!=node["wallets"]["monitor"]:
            raise ValueError("node-local monitor key does not match configured monitor role")
        rpc=RPC(args.rpc_url)
        state=inspect_chain(rpc,policy["settlement"],args.lease_id,args.epoch_id,
                            expected_chain_id=policy["chainId"],pin_block_hash=True)
        authorize_selected_monitor(node,state,monitor.address)
        scope=EvidenceScope(policy["chainId"],policy["settlement"],
                            args.lease_id,args.epoch_id,policy_hash(policy),
                            resource_hash(profile),state["epoch"]["requestHash"])
        binding=bind_capture_to_chain(
            rpc,scope,args.endpoint,state["lease"]["provider"],pin_block_hash=True)
        if not args.archive.is_absolute() or args.archive.is_symlink():
            raise ValueError("archive must be an absolute ordinary file path")
        archive=EvidenceArchive(args.archive)
        signed=capture_response(
            args.endpoint,Domain(policy["chainId"],policy["settlement"]),
            state["lease"]["provider"],scope,
            "0x"+bytes(monitor.key).hex(),binding.context,archive,
            chain_binding=binding,rpc=rpc)
        print(json.dumps({
            "kind":"SSE_MONITOR_CHAIN_BOUND_CAPTURE",
            "nodeId":node["nodeId"],"evidenceId":signed.evidence_id,
            "selectedMonitor":signed.monitor,"storedNew":signed.stored_new,
            "monitorVoteSubmitted":False,"ethereumTransactionsSent":False,
            "physicalSlaVerified":False,"operatorIndependenceVerified":False,
            "chainFinalityVerified":False
        },sort_keys=True,indent=2))
        return 0
    except (ValueError,OSError,TypeError,KeyError,RuntimeError) as exc:
        print("SSE_MONITOR_CAPTURE_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
