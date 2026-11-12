"""Read-only WP13 V2 chain/committee authority inspection against local RPC.

The provided runtime code fingerprints MUST come from a separately trusted
deployment manifest, not merely from the very RPC being verified. On Anvil,
'latest --allow-unfinalized' is useful for functional testing, NOT finality.
"""
from __future__ import annotations

import argparse
import json

from sse_chain_read import LocalRPC
from sse_evidence_wire_v1 import EvidenceScope
from sse_v2_chain_authority_v1 import V2AuthoritySpec, read_v2_authority


def main() -> None:
    p = argparse.ArgumentParser(description="Inspect V2 lease and monitor authority at one RPC block hash")
    p.add_argument("--rpc-url", default="http://127.0.0.1:8545",
                   help="numeric loopback RPC; no remote RPC accepted by this CLI")
    p.add_argument("--chain-id", type=int, required=True)
    p.add_argument("--controller", required=True)
    p.add_argument("--pool", required=True)
    p.add_argument("--lease-id", type=int, required=True)
    p.add_argument("--epoch-id", type=int, required=True)
    p.add_argument("--sla-policy-hash", required=True)
    p.add_argument("--resource-profile-hash", required=True)
    p.add_argument("--request-hash", required=True)
    p.add_argument("--service-root", required=True, help="e.g. http://127.0.0.1:8899")
    p.add_argument("--controller-code-hash", required=True,
                   help="Keccak256(runtime code) from trusted deployment manifest")
    p.add_argument("--pool-code-hash", required=True,
                   help="Keccak256(runtime code) from trusted deployment manifest")
    p.add_argument("--block-tag", choices=("finalized", "safe", "latest"),
                   default="finalized")
    p.add_argument("--allow-unfinalized", action="store_true",
                   help="opt in to 'safe' or 'latest' for local Anvil testing")
    args = p.parse_args()

    scope = EvidenceScope(
        args.chain_id, args.controller, args.lease_id, args.epoch_id,
        args.sla_policy_hash, args.resource_profile_hash, args.request_hash)
    spec = V2AuthoritySpec(
        scope, args.pool, args.service_root, args.controller_code_hash,
        args.pool_code_hash, args.block_tag, args.allow_unfinalized)
    snapshot = read_v2_authority(LocalRPC(args.rpc_url), spec)
    print(json.dumps({
        "authority": snapshot.fields(), "referenceCommitment": snapshot.commitment(),
        "status": "RPC_ASSUMPTION_BOUND_RAW_OBSERVATION_AUTHORIZATION",
        "payoutAuthorized": False, "consumerDeliveryProven": False,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
