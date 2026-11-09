"""Isolated R1 WP-03 finite trace tests; stdlib only, no live chain claims."""
import itertools
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from sse_service_trace_reference import (Actor, Event, EventKind, FulfillmentMode, IncompleteTrace,
                                         InvalidTrace, MonitorView, PhysicalTrace, ServiceConditions,
                                         ServiceKind, UnsupportedService, World, classify, monitor_view)

C, P = Actor.CONSUMER, Actor.PROVIDER
SEND = Event(EventKind.REQUEST_SENT, C, 1)
RECV = Event(EventKind.PROVIDER_RECEIVED, P, 2)


def ev(kind, at, artifact="", valid=False):
    actors = {EventKind.REQUEST_SENT: C, EventKind.CONSUMER_RECEIVED: C}
    return Event(kind, actors.get(kind, P), at, artifact, valid)


def t(*events, horizon=12):
    return PhysicalTrace(tuple(sorted(events, key=lambda e: e.at)), horizon)


def terms(kind=ServiceKind.HTTP_CHALLENGE, mode=FulfillmentMode.CONSUMER_DELIVERY,
          receipt_deadline=4, fulfillment_deadline=10):
    return ServiceConditions(kind, mode, receipt_deadline, fulfillment_deadline)


class EventOntologyTests(unittest.TestCase):
    def test_no_request_sent_is_N(self):
        self.assertEqual(classify(t(), terms()), World.N)

    def test_sent_not_received_is_N(self):
        self.assertEqual(classify(t(SEND), terms()), World.N)

    def test_received_without_result_is_F(self):
        self.assertEqual(classify(t(SEND, RECV), terms()), World.F)

    def test_valid_generated_and_delivered_on_time_is_S(self):
        trace = t(SEND, RECV, ev(EventKind.RESULT_PRODUCED, 3, "a", True),
                  ev(EventKind.RESULT_SENT, 4, "a"), ev(EventKind.CONSUMER_RECEIVED, 5, "a"))
        self.assertEqual(classify(trace, terms()), World.S)

    def test_produced_only_is_S_for_generation_contract(self):
        trace = t(SEND, RECV, ev(EventKind.RESULT_PRODUCED, 4, "a", True))
        self.assertEqual(classify(trace, terms(mode=FulfillmentMode.PROVIDER_RESULT)), World.S)
        self.assertEqual(classify(trace, terms()), World.F)

    def test_response_signed_but_not_delivered_is_F(self):
        trace = t(SEND, RECV, ev(EventKind.RESPONSE_SIGNED, 3, "a"))
        self.assertEqual(classify(trace, terms()), World.F)

    def test_ack_signed_without_receipt_still_N(self):
        trace = t(SEND, ev(EventKind.ACK_SIGNED, 2))
        self.assertEqual(classify(trace, terms()), World.N)

    def test_junk_delivered_is_not_fulfillment(self):
        trace = t(SEND, RECV, ev(EventKind.RESULT_SENT, 3, "junk"),
                  ev(EventKind.CONSUMER_RECEIVED, 4, "junk"))
        self.assertEqual(classify(trace, terms()), World.F)

    def test_invalid_result_is_F_even_when_delivered(self):
        trace = t(SEND, RECV, ev(EventKind.RESULT_PRODUCED, 3, "wrong", False),
                  ev(EventKind.RESULT_SENT, 4, "wrong"), ev(EventKind.CONSUMER_RECEIVED, 5, "wrong"))
        self.assertEqual(classify(trace, terms()), World.F)

    def test_correct_but_late_delivery_is_F(self):
        trace = t(SEND, RECV, ev(EventKind.RESULT_PRODUCED, 6, "a", True),
                  ev(EventKind.RESULT_SENT, 8, "a"), ev(EventKind.CONSUMER_RECEIVED, 11, "a"))
        self.assertEqual(classify(trace, terms()), World.F)

    def test_deadline_is_inclusive(self):
        trace = t(SEND, RECV, ev(EventKind.RESULT_PRODUCED, 7, "a", True),
                  ev(EventKind.RESULT_SENT, 8, "a"), ev(EventKind.CONSUMER_RECEIVED, 10, "a"))
        self.assertEqual(classify(trace, terms()), World.S)

    def test_late_receipt_means_no_qualifying_receipt_in_this_policy(self):
        trace = t(SEND, ev(EventKind.PROVIDER_RECEIVED, 5))
        self.assertEqual(classify(trace, terms()), World.N)

    def test_unclosed_window_is_unknown_not_failure(self):
        with self.assertRaises(IncompleteTrace):
            classify(t(SEND, RECV, horizon=5), terms())

    def test_causal_inconsistency_is_rejected(self):
        with self.assertRaises(InvalidTrace):
            t(ev(EventKind.PROVIDER_RECEIVED, 2))
        with self.assertRaises(InvalidTrace):
            t(SEND, RECV, ev(EventKind.CONSUMER_RECEIVED, 3, "a"))

    def test_bad_actor_and_invalid_truth_flag(self):
        with self.assertRaises(InvalidTrace):
            Event(EventKind.PROVIDER_RECEIVED, C, 1)
        with self.assertRaises(InvalidTrace):
            Event(EventKind.RESPONSE_SIGNED, P, 1, "a", True)

    def test_bad_timestamps_and_versions(self):
        with self.assertRaises(InvalidTrace):
            terms(receipt_deadline=11, fulfillment_deadline=10)
        with self.assertRaises(InvalidTrace):
            ServiceConditions(ServiceKind.HTTP_CHALLENGE, FulfillmentMode.CONSUMER_DELIVERY,
                              1, 10, version="UNSAFE")
        with self.assertRaises(InvalidTrace):
            Event(EventKind.REQUEST_SENT, C, True)

    def test_reserved_service_kinds_fail_closed(self):
        for kind in (ServiceKind.OBJECT_STORAGE, ServiceKind.OCI_CONTAINER, ServiceKind.GENERAL_API):
            with self.subTest(kind=kind), self.assertRaises(UnsupportedService):
                classify(t(SEND), terms(kind=kind))


