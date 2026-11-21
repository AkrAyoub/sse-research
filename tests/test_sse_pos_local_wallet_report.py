"""R20 SOURCE-ONLY tests: safe inspection and private test-only EOA procedure.

All sample keystores are synthetic malformed/fake fixtures, NEVER generated
cryptographic keys, wallet credentials, Genesis contributions or deposits.
"""
from pathlib import Path
import json
import os
import stat
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sse_pos_local_wallet_report import WalletCheckError, inspect_encrypted_dir


class LocalOwnerWithdrawalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name) / "keystore"
        self.p.mkdir(mode=0o700)
        self.fake = self.p / "sse-r20-withdrawal"
        self.doc = {
            "version": 3,
            "id": "00000000-0000-0000-0000-000000000000",
            "address": "a" * 40,
            "crypto": {
                "cipher": "aes-128-ctr",
                "cipherparams": {"iv": "c" * 32},
                "ciphertext": "b" * 64,
                "kdf": "scrypt",
                "kdfparams": {"dklen": 32, "n": 8192, "p": 1, "r": 8, "salt": "d"*64},
                "mac": "e" * 64,
            },
        }
        self.write()

    def write(self):
        self.fake.write_text(json.dumps(self.doc), encoding="utf-8")
        self.fake.chmod(0o600)

    def test_only_public_address_and_claim_flags_reported(self):
        result = inspect_encrypted_dir(self.p)
        self.assertEqual(result["withdrawalAddress"], "0x" + "a" * 40)
        self.assertTrue(result["encryptedKeystoreStructurePresent"])
        self.assertFalse(result["privateKeyPrinted"])
        self.assertFalse(result["walletPasswordVerified"])
        self.assertFalse(result["operatorPhysicalIndependenceVerified"])
        self.assertFalse(result["genesisOrValidatorActivated"])
        # Distinguish a reassuring status FIELD from actual secret material:
        # "privateKeyPrinted": false is safe; privateKey: "<hex>" is not.
        self.assertNotIn("ciphertext", result)
        self.assertNotIn("privateKey", result)
        self.assertNotIn("private_key", result)
        self.assertNotIn("mnemonic", result)
        self.assertNotIn("secretKey", result)
        self.assertIs(result["privateKeyPrinted"], False)

    def test_address_may_use_ethereum_0x_prefix(self):
        self.doc["address"] = "0x" + "b" * 40
        self.write()
        result = inspect_encrypted_dir(self.p)
        self.assertEqual(result["withdrawalAddress"], "0x" + "b" * 40)

    def test_real_cast_eth_keystore_without_embedded_address_is_not_refused(self):
        # eth-keystore 0.5.0's optional geth-compat feature controls
        # whether the V3 address field is serialized. Do not invent one.
        del self.doc["address"]
        self.write()
        report = inspect_encrypted_dir(self.p)
        self.assertIsNone(report["withdrawalAddress"])
        self.assertIs(report["withdrawalAddressEmbeddedInKeystore"], False)
        self.assertIs(report["addressCryptographicallyVerified"], False)
        self.assertTrue(report["encryptedKeystoreStructurePresent"])
        self.assertNotIn("ciphertext", report)

    def test_address_in_v3_fixture_is_not_password_or_signer_verified(self):
        report = inspect_encrypted_dir(self.p)
        self.assertTrue(report["withdrawalAddressEmbeddedInKeystore"])
        self.assertFalse(report["addressCryptographicallyVerified"])
        self.assertFalse(report["walletPasswordVerified"])

    def test_extra_plaintext_key_or_dual_encryption_envelope_still_refused(self):
        self.doc["plainPrivateKey"] = "DO_NOT_REPORT"
        self.write()
        with self.assertRaises(WalletCheckError):
            inspect_encrypted_dir(self.p)
        del self.doc["plainPrivateKey"]
        self.doc["Crypto"] = self.doc["crypto"]
        self.write()
        with self.assertRaises(WalletCheckError):
            inspect_encrypted_dir(self.p)

    def test_missing_wallet_id_still_refused_even_if_encrypted(self):
        del self.doc["id"]
        self.write()
        with self.assertRaises(WalletCheckError):
            inspect_encrypted_dir(self.p)

    def test_refuse_plaintext_private_fields(self):
        for bad in ("private_key", "privateKey", "mnemonic", "secretKey"):
            self.doc[bad] = "DO_NOT_PUBLISH"
            self.write()
            with self.subTest(key=bad), self.assertRaises(WalletCheckError):
                inspect_encrypted_dir(self.p)
            del self.doc[bad]

    def test_refuse_missing_or_unencrypted_keystore(self):
        self.doc["crypto"] = {}
        self.write()
        with self.assertRaises(WalletCheckError):
            inspect_encrypted_dir(self.p)
        self.doc["crypto"] = {
            "cipher": "aes-128-ctr",
            "cipherparams": {},
            "ciphertext": "",
            "kdf": "scrypt",
            "kdfparams": {},
            "mac": "x"
        }
        self.write()
        with self.assertRaises(WalletCheckError):
            inspect_encrypted_dir(self.p)

    def test_refuse_world_access_and_symlinks(self):
        self.fake.chmod(0o644)
        with self.assertRaises(WalletCheckError):
            inspect_encrypted_dir(self.p)
        self.fake.unlink()
        self.fake.symlink_to("/etc/hosts")
        with self.assertRaises(WalletCheckError):
            inspect_encrypted_dir(self.p)
        self.fake.unlink()
        self.write()
        self.p.chmod(0o755)
        with self.assertRaises(WalletCheckError):
            inspect_encrypted_dir(self.p)

    def test_no_wallet_dump_or_unsafe_key_cli_in_github_script(self):
        s = (ROOT / "scripts" / "r20_create_local_operator_withdrawal.sh").read_text()
        self.assertIn('CAST_SHA="cae9d8a3e9a2c2f121879f39498472fee8a767318fc26ff7e3c73908133fdaa4"', s)
        self.assertIn('wallet new "$DIR" "sse-r20-withdrawal" > "$LOG"', s)
        self.assertIn("tools/sse_pos_local_wallet_report.py", s)
        self.assertIn("R20_BLS_VALIDATORS_CREATED=false", s)
        self.assertIn("R20_PUBLIC_POS_NETWORK_DEPLOYED=false", s)
        self.assertIn("R20_OPERATOR_REFUSED: operator private dir already exists", s)
        self.assertIn('--network none', s)
        self.assertIn('--read-only', s)
        self.assertIn('--cap-drop ALL', s)
        self.assertIn('--security-opt no-new-privileges', s)
        self.assertNotIn("--unsafe-password", s)
        self.assertNotIn("--private-key", s)
        self.assertNotIn("wallet decrypt", s)
        self.assertNotIn("--network mainnet", s)
        self.assertNotIn("R20_PRIVATE_KEY=", s)

if __name__ == "__main__":
    unittest.main()
