"""WP-08D: monitor-signed provenance for a particular canonical RPC block view.

Not a light client, finality proof, trusted clock, or physical SLA certificate.
The RPC is a local trust input. Never use this to produce QualifiedFact,
on-chain votes, slashes or escrow payouts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sse_chain_read import ChainReadError, _hex_integer
from sse_evidence_wire_v1 import EvidenceError, VerificationContext

HASH = re.compile(r'0x[0-9a-f]{64}\Z')
ADDRESS = re.compile(r'0x[0-9a-fA-F]{40}\Z')
SIGNATURE = re.compile(r'0x[0-9a-fA-F]{130}\Z')
DOMAIN = 'SSEChainObservationAnchor'
VERSION = '1'
SCHEMA = 'sse-rpc-snapshot-anchor-v1'


class ProvenanceError(EvidenceError):
    """Missing, malformed or falsely attributed chain-snapshot provenance."""


class SnapshotReorganized(ProvenanceError):
    """The previously pinned block no longer belongs to the RPC's chain."""


def valid_block_hash(value: object) -> bool:
    return type(value) is str and HASH.fullmatch(value) is not None and int(value, 16) != 0


@dataclass(frozen=True)
class BlockAnchor:
    chain_id: int
    settlement: str
    lease_id: int
    epoch_id: int
    evidence_id: str
    block_number: int
    block_hash: str
    block_timestamp: int

    def __post_init__(self):
        if (type(self.chain_id) is not int or self.chain_id < 1 or
                type(self.lease_id) is not int or self.lease_id < 1 or
                type(self.epoch_id) is not int or self.epoch_id < 0 or
                type(self.block_number) is not int or self.block_number < 0 or
                type(self.block_timestamp) is not int or self.block_timestamp < 0 or
                type(self.settlement) is not str or
                ADDRESS.fullmatch(self.settlement) is None or
                self.settlement != self.settlement.lower() or
                not valid_block_hash(self.block_hash) or
                not valid_block_hash(self.evidence_id)):
            raise ProvenanceError('invalid canonical snapshot anchor')

    def fields(self) -> dict:
        return {
            'schema': SCHEMA, 'chainId': self.chain_id,
            'settlement': self.settlement, 'leaseId': self.lease_id,
            'epochId': self.epoch_id, 'evidenceId': self.evidence_id,
            'blockNumber': self.block_number, 'blockHash': self.block_hash,
            'blockTimestamp': self.block_timestamp,
        }

    @classmethod
    def parse(cls, data):
        if type(data) is not dict or set(data) != {
                'schema', 'chainId', 'settlement', 'leaseId', 'epochId',
                'evidenceId', 'blockNumber', 'blockHash', 'blockTimestamp'
                } or data.get('schema') != SCHEMA:
            raise ProvenanceError('invalid anchor schema')
        return cls(data['chainId'], data['settlement'], data['leaseId'],
                   data['epochId'], data['evidenceId'], data['blockNumber'],
                   data['blockHash'], data['blockTimestamp'])


def anchor_typed_data(anchor: BlockAnchor) -> dict:
    if not isinstance(anchor, BlockAnchor):
        raise ProvenanceError('expected validated BlockAnchor')
    return {
        'types': {
            'EIP712Domain': [
                {'name': 'name', 'type': 'string'},
                {'name': 'version', 'type': 'string'},
                {'name': 'chainId', 'type': 'uint256'},
                {'name': 'verifyingContract', 'type': 'address'},
            ],
            'SSEChainSnapshot': [
                {'name': 'leaseId', 'type': 'uint256'},
                {'name': 'epochId', 'type': 'uint256'},
                {'name': 'evidenceId', 'type': 'bytes32'},
                {'name': 'blockNumber', 'type': 'uint256'},
                {'name': 'blockHash', 'type': 'bytes32'},
                {'name': 'blockTimestamp', 'type': 'uint256'},
            ],
        },
        'primaryType': 'SSEChainSnapshot',
        'domain': {
            'name': DOMAIN, 'version': VERSION,
            'chainId': anchor.chain_id, 'verifyingContract': anchor.settlement,
        },
        'message': {
            'leaseId': anchor.lease_id, 'epochId': anchor.epoch_id,
            'evidenceId': anchor.evidence_id, 'blockNumber': anchor.block_number,
            'blockHash': anchor.block_hash, 'blockTimestamp': anchor.block_timestamp,
        },
    }


