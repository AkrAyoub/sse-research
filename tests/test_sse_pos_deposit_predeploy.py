"""R33 synthetic public shape mutation tests; NOT genuine PoS/deposit results."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sse_pos_deposit_predeploy import DepositPredeployError, standard_reference, zero_hash_storage, validate_predeploy

ADDRESS = "0x" + "ab" * 20


class DepositPredeployReferenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "public-genesis.json"
        self.canonical = standard_reference()
        self.account = copy.deepcopy(self.canonical)
        self.write()

    def write(self):
        self.path.write_text(json.dumps({"alloc": {ADDRESS: self.account}}), encoding="utf-8")

    def test_pinned_runtime_and_constructor_storage_have_expected_layout(self):
        self.assertGreater(len(self.canonical["code"]), 5000)
        self.assertEqual(self.canonical["storage"], zero_hash_storage())
        self.assertEqual(len(self.canonical["storage"]), 31)
        self.assertEqual(min(int(x, 16) for x in self.canonical["storage"]), 34)
        self.assertEqual(max(int(x, 16) for x in self.canonical["storage"]), 64)

    def test_reference_match_is_not_live_consensus_or_deposit_verification(self):
        result = validate_predeploy(self.path, ADDRESS)
        self.assertTrue(result["depositPredeployMatchesPinnedUngatedReference"])
        self.assertTrue(result["depositConstructorZeroHashesVerified"])
        self.assertFalse(result["actualDepositContractExecutionVerified"])
        self.assertFalse(result["elClForkParityVerified"])
        self.assertFalse(result["newValidatorDepositActivationVerified"])

    def test_known_revert_stub_and_mutated_runtime_refused(self):
        for bad in ("0x60006000fd", "0x00", self.canonical["code"][:-2] + "ff"):
            with self.subTest(bad=bad[:16]):
                self.account["code"] = bad
                self.write()
                with self.assertRaisesRegex(DepositPredeployError, "bytecode differs"):
                    validate_predeploy(self.path, ADDRESS)

    def test_missing_mutated_or_extra_zero_hash_storage_refused(self):
        original = copy.deepcopy(self.canonical["storage"])
        self.account["storage"] = {}
        self.write()
        with self.assertRaisesRegex(DepositPredeployError, "storage missing"):
            validate_predeploy(self.path, ADDRESS)
        self.account["storage"] = dict(original)
        first = next(iter(original))
        self.account["storage"][first] = "0x" + "00" * 32
        self.write()
        with self.assertRaisesRegex(DepositPredeployError, "does NOT match"):
            validate_predeploy(self.path, ADDRESS)
        self.account["storage"] = dict(original)
        self.account["storage"]["0x" + "00" * 32] = "0x" + "00" * 32
        self.write()
        with self.assertRaisesRegex(DepositPredeployError, "storage missing"):
            validate_predeploy(self.path, ADDRESS)

    def test_canonical_address_alias_rejected(self):
        self.path.write_text(json.dumps({"alloc": {
            ADDRESS: self.account,
            ADDRESS.upper().replace("0X", ""): self.account,
        }}), encoding="utf-8")
        with self.assertRaisesRegex(DepositPredeployError, "exactly one"):
            validate_predeploy(self.path, ADDRESS)

    def test_nonzero_balance_refused(self):
        self.account["balance"] = "1"
        self.write()
        with self.assertRaisesRegex(DepositPredeployError, "balance prohibited"):
            validate_predeploy(self.path, ADDRESS)

    def test_symlink_or_duplicate_property_refused(self):
        link = self.path.with_suffix(".link")
        link.symlink_to(self.path)
        with self.assertRaisesRegex(DepositPredeployError, "bounded regular"):
            validate_predeploy(link, ADDRESS)
        self.path.write_text('{"alloc":{},"alloc":{}}', encoding="utf-8")
        with self.assertRaisesRegex(DepositPredeployError, "invalid unique-key"):
            validate_predeploy(self.path, ADDRESS)


if __name__ == "__main__":
    unittest.main()
