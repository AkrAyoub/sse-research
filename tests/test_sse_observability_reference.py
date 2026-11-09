"""WP-04 finite observational indistinguishability and financial-safety tests.

A simulator knows physical history; a remote monitor gets only a projection.
"""
import itertools
import random
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

from sse_formal_reference import ALL_WORLDS, SLA, World, evaluate, interpret, world_sound
from sse_service_trace_reference import (
    Actor, Event, EventKind, FulfillmentMode, PhysicalTrace,
    ServiceConditions, ServiceKind,
)
from sse_observability_reference import (
    Execution, InvalidUniverse, Observation, observation_equivalence_class,
    finite_universe_sound, unsafe_quorum_rule, unsafe_receipt_rule, excess_credits,
    projection_to_provisional_claims,
)

C, P = Actor.CONSUMER, Actor.PROVIDER
REQUEST = Event(EventKind.REQUEST_SENT, C, 1)
RECEIVE = Event(EventKind.PROVIDER_RECEIVED, P, 2)


def ev(kind, t, artifact='', correct=False):
    return Event(kind, C if kind == EventKind.CONSUMER_RECEIVED else P, t, artifact, correct)


def trace(*events, horizon=12):
    return PhysicalTrace(tuple(sorted(events, key=lambda e: e.at)), horizon)


def terms(kind=ServiceKind.HTTP_CHALLENGE, mode=FulfillmentMode.CONSUMER_DELIVERY):
    return ServiceConditions(kind, mode, receipt_deadline=4, fulfillment_deadline=10)


def worlds():
    return {
        'N': trace(REQUEST),
        'F_silent': trace(REQUEST, RECEIVE),
        'F_invalid': trace(REQUEST, RECEIVE,
                           ev(EventKind.RESULT_PRODUCED, 3, 'r', False),
                           ev(EventKind.RESULT_SENT, 4, 'r'),
                           ev(EventKind.CONSUMER_RECEIVED, 5, 'r')),
        'F_undelivered': trace(REQUEST, RECEIVE,
                               ev(EventKind.RESULT_PRODUCED, 3, 'r', True),
                               ev(EventKind.RESULT_SENT, 4, 'r')),
        'S': trace(REQUEST, RECEIVE,
                   ev(EventKind.RESULT_PRODUCED, 3, 'r', True),
                   ev(EventKind.RESULT_SENT, 4, 'r'),
                   ev(EventKind.CONSUMER_RECEIVED, 5, 'r')),
        'N_ack': trace(REQUEST, ev(EventKind.ACK_SIGNED, 2)),
        'F_ack': trace(REQUEST, RECEIVE, ev(EventKind.ACK_SIGNED, 3)),
        'F_compute': trace(REQUEST, RECEIVE,
                            ev(EventKind.RESULT_PRODUCED, 4, 'digest', True),
                            ev(EventKind.RESULT_SENT, 5, 'digest'),
                            ev(EventKind.CONSUMER_RECEIVED, 6, 'digest')),
        'S_compute': trace(REQUEST, RECEIVE,
                            ev(EventKind.WORK_EXECUTED, 3, 'digest'),
                            ev(EventKind.RESULT_PRODUCED, 4, 'digest', True),
                            ev(EventKind.RESULT_SENT, 5, 'digest'),
                            ev(EventKind.CONSUMER_RECEIVED, 6, 'digest')),
    }


def scenario(name, connected=(True, True, True, True), claim=False):
    return Execution(name, worlds()[name], connected, observed_through=10,
                     client_completion_claim_seen=claim)


class ObservationalEquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.sla = SLA(25, 5)
        self.terms = terms()

    def test_partitions_make_all_three_worlds_identical(self):
        d = (False, False, False, False)
        universe = tuple(scenario(n, d) for n in ('N', 'F_silent', 'S'))
        obs = universe[2].projection()
        self.assertEqual(obs.negative_reports, 4)
        self.assertEqual(obs.positive_reports, 0)
        answer = observation_equivalence_class(obs, universe, self.terms, self.sla)
        self.assertEqual(answer.histories, ALL_WORLDS)
        self.assertEqual((answer.allocation.guaranteed_provider,
                          answer.allocation.guaranteed_consumer,
                          answer.allocation.unresolved), (0, 0, 25))
        self.assertEqual(len(answer.compatible_scenarios), 3)

    def test_failed_and_successful_services_same_observation(self):
        universe = (scenario('F_silent', (False,) * 4), scenario('S', (False,) * 4))
        self.assertEqual(universe[0].projection(), universe[1].projection())
        b = observation_equivalence_class(universe[0].projection(), universe, self.terms, self.sla)
        self.assertEqual(b.histories, frozenset((World.F, World.S)))
        self.assertEqual(b.allocation.unresolved, 25)

    def test_response_seen_does_not_prove_correctness(self):
        universe = (scenario('F_invalid'), scenario('S'))
        self.assertEqual(universe[0].projection(), universe[1].projection())
        answer = observation_equivalence_class(universe[0].projection(), universe, self.terms, self.sla)
        self.assertEqual(answer.histories, frozenset((World.F, World.S)))
        self.assertEqual(answer.allocation.guaranteed_provider, 0)

    def test_response_seen_does_not_prove_consumer_delivery(self):
        universe = (scenario('F_undelivered'), scenario('S'))
        self.assertEqual(universe[0].projection(), universe[1].projection())
        answer = observation_equivalence_class(universe[0].projection(), universe, self.terms, self.sla)
        self.assertEqual(answer.histories, frozenset((World.F, World.S)))

    def test_same_wire_evidence_different_financial_entitlements(self):
        f, s = scenario('F_undelivered'), scenario('S')
        self.assertEqual(f.projection(), s.projection())
        self.assertEqual(self.sla.entitlement(f.physical_world(self.terms)), 0)
        self.assertEqual(self.sla.entitlement(s.physical_world(self.terms)), 25)

    def test_signed_ack_is_not_receipt(self):
        n, f = scenario('N_ack'), scenario('F_ack')
        self.assertEqual(n.projection(), f.projection())
        answer = observation_equivalence_class(n.projection(), (n, f), self.terms, self.sla)
        self.assertEqual(answer.histories, frozenset((World.N, World.F)))
        self.assertEqual(answer.allocation.guaranteed_consumer, 20)
        self.assertEqual(answer.allocation.unresolved, 5)

    def test_success_with_three_monitor_timeouts(self):
        # Three isolated monitors and one honest observer of RESULT_SENT.
        e = scenario('S', (False, False, False, True))
        view = e.projection()
        self.assertEqual((view.negative_reports, view.positive_reports), (3, 1))
        unsafe = unsafe_quorum_rule(view)
        self.assertNotIn(World.S, unsafe)
        self.assertEqual(excess_credits(evaluate(self.sla, unsafe), e, self.terms,
                                       self.sla), (0, 20))

    def test_all_monitors_see_invalid_response_and_false_success(self):
        e = scenario('F_invalid')
        view = e.projection()
        self.assertEqual(view.positive_reports, 4)
        unsafe = unsafe_quorum_rule(view)
        self.assertEqual(unsafe, frozenset((World.S,)))
        self.assertEqual(excess_credits(evaluate(self.sla, unsafe), e, self.terms,
                                       self.sla), (25, 0))

    def test_monitor_quorum_is_not_cryptographic_certificate(self):
        bad = scenario('S', (False, False, False, True))
        good = scenario('F_invalid', (False, False, False, True))
        self.assertEqual(bad.projection(), good.projection())
        answer = observation_equivalence_class(bad.projection(), (bad, good), self.terms, self.sla)
        self.assertEqual(answer.histories, frozenset((World.F, World.S)))
        self.assertTrue(world_sound(bad.physical_world(self.terms), answer.histories))

    def test_compute_has_an_extra_unobservable_execution_requirement(self):
        comp = terms(kind=ServiceKind.DETERMINISTIC_COMPUTE)
        f, s = scenario('F_compute'), scenario('S_compute')
        self.assertEqual(f.projection(), s.projection())
        answer = observation_equivalence_class(f.projection(), (f, s), comp, self.sla)
        self.assertEqual(answer.histories, frozenset((World.F, World.S)))

    def test_full_enumerated_universe_is_sound_for_own_observations(self):
        entries = []
        variants = ((False,)*4, (True,)*4, (False,False,False,True))
        for name, topology in itertools.product(('N', 'F_silent', 'F_invalid',
                                                  'F_undelivered', 'S', 'N_ack', 'F_ack'), variants):
            entries.append(scenario(name, topology))
        # Distinct IDs are required, so name by network variant as well.
        entries = [Execution(e.name+str(i), e.trace, e.connected, e.observed_through,
                             e.client_completion_claim_seen) for i,e in enumerate(entries)]
        self.assertTrue(finite_universe_sound(entries, self.terms, self.sla))

    def test_missing_possible_execution_can_falsify_global_safety(self):
        actual_f = scenario('F_undelivered')
        incomplete_model = (scenario('S'),)
        answer = observation_equivalence_class(actual_f.projection(), incomplete_model,
                                               self.terms, self.sla)
        self.assertEqual(answer.histories, frozenset((World.S,)))
        self.assertFalse(world_sound(actual_f.physical_world(self.terms), answer.histories))
        self.assertEqual(excess_credits(answer.allocation, actual_f,
                                       self.terms, self.sla), (25, 0))

    def test_observation_set_can_change_when_network_changes(self):
        success = scenario('S')
        isolated = scenario('S', (False,) * 4)
        self.assertNotEqual(success.projection(), isolated.projection())

    def test_valid_observation_must_match_some_scenario(self):
        data = (scenario('S'),)
        with self.assertRaises(InvalidUniverse):
            observation_equivalence_class(scenario('N').projection(), data,
                                          self.terms, self.sla)

    def test_duplicate_universe_identifiers_rejected(self):
        with self.assertRaises(InvalidUniverse):
            observation_equivalence_class(scenario('S').projection(),
                                          (scenario('S'), scenario('S')),
                                          self.terms, self.sla)

    def test_mismatched_monitor_counts_rejected(self):
        two = scenario('S', (True, True))
        four = scenario('S')
        with self.assertRaises(InvalidUniverse):
            observation_equivalence_class(four.projection(), (two,), self.terms, self.sla)
        with self.assertRaises(InvalidUniverse):
            observation_equivalence_class(four.projection(), (two, four), self.terms, self.sla)

    def test_observation_before_deadline_rejected_for_world_classification(self):
        e = Execution('early', worlds()['S'], (True,) * 4, observed_through=5)
        with self.assertRaises(InvalidUniverse):
            observation_equivalence_class(e.projection(), (e,), self.terms, self.sla)

    def test_observation_horizon_beyond_trace_rejected(self):
        with self.assertRaises(InvalidUniverse):
            Execution('bad', worlds()['S'], (True,) * 4, observed_through=20)

    def test_invalid_network_and_claim_types_rejected(self):
        with self.assertRaises(InvalidUniverse):
            Execution('bad', worlds()['S'], (True, 1), observed_through=10)
        with self.assertRaises(InvalidUniverse):
            Execution('bad', worlds()['S'], (True,), observed_through=10,
                      client_completion_claim_seen=1)
        with self.assertRaises(InvalidUniverse):
            Observation(())

    def test_wp02_default_interpreter_keeps_all_worlds_for_monitor_votes(self):
        for name, topology in itertools.product(
            ('N_ack', 'F_silent', 'F_undelivered', 'S'),
            ((False,) * 4, (True,) * 4, (False, False, False, True))):
            view = scenario(name, topology).projection()
            claims = projection_to_provisional_claims(view)
            self.assertEqual(interpret(claims), ALL_WORLDS)

    def test_wp02_claim_mapping_counts_only_observed_signatures(self):
        view = scenario('N_ack', (False, True, True, False)).projection()
        claims = projection_to_provisional_claims(view)
        self.assertTrue(claims.provider_signed_ack)
        self.assertEqual(claims.failure_votes, 4)
        self.assertEqual(claims.success_votes, 0)

    def test_wp02_quorum_observation_is_not_certified_nonfulfillment(self):
        view = scenario('S', (False, False, False, True)).projection()
        claims = projection_to_provisional_claims(view)
        self.assertEqual(claims.failure_votes, 3)
        self.assertFalse(claims.certified_nonfulfillment)
        self.assertIn(World.S, interpret(claims))

    def test_no_universe_never_infers_all_or_success(self):
        with self.assertRaises(InvalidUniverse):
            observation_equivalence_class(scenario('S').projection(), (), self.terms, self.sla)


