"""Local-only CLI to capture provider-signed HTTP replies as WP08 signed raw evidence.

By default the authorization set is operator-supplied. With --rpc-url, WP08C
reads the admitted lease and selected committee from trusted loopback Anvil.
Neither mode submits Solidity votes or proves physical service delivery.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'services' / 'monitor-agent'))

from sse_evidence_wire_v1 import EvidenceScope, VerificationContext
from sse_http_signed_delivery_v1 import EvidenceArchive, capture_response
from typed_evidence import Domain


def main() -> None:
    p = argparse.ArgumentParser(description='Capture WP08B signed provider and monitor evidence')
    p.add_argument('--endpoint', required=True, help='loopback-only HTTP root with explicit port')
    p.add_argument('--chain-id', required=True, type=int)
    p.add_argument('--settlement', required=True)
    p.add_argument('--lease-id', required=True, type=int)
    p.add_argument('--epoch-id', required=True, type=int)
    p.add_argument('--sla-policy-hash', required=True)
    p.add_argument('--resource-profile-hash', required=True)
    p.add_argument('--request-hash', required=True)
    p.add_argument('--provider', required=True)
    p.add_argument('--rpc-url', help='opt-in chain binding via trusted loopback RPC; no implicit fallback')
    p.add_argument('--archive', required=True, help='SQLite file in an existing directory')
    p.add_argument('--timeout', type=float, default=2.0)
    args = p.parse_args()
    monitor_key = os.getenv('SSE_WP08B_MONITOR_KEY')
    if not monitor_key:
        p.error('set SSE_WP08B_MONITOR_KEY (testing key only)')
    from eth_account import Account
    monitor = Account.from_key(monitor_key).address.lower()
    scope = EvidenceScope(args.chain_id, args.settlement, args.lease_id, args.epoch_id,
                          args.sla_policy_hash, args.resource_profile_hash, args.request_hash)
    if args.rpc_url:
        from sse_chain_read import LocalRPC
        from sse_wp08c_chain_binding import bind_capture_to_chain
        bound = bind_capture_to_chain(LocalRPC(args.rpc_url), scope, args.endpoint, args.provider)
        context = bound.context
        provider = bound.provider
    else:
        context = VerificationContext(scope, frozenset({monitor}))
        provider = args.provider
    saved = capture_response(args.endpoint, Domain(args.chain_id, args.settlement),
                             provider, scope, monitor_key, context,
                             EvidenceArchive(args.archive), timeout=args.timeout)
    print(f'RAW observation captured: {saved.evidence_id} (new={saved.stored_new})')
    if args.rpc_url:
        print(f'Chain-bound context read at block {bound.block_number}; trusted RPC, not finality proof.')
    else:
        print('WARNING: authorization remains operator-supplied; use --rpc-url for chain binding.')
    print('Signed provider/monitor records verified; physical consumer delivery NOT proven.')


if __name__ == '__main__':
    main()
