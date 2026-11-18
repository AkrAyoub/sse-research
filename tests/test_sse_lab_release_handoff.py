"""Offline tests for the SSH release handoff; no actual SSH or remote VM."""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_lab_release_handoff as h


def git(repo: Path, *arguments: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *arguments],
                          check=True, capture_output=True, text=True).stdout.strip()


class ReleaseHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        git(self.source, "init", "-q")
        git(self.source, "config", "user.name", "SSE Test")
        git(self.source, "config", "user.email", "sse@example.invalid")
        (self.source / "requirements.txt").write_text("pycryptodome==3.23.0\n")
        (self.source / "marker.txt").write_text("public approved source")
        git(self.source, "add", ".")
        git(self.source, "commit", "-qm", "safe release")
        self.revision = git(self.source, "rev-parse", "HEAD")
        self.namespace = {"__name__": "safe_test_receiver"}
        exec(h.RECEIVER_SCRIPT, self.namespace)
        self.receive = self.namespace["receive_release"]

    def test_verified_source_handoff_preserves_git_revision(self):
        payload = h.package_release(self.source, self.revision)
        self.assertLess(len(payload), h.MAX_BYTES)
        target_home = self.root / "receiver"
        target_home.mkdir()
        result = self.receive(payload, hashlib.sha256(payload).hexdigest(),
                              self.revision, target_home, install=False)
        self.assertEqual(result["revision"], self.revision)
        self.assertFalse(result["githubCredentialsInstalled"])
        self.assertFalse(result["walletKeysInstalled"])
        self.assertFalse(result["ethereumTransactionsSent"])
        self.assertFalse(result["pythonEnvironmentInstalled"])
        self.assertEqual(git(target_home / "sse-research", "rev-parse", "HEAD"), self.revision)
        self.assertEqual((target_home / "sse-research" / "marker.txt").read_text(),
                         "public approved source")
        with self.assertRaises(ValueError):
            self.receive(payload, hashlib.sha256(payload).hexdigest(),
                         self.revision, target_home, install=False)

    def test_modified_or_wrong_revision_rejected(self):
        with self.assertRaises(h.RelayError):
            h.package_release(self.source, "0" * 40)
        (self.source / "marker.txt").write_text("tampered")
        with self.assertRaises(h.RelayError):
            h.package_release(self.source, self.revision)

    def test_tampered_bytes_refused_before_extraction(self):
        payload = h.package_release(self.source, self.revision)
        target_home = self.root / "receiver"
        target_home.mkdir()
        with self.assertRaises(ValueError):
            self.receive(payload + b"tamper", hashlib.sha256(payload).hexdigest(),
                         self.revision, target_home, install=False)
        self.assertFalse((target_home / "sse-research").exists())

    def test_archive_path_traversal_refused(self):
        blob = io.BytesIO()
        with tarfile.open(fileobj=blob, mode="w:gz") as tar:
            body = b"bad"
            member = tarfile.TarInfo("sse-research/../../escape.txt")
            member.size = len(body)
            tar.addfile(member, io.BytesIO(body))
        payload = blob.getvalue()
        target_home = self.root / "receiver"
        target_home.mkdir()
        with self.assertRaises(ValueError):
            self.receive(payload, hashlib.sha256(payload).hexdigest(),
                         self.revision, target_home, install=False)
        self.assertFalse((self.root / "escape.txt").exists())

    @unittest.skipUnless(os.name == "posix", "POSIX SSH-key ownership/mode semantics require Ubuntu")
    def test_private_ip_role_allowlist_and_key_permissions(self):
        key = self.root / "private-ssh-key"
        key.write_text("not a real key, dry-run validation only")
        key.chmod(0o600)
        self.assertEqual(h.validated_destination(
            "10.50.56.30", "ayoubakrvm9999", key, "provider,monitor"),
            ("ayoubakrvm9999@10.50.56.30", ["provider", "monitor"]))
        for ip in ("127.0.0.1", "8.8.8.8", "169.254.1.1"):
            with self.subTest(ip=ip), self.assertRaises(h.RelayError):
                h.validated_destination(ip, "ubuntu", key, "provider")
        for roles in ("monitor,monitor", "provider,unknown", ""):
            with self.subTest(roles=roles), self.assertRaises(h.RelayError):
                h.validated_destination("10.50.56.30", "ubuntu", key, roles)
        key.chmod(0o644)
        with self.assertRaises(h.RelayError):
            h.validated_destination("10.50.56.30", "ubuntu", key, "provider")

    @unittest.skipUnless(os.name == "posix", "POSIX SSH-key ownership/mode semantics require Ubuntu")
    def test_dry_run_uses_no_ssh(self):
        key = self.root / "ssh-key"
        key.write_text("test-only")
        key.chmod(0o600)
        result = h.transfer(self.source, self.revision, "10.50.56.30",
                            "ubuntu", key, "provider", False)
        self.assertEqual(result["mode"], "DRY_RUN")
        self.assertFalse(result["githubCredentialsRequiredOnDestination"])
        self.assertGreater(result["bundleBytes"], 0)


if __name__ == "__main__":
    unittest.main()