class ConditionalCertificateTests(unittest.TestCase):
    def setUp(self):
        self.terms = terms()
        self.sla = SLA(25, 5)

    def test_untrusted_client_claim_does_not_exclude_any_world(self):
        e = scenario('F_undelivered', claim=True)
        self.assertEqual(unsafe_receipt_rule(e.projection(), trust_client_claim=False), ALL_WORLDS)

    def test_assuming_sound_receipt_can_identify_success_in_restricted_universe(self):
        e = scenario('S', claim=True)
        c = unsafe_receipt_rule(e.projection(), trust_client_claim=True)
        self.assertEqual(c, frozenset((World.S,)))
        self.assertTrue(world_sound(e.physical_world(self.terms), c))

    def test_forged_or_untruthful_receipt_disproves_unconditional_soundness(self):
        e = scenario('F_undelivered', claim=True)
        c = unsafe_receipt_rule(e.projection(), trust_client_claim=True)
        self.assertFalse(world_sound(e.physical_world(self.terms), c))
        self.assertEqual(excess_credits(evaluate(self.sla, c), e, self.terms, self.sla), (25, 0))

    def test_even_claimed_receipt_does_not_prove_correct_compute_execution(self):
        comp_terms = terms(kind=ServiceKind.DETERMINISTIC_COMPUTE)
        e = scenario('F_compute', claim=True)
        c = unsafe_receipt_rule(e.projection(), trust_client_claim=True)
        self.assertNotIn(e.physical_world(comp_terms), c)

    def test_no_receipt_claim_does_not_imply_failure(self):
        e = scenario('S', claim=False)
        c = unsafe_receipt_rule(e.projection(), trust_client_claim=True)
        self.assertEqual(c, ALL_WORLDS)

    def test_bad_quorum_and_trust_parameter_rejected(self):
        e = scenario('S')
        with self.assertRaises(InvalidUniverse):
            unsafe_quorum_rule(e.projection(), quorum=0)
        with self.assertRaises(InvalidUniverse):
            unsafe_quorum_rule(e.projection(), quorum=5)
        with self.assertRaises(InvalidUniverse):
            unsafe_receipt_rule(e.projection(), trust_client_claim=1)

    def test_extreme_integer_fee_and_full_uncertainty_conserve(self):
        rng = random.Random(20261109)
        d = (False,) * 4
        universe = (scenario('N', d), scenario('F_silent', d), scenario('S', d))
        for _ in range(150):
            fee = rng.randrange(1, 2**128)
            reservation = rng.randrange(fee+1)
            b = observation_equivalence_class(universe[0].projection(), universe,
                                              self.terms, SLA(fee, reservation)).allocation
            self.assertEqual(b.guaranteed_provider+b.guaranteed_consumer+b.unresolved,fee)
            self.assertEqual(b.unresolved,fee)


if __name__ == '__main__':
    unittest.main()
