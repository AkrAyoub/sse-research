"""Integrated R1/R2 compute-delivery scenario lab (NOT a payout verifier).

Bridges stipulated physical trace -> unauthenticated simulated monitor views ->
explicitly *assumed*, externally supplied physical facts -> admissible histories
-> service escrow and hypothetical collateral bounds.

Never turn a scenario's physical ground truth into a real SLA certificate. The
diagnostic "worldSound" is available in simulation only, not in deployment.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from sse_service_trace_reference import (
    Actor, Event, EventKind, FulfillmentMode, PhysicalTrace, ServiceConditions,
    ServiceKind, classify, monitor_view,
)
from sse_evidence_policy_v1 import (
    Assumption, Binding, FactKind, PhysicalPolicyState, PolicyManifest,
    PolicyMode, QualifiedFact, RawKind, RawObservation, TimeInterval,
)
from sse_formal_reference import SLA, World
from sse_sla_economy_reference import HypotheticalProviderCollateral, allocate

# These are deterministic RESEARCH scope IDs, not on-chain addresses or proofs.
DEMO_BINDING = Binding(1, 0, "0x" + "a" * 64)
FACT_ASSUMPTION = {
    FactKind.PHYSICAL_RECEIPT: Assumption.RECEIPT_CERT_SOUND,
    FactKind.PHYSICAL_FULFILLMENT: Assumption.FULFILLMENT_CERT_SOUND,
    FactKind.PHYSICAL_NONFULFILLMENT: Assumption.NONFULFILLMENT_CERT_SOUND,
}


@dataclass(frozen=True)
class SimulatedFact:
    """An externally stipulated certificate assumption, NEVER independently verified."""
    kind: FactKind
    event_lower: Optional[int] = None
    event_upper: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, FactKind):
            raise ValueError("unknown assumed certificate")
        if (self.event_lower is None) != (self.event_upper is None):
            raise ValueError("require both interval bounds or neither")
        if self.kind == FactKind.PHYSICAL_FULFILLMENT and self.event_lower is None:
            raise ValueError("success assertion needs a stated time interval")


@dataclass(frozen=True)
class Scenario:
    name: str
    trace: PhysicalTrace
    conditions: ServiceConditions
    connected_monitors: tuple[bool, ...]
    assumed_facts: tuple[SimulatedFact, ...] = ()
    epoch_fee_wei: int = 25
    reservation_fee_wei: int = 0
    collateral: HypotheticalProviderCollateral = HypotheticalProviderCollateral()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("scenario must have a name")
        if self.conditions.kind != ServiceKind.DETERMINISTIC_COMPUTE or (
            self.conditions.mode != FulfillmentMode.CONSUMER_DELIVERY
        ):
            raise ValueError("this experiment ONLY models compute consumer delivery")
        if not self.connected_monitors or any(
            type(x) is not bool for x in self.connected_monitors
        ):
            raise ValueError("monitor connectivity requires explicit booleans")
        if any(not isinstance(x, SimulatedFact) for x in self.assumed_facts):
            raise ValueError("invalid assumed certificate")


def evaluate_scenario(scenario: Scenario) -> dict:
    """Model observation ambiguity; do NOT authorize any actual transfers."""
    if not isinstance(scenario, Scenario):
        raise ValueError("invalid scenario")
    physical = World(classify(scenario.trace, scenario.conditions).value)
    assumed = frozenset(FACT_ASSUMPTION[x.kind] for x in scenario.assumed_facts)
    manifest = PolicyManifest(
        DEMO_BINDING, PolicyMode.PHYSICAL_DELIVERY,
        admission_time=0, deadline=scenario.conditions.fulfillment_deadline,
        assumptions=assumed,
    )
    state = PhysicalPolicyState(manifest,
                                SLA(scenario.epoch_fee_wei, scenario.reservation_fee_wei))
    successes = 0
    timeouts = 0
    for i, connected in enumerate(scenario.connected_monitors):
        observation = monitor_view(
            scenario.trace, connected=connected,
            observed_through=scenario.conditions.fulfillment_deadline,
        )
        if observation.response_observed:
            successes += 1
            kind = RawKind.MONITOR_SUCCESS
        else:
            timeouts += 1
            kind = RawKind.MONITOR_TIMEOUT
        # This is a synthesized raw report, not an EIP-712-verified signature.
        state = state.with_raw(RawObservation(
            DEMO_BINDING, "raw-" + str(i), kind, "sim-monitor-" + str(i)
        ))

    for i, certificate in enumerate(scenario.assumed_facts):
        time = (TimeInterval(certificate.event_lower, certificate.event_upper)
                if certificate.event_lower is not None else None)
        state = state.with_fact(
            QualifiedFact(
                DEMO_BINDING, "synthetic-assumption-" + str(i),
                certificate.kind, FACT_ASSUMPTION[certificate.kind],
                "SIMULATOR_ORACLE_NOT_A_VERIFIER", time
            ),
            observed_at=scenario.conditions.fulfillment_deadline + 1,
        )
    decision = state.decision()
    pot = allocate(state.sla, decision.histories, scenario.collateral)
    return {
        "scenario": scenario.name,
        "physicalGroundTruth": physical.value,
        "rawMonitorSuccesses": successes,
        "rawMonitorTimeouts": timeouts,
        "assumedCertificateKinds": [x.kind.value for x in scenario.assumed_facts],
        "admissibleHistories": sorted(x.value for x in decision.histories),
        "worldSoundInSimulation": physical in decision.histories,
        "serviceProviderWei": pot.service_provider_wei,
        "serviceConsumerWei": pot.service_consumer_wei,
        "serviceHeldWei": pot.service_held_wei,
        "collateralConsumerWei": pot.collateral_consumer_wei,
        "collateralProviderWei": pot.collateral_provider_wei,
        "collateralHeldWei": pot.collateral_held_wei,
        "conservesBothFundingPots": pot.conserves(
            state.sla.fee, scenario.collateral.deposit_wei
        ),
        "realCertificateVerified": False,
        "safeForOnChainPayout": False,
    }


def example_scenarios() -> tuple[Scenario, ...]:
    """Different physical worlds can produce indistinguishable monitor reports."""
    c, p, k = Actor.CONSUMER, Actor.PROVIDER, EventKind
    terms = ServiceConditions(ServiceKind.DETERMINISTIC_COMPUTE,
                              FulfillmentMode.CONSUMER_DELIVERY, 4, 10)
    request = Event(k.REQUEST_SENT, c, 1)
    receive = Event(k.PROVIDER_RECEIVED, p, 2)
    work = Event(k.WORK_EXECUTED, p, 3, "job")
    output = Event(k.RESULT_PRODUCED, p, 4, "job", True)
    send = Event(k.RESULT_SENT, p, 5, "job")
    consumer_delivery = Event(k.CONSUMER_RECEIVED, c, 6, "job")
    success = PhysicalTrace((request, receive, work, output, send, consumer_delivery), 12)
    undelivered = PhysicalTrace((request, receive, work, output, send), 12)
    not_received = PhysicalTrace((request,), 12)
    bond = HypotheticalProviderCollateral(6, 4)
    return (
        Scenario("S_but_monitors_partitioned", success, terms, (False,) * 4),
        Scenario("F_but_monitors_saw_response", undelivered, terms, (True,) * 4),
        Scenario("N_unverified", not_received, terms, (False,) * 4),
        Scenario("S_with_ASSUMED_sound_delivery_certificate", success, terms,
                 (True,) * 4,
                 (SimulatedFact(FactKind.PHYSICAL_FULFILLMENT, 6, 6),)),
        Scenario("F_with_ASSUMED_receipt_and_nonfulfillment_certificates",
                 undelivered, terms, (True,) * 4,
                 (SimulatedFact(FactKind.PHYSICAL_RECEIPT),
                  SimulatedFact(FactKind.PHYSICAL_NONFULFILLMENT)), collateral=bond),
        Scenario("UNSOUND_nonfulfillment_certificate_against_actual_S",
                 success, terms, (False,) * 4,
                 (SimulatedFact(FactKind.PHYSICAL_NONFULFILLMENT),), collateral=bond),
    )


def main() -> None:
    print(json.dumps(
        {
            "notice": "SIMULATION ONLY; no real certificate verifier or on-chain payout authority",
            "cases": [evaluate_scenario(x) for x in example_scenarios()],
        },
        sort_keys=True, indent=2,
    ))


if __name__ == "__main__":
    main()