class ComputeContractTests(unittest.TestCase):
    def test_valid_compute_requires_execution_event(self):
        trace = t(SEND, RECV, ev(EventKind.RESULT_PRODUCED, 4, "digest", True),
                  ev(EventKind.RESULT_SENT, 5, "digest"),
                  ev(EventKind.CONSUMER_RECEIVED, 6, "digest"))
        self.assertEqual(classify(trace, terms(kind=ServiceKind.DETERMINISTIC_COMPUTE)), World.F)
        trace2 = t(SEND, RECV, ev(EventKind.WORK_EXECUTED, 3, "digest"),
                   ev(EventKind.RESULT_PRODUCED, 4, "digest", True),
                   ev(EventKind.RESULT_SENT, 5, "digest"),
                   ev(EventKind.CONSUMER_RECEIVED, 6, "digest"))
        self.assertEqual(classify(trace2, terms(kind=ServiceKind.DETERMINISTIC_COMPUTE)), World.S)

    def test_compute_requires_correct_artifact_identity(self):
        trace = t(SEND, RECV, ev(EventKind.WORK_EXECUTED, 3, "job-A"),
                  ev(EventKind.RESULT_PRODUCED, 4, "job-B", True),
                  ev(EventKind.RESULT_SENT, 5, "job-B"),
                  ev(EventKind.CONSUMER_RECEIVED, 6, "job-B"))
        self.assertEqual(classify(trace, terms(kind=ServiceKind.DETERMINISTIC_COMPUTE)), World.F)

    def test_compute_result_after_deadline_is_F(self):
        trace = t(SEND, RECV, ev(EventKind.WORK_EXECUTED, 5, "job"),
                  ev(EventKind.RESULT_PRODUCED, 11, "job", True))
        self.assertEqual(classify(trace, terms(kind=ServiceKind.DETERMINISTIC_COMPUTE,
                                                mode=FulfillmentMode.PROVIDER_RESULT)), World.F)


class ObservationSoundnessTests(unittest.TestCase):
    def test_network_partition_makes_S_and_F_observationally_identical(self):
        s = t(SEND, RECV, ev(EventKind.RESULT_PRODUCED, 3, "a", True),
              ev(EventKind.RESULT_SENT, 4, "a"), ev(EventKind.CONSUMER_RECEIVED, 5, "a"))
        f = t(SEND, RECV)
        self.assertEqual(classify(s, terms()), World.S)
        self.assertEqual(classify(f, terms()), World.F)
        self.assertEqual(monitor_view(s, connected=False, observed_through=10),
                         monitor_view(f, connected=True, observed_through=10))
        self.assertTrue(monitor_view(s, connected=False, observed_through=10).timeout_observed)

    def test_visible_response_proves_observation_not_contractual_delivery(self):
        t1 = t(SEND, RECV, ev(EventKind.RESULT_PRODUCED, 3, "a", True), ev(EventKind.RESULT_SENT, 4, "a"))
        self.assertEqual(classify(t1, terms()), World.F)
        observed = monitor_view(t1, connected=True, observed_through=10)
        self.assertEqual(observed.response_observed, True)
        self.assertFalse(observed.timeout_observed)

    def test_signed_ACK_may_be_visible_without_physical_receipt(self):
        trace = t(SEND, ev(EventKind.ACK_SIGNED, 2))
        self.assertEqual(classify(trace, terms()), World.N)
        self.assertTrue(monitor_view(trace, connected=True, observed_through=10).signed_ack_seen)

    def test_unreachable_monitor_cannot_claim_saw_signature(self):
        trace = t(SEND, RECV, ev(EventKind.RESPONSE_SIGNED, 3, "x"))
        v = monitor_view(trace, connected=False, observed_through=10)
        self.assertFalse(v.signed_response_seen)
        self.assertTrue(v.timeout_observed)

    def test_monitor_observation_cannot_extend_future(self):
        with self.assertRaises(IncompleteTrace):
            monitor_view(t(SEND, horizon=12), connected=True, observed_through=20)

    def test_monitor_view_rejects_non_boolean_network(self):
        with self.assertRaises(InvalidTrace):
            monitor_view(t(SEND), connected=1, observed_through=10)


if __name__ == "__main__":
    unittest.main()
