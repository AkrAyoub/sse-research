"""WP-09G offline model: deterministic, bounded batched global-election recovery.

Research-only reference for an optional OpenMonitorCommittee extension.  This
module does NOT cryptographically verify RSA-VRF proofs or onchain Merkle paths.
It models ordered address proof validation, provisional bond locks and expiry.
No external RPC, no GitHub, no paid compute service.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from keccak import keccak256

DRAW_LIMIT = 40
BATCH_LIMIT = 8
SEATS = 4
TIMEOUT = 3600
MAX_ACTIVE = 1 << 20


def u256(value: int) -> bytes:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < (1 << 256):
        raise ValueError('uint256 expected')
    return value.to_bytes(32, 'big')


def global_draw(seed: int, request_id: int, n: int, cap: int = DRAW_LIMIT) -> list[int]:
    """Same sparse Fisher-Yates index permutation as WP09E, extended to cap=40."""
    if not 4 <= n <= MAX_ACTIVE or not 1 <= cap <= DRAW_LIMIT or request_id <= 0:
        raise ValueError('invalid roster, cap or request')
    u256(seed)
    u256(request_id)
    swaps: dict[int, int] = {}
    results: list[int] = []
    for i in range(min(n, cap)):
        j = i + int.from_bytes(keccak256(u256(seed) + u256(request_id) + u256(i)), 'big') % (n - i)
        chosen = swaps.get(j, j)
        swapped = swaps.get(i, i)
        swaps[j] = swapped
        results.append(chosen)
    return results


def dense_reference(seed: int, request_id: int, n: int, cap: int = DRAW_LIMIT) -> list[int]:
    """Independent full-length shuffle reference, only used for local regression."""
    u256(seed)
    roster = list(range(n))
    for i in range(min(n, cap)):
        j = i + int.from_bytes(keccak256(u256(seed) + u256(request_id) + u256(i)), 'big') % (n - i)
        roster[i], roster[j] = roster[j], roster[i]
    return roster[:min(n, cap)]


class Status(str, Enum):
    AWAITING_SEED = 'awaiting_seed'
    AWAITING_PROOFS = 'awaiting_proofs'
    ASSIGNED = 'assigned'
    EXPIRED = 'expired'


class ElectionError(ValueError):
    pass


@dataclass
class Election:
    snapshot: tuple[str, ...]
    request_id: int
    consumer: str
    provider: str
    requested_at: int = 0
    timeout_seconds: int = TIMEOUT
    status: Status = Status.AWAITING_SEED
    seed: int | None = None
    _draw_indexes: list[int] | None = field(default=None, repr=False)
    proof_cursor: int = 0
    committee: list[str] = field(default_factory=list)
    standbys: list[str] = field(default_factory=list)
    active: set[str] = field(default_factory=set)
    locked: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.snapshot) < SEATS or len(self.snapshot) > MAX_ACTIVE:
            raise ValueError('invalid registry size')
        if len(set(self.snapshot)) != len(self.snapshot):
            raise ValueError('duplicate active address')
        if self.request_id < 1 or self.timeout_seconds < 1:
            raise ValueError('invalid request or timeout')
        self.active = set(self.snapshot)
        self.locked = dict.fromkeys(self.snapshot, 0)
        if len(self.active - {self.consumer, self.provider}) < SEATS:
            raise ElectionError('insufficient monitor identities')

    @property
    def indexes(self) -> list[int]:
        if self.seed is None:
            raise ElectionError('entropy not available')
        if self._draw_indexes is None:
            self._draw_indexes = global_draw(self.seed, self.request_id, len(self.snapshot))
        return self._draw_indexes

    @property
    def remaining(self) -> int:
        return len(self.indexes) - self.proof_cursor

    def fulfill_entropy(self, seed: int, *, verified: bool, now: int) -> None:
        self._check_time(now)
        if self.status != Status.AWAITING_SEED:
            raise ElectionError('already fulfilled, expired or assigned')
        if not verified:
            raise ElectionError('proof must be validated by the selected on-chain entropy mode')
        u256(seed)
        self.seed = seed
        self._draw_indexes = None
        self.status = Status.AWAITING_PROOFS

    def _check_time(self, now: int) -> None:
        if now < self.requested_at or now > self.requested_at + self.timeout_seconds:
            raise ElectionError('outside bounded assignment deadline')

    def withdraw(self, account: str) -> None:
        if account not in self.active:
            raise ElectionError('already exited or not enrolled')
        if self.locked.get(account, 0) != 0:
            raise ElectionError('selected or provisional bond is locked')
        self.active.remove(account)

    def batch(self, provided: Sequence[tuple[int, str]], *, now: int) -> Status:
        """Checks all and only the next indexes, atomically; then reserves seats.

        Each (index,address) stands in for an actual Merkle inclusion proof,
        which the proposed Solidity integration additionally checks against
        frozen globalSnapshotRoot. The model assumes that cryptographic proof.
        """
        self._check_time(now)
        if self.status != Status.AWAITING_PROOFS:
            raise ElectionError('no pending seed')
        if not 1 <= len(provided) <= BATCH_LIMIT or len(provided) > self.remaining:
            raise ElectionError('batch exceeds proof boundary')
        expected = self.indexes[self.proof_cursor:self.proof_cursor + len(provided)]
        # Validate the whole batch before any mutation. In Solidity, a revert
        # achieves the same atomicity if any proof does not match.
        if any(index != sampled_index or address != self.snapshot[index]
               for (index, address), sampled_index in zip(provided, expected)):
            raise ElectionError('out-of-order, forged or omitted proof')
        for index, account in provided:
            if account in (self.consumer, self.provider) or account not in self.active:
                continue
            if len(self.committee) < SEATS:
                self.committee.append(account)
                self.locked[account] += 1
            else:
                self.standbys.append(account)
        self.proof_cursor += len(provided)
        if self.remaining == 0:
            if len(self.committee) == SEATS:
                self.status = Status.ASSIGNED
            else:
                self._fail_closed()
        return self.status

    def expire(self, *, now: int) -> None:
        if now <= self.requested_at + self.timeout_seconds:
            raise ElectionError('too early to expire')
        if self.status not in (Status.AWAITING_SEED, Status.AWAITING_PROOFS):
            raise ElectionError('assignment already terminal')
        self._fail_closed()

    def _fail_closed(self) -> None:
        for account in self.committee:
            if self.locked[account] <= 0:
                raise AssertionError('bad provisional lock accounting')
            self.locked[account] -= 1
        self.committee.clear()
        self.standbys.clear()
        self.seed = None
        self.status = Status.EXPIRED


def complete_attempt(election: Election, *, seed: int, exited: set[str],
                     time_per_batch: int = 10) -> Status:
    """Run an offline ideal signer, independent true membership proofs.

    The signer always publishes. Selective withholding is explicitly NOT
    mitigated by this liveness strategy.
    """
    election.fulfill_entropy(seed, verified=True, now=election.requested_at)
    for account in exited:
        election.withdraw(account)
    cursor = 0
    while election.status == Status.AWAITING_PROOFS:
        positions = election.indexes[cursor:cursor + BATCH_LIMIT]
        proofs = [(i, election.snapshot[i]) for i in positions]
        election.batch(proofs, now=election.requested_at + time_per_batch * (cursor // BATCH_LIMIT + 1))
        cursor += len(proofs)
    return election.status
