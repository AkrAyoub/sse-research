"""R1 reference-model verification: self-contained and no blockchain dependencies."""
import itertools
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from sse_formal_reference import (ALL_WORLDS, Assumptions, EvidenceRetraction,
                                  InconsistentEvidence, InvalidModel, Observations,
                                  ProgressivePosition, SLA, World, admission_permitted,
                                  evaluate, interpret, world_sound)


def subsets():
    members = tuple(World)
    return tuple(frozenset(c) for n in range(1, 4) for c in itertools.combinations(members, n))


class FormalBoundsTests(unittest.TestCase):
    def setUp(self):
        self.sla = SLA(25, 5)

    def test_all_seven_admissible_sets(self):
        expected = {
            frozenset((World.N,)): (5, 5, 20, 0),
            frozenset((World.F,)): (0, 0, 25, 0),
            frozenset((World.S,)): (25, 25, 0, 0),
            frozenset((World.N, World.F)): (0, 5, 20, 5),
            frozenset((World.N, World.S)): (5, 25, 0, 20),
            frozenset((World.F, World.S)): (0, 25, 0, 25),
            ALL_WORLDS: (0, 25, 0, 25),
        }
        self.assertEqual(len(expected), 7)
        for histories, row in expected.items():
            with self.subTest(worlds=histories):
                b = evaluate(self.sla, histories)
                self.assertEqual((b.guaranteed_provider, b.maximum_provider,
                                  b.guaranteed_consumer, b.unresolved), row)

    def test_exhaustive_safety_conservation_and_maximality(self):
        for fee in range(1, 16):
            for reservation in range(fee + 1):
                sla = SLA(fee, reservation)
                for allowed in subsets():
                    b = evaluate(sla, allowed)
                    self.assertEqual(b.guaranteed_provider + b.guaranteed_consumer + b.unresolved, fee)
                    for true_world in allowed:
                        self.assertTrue(world_sound(true_world, allowed))
                        entitlement = sla.entitlement(true_world)
                        self.assertLessEqual(b.guaranteed_provider, entitlement)
                        self.assertLessEqual(b.guaranteed_consumer, fee - entitlement)
                    self.assertEqual(b.guaranteed_provider, min(sla.entitlement(h) for h in allowed))
                    self.assertEqual(b.guaranteed_consumer, min(fee - sla.entitlement(h) for h in allowed))

    def test_every_subset_refinement_is_monotone(self):
        for parent in subsets():
            initial = ProgressivePosition.initial(self.sla)
            parent_position, _, _ = initial.refine(parent)
            for child in subsets():
                if child.issubset(parent):
                    refined, dp, dc = parent_position.refine(child)
                    self.assertGreaterEqual(dp, 0)
                    self.assertGreaterEqual(dc, 0)
                    self.assertLessEqual(refined.unresolved, parent_position.unresolved)
                    self.assertEqual(refined.provider_credited + refined.consumer_credited + refined.unresolved, 25)

    def test_randomized_amounts_avoid_float_rounding(self):
        rng = random.Random(20261109)
        for _ in range(300):
            fee = rng.randrange(1, 10 ** 19)
            reservation = rng.randrange(fee + 1)
            h = rng.choice(subsets())
            b = evaluate(SLA(fee, reservation), h)
            self.assertEqual(b.guaranteed_provider + b.guaranteed_consumer + b.unresolved, fee)

    def test_empty_and_invalid_worlds_fail_closed(self):
        with self.assertRaises(InvalidModel):
            evaluate(self.sla, frozenset())
        with self.assertRaises(InvalidModel):
            evaluate(self.sla, frozenset(("S",)))
        with self.assertRaises(InvalidModel):
            SLA(True, 0)
        with self.assertRaises(InvalidModel):
            SLA(25, 26)


