"""WP-08E research: distinct witnesses sign the same RPC-observed block snapshot.

Evidence of independent signing-key agreement, NOT independent Ethereum
consensus verification or finalized block validity. Each witness may depend on
the same dishonest RPC. Never qualify a physical SLA fact or release escrow.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sse_wp08d_provenance import BlockAnchor, ProvenanceError, check_canonical_snapshot
from sse_evidence_wire_v1 import VerificationContext

WITNESS_SCHEMA = 'sse-external-checkpoint-witness-v1'
WITNESS_DOMAIN = 'SSEExternalCheckpointWitness'
WITNESS_VERSION = '1'
CLAIM = 'RPC_CANONICAL_OBSERVED_ONLY'
ADDRESS = re.compile(r'0x[0-9a-f]{40}\Z')
SIG = re.compile(r'0x[0-9a-fA-F]{130}\Z')


class WitnessError(ProvenanceError):
    """Checkpoint witness signature, identity, scope or quorum is invalid."""


@dataclass(frozen=True)
class WitnessPolicy:
    """Out-of-band allowlist. Key separation is checked, operator independence is NOT."""
    authorized_witnesses: frozenset[str]
    threshold: int

    def __post_init__(self):
        signers = self.authorized_witnesses
        if (type(signers) is not frozenset or
                not 2 <= len(signers) <= 16 or
                any(type(s) is not str or ADDRESS.fullmatch(s) is None or
                    int(s, 16) == 0 for s in signers) or
                type(self.threshold) is not int or
                not 2 <= self.threshold <= len(signers)):
            raise WitnessError('require 2..16 distinct canonical witness keys and quorum >= 2')


def _fields(anchor: BlockAnchor) -> dict:
    if not isinstance(anchor, BlockAnchor):
        raise WitnessError('validated BlockAnchor required')
    return {
        'schema': WITNESS_SCHEMA,
        'claim': CLAIM,
        'chainId': anchor.chain_id,
        'settlement': anchor.settlement,
        'leaseId': anchor.lease_id,
        'epochId': anchor.epoch_id,
        'evidenceId': anchor.evidence_id,
        'blockNumber': anchor.block_number,
        'blockHash': anchor.block_hash,
        'blockTimestamp': anchor.block_timestamp,
    }


def witness_typed_data(anchor: BlockAnchor) -> dict:
    """Separate EIP-712 namespace; cannot be submitted as on-chain MonitorVote."""
    return {
        'types': {
            'EIP712Domain': [
                {'name': 'name', 'type': 'string'},
                {'name': 'version', 'type': 'string'},
                {'name': 'chainId', 'type': 'uint256'},
                {'name': 'verifyingContract', 'type': 'address'},
            ],
            'SSECheckpointWitness': [
                {'name': 'leaseId', 'type': 'uint256'},
                {'name': 'epochId', 'type': 'uint256'},
                {'name': 'evidenceId', 'type': 'bytes32'},
                {'name': 'blockNumber', 'type': 'uint256'},
                {'name': 'blockHash', 'type': 'bytes32'},
                {'name': 'blockTimestamp', 'type': 'uint256'},
                {'name': 'claimKind', 'type': 'uint8'},
            ],
        },
        'primaryType': 'SSECheckpointWitness',
        'domain': {
            'name': WITNESS_DOMAIN, 'version': WITNESS_VERSION,
            'chainId': anchor.chain_id, 'verifyingContract': anchor.settlement,
        },
        'message': {
            'leaseId': anchor.lease_id, 'epochId': anchor.epoch_id,
            'evidenceId': anchor.evidence_id, 'blockNumber': anchor.block_number,
            'blockHash': anchor.block_hash, 'blockTimestamp': anchor.block_timestamp,
            'claimKind': 1,  # RPC_CANONICAL_OBSERVED_ONLY. NOT finality.
        },
    }


def sign_witness(anchor: BlockAnchor, private_key: str, rpc) -> dict:
    """Recheck CURRENT canonical view at this witness's configured RPC then sign."""
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    check_canonical_snapshot(rpc, anchor)  # refuses stale/reorged local history
    signer = Account.from_key(private_key)
    sig = Account.sign_message(
        encode_typed_data(full_message=witness_typed_data(anchor)),
        private_key=private_key,
    )
    return {
        'checkpoint': _fields(anchor),
        'signer': signer.address.lower(),
        'signature': '0x' + bytes(sig.signature).hex(),
    }


def verify_witnesses(envelopes: object, anchor: BlockAnchor,
                     context: VerificationContext, provider: str,
                     policy: WitnessPolicy) -> tuple[str, ...]:
    """Require distinct eligible EIP-712 signers all attesting EXACTLY this anchor.

    A quorum never overrides an observed reorg. Nor is witness signing proof
    of PoS finality, honest RPC, different node ownership, or service receipt.
    """
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    from eth_keys.exceptions import BadSignature
    if not isinstance(anchor, BlockAnchor) or not isinstance(context, VerificationContext):
        raise WitnessError('validated anchor and committee context required')
    if not isinstance(policy, WitnessPolicy):
        raise WitnessError('out-of-band witness policy required')
    if (type(provider) is not str or ADDRESS.fullmatch(provider.lower()) is None or
            not policy.authorized_witnesses.isdisjoint(
                {x.lower() for x in context.authorized_monitors} | {provider.lower()})):
        raise WitnessError('checkpoint witness cannot be a lease provider or selected monitor')
    s = context.scope.normalized()
    if (anchor.chain_id != s.chain_id or anchor.settlement != s.settlement or
            anchor.lease_id != s.lease_id or anchor.epoch_id != s.epoch_id):
        raise WitnessError('checkpoint does not match expected lease scope')
    if type(envelopes) not in (list, tuple) or not 1 <= len(envelopes) <= 16:
        raise WitnessError('bounded witness signatures required')
    witnessed = set()
    expected = _fields(anchor)
    typed = encode_typed_data(full_message=witness_typed_data(anchor))
    for item in envelopes:
        if type(item) is not dict or set(item) != {'checkpoint', 'signer', 'signature'}:
            raise WitnessError('wrong witness envelope fields')
        if item['checkpoint'] != expected:
            raise WitnessError('conflicting or malformed witnessed block')
        signer, sig = item['signer'], item['signature']
        if (type(signer) is not str or signer not in policy.authorized_witnesses or
                signer in witnessed or type(sig) is not str or SIG.fullmatch(sig) is None):
            raise WitnessError('duplicate, unauthorized or malformed witness signature')
        try:
            recovered = Account.recover_message(typed, signature=sig)
        except (ValueError, TypeError, OverflowError, BadSignature) as exc:
            raise WitnessError('unrecoverable witness signature') from exc
        if recovered.lower() != signer:
            raise WitnessError('witness signature attribution failed')
        witnessed.add(signer)
    if len(witnessed) < policy.threshold:
        raise WitnessError('checkpoint witness quorum not met')
    return tuple(sorted(witnessed))
