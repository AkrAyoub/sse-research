"""Unit tests for the V4 committee planner. SOURCE-ONLY: written 2026-11-27, not executed."""
import sys
import unittest
from fractions import Fraction
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_v4_committee_planner as p


class PlannerTest(unittest.TestCase):
    def test_quorum_matches_contract(self):
        self.assertEqual([p.quorum(n) for n in (4, 5, 6, 7, 10)], [3, 4, 5, 5, 7])

    def test_intersection_conditions_hold_for_all_valid(self):
        for b in range(1, 21):
            for n in range(3 * b + 1, 65):
                q = p.quorum(n)
                self.assertGreater(2 * q - n, b)
                self.assertLessEqual(q, n - b)
                self.assertEqual(p.validate(n, b, 0), [])

    def test_rejects_weak_configurations(self):
        self.assertTrue(p.validate(4, 2, 0))
        self.assertTrue(p.validate(3, 1, 0))
        self.assertTrue(p.validate(60, 1, 5))

    def test_prices_exact_integers(self):
        r = p.prices(4, 3, 100, 10)
        self.assertEqual((r["serviceWei"], r["monitorReportBudgetWei"], r["totalFundingWei"]), (300, 120, 420))

    def test_draw_probability_edges(self):
        self.assertEqual(p.draw_success_probability(8, 5, 6), 0)
        self.assertEqual(p.draw_success_probability(1, 1, 1), 1)
        pr = p.draw_success_probability(8, 8, 6)
        self.assertTrue(Fraction(99, 100) < pr < 1)

    def test_risk_matches_r412_example(self):
        # R417 recorded N=12, A=3, n=4: P(>1 attacker) = 13/55 (ideal model).
        self.assertEqual(p.drawn_identity_risk(12, 3, 4, 1), Fraction(13, 55))

    def test_alternatives_never_silently_weaken(self):
        r = p.plan(7, 2, 2, 20, 8, 3, 100, 10)
        self.assertFalse(r["feasibleNow"])
        for alt in r["alternatives"]:
            if alt.get("faultTolerance") is not None and alt["faultTolerance"] < 2:
                self.assertTrue(alt["weakensFaultGoal"])
                self.assertTrue(alt["requiresExplicitConsent"])
        r2 = p.plan(7, 2, 0, 20, 5, 3, 100, 10)
        weak = [a for a in r2["alternatives"] if a["action"] == "lower_fault_tolerance"]
        self.assertEqual(weak[0]["faultTolerance"], 1)
        self.assertTrue(weak[0]["requiresExplicitConsent"])


if __name__ == "__main__":
    unittest.main()
