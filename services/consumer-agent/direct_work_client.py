#!/usr/bin/env python3
"""Consumer-owned direct request client for already-selected SSE marketplace leases.

No direct request until a real funded lease names this consumer/provider and
an admitted epoch commits the request hash. --send signs with local owner
credential, verifies pinned chain state, and requests actual provider work.
The global dashboard never sends consumer workloads or holds wallet secrets.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "services" / "monitor-agent"))

from sse_chain_read import inspect_chain, ChainReadError
from sse_node_marketplace import RPC, _load_signer
from sse_sla_manifest import policy_hash, validate_policy
from sse_direct_delivery import (
    ExchangeError, validate_endpoint_url, submit_work_request,
)


def main(argv=None):
    p = argparse.ArgumentParser(description="SSE consumer-to-chosen-provider signed workload")
    p.add_argument("--policy", type=Path, required=True)
    p.add_argument("--endpoint", required=True, help="lease-committed Tailscale HTTPS origin")
    p.add_argument("--lease-id", type=int, required=True)
    p.add_argument("--epoch-id", type=int, required=True)
    p.add_argument("--rpc-url", help="required for --send; only trusted RPC")
    p.add_argument("--signer-file", help="required for --send; node-local 0600 secret")
    p.add_argument("--nonce", help="optional fresh 32-byte nonzero hex random nonce")
    p.add_argument("--send", action="store_true",
                   help="actually send signed request over HTTPS to chosen provider")
    args = p.parse_args(argv)
    try:
        if args.policy.stat().st_size > 8192:
            raise ValueError("SLA manifest too large")
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        validate_policy(policy)
        endpoint = validate_endpoint_url(args.endpoint)
        if args.lease_id < 1 or args.epoch_id < 0:
            raise ValueError("invalid lease or epoch")
        if not args.send:
            print(json.dumps({
                "kind": "SSE_CONSUMER_WORK_PLAN",
                "leaseId": args.lease_id, "epochId": args.epoch_id,
                "serviceKind": policy["serviceKind"],
                "slaPolicyHash": policy_hash(policy), "endpoint": endpoint,
                "requiresSignedFundedLease": True,
                "ethereumTransactionsSent": False, "providerContacted": False,
            }, indent=2, sort_keys=True))
            return 0
        if not args.rpc_url or not args.signer_file:
            raise ExchangeError("--send requires RPC and owner-only local signer file")
        nonce = args.nonce or "0x" + secrets.token_hex(32)
        rpc = RPC(args.rpc_url)
        state = inspect_chain(rpc, policy["settlement"], args.lease_id, args.epoch_id,
                              expected_chain_id=policy["chainId"],
                              endpoint=endpoint if endpoint.startswith("http://127.0.0.1:") else None,
                              pin_block_hash=True)
        owner = _load_signer(args.signer_file)
        result = submit_work_request(endpoint, state, policy, owner, nonce)
        # Avoid printing raw consumer requests or receipt signatures to terminal.
        # Durable consumer-side evidence archival is an independent R4 gate.
        print(json.dumps({
            "result": "SIGNED_CONSUMER_PROVIDER_EXCHANGE",
            "requestHash": result["request"]["message"]["requestHash"],
            "resultHash": result["response"]["message"]["resultHash"],
            "receiptAcceptedByProvider": result["receiptAcceptedByProvider"],
            "onChainSettlementSubmitted": False,
            "physicalDeadlineCertified": False,
            "consumerClockAttested": False,
        }, indent=2, sort_keys=True))
        return 0
    except (ExchangeError, ChainReadError, OSError, ValueError, TypeError) as exc:
        print("SSE_CONSUMER_WORK_FAILED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
