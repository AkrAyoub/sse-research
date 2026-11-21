"""Only synthetic encrypted-EIP2335-shaped fixtures; NO real keys generated."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sse_pos_public_keystore_export import (
    PublicKeystoreExportError, export_public,
    public_pubkey_from_encrypted_keyfile,
)


class LocalEncryptedKeystorePublicExportTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.keys = self.root / "private-keys"
        self.keys.mkdir(mode=0o700)
        self.output = self.root / "public-operator.json"
        self.address = "0x" + "b" * 40

    def keystore(self, index=1, *, folder=None, mutation=None):
        folder = folder or self.keys
        path = folder / f"keystore-{index}.json"
        content = {
            "version": 4,
            "uuid": f"FAKE-FIXTURE-{index}",
            "pubkey": f"{index:096x}",
            "crypto": {
                "kdf": {"function": "scrypt", "params": {}, "message": ""},
                "cipher": {"function": "aes-128-ctr", "message": "a" * 64},
                "checksum": {"function": "sha256", "message": "b" * 64},
            },
            "path": "m/12381/3600/0/0/0",
        }
        if mutation:
            mutation(content)
        path.write_text(json.dumps(content), encoding="utf-8")
        path.chmod(0o600)
        return path

    def go(self):
        return export_public(
            self.keys, operator_id="independent-one",
            withdrawal_address=self.address, output=self.output
        )

    def test_owner_local_export_contains_only_public_data(self):
        self.keystore(1)
        self.keystore(2)
        report = self.go()
        self.assertEqual(report["publicValidatorKeys"], 2)
        self.assertFalse(report["blsPrivateKeyPossessionVerified"])
        self.assertFalse(report["publicMultioperatorNetworkReady"])
        d = json.loads(self.output.read_text())
        self.assertEqual(len(d["validators"]), 2)
        self.assertEqual(d["validators"][0]["balanceGwei"], 32000000000)
        self.assertTrue(d["validators"][0]["withdrawalCredentials"].startswith("0x01"))
        self.assertNotIn("crypto", self.output.read_text())
        self.assertNotIn("cipher", self.output.read_text())
        self.assertNotIn("uuid", self.output.read_text())
        self.assertNotIn("password", self.output.read_text())
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)

    def test_lighthouse_nested_voting_keystore_accepted_without_reading_passwords(self):
        nested = self.keys / "validator-key-1"
        nested.mkdir(mode=0o700)
        key = self.keystore(1, folder=nested)
        key.rename(nested / "voting-keystore.json")
        (nested / "password.txt").write_text("NEVER READ THIS PASSWORD")
        report = self.go()
        self.assertEqual(report["publicValidatorKeys"], 1)
        self.assertNotIn("NEVER READ THIS PASSWORD", self.output.read_text())

    def test_duplicate_pubkeys_rejected_without_partial_public_file(self):
        self.keystore(1)
        self.keystore(2, mutation=lambda d: d.update(pubkey=f"{1:096x}"))
        with self.assertRaises(PublicKeystoreExportError):
            self.go()
        self.assertFalse(self.output.exists())

    def test_no_unencrypted_or_malformed_validator_secrets_accepted(self):
        for mutation in (
            lambda d: d.pop("crypto"),
            lambda d: d.update(version=3),
            lambda d: d["crypto"]["cipher"].update(message="not-encrypted"),
            lambda d: d.update(pubkey="00"),
            lambda d: d.update(pubkey="00" * 48),
        ):
            key = self.keystore(1, mutation=mutation)
            with self.subTest(mutation=repr(mutation)), self.assertRaises(PublicKeystoreExportError):
                public_pubkey_from_encrypted_keyfile(key)

    def test_world_readable_keystore_or_directory_rejected(self):
        key = self.keystore()
        key.chmod(0o644)
        with self.assertRaises(PublicKeystoreExportError):
            self.go()
        key.chmod(0o600)
        self.keys.chmod(0o755)
        with self.assertRaises(PublicKeystoreExportError):
            self.go()

    def test_invalid_withdrawal_address_or_operator_label_rejected(self):
        self.keystore()
        with self.assertRaises(PublicKeystoreExportError):
            export_public(self.keys, operator_id="bad id",
                          withdrawal_address=self.address, output=self.output)
        with self.assertRaises(PublicKeystoreExportError):
            export_public(self.keys, operator_id="independent-one",
                          withdrawal_address="0x" + "0" * 40, output=self.output)

    def test_symlink_keystore_and_symlink_operator_dir_rejected(self):
        file = self.keystore()
        link = self.keys / "keystore-copy.json"
        link.symlink_to(file)
        with self.assertRaises(PublicKeystoreExportError):
            self.go()
        link.unlink()
        linked = self.root / "linked-private"
        linked.symlink_to(self.keys, target_is_directory=True)
        with self.assertRaises(PublicKeystoreExportError):
            export_public(linked, operator_id="independent-one",
                          withdrawal_address=self.address, output=self.output)

    def test_public_output_never_overwritten(self):
        self.keystore()
        self.go()
        before = self.output.read_bytes()
        with self.assertRaises(PublicKeystoreExportError):
            self.go()
        self.assertEqual(self.output.read_bytes(), before)

    def test_nested_world_access_is_rejected(self):
        d = self.keys / "validator-one"
        d.mkdir(mode=0o755)
        f = self.keystore(folder=d)
        f.rename(d / "voting-keystore.json")
        with self.assertRaises(PublicKeystoreExportError):
            self.go()


if __name__ == "__main__":
    unittest.main()
