"""Local-RPC signed monitor adapter for the existing SSESettlement v1 contract.

SUCCESS requires a provider-authenticated HTTP response. FAILURE means only
that THIS MONITOR did not observe such a response by its local deadline; it is
not proof of physical non-receipt, fault, or independent clock synchronization.
This preliminary adapter is NOT the autonomous distributed R4/R5 monitor.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'services' / 'provider-agent'))

from sse_challenge import expected_response_hash, keccak256
from sse_chain_read import LocalRPC, inspect_chain
from signed_probe import signed_probe
from resource_profile import load_profile, verify_lease_profile
from typed_evidence import Domain, ZERO_HASH, signed_vote, signer_address


def observe_until_deadline(endpoint: str, domain: Domain, provider: str,
                           lease_id: int, epoch_id: int, request_hash: str,
                           response_deadline: float, interval=0.25,
                           timeout=2.0, clock=time.time, sleeper=time.sleep) -> dict:
    if interval <= 0 or timeout <= 0:
        raise ValueError('interval and timeout must be positive')
    if clock() >= response_deadline:
        raise ValueError('monitor started after deadline; absence cannot be certified')
    observations = []
    while clock() < response_deadline:
        remaining = response_deadline - clock()
        if remaining <= 0:
            break
        attempt = signed_probe(endpoint, domain, provider, lease_id, epoch_id,
                               request_hash, timeout=min(timeout, remaining))
        observations.append({k: v for k, v in attempt.items() if k != 'response'})
        if attempt['kind'] == 'SUCCESS' and clock() <= response_deadline:
            return {'outcome': 1, 'responseHash': expected_response_hash(request_hash),
                    'observations': observations, 'providerResponse': attempt['response'],
                    'lastReason': 'valid signature observed before local deadline'}
        sleeper(min(interval, max(0, response_deadline - clock())))
    if not observations:
        raise RuntimeError('no probes performed; refusing a negative observation')
    return {'outcome': 2, 'responseHash': ZERO_HASH,
            'observations': observations,
            'lastReason': 'no provider-authenticated response observed by local deadline'}


def produce_vote(rpc: LocalRPC, contract: str, endpoint: str, provider: str,
                 lease_id: int, epoch_id: int, monitor_key: str,
                 interval: float = 0.25, timeout: float = 2.0,
                 resource_manifest_path: str | None = None,
                 expected_chain_id: int = 31337) -> dict:
    # inspect_chain validates actual deployed code, domain, lease/epoch ABI, chain ID
    # and a single consistent block snapshot. The remote endpoint is separately
    # checked against both the immutable resource profile and on-chain hash.
    chain = inspect_chain(rpc, contract, lease_id, epoch_id,
                          expected_chain_id=expected_chain_id)
    lease = chain['lease']
    epoch = chain['epoch']
    if epoch is None or epoch['monitoringSealed'] or epoch['evidenceClosed']:
        raise ValueError('epoch missing, sealed, or evidence closed')
    if lease['provider'].lower() != provider.lower():
        raise ValueError('provider is not the lease provider')
    if lease['stateName'] != 'Active':
        raise ValueError('lease not active')
    if signer_address(monitor_key).lower() not in {a.lower() for a in lease['monitors']}:
        raise ValueError('signer is not one of the selected monitors')
    if lease['serviceEndpointHash'].lower() != '0x' + keccak256(endpoint.encode()).hex():
        raise ValueError('endpoint descriptor does not match lease')
    if resource_manifest_path is None:
        raise ValueError('bound resource manifest is mandatory')
    manifest = load_profile(resource_manifest_path)
    profile_hash = verify_lease_profile(manifest, lease, endpoint)
    if chain['blockTimestamp'] > epoch['monitoringClose']:
        raise ValueError('monitoring window already closed')
    admitted_at = epoch['responseDeadline'] - lease['responsePeriod']
    if not (admitted_at - 5 <= time.time() <= admitted_at + 5):
        raise RuntimeError('agent did not start near epoch admission; cannot certify absence')
    domain = Domain(expected_chain_id, contract)
    result = observe_until_deadline(endpoint, domain, provider, lease_id, epoch_id,
                                    epoch['requestHash'], epoch['responseDeadline'], interval, timeout)
    # Read a fresh chain timestamp after probing; a local wall clock alone is
    # not a chain finality or trusted timestamp proof.
    latest = rpc.request('eth_getBlockByNumber', ['latest', False])
    now_chain = int(latest['timestamp'], 16)
    if result['outcome'] == 2 and now_chain < epoch['responseDeadline']:
        raise RuntimeError('block timestamp has not reached response deadline; refuse FAILURE vote')
    if now_chain > epoch['monitoringClose']:
        raise RuntimeError('monitoring window elapsed before signing')
    return signed_vote(monitor_key, domain, lease_id, epoch_id, epoch['requestHash'],
                       result['outcome'], result['responseHash'],
                       observation={'probeCount': len(result['observations']),
                                    'lastReason': result['lastReason'],
                                    'probes': result['observations'],
                                    'localClockNotCryptographicallyProven': True,
                                    'resourceProfileHash': profile_hash},
                       provider_response=result.get('providerResponse'))


def main():
    parser = argparse.ArgumentParser(description='SSE signed observation adapter (local RPC, experimental)')
    parser.add_argument('--rpc-url', default='http://127.0.0.1:8545',
                        help='Loopback RPC only; use a trusted tunnel for external RPC')
    parser.add_argument('--expected-chain-id', type=int, default=31337)
    parser.add_argument('--contract', required=True)
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--resource-manifest', required=True)
    parser.add_argument('--provider-address', required=True)
    parser.add_argument('--lease-id', type=int, required=True)
    parser.add_argument('--epoch-id', type=int, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    key = os.getenv('SSE_MONITOR_PRIVATE_KEY')
    if not key:
        parser.error('SSE_MONITOR_PRIVATE_KEY environment variable is required (research-only keys)')
    evidence = produce_vote(LocalRPC(args.rpc_url), args.contract, args.endpoint,
                            args.provider_address, args.lease_id, args.epoch_id, key,
                            resource_manifest_path=args.resource_manifest,
                            expected_chain_id=args.expected_chain_id)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        parser.error('refusing to overwrite existing evidence')
    with output.open('x', encoding='utf-8') as f:
        json.dump(evidence, f, indent=2)
    print(f'Saved signed {"SUCCESS" if evidence["outcome"] == 1 else "FAILURE"} observation: {output}')


if __name__ == '__main__':
    main()
