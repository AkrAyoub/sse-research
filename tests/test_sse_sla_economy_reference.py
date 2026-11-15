"""Research-only economy invariants. No chain, key, or SLA-fact verification."""
from __future__ import annotations

import itertools
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from sse_formal_reference import SLA, World
from sse_sla_economy_reference import (
    EconomyDraftError, HypotheticalProviderCollateral, allocate, funding_plan,
)

WORLDS = frozenset(World)


def subsets():
    seq = list(World)
    for size in range(1, 4):
        for members in itertools.combinations(seq, size):
            yield frozenset(members)


class ComputeDeliveryEconomyTests(unittest.TestCase):
    def test_zero_reservation_compute_delivery_is_not_legacy_five_wei(self):
        terms = SLA(25, 0)
        all_worlds = allocate(terms, WORLDS)
        self.assertEqual((all_worlds.service_provider_wei,
                          all_worlds.service_consumer_wei,
                          all_worlds.service_held_wei), (0, 0, 25))
        no_success = allocate(terms, frozenset({World.N, World.F}))
        self.assertEqual((no_success.service_provider_wei,
                          no_success.service_consumer_wei,
                          no_success.service_held_wei), (0, 25, 0))

    def test_legacy_nonzero_reservation_is_not_reinterpreted(self):
        no_success = allocate(SLA(25, 5), frozenset({World.N, World.F}))
        self.assertEqual((no_success.service_provider_wei,
                          no_success.service_consumer_wei,
                          no_success.service_held_wei), (0, 20, 5))

    def test_hypothetical_penalty_requires_unique_f_world(self):
        collateral = HypotheticalProviderCollateral(6, 4)
        exactly_failed = allocate(SLA(25, 0), frozenset({World.F}), collateral)
        self.assertEqual((exactly_failed.collateral_consumer_wei,
                          exactly_failed.collateral_provider_wei,
                          exactly_failed.collateral_held_wei), (4, 2, 0))
        ambiguous = allocate(SLA(25, 0), frozenset({World.N, World.F}), collateral)
        self.assertEqual((ambiguous.collateral_consumer_wei,
                          ambiguous.collateral_provider_wei,
                          ambiguous.collateral_held_wei), (0, 2, 4))
        success = allocate(SLA(25, 0), frozenset({World.S}), collateral)
        self.assertEqual((success.collateral_consumer_wei,
                          success.collateral_provider_wei,
                          success.collateral_held_wei), (0, 6, 0))

    def test_all_subsets_conserve_both_pots_and_release_monotonically(self):
        histories = list(subsets())
        for reserve in (0, 5, 25):
            for bond, penalty in ((0, 0), (6, 0), (6, 4), (6, 6)):
                collateral = HypotheticalProviderCollateral(bond, penalty)
                terms = SLA(25, reserve)
                with self.subTest(reserve=reserve, bond=bond, penalty=penalty):
                    amounts = {h: allocate(terms, h, collateral) for h in histories}
                    for subset, after in amounts.items():
                        self.assertTrue(after.conserves(25, bond))
                        for superset, before in amounts.items():
                            if subset.issubset(superset):
                                self.assertGreaterEqual(after.service_provider_wei, before.service_provider_wei)
                                self.assertGreaterEqual(after.service_consumer_wei, before.service_consumer_wei)
                                self.assertLessEqual(after.service_held_wei, before.service_held_wei)
                                self.assertGreaterEqual(after.collateral_consumer_wei, before.collateral_consumer_wei)
                                self.assertGreaterEqual(after.collateral_provider_wei, before.collateral_provider_wei)
                                self.assertLessEqual(after.collateral_held_wei, before.collateral_held_wei)

    def test_rejects_unfunded_and_invalid_policy_amounts(self):
        with self.assertRaises(EconomyDraftError):
            HypotheticalProviderCollateral(3, 4)
        with self.assertRaises(EconomyDraftError):
            HypotheticalProviderCollateral(-1, 0)
        with self.assertRaises(EconomyDraftError):
            HypotheticalProviderCollateral(True, 0)
        with self.assertRaises(EconomyDraftError):
            allocate(SLA(25, 0), frozenset())
        with self.assertRaises(EconomyDraftError):
            allocate(SLA(25, 0), frozenset({"F"}))

    def test_funding_plan_matches_existing_native_escrow_formulas(self):
        p = funding_plan(epoch_fee_wei=25, max_epochs=2, committee_size=4,
                         monitor_reward_per_report_wei=3, seal_bounty_wei=1,
                         settlement_bounty_wei=2, evidence_close_bounty_wei=3,
                         release_bounty_wei=4, vrf_fee_wei=5,
                         estimated_consumer_gas_wei=7)
        self.assertEqual((p.service_escrow_wei, p.monitor_reward_budget_wei,
                          p.executor_reward_budget_wei, p.vrf_prepayment_wei),
                         (50, 24, 16, 5))
        self.assertEqual(p.consumer_funding_wei, 95)
        self.assertEqual(p.estimated_total_consumer_outlay_wei, 102)

    def test_funding_is_wei_not_percent_or_floating_point(self):
        for args in ({"epoch_fee_wei": 0}, {"epoch_fee_wei": 0.5},
                     {"max_epochs": True}, {"committee_size": -1},
                     {"vrf_fee_wei": -2}):
            kw = {"epoch_fee_wei": 25, "max_epochs": 1, "committee_size": 4}
            kw.update(args)
            with self.subTest(args=args), self.assertRaises(EconomyDraftError):
                funding_plan(**kw)


if __name__ == "__main__":
    unittest.main()