def sign_anchor(anchor: BlockAnchor, monitor_private_key: str) -> dict:
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    account = Account.from_key(monitor_private_key)
    signed = Account.sign_message(
        encode_typed_data(full_message=anchor_typed_data(anchor)),
        private_key=monitor_private_key)
    return {
        'anchor': anchor.fields(), 'signer': account.address.lower(),
        'signature': '0x' + bytes(signed.signature).hex(),
    }


def verify_anchor(envelope: object, context: VerificationContext,
                  evidence_id: str, expected_signer: str | None = None) -> BlockAnchor:
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    from eth_keys.exceptions import BadSignature
    if not isinstance(context, VerificationContext):
        raise ProvenanceError('explicit expected scope and monitor set required')
    if type(envelope) is not dict or set(envelope) != {'anchor', 'signer', 'signature'}:
        raise ProvenanceError('unexpected provenance envelope shape')
    anchor = BlockAnchor.parse(envelope['anchor'])
    if anchor.fields() != envelope['anchor']:
        raise ProvenanceError('noncanonical provenance envelope')
    scope = context.scope.normalized()
    if (anchor.chain_id != scope.chain_id or
            anchor.settlement != scope.settlement or
            anchor.lease_id != scope.lease_id or
            anchor.epoch_id != scope.epoch_id or
            anchor.evidence_id != evidence_id):
        raise ProvenanceError('anchor scope or evidence commitment mismatch')
    signer = envelope['signer']
    if (type(signer) is not str or signer != signer.lower() or
            ADDRESS.fullmatch(signer) is None or
            signer not in {x.lower() for x in context.authorized_monitors} or
            (expected_signer is not None and signer != expected_signer.lower())):
        raise ProvenanceError('anchor signer not authorized for this evidence')
    signature = envelope['signature']
    if type(signature) is not str or SIGNATURE.fullmatch(signature) is None:
        raise ProvenanceError('invalid anchor EIP-712 signature')
    try:
        recovered = Account.recover_message(
            encode_typed_data(full_message=anchor_typed_data(anchor)),
            signature=signature)
    except (ValueError, TypeError, OverflowError, BadSignature) as exc:
        raise ProvenanceError('unrecoverable anchor signature') from exc
    if recovered.lower() != signer:
        raise ProvenanceError('anchor EIP-712 signature signer mismatch')
    return anchor


def check_canonical_snapshot(rpc, anchor: BlockAnchor) -> None:
    """Validate a pinned header at a trusted RPC's CURRENT canonical view.

    This detects changed/missing blocks or inconsistent RPC replies; it cannot
    prove RPC honesty, chain finality, header consensus, or service delivery.
    """
    if not isinstance(anchor, BlockAnchor):
        raise ProvenanceError('validated anchor required')
    try:
        by_height = rpc.request('eth_getBlockByNumber', [hex(anchor.block_number), False])
        by_hash = rpc.request('eth_getBlockByHash', [anchor.block_hash, False])
        for item in (by_height, by_hash):
            if (type(item) is not dict or
                    type(item.get('hash')) is not str or
                    item['hash'].lower() != anchor.block_hash or
                    _hex_integer(item.get('number')) != anchor.block_number or
                    _hex_integer(item.get('timestamp')) != anchor.block_timestamp):
                raise SnapshotReorganized('snapshot block no longer matches canonical RPC history')
    except ChainReadError as exc:
        raise SnapshotReorganized('cannot validate anchored RPC history') from exc
