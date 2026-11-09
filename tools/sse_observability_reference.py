"""R1 WP-04: finite epistemic observation equivalence for SSE physical traces.

Research-only model: observers see *projections* of physical executions, not the
physical truth. Every claim of soundness is relative to an explicitly listed,
possibly incomplete universe of possible executions. Not a network/crypto/clock
verifier and NEVER a production smart-contract evidence interpreter.

Dependencies: WP-02 sse_formal_reference.py and WP-03 sse_service_trace_reference.py.
This model intentionally does NOT make votes a certificate of physical failure.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable

from sse_formal_reference import (
    ALL_WORLDS, Bounds, SLA, World, Observations, evaluate, world_sound,
)
from sse_service_trace_reference import (
    MonitorView, PhysicalTrace, ServiceConditions, classify, monitor_view,
)


class InvalidUniverse(ValueError):
    """An execution universe is incomplete/malformed relative to its declared model."""


@dataclass(frozen=True)
class Observation:
    """Read-only, network-dependent report bundle; not physical ground truth.

    `client_completion_claim_seen` says that a client-side claim was observed,
    NOT that its signature, timestamp, correctness or honesty were verified.
    """
    monitors: tuple[MonitorView, ...]
    client_completion_claim_seen: bool = False

    def __post_init__(self) -> None:
        if not self.monitors or len(self.monitors) > 32 or not all(
            isinstance(m, MonitorView) for m in self.monitors
        ):
            raise InvalidUniverse("require 1..32 typed monitor observations")
        if type(self.client_completion_claim_seen) is not bool:
            raise InvalidUniverse("client claim must be an explicit bool")

    @property
    def negative_reports(self) -> int:
        return sum(int(m.timeout_observed) for m in self.monitors)

    @property
    def positive_reports(self) -> int:
        return sum(int(m.response_observed) for m in self.monitors)


@dataclass(frozen=True)
class Execution:
    """One stipulated complete physical trace and its observation channel states.

    `connected` has one bool per independent monitor. The toy WP-03 projector
    assumes each connected monitor sees any RESULT_SENT, so it is NOT a full
    asynchronous network simulator. Claim creation may be dishonest.
    """
    name: str
    trace: PhysicalTrace
    connected: tuple[bool, ...]
    observed_through: int
    client_completion_claim_seen: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name or len(self.name) > 100:
            raise InvalidUniverse("a bounded scenario identifier is required")
        if not isinstance(self.trace, PhysicalTrace):
            raise InvalidUniverse("scenario must carry a typed physical trace")
        if not isinstance(self.connected, tuple) or not 1 <= len(self.connected) <= 32 or any(
            type(c) is not bool for c in self.connected
        ):
            raise InvalidUniverse("connected must be a tuple of 1..32 bools")
        if type(self.observed_through) is not int or self.observed_through < 0:
            raise InvalidUniverse("observation horizon must be a nonnegative integer")
        if self.observed_through > self.trace.closed_through:
            raise InvalidUniverse("monitor cannot observe beyond complete physical trace")
        if type(self.client_completion_claim_seen) is not bool:
            raise InvalidUniverse("client claim must be bool")

    def projection(self) -> Observation:
        return Observation(tuple(
            monitor_view(self.trace, connected=connected, observed_through=self.observed_through)
            for connected in self.connected
        ), self.client_completion_claim_seen)

    def physical_world(self, terms: ServiceConditions) -> World:
        if self.observed_through < terms.fulfillment_deadline:
            raise InvalidUniverse("no post-deadline interpretation from pre-deadline view")
        return World(classify(self.trace, terms).value)


@dataclass(frozen=True)
class EpistemicResult:
    """Settlement bound valid only for the enumerated observational equivalence class."""
    observation: Observation
    compatible_scenarios: tuple[str, ...]
    histories: FrozenSet[World]
    allocation: Bounds


def observation_equivalence_class(actual_view: Observation,
                                  candidates: Iterable[Execution],
                                  terms: ServiceConditions, sla: SLA) -> EpistemicResult:
    """Finite possible-worlds interpretation, with exact projection matching.

    If a real execution is among `candidates`, its physical world is included.
    If not, *no global claim follows*, even if the tests happen to pass.
    Different network conditions are included by listing different Executions.
    """
    if not isinstance(actual_view, Observation):
        raise InvalidUniverse("observed evidence must be a typed Observation")
    scenarios = tuple(candidates)
    if not scenarios or any(not isinstance(c, Execution) for c in scenarios):
        raise InvalidUniverse("need a nonempty universe of typed executions")
    names = tuple(c.name for c in scenarios)
    if len(set(names)) != len(names):
        raise InvalidUniverse("scenario identifiers must be unique")
    if len({len(c.connected) for c in scenarios}) != 1:
        raise InvalidUniverse("all candidates must have the same monitor committee size")
    if len(actual_view.monitors) != len(scenarios[0].connected):
        raise InvalidUniverse("observation has the wrong monitor committee size")
    matching = tuple(c for c in scenarios if c.projection() == actual_view)
    if not matching:
        raise InvalidUniverse("the modeled universe has no execution compatible with evidence")
    worlds = frozenset(c.physical_world(terms) for c in matching)
    if not worlds or not worlds.issubset(ALL_WORLDS):
        raise AssertionError("invalid history inference")
    return EpistemicResult(actual_view, tuple(c.name for c in matching),
                           worlds, evaluate(sla, worlds))


def finite_universe_sound(executions: Iterable[Execution],
                          terms: ServiceConditions, sla: SLA) -> bool:
    """Property over *listed* executions, not a proof about arbitrary networks.

    For every execution in the closed enumeration, compute the possible worlds
    from its projection and verify that the stipulated true world is retained.
    """
    universe = tuple(executions)
    if not universe:
        raise InvalidUniverse("empty universe")
    for execution in universe:
        result = observation_equivalence_class(execution.projection(), universe, terms, sla)
        if not world_sound(execution.physical_world(terms), result.histories):
            return False
    return True


def unsafe_quorum_rule(view: Observation, quorum: int = 3) -> FrozenSet[World]:
    """Explicitly UNSAFE illustrative model of present quorum-to-failure inference.

    The actual Solidity rule also checks monitor authorization, windows, and
    response-authentication; this is a deliberately simplified comparison.
    """
    if type(quorum) is not int or not 1 <= quorum <= len(view.monitors):
        raise InvalidUniverse("quorum must be between 1 and number of monitors")
    if view.negative_reports >= quorum:
        return frozenset((World.N, World.F))
    if view.positive_reports >= quorum:
        return frozenset((World.S,))
    return ALL_WORLDS


def unsafe_receipt_rule(view: Observation, *, trust_client_claim: bool) -> FrozenSet[World]:
    """An optimistic certificate rule: safe only IF the claimed receipt entails S.

    Real guarantees would also require verifying the signer, data binding,
    application correctness, delivery by deadline, and honest/secure clock.
    """
    if type(trust_client_claim) is not bool:
        raise InvalidUniverse("trust assumption must be explicit")
    if trust_client_claim and view.client_completion_claim_seen:
        return frozenset((World.S,))
    return ALL_WORLDS


def excess_credits(allocation: Bounds, actual: Execution, terms: ServiceConditions,
                   sla: SLA) -> tuple[int, int]:
    """How much a candidate release exceeds *true* provider/consumer entitlements.

    Requires simulated ground truth and is not computable by production monitors.
    """
    e = sla.entitlement(actual.physical_world(terms))
    return (max(0, allocation.guaranteed_provider - e),
            max(0, allocation.guaranteed_consumer - (sla.fee - e)))


def projection_to_provisional_claims(view: Observation) -> Observations:
    """Translate *toy views* to the old raw-observation shape for WP-02 tests.

    The toy signatures are NOT cryptographically verified. Therefore this
    adapter MUST NOT be used as the production evidence pipeline. Its purpose
    is to show WP-02's default interpreter cannot exclude histories based only
    on claimed ACKs, claimed responses and timeout reports.
    """
    return Observations(
        provider_signed_ack=any(m.signed_ack_seen for m in view.monitors),
        provider_signed_response=any(m.signed_response_seen for m in view.monitors),
        no_response_observed=all(m.timeout_observed for m in view.monitors),
        failure_votes=view.negative_reports,
        success_votes=view.positive_reports,
    )
