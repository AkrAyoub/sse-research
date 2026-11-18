"""Offline malicious/missing/rollback peer discovery scenarios."""
import json
import sys
import unittest
from pathlib import Path

from Crypto.PublicKey import ECC

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sse_network_peers import sign
from sse_peer_refresh import (PeerRefreshError, trusted_https_url,
                              prepare, _atomic_replace)
from sse_network_peers import PeerCatalogError

NOW = 1795000000
GENESIS = "0x" + "11" * 32
KEY = ECC.generate(curve="Ed25519")
PRIV = KEY.export_key(format="PEM")
PUB = KEY.public_key().export_key(format="PEM")


def signed(issued=NOW-100, last_octet=1):
    payload = {
        "schema": "SSE_QBFT_PEERS_V1", "chainId": 31338,
        "genesisHash": GENESIS, "revision": "a" * 40,
        "issuedAt": issued, "expiresAt": NOW + 1000,
        "nodes": [
            {"nodeId": f"validator-{i}", "role": "validator",
             "enode": "enode://" + f"{i:02x}" * 64 +
                      f"@validator-{i}.mesh.example.org:30303"}
            for i in range(1,5)],
    }
    return sign(payload, PRIV, chain_id=31338, genesis_hash=GENESIS, now=NOW)


class PeerRefreshTests(unittest.TestCase):
    def test_verified_catalog_stages_without_network_or_writes(self):
        doc = signed()
        envelope, body = prepare(json.dumps(doc).encode(), PUB, chain_id=31338,
                                 genesis_hash=GENESIS, self_id="validator-1", now=NOW)
        self.assertEqual(envelope, doc)
        self.assertEqual(len(body.splitlines()), 3)

    def test_rollback_after_newer_accepted_rejected(self):
        current = signed(issued=NOW-20)
        old = signed(issued=NOW-100)
        with self.assertRaises(PeerRefreshError):
            prepare(json.dumps(old).encode(), PUB, chain_id=31338,
                    genesis_hash=GENESIS, self_id="validator-1",
                    previous=current, now=NOW)

    def test_tampering_rejected(self):
        doc = signed()
        doc["payload"]["nodes"][0]["role"] = "full"
        with self.assertRaises(PeerCatalogError):
            prepare(json.dumps(doc).encode(), PUB, chain_id=31338,
                    genesis_hash=GENESIS, self_id="validator-1", now=NOW)

    def test_reject_http_credentials_and_redirect_destinations(self):
        for url in ("http://repo.example.org/peers.json",
                    "https://u:p@repo.example.org/peers.json",
                    "https://repo.example.org/../secret",
                    "https://repo.example.org/peers.json?token=xyz"):
            with self.assertRaises(PeerRefreshError):
                trusted_https_url(url)

    def test_atomic_file_rejects_world_writable_directory(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            os.chmod(directory, 0o777)
            try:
                with self.assertRaises(PeerRefreshError):
                    _atomic_replace(directory / "bootnodes.txt", b"test")
            finally:
                os.chmod(directory, 0o700)


if __name__ == "__main__":
    unittest.main()
