"""MPT/RLP verifier tests. SOURCE-ONLY: written 2026-11-27, not executed.
Fixture tries are built in-test from RLP primitives (test-only data, not chain data).
A real eth_getProof fixture captured from chain31340 is deferred (DRV-EXPLORER-01)."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_v4_proof as p
from sse_challenge import keccak256


def hp(nibbles, leaf):
    flag = 2 if leaf else 0
    if len(nibbles) % 2:
        n = [flag + 1] + nibbles
    else:
        n = [flag, 0] + nibbles
    return bytes(n[i] * 16 + n[i + 1] for i in range(0, len(n), 2))


class RlpTest(unittest.TestCase):
    def test_roundtrip(self):
        for x in (b"", b"\x01", b"\x80", b"a" * 60, [b"a", [b"b", b""]], [b"x" * 70] * 3):
            self.assertEqual(p.rlp_decode(p.rlp_encode(x)), x)

    def test_rejects_noncanonical(self):
        with self.assertRaises(p.ProofError):
            p.rlp_decode(b"\x81\x05")
        with self.assertRaises(p.ProofError):
            p.rlp_decode(b"\x83ab")


class MptTest(unittest.TestCase):
    def test_single_leaf_trie(self):
        key = b"\x01" * 20
        nib = p._nibbles(keccak256(key))
        leaf = p.rlp_encode([hp(nib, True), b"value"])
        root = keccak256(leaf)
        v, path = p.verify_mpt(root, key, [leaf])
        self.assertEqual(v, b"value")
        self.assertEqual(path[0]["kind"], "leaf")
        other = b"\x02" * 20
        v2, _ = p.verify_mpt(root, other, [leaf])
        self.assertIsNone(v2)  # divergent path => proven absent

    def test_branch_with_two_leaves(self):
        k1, k2 = b"\x01" * 20, b"\x02" * 20
        n1, n2 = p._nibbles(keccak256(k1)), p._nibbles(keccak256(k2))
        if n1[0] == n2[0]:
            self.skipTest("fixture keys share first nibble")
        l1 = p.rlp_encode([hp(n1[1:], True), b"A" * 40])
        l2 = p.rlp_encode([hp(n2[1:], True), b"B" * 40])
        children = [b""] * 17
        children[n1[0]] = keccak256(l1)
        children[n2[0]] = keccak256(l2)
        branch = p.rlp_encode(children)
        root = keccak256(branch)
        self.assertEqual(p.verify_mpt(root, k1, [branch, l1])[0], b"A" * 40)
        self.assertEqual(p.verify_mpt(root, k2, [branch, l2])[0], b"B" * 40)
        with self.assertRaises(p.ProofError):
            p.verify_mpt(root, k1, [branch])  # missing node is an error, never "absent"

    def test_tampered_value_detected_by_root(self):
        key = b"\x03" * 20
        leaf = p.rlp_encode([hp(p._nibbles(keccak256(key)), True), b"v1"])
        bad = p.rlp_encode([hp(p._nibbles(keccak256(key)), True), b"v2"])
        with self.assertRaises(p.ProofError):
            p.verify_mpt(keccak256(leaf), key, [bad])


if __name__ == "__main__":
    unittest.main()
