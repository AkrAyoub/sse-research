#!/usr/bin/env python3
"""Build canonical HTTP or compute SLA + resource manifests for marketplace bids.

Offline only. Outputs exact hashes to use in the consumer's on-chain
requestResource(...) and a pinned profile for winning provider selection.
Manifest generation does NOT submit the request or register any service.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from sse_resource_profile_v2 import make_profile, resource_hash, canonical_profile
from sse_sla_manifest import (proposed_policy, canonical_policy, policy_hash)
from sse_challenge import keccak256


def main(argv=None):
    p=argparse.ArgumentParser(description="SSE V1 versioned SLA/resource commitment builder")
    p.add_argument("--service-kind",required=True,choices=("http_challenge","deterministic_compute"))
    p.add_argument("--endpoint",required=True)
    p.add_argument("--chain-id",type=int,required=True)
    p.add_argument("--settlement",required=True)
    p.add_argument("--image-digest",help="compute only, immutable sha256 Docker image digest")
    p.add_argument("--cpu-milli",type=int,default=0)
    p.add_argument("--memory-bytes",type=int,default=0)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        profile=make_profile(args.service_kind,args.endpoint,
                             image_digest=args.image_digest,
                             cpu_milli=args.cpu_milli,
                             memory_bytes=args.memory_bytes)
        resource=resource_hash(profile)
        policy=proposed_policy(service_kind=args.service_kind,
                               chain_id=args.chain_id,settlement=args.settlement,
                               resource_profile_hash=resource)
        sla=policy_hash(policy)
        target=args.output_dir
        if not target.is_dir() or target.is_symlink():
            raise ValueError("output directory must exist and not be symlinked")
        if any(x.is_symlink() or x.exists() for x in (
                target/"sse-resource-profile.json",target/"sse-sla-policy.json")):
            raise ValueError("refusing to overwrite existing signed research artifacts")
        # Files are immutable once written; if the second create fails, the
        # first remains for operator inspection (no silent rewriting).
        for name, data in (
            ("sse-resource-profile.json", canonical_profile(profile)),
            ("sse-sla-policy.json", canonical_policy(policy)),
        ):
            fd=os.open(target/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,"wb") as stream:
                stream.write(data+b"\n")
        print(json.dumps({
            "resourceProfileHash":resource, "slaPolicyHash":sla,
            "serviceEndpointHash":"0x"+keccak256(args.endpoint.encode("ascii")).hex(),
            "onChainAction":"OpenResourceBoard.requestResource",
            "next":("Use these hashes with the CONSUMER-owned request CLI; then let "
                    "providers bid, consumer select/fund, monitors confirm, "
                    "and only then begin direct work exchange."),
            "submittedToBlockchain":False,
        },indent=2,sort_keys=True))
        return 0
    except (OSError,ValueError,TypeError,UnicodeError) as exc:
        print("SSE_SLA_BUILD_FAILED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
