"""WP09F offline self-checks; run python -m unittest -v (no CI runner)."""
import math
import unittest

from keccak import keccak256
from wp09f_experiments import (
    N, K, WINDOW, WINDOW_STARTS, ATTACKER_IDENTITIES,
    exact_wp09e_sparse_draw, dense_draw_reference, hypergeom_at_least,
    retain_at_least, global_snapshot_survival, window_attacker_counts,
    ideal_entropy_monte_carlo, run_experiment
)


class WP09FOfflineTests(unittest.TestCase):
    def test_keccak_is_ethereum_keccak_not_nist_sha3(self):
        self.assertEqual(keccak256(b'').hex(),
                         'c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470')

    def test_sparse_fisher_yates_matches_independent_dense_for_many_populations(self):
        for n in (4, 5, 9, 10, 11, 32, 64, 65, 80, 160, 300):
            for seed in (0, 1, 17, 1234):
                with self.subTest(n=n, seed=seed):
                    sparse = exact_wp09e_sparse_draw(seed, 91, n)
                    dense = dense_draw_reference(seed, 91, n)
                    self.assertEqual(sparse, dense)
                    self.assertEqual(len(sparse), min(n, 10))
                    self.assertEqual(len(sparse), len(set(sparse)))
                    self.assertTrue(all(0 <= i < n for i in sparse))

    def test_global_draw_not_limited_to_first64(self):
        draws = set()
        for seed in range(8):
            draws.update(exact_wp09e_sparse_draw(seed, 1, N))
        self.assertTrue(any(i > 63 for i in draws))
        self.assertTrue(any(i >= 128 for i in draws))

    def test_draw_reproducibility_and_domain_scope(self):
        self.assertEqual(exact_wp09e_sparse_draw(1234, 1, 160),
                         exact_wp09e_sparse_draw(1234, 1, 160))
        self.assertNotEqual(exact_wp09e_sparse_draw(1234, 1, 160),
                            exact_wp09e_sparse_draw(1234, 2, 160))

    def test_hypergeometric_extreme_cases(self):
        self.assertEqual(hypergeom_at_least(160, 0, 4, 1), 0)
        self.assertEqual(hypergeom_at_least(160, 160, 4, 1), 1)
        self.assertEqual(hypergeom_at_least(160, 40, 4, 0), 1)
        self.assertGreater(hypergeom_at_least(160, 40, 4, 1), 0)
        self.assertLess(hypergeom_at_least(160, 40, 4, 1), 1)

    def test_window_cycle_is_complete_and_concentration_varies(self):
        self.assertEqual(WINDOW_STARTS, (0, 64, 128, 32, 96))
        counts = window_attacker_counts()
        self.assertEqual(counts, [40, 0, 32, 8, 0])
        self.assertEqual(sum(counts), 2 * ATTACKER_IDENTITIES)
        self.assertEqual(sum(counts) * K / (5 * WINDOW), ATTACKER_IDENTITIES * K / N)

    def test_churn_bounds_and_survival_monotonicity(self):
        self.assertEqual(retain_at_least(10, 1), 1)
        self.assertEqual(retain_at_least(10, 0), 0)
        self.assertEqual(retain_at_least(3, 1), 0)
        rates = [global_snapshot_survival(160, 2, 10, p) for p in (0, .1, .2, .4, .6)]
        self.assertEqual(rates[0], 1)
        self.assertTrue(all(rates[i] > rates[i+1] for i in range(4)))
        self.assertLess(global_snapshot_survival(160, 2, 10, .3), retain_at_least(10, .7))

    def test_two_active_parties_can_be_drawn_but_not_eligible(self):
        self.assertEqual(global_snapshot_survival(10, 2, 10, 0), 1)
        self.assertEqual(global_snapshot_survival(10, 9, 10, 0), 0)

    def test_seeded_simulation_near_exact_distribution(self):
        r = ideal_entropy_monte_carlo(5_000, 2121)
        expected = hypergeom_at_least(N, ATTACKER_IDENTITIES, K, 1)
        self.assertLess(abs(r['global_attack_frequency'] - expected), .035)
        counts = window_attacker_counts()
        for i in range(5):
            expected_window = hypergeom_at_least(WINDOW, counts[i], K, 1)
            self.assertLess(abs(r['window_attack_frequency_by_start'][i] - expected_window), .06)

    def test_selective_withholding_publishes_only_favorable_committees(self):
        p = run_experiment(rounds=5_000, random_seed=2121)
        policies = p['selective_proof_withholding']
        self.assertGreater(policies[0]['publication_rate'], policies[1]['publication_rate'])
        self.assertGreater(policies[1]['publication_rate'], policies[2]['publication_rate'])
        self.assertEqual(policies[1]['p_attack_in_published_committees'], 1)
        self.assertEqual(policies[2]['p_attack_in_published_committees'], 1)
        self.assertEqual(p['adversarial_exit_bound']['exits_that_guarantee_failure_if_all_draws_were_initially_eligible'], 7)

    def test_invalid_sampler_parameters_fail(self):
        for args in [(0, 1, 3), (0, 0, 160), (-1, 1, 160)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                exact_wp09e_sparse_draw(*args)


if __name__ == '__main__':
    unittest.main(verbosity=2)
