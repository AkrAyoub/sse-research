"""WP09D independent Python RSA-2048 proof fixture tests. LAB ONLY."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sse_wp09d_rsa_entropy import (
    REPRESENTATIVE_DOMAIN, RSA_ENTROPY_DOMAIN, RSA_PUBLIC_EXPONENT,
    read_lab_key, representative, rsa_request_digest, laboratory_proof,
    verify_proof, seed_from_proof,
)
from sse_challenge import keccak256
from eth_abi import encode

STATIC_REPRESENTATIVE = bytes.fromhex(
    "7e60bc5d982dc39f410836c4adf1259f2708baa1bfa088b16c7956a3090a69231bcb2d23ff1adfb6c3bca6a115ec269c45fb3fe7cb67427df4200a87cb9db201dbac9f68a400452a40480c7e9187a61febd2f1976c1accf7a6cf70239f0abc28d37c6809a7ed201171caa12151383acaf8a51672667e6809441fec3b7d6f736b7464ccdfab699a369c26f969c378bebc4d1ec64f7cb7e312a9c94f0462f3e830b0c966da059150fe2b4f9129494f914184e7ff4ffb1d576877f87e2eeb1cfdc2f65f652a5c5f5a2171638ae418bdba63a7e700ce4dfe8275035cec18a6a6a8a9cd573d9f3847cdf971cd63df6a3593ac3e037a72957f1071c8215f66e5c97df4"
)


class RSAProofLabTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modulus, cls.private = read_lab_key()

    def test_public_lab_fixture_is_rsa2048(self):
        self.assertEqual(self.modulus.bit_length(), 2048)
        self.assertEqual(self.modulus % 2, 1)
        self.assertEqual(RSA_PUBLIC_EXPONENT, 65537)
        self.assertEqual(pow(2, RSA_PUBLIC_EXPONENT * self.private, self.modulus), 2)

    def test_static_solidity_representative_matches_python(self):
        digest = (17).to_bytes(32, "big")
        self.assertEqual(representative(digest), STATIC_REPRESENTATIVE)
        self.assertEqual(len(representative(digest)), 256)
        self.assertLess(representative(digest)[0], 128)

    def test_proof_is_unique_for_fixed_digest_with_canonical_encoding(self):
        digest = (17).to_bytes(32, "big")
        proof = laboratory_proof(digest, self.modulus, self.private)
        self.assertEqual(proof, laboratory_proof(digest, self.modulus, self.private))
        self.assertTrue(verify_proof(digest, proof, self.modulus))
        self.assertFalse(verify_proof((18).to_bytes(32, "big"), proof, self.modulus))
        altered = bytearray(proof)
        altered[-1] ^= 1
        self.assertFalse(verify_proof(digest, bytes(altered), self.modulus))

    def test_add_modulus_malleation_is_rejected(self):
        digest = (17).to_bytes(32, "big")
        proof = laboratory_proof(digest, self.modulus, self.private)
        p_plus_n = (int.from_bytes(proof, "big") + self.modulus).to_bytes(256, "big")
        self.assertEqual(pow(int.from_bytes(p_plus_n, "big"), RSA_PUBLIC_EXPONENT,
                             self.modulus), int.from_bytes(representative(digest), "big"))
        self.assertFalse(verify_proof(digest, p_plus_n, self.modulus))
        self.assertFalse(verify_proof(digest, self.modulus.to_bytes(256, "big"),
                                      self.modulus))

    def test_different_pool_chain_lease_and_snapshot_change_digest(self):
        pool = "0x" + "12" * 20
        snapshot = bytes.fromhex("ab" * 32)
        args = (31337, pool, 1, 200, snapshot)
        d = rsa_request_digest(*args)
        self.assertEqual(d, keccak256(encode(
            ["bytes32", "uint256", "address", "uint256", "uint256", "bytes32"],
            [RSA_ENTROPY_DOMAIN, *args]
        )))
        alternatives = [
            (1, pool, 1, 200, snapshot),
            (31337, "0x" + "34" * 20, 1, 200, snapshot),
            (31337, pool, 2, 200, snapshot),
            (31337, pool, 1, 201, snapshot),
            (31337, pool, 1, 200, bytes.fromhex("cd" * 32)),
        ]
        for alternative in alternatives:
            with self.subTest(alternative=alternative):
                self.assertNotEqual(d, rsa_request_digest(*alternative))

    def test_proof_seed_changes_with_request_and_proof(self):
        d0 = rsa_request_digest(31337, "0x" + "12" * 20, 1, 201,
                                bytes.fromhex("ab" * 32))
        d1 = rsa_request_digest(31337, "0x" + "12" * 20, 2, 201,
                                bytes.fromhex("ab" * 32))
        p0 = laboratory_proof(d0, self.modulus, self.private)
        p1 = laboratory_proof(d1, self.modulus, self.private)
        self.assertNotEqual(p0, p1)
        self.assertNotEqual(seed_from_proof(d0, p0), seed_from_proof(d1, p1))
        self.assertEqual(seed_from_proof(d0, p0), int.from_bytes(keccak256(encode(
            ["bytes32", "bytes32", "bytes32"],
            [RSA_ENTROPY_DOMAIN, d0, keccak256(p0)]
        )), "big"))

    def test_invalid_arguments_fail_closed(self):
        digest = b"\x01" * 32
        proof = laboratory_proof(digest, self.modulus, self.private)
        self.assertFalse(verify_proof(digest, proof[:-1], self.modulus))
        self.assertFalse(verify_proof(digest, proof, 17))
        for malformed in [b"", b"x" * 31, "0x00", None]:
            with self.subTest(malformed=malformed):
                with self.assertRaises(ValueError):
                    representative(malformed)
        with self.assertRaises(ValueError):
            rsa_request_digest(0, "0x" + "12" * 20, 1, 1, digest)
        with self.assertRaises(ValueError):
            laboratory_proof(digest, 17, self.private)

    def test_keccak_domain_distinct(self):
        self.assertNotEqual(REPRESENTATIVE_DOMAIN, RSA_ENTROPY_DOMAIN)


if __name__ == "__main__":
    unittest.main()
