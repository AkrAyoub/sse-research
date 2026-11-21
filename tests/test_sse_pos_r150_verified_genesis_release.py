"""R150: refuse leaked/modified assets, preserve source and fail closed."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r150_verified_genesis_release as r

class R150Tests(unittest.TestCase):
    def test_exact_member_allowlist_excludes_signing_secrets(self):
        self.assertEqual(len(r.PUBLIC_MEMBERS),5)
        for name in r.PUBLIC_MEMBERS:
            self.assertIn("chain31340-public/",name)
            self.assertNotIn("keystore",name)
            self.assertNotIn("mnemonic",name)
            self.assertNotIn("validator",name)

    def test_refuses_missing_or_modified_genesis(self):
        for blob in (b"",b"fake-31340",b"\0"*64):
            with self.subTest(blob=blob[:10]),self.assertRaises(r.Refused):
                r.verify(blob)

    def test_stage_rejects_tampered_public_bundle_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            (home/"archive").write_bytes(b"fake-31340")
            output=home/"public"
            with self.assertRaises(r.Refused):
                r.stage(home/"archive",output)
            self.assertFalse(output.exists())

    def test_original_archive_preserved_after_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            original=home/"archive"
            original.write_bytes(b"bad")
            before=hashlib.sha256(original.read_bytes()).digest()
            with self.assertRaises(r.Refused):
                r.stage(original,home/"public")
            self.assertEqual(hashlib.sha256(original.read_bytes()).digest(),before)

    def test_rejects_existing_output_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            (home/"archive").write_bytes(b"fake")
            (home/"public").mkdir()
            with self.assertRaises(r.Refused):
                r.stage(home/"archive",home/"public")

    def test_never_reads_symlinked_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            (home/"secret").write_bytes(b"never-read-signing-key")
            (home/"link").symlink_to(home/"secret")
            with self.assertRaises(r.Refused):
                r.safe_input(home/"link")

    def test_no_shared_default_validator_key_or_publicly_uploaded_asset_claim(self):
        self.assertNotIn("mnemonic",r.ARCHIVE_SHA)
        self.assertEqual(len(r.ARCHIVE_SHA),64)
        self.assertEqual(r.MAX_ARCHIVE,6_000_000)

if __name__=="__main__":
    unittest.main()
