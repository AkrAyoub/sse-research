"""Read-only WP-08C chain-derived monitor/provider authorization inspection.

Example (local Anvil):
  python tools/sse_chain_authority_cli.py \
    --rpc-url http://127.0.0.1:8545 --chain-id 31337 \
    --settlement 0x... --committee 0x... --lease-id 1 --epoch-id 0 \
    --sla-policy-hash 0x... --resource-profile-hash 0x... \
    --request-hash 0x... --settlement-code-hash 0x... \
    --committee-code-hash 0x... --block-tag latest --allow-unfinalized

WARNING: RPC itself is a TRUST ASSUMPTION. This is not an on-chain light
client, independent finality proof, physical fulfillment certificate, or
authorization for live escrow disbursement.
"""
from __future__ import annotations

import argparse
import json

from sse_chain_read import LocalRPC
from sse_evidence_wire_v1 import EvidenceScope
from sse_chain_authority_v1 import AuthoritySpec, read_chain_authority


def main() -> None:
    p = argparse.ArgumentParser(description="Inspect pinned SSE V1 chain authority")
    p.add_argument("--rpc-url", required=True, help="numeric loopback URL; e.g. http://127.0.0.1:8545")
    p.add_argument("--chain-id", type=int, required=True)
    p.add_argument("--settlement", required=True)
    p.add_argument("--committee", required=True)
    p.add_argument("--lease-id", type=int, required=True)
    p.add_argument("--epoch-id", type=int, required=True)
    p.add_argument("--sla-policy-hash", required=True)
    p.add_argument("--resource-profile-hash", required=True)
    p.add_argument("--request-hash", required=True)
    p.add_argument("--settlement-code-hash", required=True,
                   help="independently trusted keccak256(runtime bytecode)")
    p.add_argument("--committee-code-hash", required=True,
                   help="independently trusted keccak256(runtime bytecode)")
    p.add_argument("--block-tag", choices=("finalized", "safe", "latest"), default="finalized")
    p.add_argument("--allow-unfinalized", action="store_true",
                   help="explicitly allow safe/latest tags for local research only")
    args = p.parse_args()

    scope = EvidenceScope(args.chain_id, args.settlement, args.lease_id,
                          args.epoch_id, args.sla_policy_hash,
                          args.resource_profile_hash, args.request_hash)
    spec = AuthoritySpec(
        scope, args.committee, args.settlement_code_hash,
        args.committee_code_hash, args.block_tag, args.allow_unfinalized)
    snap = read_chain_authority(LocalRPC(args.rpc_url), spec)
    print(json.dumps({
        "chainReference": snap.fields(),
        "localCommitment": snap.commitment(),
        "status": "RPC_ASSUMPTION_BOUND_RAW_AUTHORITY_ONLY_NOT_PHYSICAL_FACT",
    }, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
