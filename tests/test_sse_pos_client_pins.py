"""Guard immutable observed native PoS image pins and safe offline checks.

These tests validate source and deliberately do NOT claim P2P or validator
activation, image runtime execution or Docker access.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sse_pos_client_pins import ClientPinError, load_pins, FILE

EXPECTED_BESU = (
    "hyperledger/besu@sha256:"
    "4fd2ba40f0d65917bcb3abd9af60673946f66dee2ecb1b87f7cdfa6a30fe458d"
)
EXPECTED_LIGHTHOUSE = (
    "sigp/lighthouse@sha256:"
    "53f9063d98c3d3a2d290207873f019ea2298cfc02f8cd58d87c33b04aab856d1"
)

class PinnedNativeClientTests(unittest.TestCase):
    @staticmethod
    def validate_modified(mutator):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "pins.json"
            payload = json.loads(FILE.read_text("utf-8"))
            mutator(payload)
            target.write_text(json.dumps(payload), encoding="utf-8")
            return load_pins(target)

    def test_digests_are_derived_from_actual_vm4706_observations(self):
        cfg = load_pins()
        self.assertEqual(cfg["intendedChainId"], 31340)
        self.assertEqual(
            cfg["evidenceSourceSha"],
            "2908450be6e3360d58ea35d64f7a72bcfa4f5f43",
        )
        self.assertEqual(cfg["images"]["besu"]["ref"], EXPECTED_BESU)
        self.assertEqual(cfg["images"]["lighthouse"]["ref"], EXPECTED_LIGHTHOUSE)
        self.assertTrue(cfg["verification"]["versionCommandsExecutedOnVM4706"])
        self.assertFalse(cfg["verification"]["publicP2PStarted"])
        self.assertFalse(cfg["verification"]["genesisBuilt"])

    def test_missing_or_changed_digest_fails_closed(self):
        for field, value in (
            ("ref", "hyperledger/besu:26.11.1"),
            ("ref", "hyperledger/besu@sha256:" + "z" * 64),
            ("imageId", "sha256:" + "c" * 63),
        ):
            def corrupt(payload):
                payload["images"]["besu"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ClientPinError):
                self.validate_modified(corrupt)

    def test_role_removal_or_wrong_chain_fails_closed(self):
        def drop_lighthouse(payload):
            del payload["images"]["lighthouse"]
        with self.assertRaises(ClientPinError):
            self.validate_modified(drop_lighthouse)

        def wrong_chain(payload):
            payload["intendedChainId"] = 31339
        with self.assertRaises(ClientPinError):
            self.validate_modified(wrong_chain)

    def test_fabricated_live_network_claims_refused(self):
        for key in ("publicP2PStarted", "genesisBuilt",
                    "validatorKeysGenerated", "realTestEthDeposited"):
            def claim(payload):
                payload["verification"][key] = True
            with self.subTest(key=key), self.assertRaises(ClientPinError):
                self.validate_modified(claim)

    def test_duplicate_json_pin_fields_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pins.json"
            raw = FILE.read_text("utf-8")
            raw = raw.replace(
                '"intendedChainId": 31340,',
                '"intendedChainId": 31340, "intendedChainId": 31339,',
                1,
            )
            path.write_text(raw, encoding="utf-8")
            with self.assertRaises(ClientPinError):
                load_pins(path)

    def test_version_checker_uses_only_digests(self):
        src = (ROOT / "scripts" / "r19_verify_pinned_pos_clients.sh").read_text()
        self.assertIn('tools/sse_pos_client_pins.py --refs', src)
        self.assertIn('tools/sse_pos_client_pins.py --image-ids', src)
        self.assertIn('docker pull --platform linux/amd64 "$REF"', src)
        self.assertIn('"$ACTUAL_ID" != "$ID"', src)
        self.assertIn('--network none', src)
        self.assertIn('--add-host sse-local-probe:127.0.0.1', src)
        self.assertIn('--read-only', src)
        self.assertIn('--cap-drop ALL', src)
        self.assertIn('--security-opt no-new-privileges', src)
        self.assertNotIn('--privileged', src)
        self.assertNotIn('--network host', src)
        self.assertNotIn('--publish ', src)

    def test_besu_default_entrypoint_and_no_network_claim(self):
        src = (ROOT / "scripts" / "r19_verify_pinned_pos_clients.sh").read_text()
        self.assertIn('ENTRY=()', src)
        self.assertIn('ENTRY=(--entrypoint lighthouse)', src)
        self.assertIn('R19_NATIVE_EL_CL_P2P_STARTED=false', src)
        self.assertIn('R19_BEACON_GENESIS_CREATED=false', src)
        self.assertIn('R19_PUBLIC_POS_NETWORK_DEPLOYED=false', src)

if __name__ == "__main__":
    unittest.main()
