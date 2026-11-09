"""Human-readable SSE WP-04 finite observational-equivalence demonstration.

Execute: python tools/sse_wp04_demo.py
Uses *stipulated physical truth* solely to test evidence interpretation.
"""
from sse_formal_reference import SLA, evaluate, world_sound
from sse_service_trace_reference import (
    Actor, Event, EventKind, FulfillmentMode, PhysicalTrace, ServiceConditions,
    ServiceKind,
)
from sse_observability_reference import (
    Execution, observation_equivalence_class, unsafe_quorum_rule, excess_credits,
)


def ev(kind, at, artifact="", valid=False):
    actor = Actor.CONSUMER if kind in (EventKind.REQUEST_SENT, EventKind.CONSUMER_RECEIVED) else Actor.PROVIDER
    return Event(kind, actor, at, artifact, valid)


def execution(name, event_types, topology):
    return Execution(name, PhysicalTrace(event_types, 12), topology, 10)


def show(name, candidates, true_index=0):
    sla = SLA(25, 5)
    conditions = ServiceConditions(ServiceKind.HTTP_CHALLENGE, FulfillmentMode.CONSUMER_DELIVERY, 4, 10)
    actual = candidates[true_index]
    evidence = actual.projection()
    sound = observation_equivalence_class(evidence, candidates, conditions, sla)
    naive_histories = unsafe_quorum_rule(evidence)
    naive_money = evaluate(sla, naive_histories)
    extra_p, extra_c = excess_credits(naive_money, actual, conditions, sla)
    print(f"\n{name}")
    print(f"  ground truth in simulation: {actual.physical_world(conditions).value}")
    print(f"  monitor reports (timeouts/saw response): {evidence.negative_reports}/{evidence.positive_reports}")
    print(f"  finite matching worlds: {','.join(sorted(h.value for h in sound.histories))}")
    print(f"  cautious allocation: provider={sound.allocation.guaranteed_provider}, "
          f"consumer={sound.allocation.guaranteed_consumer}, unresolved={sound.allocation.unresolved}")
    print(f"  naive quorum worlds: {','.join(sorted(h.value for h in naive_histories))}")
    print(f"  naive excess credits against ground truth: provider={extra_p}, consumer={extra_c}")
    print(f"  naive rule world-sound?: {world_sound(actual.physical_world(conditions), naive_histories)}")


def main():
    sent = ev(EventKind.REQUEST_SENT, 1)
    recv = ev(EventKind.PROVIDER_RECEIVED, 2)
    produced = ev(EventKind.RESULT_PRODUCED, 3, "result-A", True)
    sent_result = ev(EventKind.RESULT_SENT, 4, "result-A")
    delivered = ev(EventKind.CONSUMER_RECEIVED, 5, "result-A")
    n = (sent,)
    f = (sent, recv)
    s = (sent, recv, produced, sent_result, delivered)
    undelivered = (sent, recv, produced, sent_result)
    disconnected = (False, False, False, False)
    show("All monitors partitioned: all histories possible", (
        execution("N", n, disconnected), execution("F", f, disconnected),
        execution("S", s, disconnected)), true_index=2)
    quorum_partition = (False, False, False, True)
    show("Three timeouts, one observed response: failure does not follow", (
        execution("S", s, quorum_partition),
        execution("F-undelivered", undelivered, quorum_partition)), true_index=0)
    connected = (True, True, True, True)
    show("Monitor sees result sent, but delivery is not established", (
        execution("F-undelivered", undelivered, connected),
        execution("S", s, connected)), true_index=0)


if __name__ == "__main__":
    main()
