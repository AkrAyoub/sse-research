"""Reproduce three counterexamples and one clock-boundary ambiguity (stdlib)."""
from __future__ import annotations

import json
from sse_formal_reference import World
from sse_async_contract_reference import (
    BoundedClockReading, EpochShadow, EpochTerms, Probe, Vote, excess_credits,
)


def new_epoch() -> EpochShadow:
    return EpochShadow(EpochTerms(25, 5, 100, 10, 5, 8))


def snapshot(ep: EpochShadow, true_world: World, scenario: str) -> dict:
    b, _, _ = ep.settle()
    return dict(
        scenario=scenario,
        simulated_true_world=true_world.value,
        contract_outcome=ep.outcome.value,
        admitted_history_set=sorted(w.value for w in ep.admissible_after_contract_filters()),
        provider_credited=b.guaranteed_provider,
        consumer_credited=b.guaranteed_consumer,
        unresolved=b.unresolved,
        excess_credit_vs_simulated_true_world=dict(zip(('provider', 'consumer'), excess_credits(ep, true_world))),
        report_authorization_and_timing_checked_by_shadow=True,
        evidence_world_sound= true_world in ep.admissible_after_contract_filters(),
        on_chain_execution_verified=False,
    )


def main() -> None:
    # Case 1: real S. Consumer received correct result at t=108, but three
    # monitor probes timed out at t=109; replies to monitors arrive at t=113.
    # Physical and signature premises are *stipulated* by this demo.
    negative = new_epoch()
    for i in range(3):
        probe = Probe(f'm{i}', sent_at=103, timeout_at=109, response_arrival=113)
        assert probe.honest_timeout
        negative.monitor_vote(110, probe.monitor, Vote.FAILURE)
    negative.seal(116)
    print(json.dumps(snapshot(negative, World.S, 'three_honest_timeouts_but_true_S'), sort_keys=True))

    # Case 2: an authenticated ACK attests a signed statement, not physical
    # receipt of a request. Here S is true, so ACK+failure quorum filters to F.
    acked = new_epoch()
    acked.acknowledgment(105, authenticated=True)
    for i in range(3):
        acked.monitor_vote(110, f'm{i}', Vote.FAILURE)
    acked.seal(116)
    print(json.dumps(snapshot(acked, World.S, 'ack_plus_failure_quorum_true_S'), sort_keys=True))

    # Case 3: provider's signature on the expected hash and 3 valid monitors
    # are present, yet consumer didn't physically receive correct output.
    positive = new_epoch()
    positive.provider_response(105, authenticated=True)
    for i in range(3):
        positive.monitor_vote(106, f'm{i}', Vote.SUCCESS)
    positive.seal(116)
    print(json.dumps(snapshot(positive, World.F, 'signed_response_and_quorum_but_true_F'), sort_keys=True))

    # Case 4: a provider response FIRST PHYSICALLY COMPLETED late under the
    # stipulated consumer-delivery SLA, but is authenticated within monitoring
    # grace and receives three success votes. Inclusion time is NOT a proof
    # of physical time; this model counterexample assumes physical lateness.
    late = new_epoch()
    late.provider_response(114, authenticated=True)
    for i in range(3):
        late.monitor_vote(115, f'm{i}', Vote.SUCCESS)
    late.seal(116)
    print(json.dumps(snapshot(late, World.F, 'physically_late_response_success_path'), sort_keys=True))

    reading = BoundedClockReading(reported_at=110, max_error=2)
    print(json.dumps(dict(scenario='clock_interval', local_timestamp=110,
                          stipulated_max_error=2, possible_actual_time=[reading.earliest, reading.latest],
                          contractual_deadline=110, verdict=reading.compare_deadline(110).value,
                          clock_bound_externally_proven=False), sort_keys=True))


if __name__ == '__main__':
    main()
