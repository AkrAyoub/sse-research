"""WP-05: source-traced, NON-ON-CHAIN shadow model of one SSESettlement epoch.

This model intentionally follows the named validation branches in the checked-in
SSESettlement.sol, NOT a secure replacement for its observation policy. Its
`authenticated` inputs represent results of external cryptographic verification;
no ECDSA is performed here. No simulated physical event is inferable on chain.

Adversarial test research only. No use for authorizing monetary transfers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from sse_formal_reference import SLA, World, Bounds, evaluate


class RuleViolation(ValueError):
    """Transaction would revert under the modeled contract precondition."""


class Vote(str, Enum):
    SUCCESS = 'success'
    FAILURE = 'failure'


class Outcome(str, Enum):
    NONE = 'none'
    SUCCESS = 'success'
    FAILURE = 'failure'


def _time(value: int, label: str) -> None:
    if type(value) is not int or value < 0:
        raise RuleViolation(f'{label} must be a nonnegative integer chain timestamp')


@dataclass(frozen=True)
class EpochTerms:
    fee: int
    reservation: int
    admitted_at: int
    response_period: int
    monitoring_grace: int
    evidence_window: int
    monitors: tuple[str, ...] = ('m0', 'm1', 'm2', 'm3')

    def __post_init__(self) -> None:
        SLA(self.fee, self.reservation)
        for n, v in (('admitted_at', self.admitted_at),
                     ('response_period', self.response_period),
                     ('monitoring_grace', self.monitoring_grace),
                     ('evidence_window', self.evidence_window)):
            _time(v, n)
        if not all((self.response_period, self.monitoring_grace, self.evidence_window)):
            raise RuleViolation('contract periods must be positive')
        if len(self.monitors) != 4 or len(set(self.monitors)) != 4 or any(
                type(m) is not str or not m for m in self.monitors):
            raise RuleViolation('one confirmed four-monitor committee required')
        if self.evidence_close > (2**64 - 1):
            raise RuleViolation('contract epoch timestamps are uint64')

    @property
    def response_deadline(self) -> int:
        return self.admitted_at + self.response_period

    @property
    def monitoring_close(self) -> int:
        return self.response_deadline + self.monitoring_grace

    @property
    def evidence_close(self) -> int:
        return self.monitoring_close + self.evidence_window


@dataclass
class EpochShadow:
    """Single-epoch state after an already-confirmed committee and admission.

    The code reproduces response/monitor/evidence time gates and payout filters.
    It does NOT simulate assignment, incentives, balances across leases, ECDSA,
    transaction ordering by a real miner, or chain consensus.
    """
    terms: EpochTerms
    acknowledged: bool = False
    response_authenticated: bool = False
    votes: dict[str, Vote] = field(default_factory=dict)
    monitoring_sealed: bool = False
    evidence_closed: bool = False
    outcome: Outcome = Outcome.NONE
    provider_credited: int = 0
    consumer_credited: int = 0
    unresolved: Optional[int] = None
    settlement_calls: int = 0
    last_chain_time: Optional[int] = None

    def __post_init__(self) -> None:
        if self.unresolved is None:
            self.unresolved = self.terms.fee

    def _clock(self, chain_time: int) -> None:
        _time(chain_time, 'block.timestamp')
        if chain_time < self.terms.admitted_at:
            raise RuleViolation('transaction timestamp precedes admission')
        if self.last_chain_time is not None and chain_time < self.last_chain_time:
            raise RuleViolation('chain transaction timestamps cannot go backward')
        self.last_chain_time = chain_time

    def acknowledgment(self, chain_time: int, *, authenticated: bool) -> None:
        self._clock(chain_time)
        if chain_time > self.terms.evidence_close or self.evidence_closed:
            raise RuleViolation('acknowledgment outside evidence window')
        if self.acknowledged:
            raise RuleViolation('acknowledgment already recorded')
        if authenticated is not True:
            raise RuleViolation('provider signature must verify')
        self.acknowledged = True

    def provider_response(self, chain_time: int, *, authenticated: bool) -> None:
        self._clock(chain_time)
        if chain_time > self.terms.monitoring_close or self.monitoring_sealed:
            raise RuleViolation('provider response outside monitoring window')
        if self.response_authenticated:
            raise RuleViolation('provider response already recorded')
        if authenticated is not True:
            raise RuleViolation('provider response signature must verify')
        # Contract accepts a provider-signed expected response hash, NOT physical
        # proof of computation or delivery to the consumer.
        self.response_authenticated = True

    def monitor_vote(self, chain_time: int, monitor: str, vote: Vote,
                     *, authorized: bool = True, evidence_present: bool = True) -> None:
        self._clock(chain_time)
        if chain_time > self.terms.monitoring_close or self.monitoring_sealed:
            raise RuleViolation('vote outside monitoring window')
        if not isinstance(vote, Vote) or evidence_present is not True:
            raise RuleViolation('vote outcome/evidence hash invalid')
        if vote is Vote.FAILURE and chain_time < self.terms.response_deadline:
            raise RuleViolation('failure vote must wait until response deadline')
        if vote is Vote.SUCCESS and not self.response_authenticated:
            raise RuleViolation('success vote requires authenticated provider response')
        if authorized is not True or monitor not in self.terms.monitors:
            raise RuleViolation('monitor not selected/confirmed or signature invalid')
        if monitor in self.votes:
            raise RuleViolation('one vote per selected monitor and epoch')
        self.votes[monitor] = vote

    @property
    def success_votes(self) -> int:
        return sum(v is Vote.SUCCESS for v in self.votes.values())

    @property
    def failure_votes(self) -> int:
        return sum(v is Vote.FAILURE for v in self.votes.values())

    def seal(self, chain_time: int) -> Outcome:
        self._clock(chain_time)
        if chain_time <= self.terms.monitoring_close:
            raise RuleViolation('seal requires block.timestamp > monitoringClose')
        if self.monitoring_sealed:
            raise RuleViolation('monitoring was already sealed')
        self.monitoring_sealed = True
        if self.success_votes >= 3:
            self.outcome = Outcome.SUCCESS
        elif self.failure_votes >= 3:
            self.outcome = Outcome.FAILURE
        return self.outcome

    def admissible_after_contract_filters(self) -> frozenset[World]:
        worlds = {World.N, World.F, World.S}
        if self.acknowledged:
            worlds.intersection_update((World.F, World.S))
        if self.outcome is Outcome.SUCCESS:
            worlds.intersection_update((World.S,))
        if self.outcome is Outcome.FAILURE:
            worlds.intersection_update((World.N, World.F))
        if not worlds:
            raise RuleViolation('inconsistent evidence; empty world set')
        return frozenset(worlds)

    def settle(self) -> tuple[Bounds, int, int]:
        if not self.monitoring_sealed:
            raise RuleViolation('monitoring must be sealed to settle')
        b = evaluate(SLA(self.terms.fee, self.terms.reservation),
                     self.admissible_after_contract_filters())
        if b.guaranteed_provider < self.provider_credited or b.guaranteed_consumer < self.consumer_credited:
            raise RuleViolation('no reversal of previously credited funds')
        if b.unresolved > self.unresolved:
            raise RuleViolation('exposure cannot increase')
        dp = b.guaranteed_provider - self.provider_credited
        dc = b.guaranteed_consumer - self.consumer_credited
        self.provider_credited, self.consumer_credited, self.unresolved = (
            b.guaranteed_provider, b.guaranteed_consumer, b.unresolved)
        self.settlement_calls += 1
        return b, dp, dc

    def close_evidence(self, chain_time: int) -> Bounds:
        self._clock(chain_time)
        if chain_time <= self.terms.evidence_close or self.evidence_closed:
            raise RuleViolation('evidence window not elapsed or already closed')
        if not self.monitoring_sealed:
            self.seal(chain_time)
        b, _, _ = self.settle()
        self.evidence_closed = True
        return b


@dataclass(frozen=True)
class Probe:
    """Actual request/response transport as seen by an individual monitor.

    `response_arrival` is simulated physical arrival, None means unobserved.
    The monitor times out at `timeout_at`. A later arrival is still compatible
    with an honest timeout report. These are model facts, not attestations.
    """
    monitor: str
    sent_at: int
    timeout_at: int
    response_arrival: Optional[int] = None

    def __post_init__(self) -> None:
        _time(self.sent_at, 'probe sent_at')
        _time(self.timeout_at, 'probe timeout_at')
        if self.timeout_at < self.sent_at:
            raise RuleViolation('timeout must follow sending')
        if self.response_arrival is not None:
            _time(self.response_arrival, 'response arrival')
            if self.response_arrival < self.sent_at:
                raise RuleViolation('response cannot arrive before probe was sent')

    @property
    def honest_timeout(self) -> bool:
        return self.response_arrival is None or self.response_arrival > self.timeout_at

    @property
    def observed_response(self) -> bool:
        return not self.honest_timeout


class TimeVerdict(str, Enum):
    CERTAIN_TIMELY = 'certain_timely'
    CERTAIN_LATE = 'certain_late'
    UNKNOWN = 'unknown'


@dataclass(frozen=True)
class BoundedClockReading:
    """Interval bound on true time IF the external offset bound is valid.

    No realistic cryptographic verifier for this assumption is implemented.
    NTP-style estimated uncertainty does not prove a Byzantine-safe bound.
    """
    reported_at: int
    max_error: int

    def __post_init__(self) -> None:
        _time(self.reported_at, 'reported_at')
        _time(self.max_error, 'max_error')

    @property
    def earliest(self) -> int:
        return self.reported_at - self.max_error

    @property
    def latest(self) -> int:
        return self.reported_at + self.max_error

    def compare_deadline(self, deadline: int) -> TimeVerdict:
        _time(deadline, 'deadline')
        if self.latest <= deadline:
            return TimeVerdict.CERTAIN_TIMELY
        if self.earliest > deadline:
            return TimeVerdict.CERTAIN_LATE
        return TimeVerdict.UNKNOWN


def excess_credits(epoch: EpochShadow, true_world: World) -> tuple[int, int]:
    """Diagnostic only: simulator supplies a stipulated true physical outcome."""
    sla = SLA(epoch.terms.fee, epoch.terms.reservation)
    rightful_provider = sla.entitlement(true_world)
    rightful_consumer = sla.fee - rightful_provider
    return (max(0, epoch.provider_credited - rightful_provider),
            max(0, epoch.consumer_credited - rightful_consumer))
