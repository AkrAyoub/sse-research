"""Evidence index never declares it safe to destroy VM and never reads keys."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sse_experiment_evidence import EvidenceError, prepare, inspect_file, git_sha


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)],
                       check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email",
                        "sse@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name",
                        "SSE Test"], check=True)
        (self.root / "test.txt").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "test"], check=True)
        (self.root / "run.log").write_text("816 tests recorded\n", encoding="utf-8")

    def test_manifest_binds_hash_and_revision(self):
        doc = prepare(self.root, run_id="wpr9-20261118",
                      environment="windows-local", paths=["run.log"], now=1795000000)
        self.assertEqual(doc["sourceGitSha"], git_sha(self.root))
        self.assertEqual(doc["files"][0]["relativePath"], "run.log")
        self.assertEqual(len(doc["files"][0]["sha256"]), 64)
        self.assertFalse(doc["chainStateBackedUp"])
        self.assertFalse(doc["rawEvidenceBackedUp"])
        self.assertFalse(doc["acceptanceReviewed"])

    def test_path_traversal_and_secret_filename_rejected(self):
        for name in ("../bad.log", "wallet.json", ".env", "private-key.txt",
                     "run.py", "/tmp/bad.log"):
            with self.subTest(name=name), self.assertRaises(EvidenceError):
                inspect_file(self.root, name)

    def test_symlinks_rejected(self):
        out = self.root / "source.log"
        try:
            out.symlink_to(self.root / "run.log")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks cannot be created on this host")
        with self.assertRaises(EvidenceError):
            inspect_file(self.root, "source.log")

    def test_duplicate_and_unknown_environment_refused(self):
        with self.assertRaises(EvidenceError):
            prepare(self.root, run_id="run001", environment="unknown",
                    paths=["run.log"])
        with self.assertRaises(EvidenceError):
            prepare(self.root, run_id="run001", environment="ubuntu-vm",
                    paths=["run.log", "run.log"])


if __name__ == "__main__":
    unittest.main()
