"""R1 WP-03: finite physical-event reference semantics for selected SSE services.

Research-only: *not* an evidence verifier, clock oracle, signature verifier,
network monitor, production SLA evaluator, or replacement for SSESettlement.sol.
The events represent externally stipulated physical ground truth in a closed
simulation. An agent does not gain knowledge of the truth merely by calling it.

Version R1-SERVICE-TRACE-PROVISIONAL-0. STDLib only.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class InvalidTrace(ValueError):
    """Malformed or causally inconsistent ground-truth event trace."""


class IncompleteTrace(InvalidTrace):
    """The declared complete horizon has not reached the contractual deadlines."""


class UnsupportedService(ValueError):
    """A service category is reserved but its fulfillment predicate is not specified."""


class ServiceKind(str, Enum):
    HTTP_CHALLENGE = "http_challenge"
    DETERMINISTIC_COMPUTE = "deterministic_compute"
    OBJECT_STORAGE = "object_storage"
    OCI_CONTAINER = "oci_container"
    GENERAL_API = "general_api"


class FulfillmentMode(str, Enum):
    PROVIDER_RESULT = "provider_correct_result_generated"
    CONSUMER_DELIVERY = "consumer_correct_result_received"


class Actor(str, Enum):
    CONSUMER = "consumer"
    PROVIDER = "provider"


class EventKind(str, Enum):
    REQUEST_SENT = "request_sent"
    PROVIDER_RECEIVED = "provider_received"
    WORK_EXECUTED = "work_executed"
    RESULT_PRODUCED = "result_produced"
    RESULT_SENT = "result_sent"
    CONSUMER_RECEIVED = "consumer_received"
    ACK_SIGNED = "ack_signed"
    RESPONSE_SIGNED = "response_signed"


_ACTORS = {
    EventKind.REQUEST_SENT: Actor.CONSUMER,
    EventKind.PROVIDER_RECEIVED: Actor.PROVIDER,
    EventKind.WORK_EXECUTED: Actor.PROVIDER,
    EventKind.RESULT_PRODUCED: Actor.PROVIDER,
    EventKind.RESULT_SENT: Actor.PROVIDER,
    EventKind.CONSUMER_RECEIVED: Actor.CONSUMER,
    EventKind.ACK_SIGNED: Actor.PROVIDER,
    EventKind.RESPONSE_SIGNED: Actor.PROVIDER,
}
_ARTIFACT_EVENTS = frozenset({EventKind.WORK_EXECUTED, EventKind.RESULT_PRODUCED,
                             EventKind.RESULT_SENT, EventKind.CONSUMER_RECEIVED,
                             EventKind.RESPONSE_SIGNED})


class World(str, Enum):
    N = "N"  # no qualifying receipt by receipt deadline (not "no signed ACK")
    F = "F"  # timely receipt, no qualified fulfillment by fulfillment deadline
    S = "S"  # timely receipt and qualified fulfillment before deadline


def _nonnegative_integer(v: int, label: str) -> None:
    if type(v) is not int or v < 0:
        raise InvalidTrace(f"{label} must be a nonnegative integer logical tick")


@dataclass(frozen=True)
class ServiceConditions:
    """Contractually agreed *physical* conditions, not monitor report rules.

    Logical ticks are a simulation simplification, NOT blockchain timestamps or
    authoritative wall-clock certificates. Additional QoS/resources are *not*
    covered by this version and must have different versioned predicates.
    """
    kind: ServiceKind
    mode: FulfillmentMode
    receipt_deadline: int
    fulfillment_deadline: int
    version: str = "R1-SERVICE-TRACE-PROVISIONAL-0"

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ServiceKind) or not isinstance(self.mode, FulfillmentMode):
            raise InvalidTrace("unknown service kind or fulfillment mode")
        _nonnegative_integer(self.receipt_deadline, "receipt_deadline")
        _nonnegative_integer(self.fulfillment_deadline, "fulfillment_deadline")
        if self.receipt_deadline > self.fulfillment_deadline:
            raise InvalidTrace("receipt deadline must not exceed fulfillment deadline")
        if self.version != "R1-SERVICE-TRACE-PROVISIONAL-0":
            raise InvalidTrace("unsupported semantic version")


@dataclass(frozen=True)
class Event:
    kind: EventKind
    actor: Actor
    at: int
    artifact: str = ""
    valid_result: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EventKind) or not isinstance(self.actor, Actor):
            raise InvalidTrace("unknown actor or event kind")
        if self.actor != _ACTORS[self.kind]:
            raise InvalidTrace(f"{self.kind.value} must be attributed to {_ACTORS[self.kind].value}")
        _nonnegative_integer(self.at, "event time")
        if self.kind in _ARTIFACT_EVENTS:
            if not isinstance(self.artifact, str) or not self.artifact or len(self.artifact) > 128:
                raise InvalidTrace("artifact event requires a nonempty bounded artifact ID")
        elif self.artifact != "":
            raise InvalidTrace("request/ACK event must not specify a result artifact")
        if type(self.valid_result) is not bool:
            raise InvalidTrace("valid_result must be bool")
        if self.kind != EventKind.RESULT_PRODUCED and self.valid_result:
            raise InvalidTrace("only RESULT_PRODUCED can assert ground-truth correctness")


@dataclass(frozen=True)
class PhysicalTrace:
    """Closed-world simulation of ONE epoch, complete through `closed_through`.

    Absence in this declared complete physical trace is meaningful to the
    *simulator*, not to a remote monitor; remote evidence is merely a view.
    """
    events: tuple[Event, ...]
    closed_through: int

    def __post_init__(self) -> None:
        if not isinstance(self.events, tuple) or any(not isinstance(e, Event) for e in self.events):
            raise InvalidTrace("events must be a tuple of typed Event instances")
        _nonnegative_integer(self.closed_through, "closed_through")
        if any(e.at > self.closed_through for e in self.events):
            raise InvalidTrace("event occurs after declared complete trace horizon")
        if tuple(sorted(self.events, key=lambda e: e.at)) != self.events:
            raise InvalidTrace("events must be in nondecreasing time order")
        self._check_causality()

    def _check_causality(self) -> None:
        def exists_before(kind: EventKind, at: int, artifact: str | None = None) -> bool:
            return any(e.kind == kind and e.at <= at and (artifact is None or e.artifact == artifact)
                       for e in self.events)

        for e in self.events:
            if e.kind == EventKind.PROVIDER_RECEIVED and not exists_before(EventKind.REQUEST_SENT, e.at):
                raise InvalidTrace("provider cannot receive before request was sent")
            if e.kind in (EventKind.WORK_EXECUTED, EventKind.RESULT_PRODUCED) and not exists_before(EventKind.PROVIDER_RECEIVED, e.at):
                raise InvalidTrace("provider cannot execute/produce before physical receipt")
            # RESULT_SENT may be junk or fabricated output, and RESPONSE_SIGNED
            # may be signed without any service execution: neither proves correctness.
            if e.kind == EventKind.CONSUMER_RECEIVED and not exists_before(EventKind.RESULT_SENT, e.at, e.artifact):
                raise InvalidTrace("consumer cannot receive an artifact before it was sent")


def classify(trace: PhysicalTrace, terms: ServiceConditions) -> World:
    """Evaluate a stipulated complete trace; NEVER infer physical truth from votes.

    A qualifying receipt is timely; a late receipt may physically happen but is
    treated as N by this *versioned contractual predicate*, not as impossible.
    """
    if terms.kind not in (ServiceKind.HTTP_CHALLENGE, ServiceKind.DETERMINISTIC_COMPUTE):
        raise UnsupportedService(f"no implemented fulfillment predicate for {terms.kind.value}")
    if trace.closed_through < terms.fulfillment_deadline:
        raise IncompleteTrace("trace must cover entire fulfillment deadline")

    receipts = [e.at for e in trace.events
                if e.kind == EventKind.PROVIDER_RECEIVED and e.at <= terms.receipt_deadline]
    if not receipts:
        return World.N

    def work_before(artifact: str, after: int, until: int) -> bool:
        return any(e.kind == EventKind.WORK_EXECUTED and e.artifact == artifact
                   and after <= e.at <= until for e in trace.events)

    for produced in trace.events:
        if produced.kind != EventKind.RESULT_PRODUCED or not produced.valid_result:
            continue
        if produced.at > terms.fulfillment_deadline:
            continue
        for received_at in receipts:
            if received_at > produced.at:
                continue
            if terms.kind == ServiceKind.DETERMINISTIC_COMPUTE and not work_before(
                    produced.artifact, received_at, produced.at):
                continue
            if terms.mode == FulfillmentMode.PROVIDER_RESULT:
                return World.S
            # Consumer receipt is a distinct physical event; provider signing or
            # transmitting alone cannot satisfy this delivery-oriented contract.
            sends = [e.at for e in trace.events if e.kind == EventKind.RESULT_SENT
                     and e.artifact == produced.artifact and produced.at <= e.at <= terms.fulfillment_deadline]
            for sent_at in sends:
                if any(e.kind == EventKind.CONSUMER_RECEIVED and e.artifact == produced.artifact
                       and sent_at <= e.at <= terms.fulfillment_deadline for e in trace.events):
                    return World.S
    return World.F


@dataclass(frozen=True)
class MonitorView:
    """A network-dependent observation, not a contractual truth certificate."""
    response_observed: bool
    timeout_observed: bool
    signed_ack_seen: bool
    signed_response_seen: bool


def monitor_view(trace: PhysicalTrace, *, connected: bool, observed_through: int) -> MonitorView:
    """Toy monitor projection: even a correct service may look like a timeout.

    `connected` is an external network condition, not a Byzantine-probability
    claim. Signatures here denote seen claims; there is no crypto verification.
    """
    if type(connected) is not bool:
        raise InvalidTrace("connected must be bool")
    _nonnegative_integer(observed_through, "observed_through")
    if observed_through > trace.closed_through:
        raise IncompleteTrace("monitor cannot observe beyond simulated trace horizon")
    visible = connected
    saw = visible and any(e.kind == EventKind.RESULT_SENT and e.at <= observed_through
                          for e in trace.events)
    return MonitorView(
        response_observed=saw,
        timeout_observed=not saw,
        signed_ack_seen=visible and any(e.kind == EventKind.ACK_SIGNED and e.at <= observed_through
                                        for e in trace.events),
        signed_response_seen=visible and any(e.kind == EventKind.RESPONSE_SIGNED and e.at <= observed_through
                                             for e in trace.events),
    )