class EvidenceSemanticsTests(unittest.TestCase):
    def test_three_failure_votes_and_timeout_do_not_eliminate_success(self):
        evidence = Observations(failure_votes=3, no_response_observed=True)
        self.assertEqual(interpret(evidence), ALL_WORLDS)
        self.assertTrue(world_sound(World.S, interpret(evidence)))

    def test_signature_proves_attribution_not_fulfillment(self):
        evidence = Observations(provider_signed_response=True)
        self.assertEqual(interpret(evidence), ALL_WORLDS)

    def test_ack_with_explicit_honesty_assumption_excludes_no_receipt(self):
        a = Assumptions(ack_proves_physical_receipt=True)
        self.assertEqual(interpret(Observations(provider_signed_ack=True), a),
                         frozenset((World.F, World.S)))

    def test_certified_nonfulfillment_with_assumption_yields_NF(self):
        a = Assumptions(nonfulfillment_certificate_is_sound=True)
        h = interpret(Observations(certified_nonfulfillment=True), a)
        self.assertEqual(h, frozenset((World.N, World.F)))
        self.assertEqual(evaluate(SLA(25, 5), h).guaranteed_consumer, 20)

    def test_certified_failure_plus_ack_yields_F(self):
        a = Assumptions(ack_proves_physical_receipt=True, nonfulfillment_certificate_is_sound=True)
        h = interpret(Observations(provider_signed_ack=True, certified_nonfulfillment=True), a)
        self.assertEqual(h, frozenset((World.F,)))
        self.assertEqual(evaluate(SLA(25, 5), h).guaranteed_consumer, 25)

    def test_certified_success_yields_S_only_with_soundness_assumption(self):
        e = Observations(certified_fulfillment=True)
        self.assertEqual(interpret(e), ALL_WORLDS)
        self.assertEqual(interpret(e, Assumptions(fulfillment_certificate_is_sound=True)), frozenset((World.S,)))

    def test_conflicting_qualified_certificates_fail_closed(self):
        e = Observations(certified_fulfillment=True, certified_nonfulfillment=True)
        a = Assumptions(fulfillment_certificate_is_sound=True, nonfulfillment_certificate_is_sound=True)
        with self.assertRaises(InconsistentEvidence):
            interpret(e, a)

    def test_counterexample_unsound_failure_exclusion_overrefunds_consumer(self):
        # Physical S, yet an assumed 'sound' nonfulfillment certificate is false.
        # The mathematical bounds are correct over the WRONG set: no global safety.
        h = interpret(Observations(certified_nonfulfillment=True),
                      Assumptions(nonfulfillment_certificate_is_sound=True))
        self.assertFalse(world_sound(World.S, h))
        b = evaluate(SLA(25, 5), h)
        self.assertEqual(b.guaranteed_consumer, 20)
        self.assertEqual(25 - SLA(25, 5).entitlement(World.S), 0)
        self.assertGreater(b.guaranteed_consumer, 0)

    def test_counterexample_forged_ack_excludes_actual_N(self):
        h = interpret(Observations(provider_signed_ack=True), Assumptions(ack_proves_physical_receipt=True))
        self.assertFalse(world_sound(World.N, h))

    def test_negative_reports_without_attestation_do_not_prove_nonreceipt(self):
        e = Observations(failure_votes=4, no_response_observed=True)
        self.assertIn(World.S, interpret(e))
        self.assertIn(World.N, interpret(e))

    def test_invalid_vote_counter(self):
        with self.assertRaises(InvalidModel):
            Observations(failure_votes=-1)


class ContinuationTests(unittest.TestCase):
    def test_progressive_credits_are_delta_only(self):
        p = ProgressivePosition.initial(SLA(25, 5))
        self.assertEqual((p.provider_credited, p.consumer_credited, p.unresolved), (0, 0, 25))
        p, provider_delta, consumer_delta = p.refine(frozenset((World.N, World.F)))
        self.assertEqual((provider_delta, consumer_delta), (0, 20))
        p, provider_delta, consumer_delta = p.refine(frozenset((World.F,)))
        self.assertEqual((provider_delta, consumer_delta), (0, 5))
        self.assertEqual((p.provider_credited, p.consumer_credited, p.unresolved), (0, 25, 0))

    def test_retraction_and_nonmonotone_updates_rejected(self):
        p, _, _ = ProgressivePosition.initial(SLA(25, 5)).refine(frozenset((World.N, World.F)))
        with self.assertRaises(EvidenceRetraction):
            p.refine(ALL_WORLDS)
        with self.assertRaises(EvidenceRetraction):
            p.refine(frozenset())

    def test_worst_case_budget_gate(self):
        self.assertTrue(admission_permitted(25, 25, 50))
        self.assertFalse(admission_permitted(30, 25, 50))
        self.assertTrue(admission_permitted(5, 0, 5))
        with self.assertRaises(InvalidModel):
            admission_permitted(0, -1, 25)


if __name__ == "__main__":
    unittest.main()
