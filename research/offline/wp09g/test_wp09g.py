"""All local; no repository access, no CI, no EVM/Foundry required."""
import random
import unittest

from wp09g_recovery import (
    BATCH_LIMIT, DRAW_LIMIT, Election, ElectionError, Status,
    complete_attempt, dense_reference, global_draw,
)


def names(n):
    return tuple(f'0x{i + 1000:040x}' for i in range(n))


def election(n=160, request_id=1):
    return Election(names(n), request_id, consumer='0xa', provider='0xb')


def proofs(e, count=BATCH_LIMIT):
    return [(i, e.snapshot[i]) for i in e.indexes[e.proof_cursor:e.proof_cursor + count]]


class DrawChecks(unittest.TestCase):
    def test_prefix_matches_original_wp09e(self):
        from pathlib import Path
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'WP09F_offline'))
        from wp09f_experiments import exact_wp09e_sparse_draw
        for n in [4, 5, 10, 11, 65, 160, 1000]:
            for seed in [0, 1, 12, 1234, (1 << 256) - 1]:
                self.assertEqual(global_draw(seed, 1, n)[:min(n, 10)],
                                 exact_wp09e_sparse_draw(seed, 1, n))

    def test_full_draw_matches_independent_dense_reference(self):
        for n in (4, 5, 9, 11, 35, 40, 41, 64, 160, 1000):
            for seed in (1, 12, 56789, (1 << 256) - 1):
                self.assertEqual(global_draw(seed, 7, n), dense_reference(seed, 7, n))

    def test_unique_bound_and_global_reach(self):
        for n in (4, 9, 10, 11, 39, 40, 41, 160, 1000, 1 << 20):
            selected = global_draw(1234, 1, n)
            self.assertEqual(len(selected), min(n, DRAW_LIMIT))
            self.assertEqual(len(set(selected)), len(selected))
            self.assertTrue(all(0 <= i < n for i in selected))
        self.assertTrue(any(i >= 64 for i in global_draw(1234, 1, 160)))

    def test_seed_and_scope_changes_draw(self):
        self.assertNotEqual(global_draw(1, 1, 160), global_draw(2, 1, 160))
        self.assertNotEqual(global_draw(1, 1, 160), global_draw(1, 2, 160))

    def test_bad_input_rejected(self):
        for args in [(1, 1, 3), (-1, 1, 160), (1 << 256, 1, 160), (1, 0, 160), (1, 1, 1 << 20 | 1)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                global_draw(*args)
        with self.assertRaises(ValueError):
            global_draw(1, 1, 160, 41)


class RecoveryChecks(unittest.TestCase):
    def test_no_unverified_entropy_accepted(self):
        e = election()
        with self.assertRaisesRegex(ElectionError, 'validated'):
            e.fulfill_entropy(11, verified=False, now=10)
        with self.assertRaisesRegex(ElectionError, 'no pending seed'):
            e.batch([], now=10)
        self.assertEqual(e.status, Status.AWAITING_SEED)

    def test_prevent_seed_replacement(self):
        e = election()
        e.fulfill_entropy(11, verified=True, now=10)
        with self.assertRaisesRegex(ElectionError, 'already fulfilled'):
            e.fulfill_entropy(12, verified=True, now=11)
        self.assertEqual(e.seed, 11)

    def test_all_batch_indexes_mandatory_and_ordered(self):
        e = election()
        e.fulfill_entropy(111, verified=True, now=10)
        first = proofs(e)
        with self.assertRaisesRegex(ElectionError, 'out-of-order'):
            e.batch(first[1:], now=10)
        self.assertEqual(e.proof_cursor, 0)
        bad = first[:]
        bad[0] = (first[0][0], '0x' + 'f' * 40)
        with self.assertRaisesRegex(ElectionError, 'forged'):
            e.batch(bad, now=10)
        self.assertEqual(e.proof_cursor, 0)
        bad = first[:]
        bad[0], bad[1] = bad[1], bad[0]
        with self.assertRaisesRegex(ElectionError, 'out-of-order'):
            e.batch(bad, now=10)
        self.assertEqual(e.proof_cursor, 0)
        e.batch(first, now=11)
        self.assertEqual(e.proof_cursor, 8)
        self.assertEqual(e.status, Status.AWAITING_PROOFS)
        with self.assertRaisesRegex(ElectionError, 'out-of-order'):
            e.batch(first, now=12)

    def test_batch_limit(self):
        e = election()
        e.fulfill_entropy(111, verified=True, now=5)
        with self.assertRaisesRegex(ElectionError, 'boundary'):
            e.batch(proofs(e, 9), now=6)
        with self.assertRaisesRegex(ElectionError, 'boundary'):
            e.batch([], now=6)

    def test_initial_seats_locked_before_last_batch(self):
        e = election()
        e.fulfill_entropy(314, verified=True, now=10)
        e.batch(proofs(e), now=20)
        self.assertEqual(len(e.committee), 4)
        for a in e.committee:
            self.assertEqual(e.locked[a], 1)
            with self.assertRaisesRegex(ElectionError, 'locked'):
                e.withdraw(a)
        self.assertEqual(e.status, Status.AWAITING_PROOFS)

    def test_successful_batches_select_four_and_standbys(self):
        e = election()
        state = complete_attempt(e, seed=1234, exited=set())
        self.assertEqual(state, Status.ASSIGNED)
        self.assertEqual(e.proof_cursor, 40)
        self.assertEqual(len(e.committee), 4)
        self.assertEqual(len(e.standbys), 36)
        self.assertEqual(sum(e.locked.values()), 4)
        self.assertEqual(set(e.committee + e.standbys), {e.snapshot[i] for i in e.indexes})
        with self.assertRaises(ElectionError):
            e.batch([], now=70)

    def test_churn_seven_of_first_ten_recovered_by_extension(self):
        e = election()
        indexes = global_draw(1234, e.request_id, len(e.snapshot))
        exited = {e.snapshot[i] for i in indexes[:7]}
        self.assertEqual(complete_attempt(e, seed=1234, exited=exited), Status.ASSIGNED)
        self.assertEqual(e.committee, [e.snapshot[i] for i in indexes[7:11]])
        self.assertEqual(len(e.standbys), 29)

    def test_adaptive_37_exits_fails_closed_without_lost_locks(self):
        e = election()
        exited = {e.snapshot[i] for i in global_draw(1234, 1, 160)[:37]}
        self.assertEqual(complete_attempt(e, seed=1234, exited=exited), Status.EXPIRED)
        self.assertEqual(e.committee, [])
        self.assertEqual(e.standbys, [])
        self.assertTrue(all(v == 0 for v in e.locked.values()))
        self.assertEqual(e.proof_cursor, DRAW_LIMIT)

    def test_parties_excluded_but_all_proofs_required(self):
        roster = names(12)
        e = Election(roster, 1, consumer=roster[2], provider=roster[7])
        e.fulfill_entropy(123, verified=True, now=0)
        while e.status == Status.AWAITING_PROOFS:
            e.batch(proofs(e), now=10)
        self.assertEqual(e.status, Status.ASSIGNED)
        self.assertNotIn(roster[2], e.committee + e.standbys)
        self.assertNotIn(roster[7], e.committee + e.standbys)
        self.assertEqual(len(e.committee) + len(e.standbys), 10)

    def test_early_abort_disallowed_and_expiry_releases_partial_seats(self):
        e = election()
        e.fulfill_entropy(123, verified=True, now=0)
        e.batch(proofs(e), now=20)
        self.assertEqual(sum(e.locked.values()), 4)
        with self.assertRaisesRegex(ElectionError, 'too early'):
            e.expire(now=3600)
        e.expire(now=3601)
        self.assertEqual(e.status, Status.EXPIRED)
        self.assertEqual(sum(e.locked.values()), 0)
        self.assertEqual(e.committee, [])

    def test_expired_unrevealed_signer_no_locks(self):
        e = election()
        e.expire(now=3601)
        self.assertEqual(e.status, Status.EXPIRED)
        self.assertTrue(all(v == 0 for v in e.locked.values()))
        with self.assertRaises(ElectionError):
            e.fulfill_entropy(2, verified=True, now=3602)

    def test_post_timeout_batch_rejected(self):
        e = election()
        e.fulfill_entropy(777, verified=True, now=1)
        with self.assertRaisesRegex(ElectionError, 'deadline'):
            e.batch(proofs(e), now=3601)
        self.assertEqual(e.proof_cursor, 0)
        self.assertEqual(sum(e.locked.values()), 0)

    def test_no_progress_without_historical_proofs(self):
        e = election()
        e.fulfill_entropy(123, verified=True, now=10)
        candidate = proofs(e)
        with self.assertRaises(ElectionError):
            e.batch([(i, '0x' + '0' * 40) for i, _ in candidate], now=11)
        self.assertEqual(e.proof_cursor, 0)
        e.expire(now=3601)
        self.assertEqual(e.status, Status.EXPIRED)

    def test_random_churn_invariants(self):
        rng = random.Random(1474)
        for run in range(24):
            e = election(n=45, request_id=run + 1)
            seed = rng.getrandbits(256)
            indexes = global_draw(seed, e.request_id, 45)
            exited = {e.snapshot[i] for i in indexes if rng.random() < 0.55}
            complete_attempt(e, seed=seed, exited=exited)
            self.assertEqual(e.proof_cursor, 40)
            self.assertIn(e.status, (Status.ASSIGNED, Status.EXPIRED))
            self.assertEqual(len(set(e.committee)), len(e.committee))
            self.assertTrue(all(v in (0, 1) for v in e.locked.values()))
            self.assertEqual(sum(e.locked.values()), 4 if e.status == Status.ASSIGNED else 0)
            self.assertTrue(all(a in e.active for a in e.committee))


if __name__ == '__main__':
    unittest.main()
