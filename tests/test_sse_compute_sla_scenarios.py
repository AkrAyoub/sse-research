"""Cross-module R1/R2 scenario regression; physical ground truth is simulator-only."""
import itertools
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from sse_compute_sla_scenarios import (
    Scenario, SimulatedFact, evaluate_scenario, example_scenarios,
)
from sse_evidence_policy_v1 import FactKind
from sse_service_trace_reference import ServiceConditions, ServiceKind, FulfillmentMode


class IntegratedComputeScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples = {x.name: x for x in example_scenarios()}
        cls.results = {name: evaluate_scenario(s) for name, s in cls.examples.items()}

    def test_s_not_observable_from_four_honest_timeouts(self):
        r = self.results["S_but_monitors_partitioned"]
        self.assertEqual((r["physicalGroundTruth"], r["rawMonitorTimeouts"]), ("S", 4))
        self.assertEqual(r["admissibleHistories"], ["F", "N", "S"])
        self.assertEqual((r["serviceProviderWei"], r["serviceConsumerWei"], r["serviceHeldWei"]),
                         (0, 0, 25))
        self.assertTrue(r["worldSoundInSimulation"])

    def test_four_visible_responses_do_not_prove_consumer_delivery(self):
        r = self.results["F_but_monitors_saw_response"]
        self.assertEqual(r["physicalGroundTruth"], "F")
        self.assertEqual(r["rawMonitorSuccesses"], 4)
        self.assertEqual(r["admissibleHistories"], ["F", "N", "S"])
        self.assertEqual(r["serviceHeldWei"], 25)

    def test_n_unverified_remains_unsettled_not_forced_refund(self):
        r = self.results["N_unverified"]
        self.assertEqual(r["physicalGroundTruth"], "N")
        self.assertEqual(r["serviceHeldWei"], 25)

    def test_assumed_sound_delivery_releases_provider_escrow(self):
        r = self.results["S_with_ASSUMED_sound_delivery_certificate"]
        self.assertEqual(r["admissibleHistories"], ["S"])
        self.assertEqual((r["serviceProviderWei"], r["serviceConsumerWei"],
                          r["serviceHeldWei"]), (25, 0, 0))
        self.assertTrue(r["worldSoundInSimulation"])
        self.assertFalse(r["realCertificateVerified"])
        self.assertFalse(r["safeForOnChainPayout"])

    def test_assumed_failure_and_receipt_refund_without_mixing_collateral(self):
        r = self.results["F_with_ASSUMED_receipt_and_nonfulfillment_certificates"]
        self.assertEqual(r["admissibleHistories"], ["F"])
        self.assertEqual((r["serviceProviderWei"], r["serviceConsumerWei"],
                          r["serviceHeldWei"]), (0, 25, 0))
        self.assertEqual((r["collateralConsumerWei"], r["collateralProviderWei"],
                          r["collateralHeldWei"]), (4, 2, 0))
        self.assertTrue(r["worldSoundInSimulation"])

    def test_unsound_certificate_demonstrates_false_refund_danger(self):
        r = self.results["UNSOUND_nonfulfillment_certificate_against_actual_S"]
        self.assertEqual(r["physicalGroundTruth"], "S")
        self.assertEqual(r["admissibleHistories"], ["F", "N"])
        self.assertEqual(r["serviceConsumerWei"], 25)
        self.assertFalse(r["worldSoundInSimulation"])
        self.assertFalse(r["safeForOnChainPayout"])

    def test_every_case_conserves_both_funding_pots(self):
        for name, r in self.results.items():
            with self.subTest(name=name):
                self.assertTrue(r["conservesBothFundingPots"])

    def test_monitors_and_certificates_separate_interfaces(self):
        baseline = self.examples["F_but_monitors_saw_response"]
        # Four raw "success" reports alone do not change the financial set.
        self.assertEqual(evaluate_scenario(baseline)["serviceHeldWei"], 25)
        self.assertFalse(self.results["F_but_monitors_saw_response"]["assumedCertificateKinds"])

    def test_wrong_service_and_mode_fail_before_financial_evaluation(self):
        base = self.examples["N_unverified"]
        invalid = [
            ServiceConditions(ServiceKind.OBJECT_STORAGE,
                              FulfillmentMode.CONSUMER_DELIVERY, 4, 10),
            ServiceConditions(ServiceKind.DETERMINISTIC_COMPUTE,
                              FulfillmentMode.PROVIDER_RESULT, 4, 10),
        ]
        for terms in invalid:
            with self.subTest(terms=terms), self.assertRaises(ValueError):
                Scenario("invalid", base.trace, terms, (True,))

    def test_invalid_synthetic_fact_inputs_rejected(self):
        with self.assertRaises(ValueError):
            SimulatedFact(FactKind.PHYSICAL_FULFILLMENT)
        with self.assertRaises(ValueError):
            SimulatedFact(FactKind.PHYSICAL_FULFILLMENT, 4)
        with self.assertRaises(ValueError):
            SimulatedFact("PHYSICAL_FULFILLMENT", 4, 4)

    def test_monitor_connectivity_must_be_boolean(self):
        base = self.examples["N_unverified"]
        for bad in ((), (1,), ("offline",), (True, 0)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                Scenario("invalid", base.trace, base.conditions, bad)

    def test_every_monitor_configuration_still_needs_qualified_fact(self):
        base = self.examples["S_but_monitors_partitioned"]
        for config in itertools.product((False, True), repeat=4):
            r = evaluate_scenario(Scenario(
                "all-network-views", base.trace, base.conditions, config))
            self.assertEqual(r["admissibleHistories"], ["F", "N", "S"])
            self.assertEqual(r["serviceHeldWei"], 25)


if __name__ == "__main__":
    unittest.main()
