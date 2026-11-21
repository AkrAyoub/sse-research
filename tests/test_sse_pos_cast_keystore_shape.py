"""R28 safe keystore schema introspection fixtures; no live key unlock."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sse_pos_cast_keystore_shape import ShapeProbeError, shape_only


class ExistingCastKeystoreSchemaOnlyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name) / "private"
        self.directory.mkdir(mode=0o700)
        self.file = self.directory / "existing"
        self.payload = {
            "version": 3,
            "id": "test-fixture-id",
            "address": "a" * 40,
            "crypto": {
                "cipher": "aes-128-ctr",
                "ciphertext": "SENSITIVE_NEVER_PRINT_THIS_1" * 6,
                "cipherparams": {"iv": "SENSITIVE_NEVER_PRINT_THIS_2"},
                "kdf": "scrypt",
                "kdfparams": {"salt": "SENSITIVE_NEVER_PRINT_THIS_3"},
                "mac": "SENSITIVE_NEVER_PRINT_THIS_4",
            },
        }
        self.write()

    def write(self):
        self.file.write_text(json.dumps(self.payload), encoding="utf-8")
        self.file.chmod(0o600)

    def test_names_only_never_ciphertext_or_address_value(self):
        s = json.dumps(shape_only(self.directory), sort_keys=True)
        self.assertIn("topLevelFieldNames", s)
        self.assertIn("encryptionFieldNames", s)
        self.assertIn('"validEncryptionEnvelopeProved": false', s)
        for secret in ("SENSITIVE_NEVER_PRINT", "test-fixture-id", "a" * 40):
            self.assertNotIn(secret, s)
        self.assertTrue(shape_only(self.directory)["versionIsIntegerThree"])

    def test_optional_address_missing_reports_shape_without_inventing_one(self):
        del self.payload["address"]
        self.write()
        report = shape_only(self.directory)
        self.assertFalse(report["addressIsText"])
        self.assertNotIn("address", report["topLevelFieldNames"])
        self.assertFalse(report["validEncryptionEnvelopeProved"])

    def test_extra_metadata_reported_only_by_field_name(self):
        self.payload["metadata"] = {
            "secretText": "SENSITIVE_NEVER_PRINT_THIS_5"
        }
        self.write()
        s = json.dumps(shape_only(self.directory))
        self.assertIn("metadata", s)
        self.assertNotIn("secretText", s)
        self.assertNotIn("SENSITIVE_NEVER_PRINT", s)

    def test_bad_directory_mode_or_file_mode_refused(self):
        self.directory.chmod(0o755)
        with self.assertRaises(ShapeProbeError):
            shape_only(self.directory)
        self.directory.chmod(0o700)
        self.file.chmod(0o644)
        with self.assertRaises(ShapeProbeError):
            shape_only(self.directory)

    def test_keystore_symlink_refused(self):
        self.file.unlink()
        self.file.symlink_to("/etc/hosts")
        with self.assertRaises(ShapeProbeError):
            shape_only(self.directory)

    def test_duplicate_or_unsafe_json_field_names_refused(self):
        self.file.write_text(
            '{"version":3,"version":3,"crypto":{"ciphertext":"' +
            "f" * 128 + '"}}', encoding="utf-8"
        )
        # The parser detects duplicate keys, while the public-facing probe
        # intentionally masks parser detail behind a safe, generic error.
        with self.assertRaisesRegex(
            ShapeProbeError, "^encrypted keystore is not valid unique-key JSON$"
        ):
            shape_only(self.directory)
        self.file.write_text(json.dumps({
            "not-safe-key-with-hyphens": "SENSITIVE_NEVER_PRINT" * 6
        }), encoding="utf-8")
        with self.assertRaises(ShapeProbeError):
            shape_only(self.directory)


if __name__ == "__main__":
    unittest.main()
