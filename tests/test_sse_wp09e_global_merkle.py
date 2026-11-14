"""WP09E Python independent global active-roster Merkle and draw tests."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sse_wp09e_global_merkle import (
    CAPACITY, TREE_DEPTH, ZERO, RosterTree, leaf_hash, parent,
    verify, sampled_indexes, request_commitment,
)


def account(i: int) -> str:
    return "0x" + format(0xC100 + i, "040x")


class GlobalMerkleReferenceTest(unittest.TestCase):
    def test_empty_root_and_full_roster_proofs_with96_active(self):
        tree = RosterTree()
        self.assertEqual(tree.root, ZERO)
        for i in range(96):
            tree.append(account(i))
        self.assertNotEqual(tree.root, ZERO)
        for i in range(96):
            p = tree.proof(i)
            self.assertEqual(len(p), TREE_DEPTH)
            self.assertTrue(verify(tree.root, i, account(i), p))
            self.assertFalse(verify(tree.root, i, account(200), p))
        self.assertEqual(len(tree.accounts), 96)

    def test_root_is_snapshot_stable_after_swap_pop_exit(self):
        tree = RosterTree()
        for i in range(12):
            tree.append(account(i))
        root_before = tree.root
        historical = tree.proof(2)
        tree.remove(account(2))
        self.assertNotEqual(root_before, tree.root)
        self.assertTrue(verify(root_before, 2, account(2), historical))
        self.assertFalse(verify(tree.root, 2, account(2), historical))
        self.assertEqual(tree.accounts[2], account(11))
        self.assertEqual(len(tree.accounts), 11)
        for i, addr in enumerate(tree.accounts):
            self.assertTrue(verify(tree.root, i, addr, tree.proof(i)))

    def test_all_drawn_indexes_are_unique_and_entire_global_set_is_eligible(self):
        for n in (4, 5, 7, 10, 11, 63, 64, 65, 96, 160, 1000):
            for seed in (0, 1, 13, 123456, (1 << 256) - 1):
                indexes = sampled_indexes(seed, 5, n)
                self.assertEqual(len(indexes), min(n, 10))
                self.assertEqual(len(indexes), len(set(indexes)))
                self.assertTrue(all(0 <= x < n for x in indexes))

    def test_160_member_draw_eventually_selects_beyond_window64(self):
        seen = set()
        for seed in range(120):
            seen.update(sampled_indexes(seed, 1, 160))
        self.assertTrue(any(index >= 64 for index in seen))
        self.assertTrue(any(index >= 128 for index in seen))
        self.assertGreater(len(seen), 150)

    def test_full_small_roster_is_a_permutation(self):
        for n in range(4, 11):
            self.assertEqual(set(sampled_indexes(987, 1, n)), set(range(n)))

    def test_wrong_root_wrong_index_or_bad_merkle_path_fails(self):
        tree = RosterTree()
        for i in range(7):
            tree.append(account(i))
        p = tree.proof(4)
        self.assertTrue(verify(tree.root, 4, account(4), p))
        self.assertFalse(verify(tree.root, 5, account(4), p))
        self.assertFalse(verify(tree.root, 4, account(4), p[:-1]))
        bad = list(p)
        bad[0] = b"\xab" * 32
        self.assertFalse(verify(tree.root, 4, account(4), bad))
        self.assertFalse(verify(b"\xfe" * 32, 4, account(4), p))

    def test_domain_has_unambiguous_integer_index_encoding(self):
        self.assertNotEqual(leaf_hash(0, account(1)), leaf_hash(1, account(1)))
        self.assertNotEqual(leaf_hash(2, account(1)), leaf_hash(2, account(2)))
        self.assertNotEqual(parent(ZERO, ZERO), parent(ZERO, leaf_hash(3, account(2))))
        with self.assertRaises(ValueError):
            leaf_hash(CAPACITY, account(1))
        with self.assertRaises(ValueError):
            leaf_hash(-1, account(1))

    def test_request_commitment_scopes_chain_pool_block_root_count(self):
        tree = RosterTree()
        for i in range(6):
            tree.append(account(i))
        a = request_commitment(31337, account(99), 1, 10, tree.root, 6)
        variants = [
            request_commitment(1, account(99), 1, 10, tree.root, 6),
            request_commitment(31337, account(98), 1, 10, tree.root, 6),
            request_commitment(31337, account(99), 2, 10, tree.root, 6),
            request_commitment(31337, account(99), 1, 11, tree.root, 6),
            request_commitment(31337, account(99), 1, 10, tree.root, 5),
        ]
        self.assertTrue(all(v != a for v in variants))
        tree.remove(account(1))
        self.assertNotEqual(a, request_commitment(31337, account(99),
                             1, 10, tree.root, 6))

    def test_incorrect_sample_request_rejected(self):
        for args in [(1, 1, 0), (-1, 1, 4), (5, 0, 4), (5, 1, CAPACITY + 1)]:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    sampled_indexes(*args)

    def test_large_roster_not_considered_empty_when_last_index_removed(self):
        tree = RosterTree()
        tree.append(account(0))
        self.assertNotEqual(tree.root, ZERO)
        tree.remove(account(0))
        self.assertEqual(tree.root, ZERO)
        self.assertEqual(tree.accounts, [])


if __name__ == "__main__":
    unittest.main()
