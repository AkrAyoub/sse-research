"""WP09H offline research: authenticated quorum observations + honest-quorum model.

SECURITY BOUNDARY: Ed25519 signatures below authenticate response receipts,
NOT threshold-VRF shares. The unique-proof check is an injected oracle in tests:
no DKG, threshold signature aggregation, on-chain VRF verifier or honest
third-party beacon is implemented. NEVER deploy this as a randomness protocol.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from keccak import keccak256

DOMAIN = keccak256(b'SSE-WP09H-THRESHOLD-RESEARCH-v1')
RECEIPT_DOMAIN = keccak256(b'SSE-WP09H-PARTICIPATION-RECEIPT-v1')
OUTPUT_DOMAIN = keccak256(b'SSE-WP09H-UNIQUE-OUTPUT-v1')


def u256(x: int) -> bytes:
    if type(x) is not int or not 0 <= x < 2**256:
        raise ValueError('uint256 required')
    return x.to_bytes(32, 'big')


def request_digest(*, chain_id: int, pool: bytes, request_id: int,
                   requested_block: int, snapshot_root: bytes,
                   snapshot_count: int, deadline: int) -> bytes:
    if type(pool) is not bytes or len(pool) != 20 or pool == bytes(20):
        raise ValueError('20-byte nonzero pool required')
    if type(snapshot_root) is not bytes or len(snapshot_root) != 32 or snapshot_root == bytes(32):
        raise ValueError('32-byte nonzero root required')
    if chain_id <= 0 or request_id <= 0 or snapshot_count < 4:
        raise ValueError('invalid chain/request/roster')
    return keccak256(DOMAIN + u256(chain_id) + pool.rjust(32,b'\0') +
                     u256(request_id) + u256(requested_block) +
                     snapshot_root + u256(snapshot_count) + u256(deadline))


def receipt_message(digest: bytes) -> bytes:
    if type(digest) is not bytes or len(digest) != 32:
        raise ValueError('invalid request digest')
    return RECEIPT_DOMAIN + digest


class Phase(str, Enum):
    COLLECTING = 'collecting'
    READY = 'ready'
    RELEASED = 'released'
    EXPIRED = 'expired'


class InvalidRequest(ValueError):
    pass


@dataclass
class EvidenceGate:
    """Receipt threshold + unique-proof *assumption* boundary, not a VRF.

    Signatures attest to the frozen request only. A real unique threshold-VRF
    must authenticate and aggregate shares cryptographically (NOT done here).
    """
    digest: bytes
    signer_keys: Mapping[str, Ed25519PublicKey]
    threshold: int
    opened_at: int
    deadline: int
    phase: Phase = Phase.COLLECTING
    receipts: dict[str, bytes] = field(default_factory=dict)
    output_seed: int | None = None

    def __post_init__(self) -> None:
        receipt_message(self.digest)
        if not 1 <= self.threshold <= len(self.signer_keys) or self.opened_at >= self.deadline:
            raise ValueError('invalid threshold or deadline')
        if len(self.signer_keys) != len(set(self.signer_keys)):
            raise ValueError('duplicate signer IDs')

    def _time_check(self, now: int) -> None:
        if type(now) is not int or now < self.opened_at or now > self.deadline:
            raise InvalidRequest('outside response deadline')

    def submit_receipt(self, signer: str, signature: bytes, *, now: int) -> None:
        self._time_check(now)
        if self.phase not in (Phase.COLLECTING, Phase.READY):
            raise InvalidRequest('terminal request')
        if signer in self.receipts:
            raise InvalidRequest('duplicate receipt')
        if signer not in self.signer_keys:
            raise InvalidRequest('unknown signer')
        if not isinstance(signature, bytes) or len(signature) != 64:
            raise InvalidRequest('invalid signature length')
        try:
            self.signer_keys[signer].verify(signature, receipt_message(self.digest))
        except InvalidSignature as exc:
            raise InvalidRequest('wrong signature or request scope') from exc
        self.receipts[signer] = signature
        if len(self.receipts) >= self.threshold:
            self.phase = Phase.READY

    def receipt_certificate(self) -> tuple[tuple[str, bytes], ...]:
        return tuple(sorted(self.receipts.items()))

    def finalize(self, proof: bytes, *, now: int,
                 verify_unique_proof: Callable[[bytes, bytes], bool]) -> int:
        self._time_check(now)
        if self.phase != Phase.READY:
            raise InvalidRequest('signer quorum not reached')
        if not isinstance(proof, bytes) or not proof:
            raise InvalidRequest('missing unique proof')
        # The callback must be a production-audited, unique-output VRF checker
        # in any future protocol. Tests use an explicit mock, NOT a secure VRF.
        if not verify_unique_proof(self.digest, proof):
            raise InvalidRequest('invalid external unique proof')
        # Crucially: no signer ID, receipt, subset or submission order in seed.
        self.output_seed = int.from_bytes(keccak256(
            OUTPUT_DOMAIN + self.digest + keccak256(proof)), 'big')
        self.phase = Phase.RELEASED
        return self.output_seed

    def expire(self, *, now: int) -> None:
        if self.phase not in (Phase.COLLECTING, Phase.READY) or now <= self.deadline:
            raise InvalidRequest('not expirable')
        self.receipts.clear()
        self.phase = Phase.EXPIRED
        self.output_seed = None
