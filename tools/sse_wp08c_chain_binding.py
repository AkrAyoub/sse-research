"""WP-08C: read-only binding of raw HTTP evidence capture to an SSE V1 lease.

Reads one contract state snapshot using sse_chain_read.inspect_chain, then
derives expected provider and selected monitor keys. Never signs an on-chain
vote, qualifies a physical fact, or releases escrow. The local RPC and its
reported chain are still trusted; this is NOT an independent finality proof.
"""
from __future__ import annotations

from dataclasses import dataclass

from sse_chain_read import ChainReadError, inspect_chain, ZERO_ADDR
from sse_challenge import expected_response_hash
from sse_evidence_wire_v1 import EvidenceScope, VerificationContext


class ChainBindingError(ChainReadError):
    """Contract context is missing, mismatched, or unsafe for new capture."""


@dataclass(frozen=True)
class ChainCaptureBinding:
    context: VerificationContext
    provider: str
    block_number: int
    block_timestamp: int


def bind_capture_to_chain(rpc, scope: EvidenceScope, endpoint: str,
                          expected_provider: str) -> ChainCaptureBinding:
    """Derive capture authorization from a read-only, same-block chain view.

    The caller MUST supply a trusted LocalRPC. A dishonest RPC can fabricate
    its replies; this function does not prove chain finality, off-chain
    delivery, timestamp accuracy, or independence of monitor operators.

    Strictly requires an already admitted, active epoch and all four V1
    selected monitors confirmed. A direct lease with zero SLA-policy hash
    cannot pass, because there is no policy commitment to authenticate.
    """
    if not isinstance(scope, EvidenceScope):
        raise ChainBindingError('canonical EvidenceScope required')
    if type(endpoint) is not str or not endpoint:
        raise ChainBindingError('nonempty endpoint required')
    if type(expected_provider) is not str:
        raise ChainBindingError('expected provider address required')

    s = scope.normalized()
    snapshot = inspect_chain(
        rpc, s.settlement, s.lease_id, s.epoch_id,
        expected_chain_id=s.chain_id, endpoint=endpoint,
    )
    if (type(snapshot) is not dict or
            snapshot.get('schema') != 'sse-onchain-inspection-v1' or
            snapshot.get('status') != 'EPOCH_FOUND' or
            snapshot.get('readOnly') is not True or
            snapshot.get('domainSeparatorMatches') is not True or
            snapshot.get('endpointCommitmentChecked') is not True):
        raise ChainBindingError('chain inspection did not establish a bound admitted epoch')

    if (type(snapshot.get('chainId')) is not int or snapshot['chainId'] != s.chain_id or
            type(snapshot.get('leaseId')) is not int or snapshot['leaseId'] != s.lease_id or
            type(snapshot.get('epochId')) is not int or snapshot['epochId'] != s.epoch_id or
            type(snapshot.get('settlementAddress')) is not str or
            snapshot['settlementAddress'].lower() != s.settlement):
        raise ChainBindingError('chain/contract/lease/epoch mismatch')

    lease = snapshot.get('lease')
    epoch = snapshot.get('epoch')
    if type(lease) is not dict or type(epoch) is not dict:
        raise ChainBindingError('missing on-chain lease or epoch')
    if lease.get('stateName') != 'Active' or epoch.get('exists') is not True:
        raise ChainBindingError('lease and epoch must currently be active')

    if (type(lease.get('provider')) is not str or
            lease['provider'].lower() != expected_provider.lower() or
            type(lease.get('consumer')) is not str):
        raise ChainBindingError('provider or consumer does not match on-chain lease')
    if (lease.get('slaPolicyHash') != s.sla_policy_hash or
            lease.get('resourceProfileHash') != s.resource_profile_hash or
            epoch.get('requestHash') != s.request_hash or
            epoch.get('responseHash') != expected_response_hash(s.request_hash)):
        raise ChainBindingError('SLA/resource/request/response commitment mismatch')

    if (type(snapshot.get('blockNumber')) is not int or snapshot['blockNumber'] < 0 or
            type(snapshot.get('blockTimestamp')) is not int or snapshot['blockTimestamp'] < 0 or
            type(epoch.get('monitoringClose')) is not int or
            snapshot['blockTimestamp'] > epoch['monitoringClose'] or
            epoch.get('monitoringSealed') is not False or
            epoch.get('evidenceClosed') is not False):
        raise ChainBindingError('monitoring window already ended or epoch was sealed')

    monitors = lease.get('monitors')
    if type(monitors) is not list or len(monitors) != 4 or lease.get('monitorConfirmations') != 4:
        raise ChainBindingError('four selected and confirmed monitors required')
    from sse_chain_read import ADDR
    if any(type(m) is not str or not ADDR.fullmatch(m) or m.lower() == ZERO_ADDR
           for m in monitors):
        raise ChainBindingError('invalid selected monitor address')
    allowed = frozenset(m.lower() for m in monitors)
    if (len(allowed) != 4 or lease['consumer'].lower() in allowed or
            lease['provider'].lower() in allowed):
        raise ChainBindingError('committee includes duplicate or counterparty')

    return ChainCaptureBinding(VerificationContext(s, allowed),
                               lease['provider'].lower(),
                               snapshot['blockNumber'], snapshot['blockTimestamp'])
