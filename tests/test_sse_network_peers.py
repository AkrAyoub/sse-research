"""Offline Ed25519 peer-catalog tests, duplicate identity, DNS readdressing, no RPC."""
import sys
import tempfile
import unittest
from pathlib import Path

from Crypto.PublicKey import ECC

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sse_network_peers import (
    PeerCatalogError, sign, verify, bootnodes, validate_payload, validate_enode, _create_new
)

NOW = 1795000000
GENESIS = "0x" + "ab" * 32
KEY = ECC.generate(curve="Ed25519")
PRIV = KEY.export_key(format="PEM")
PUB = KEY.public_key().export_key(format="PEM")


def payload():
    return {
        "schema": "SSE_QBFT_PEERS_V1",
        "chainId": 31338,
        "genesisHash": GENESIS,
        "revision": "a" * 40,
        "issuedAt": NOW - 100,
        "expiresAt": NOW + 500,
        "nodes": [
            {"nodeId": f"validator-{i}", "role": "validator",
             "enode": "enode://" + f"{i:02x}" * 64 +
                      f"@validator-{i}.sse-tailnet.ts.net:30303"}
            for i in range(1, 5)
        ],
    }


class PeerCatalogTests(unittest.TestCase):
    def test_sign_verify_and_render_excludes_self(self):
        item = payload()
        envelope = sign(item, PRIV, chain_id=31338, genesis_hash=GENESIS, now=NOW)
        verified = verify(envelope, PUB, chain_id=31338, genesis_hash=GENESIS, now=NOW)
        self.assertEqual(verified["validators"], 4)
        self.assertTrue(verified["signatureVerified"])
        peers = bootnodes(verified, self_id="validator-1")
        self.assertEqual(len(peers.splitlines()), 3)
        self.assertNotIn("validator-1.sse-tailnet", peers)

    def test_signature_tamper_and_wrong_trust_key_rejected(self):
        envelope = sign(payload(), PRIV, chain_id=31338, genesis_hash=GENESIS, now=NOW)
        envelope["payload"]["nodes"][0]["enode"] = envelope["payload"]["nodes"][1]["enode"]
        with self.assertRaises(PeerCatalogError):
            verify(envelope, PUB, chain_id=31338, genesis_hash=GENESIS, now=NOW)
        with self.assertRaises(PeerCatalogError):
            verify(sign(payload(), PRIV, chain_id=31338, genesis_hash=GENESIS, now=NOW),
                   ECC.generate(curve="Ed25519").public_key().export_key(format="PEM"),
                   chain_id=31338, genesis_hash=GENESIS, now=NOW)

    def test_wrong_chain_genesis_expiry_and_duplicate_enode_fail(self):
        item = payload()
        cases = [
            {**item, "chainId": 31337},
            {**item, "genesisHash": "0x" + "cd" * 32},
            {**item, "expiresAt": NOW - 1},
            {**item, "nodes": item["nodes"] + [item["nodes"][0]]},
        ]
        for case in cases:
            with self.subTest(case=case.get("chainId")), self.assertRaises(PeerCatalogError):
                validate_payload(case, chain_id=31338, genesis_hash=GENESIS, now=NOW)

    def test_private_lan_literal_rejected_public_or_overlay_accepted(self):
        with self.assertRaises(PeerCatalogError):
            validate_enode("enode://" + "ab" * 64 + "@10.50.56.14:30303")
        self.assertEqual(validate_enode("enode://" + "ab" * 64 +
                                        "@100.101.102.103:30303")[2], 30303)
        self.assertEqual(validate_enode("enode://" + "ab" * 64 +
                                        "@validator.mesh.example.org:30303")[2], 30303)

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "bootnodes.txt"
            _create_new(target, "fixture\n")
            with self.assertRaises(PeerCatalogError):
                _create_new(target, "overwritten\n")
            self.assertEqual(target.read_text(), "fixture\n")

    def test_unlisted_self_fails(self):
        envelope = sign(payload(), PRIV, chain_id=31338, genesis_hash=GENESIS, now=NOW)
        verified = verify(envelope, PUB, chain_id=31338, genesis_hash=GENESIS, now=NOW)
        with self.assertRaises(PeerCatalogError):
            bootnodes(verified, self_id="unknown-node")


if __name__ == "__main__":
    unittest.main()
