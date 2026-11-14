"""WP09K local finite-state reference ONLY. NOT EVM execution, VRF verification,
proof of fairness, or cryptographic/liveness assurance. No external services.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class PolicyError(ValueError):
    pass


class PoolState(str, Enum):
    AWAITING = 'awaiting'
    ASSIGNED = 'assigned'
    EXPIRED = 'expired'
    RELEASED = 'released'


class EntropyState(str, Enum):
    NONE = 'none'
    REQUESTED = 'requested'
    READY = 'ready'
    APPLIED = 'applied'
    EXPIRED = 'expired'


@dataclass
class Election:
    """The adapter/settlement/pool composition for one funded lease."""
    sponsor: str = 'sponsor'
    consumer: str = 'consumer'
    provider: str = 'provider'
    coordinator: str = 'coordinator'
    global_merkle: bool = False
    requested_at: int = 100
    timeout: int = 100
    escrow: int = 25
    lease_state: str = 'offered'
    pool_state: PoolState = PoolState.AWAITING
    randomness_state: EntropyState = EntropyState.NONE
    used_request: bool = False
    charged_requests: int = 0
    monitors_copied: bool = False
    staged_seed: bool = False
    candidate_pending_locks: int = 6
    active_assignment_locks: int = 0
    consumer_refund: int = 0

    def __post_init__(self):
        if self.global_merkle:
            self.candidate_pending_locks = 0

    @property
    def deadline(self) -> int:
        return self.requested_at + self.timeout

    def _must(self, ok: bool, reason: str):
        if not ok:
            raise PolicyError(reason)

    def accept(self, actor: str):
        self._must(actor == self.provider and self.lease_state == 'offered',
                   'provider acceptance required')
        self.lease_state = 'accepted'

    def request(self, actor: str, time: int, coordinator_reverts: bool = False):
        self._must(actor == self.sponsor, 'VRF sponsor permission required')
        self._must(self.lease_state == 'accepted' and self.pool_state == PoolState.AWAITING,
                   'accepted, pending lease required')
        self._must(time < self.deadline and not self.used_request, 'no-reroll/timeout')
        # Checks/effects before interactions. Reversion of coordinator request
        # models atomic EVM transaction rollback of every write.
        self.used_request = True
        if coordinator_reverts:
            self.used_request = False
            raise PolicyError('coordinator request reverted atomically')
        self.charged_requests += 1
        self.randomness_state = EntropyState.REQUESTED

    def callback(self, actor: str, time: int, words: int = 1) -> bool:
        self._must(actor == self.coordinator, 'callback coordinator authentication')
        if self.randomness_state != EntropyState.REQUESTED or time > self.deadline or words != 1:
            return False
        self.randomness_state = EntropyState.READY
        return True

    def apply(self, time: int):
        self._must(self.lease_state == 'accepted' and not self.monitors_copied,
                   'closed or finalized lease cannot receive new assignment')
        self._must(self.pool_state == PoolState.AWAITING and
                   self.randomness_state == EntropyState.READY and
                   time <= self.deadline, 'invalid randomness state')
        self.randomness_state = EntropyState.APPLIED
        if self.global_merkle:
            self.staged_seed = True
        else:
            self.pool_state = PoolState.ASSIGNED
            self.candidate_pending_locks = 0
            self.active_assignment_locks = 4

    def finalize_global(self, time: int, valid_proofs: bool = True):
        self._must(self.global_merkle and self.lease_state == 'accepted' and
                   self.pool_state == PoolState.AWAITING and self.staged_seed and
                   time <= self.deadline and valid_proofs,
                   'cannot finalize global assignment')
        self.staged_seed = False
        self.pool_state = PoolState.ASSIGNED
        self.active_assignment_locks = 4

    def copy_committee(self):
        self._must(self.lease_state == 'accepted' and
                   self.pool_state == PoolState.ASSIGNED, 'not ready to copy committee')
        self.monitors_copied = True

    def close(self, actor: str):
        self._must(actor == self.consumer and self.lease_state != 'closed',
                   'consumer-only close')
        if not self.monitors_copied:
            # SSESettlement.closeLease -> OpenMonitorCommittee.cancelUnassigned
            if self.pool_state == PoolState.AWAITING:
                self.pool_state = PoolState.EXPIRED
                self.candidate_pending_locks = 0
                self.staged_seed = False
            elif self.pool_state == PoolState.ASSIGNED:
                self.pool_state = PoolState.RELEASED
                self.active_assignment_locks = 0
            else:
                self._must(self.pool_state == PoolState.EXPIRED,
                           'unexpected pool state for cancellation')
        self.lease_state = 'closed'
        self.consumer_refund += self.escrow
        self.escrow = 0

    def expire(self, time: int):
        self._must(time > self.deadline and self.pool_state == PoolState.AWAITING,
                   'expiry not applicable')
        self.pool_state = PoolState.EXPIRED
        self.candidate_pending_locks = 0
        self.staged_seed = False

    def expire_adapter(self, time: int):
        self._must(time > self.deadline and self.randomness_state in
                   (EntropyState.REQUESTED, EntropyState.READY),
                   'adapter expiry not applicable')
        self.randomness_state = EntropyState.EXPIRED

    def invariants(self):
        assert 0 <= self.charged_requests <= 1
        assert 0 <= self.active_assignment_locks <= 4
        assert self.candidate_pending_locks >= 0
        assert self.consumer_refund >= 0 and self.escrow >= 0
        assert self.escrow + self.consumer_refund == 25
        if not self.monitors_copied and self.lease_state == 'closed':
            assert self.pool_state in (PoolState.EXPIRED, PoolState.RELEASED)
            assert self.candidate_pending_locks == 0
            assert self.active_assignment_locks == 0
            assert not self.staged_seed
        if self.pool_state == PoolState.ASSIGNED:
            assert self.active_assignment_locks == 4
        if self.pool_state in (PoolState.EXPIRED, PoolState.RELEASED):
            assert self.candidate_pending_locks == 0
            assert self.active_assignment_locks == 0
