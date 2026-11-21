"""R66 stopped-owner recovery snapshot source-only tests.

Temporary tiny synthetic FILE fixtures used solely for unit tests, never claimed
as real chain data or as a usable original validator backup. No actual owner
database, Docker process or private signer accessed by test suite.
"""
from pathlib import Path
import os
import stat
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r66_consistent_owner_recovery_snapshot as m

ORIGINAL=("sse31340-g2-el-r40","sse31340-g2-bn","sse31340-g2-vc")

class R66ConsistentOwnerSnapshotTests(unittest.TestCase):
    def sample(self,tmp:Path)->Path:
        owner=tmp/"sse-r35-chain31340-g2-private"
        owner.mkdir(mode=0o700)
        d=owner/"vc"
        d.mkdir(mode=0o700)
        f=d/"slashing_protection.sqlite"
        f.write_bytes(b"TEST_FIXTURE_NEVER_REAL_SIGNER\n")
        f.chmod(0o600)
        (owner/"genesis.ssz").write_bytes(b"TEST_FIXTURE_ORIGINAL_GENESIS_NOT_REAL")
        return owner

    def test_snapshot_requires_exact_three_original_stopped_clients(self):
        class FakeProc:
            returncode=0
            stdout="false\n"
        import subprocess
        with patch.object(subprocess,"run",return_value=FakeProc()) as run:
            m.require_stopped_docker(ORIGINAL)
        self.assertEqual(run.call_count,3)
        for call in run.call_args_list:
            self.assertIn("{{.State.Running}}",call.args[0])

    def test_snapshot_refuses_unstopped_signer(self):
        import subprocess
        class FakeProc:
            returncode=0
            stdout="true\n"
        with patch.object(subprocess,"run",return_value=FakeProc()):
            with self.assertRaises(m.R66Refused):
                m.require_stopped_docker(ORIGINAL)

    def test_snapshot_refuses_any_other_validator_names(self):
        with self.assertRaises(m.R66Refused):
            m.require_stopped_docker(("sse31340-g2-el-r40","sse31340-g2-bn","second-vc"))

    def test_original_owner_tree_must_be_0700(self):
        with tempfile.TemporaryDirectory() as temp:
            owner=self.sample(Path(temp))
            owner.chmod(0o755)
            with self.assertRaises(m.R66Refused):
                m.checked_files(owner)

    def test_original_owner_tree_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            owner=self.sample(Path(temp))
            (owner/"outside").symlink_to("/etc/passwd")
            with self.assertRaises(m.R66Refused):
                m.checked_files(owner)

    def test_archive_rejects_special_types_and_parent_traversal(self):
        for member,typ in (("owner-private/../escape",tarfile.REGTYPE),
                           ("owner-private/key",tarfile.SYMTYPE)):
            entry=tarfile.TarInfo(member)
            entry.type=typ
            with self.subTest(path=member),self.assertRaises(m.R66Refused):
                m.safe_tar_entry(entry)

    def test_real_local_snapshot_integrity_on_tiny_fake_fixtures(self):
        with tempfile.TemporaryDirectory() as temp:
            owner=self.sample(Path(temp))
            with patch.object(m,"require_stopped_docker",return_value=None):
                result=m.snapshot_consistent_original_state(owner,ORIGINAL)
            self.assertTrue(result["consistentStoppedOwnerSnapshotVerified"])
            self.assertTrue(result["recoveryArchiveLocalPermissionMode0600"])
            self.assertTrue(result["recoveryDirectoryLocalPermissionMode0700"])
            self.assertTrue(result["archiveContainsSensitiveSignerMaterial"])
            self.assertTrue(result["archiveMustBeEncryptedAndBackedUpOfflineByOwner"])
            self.assertEqual(result["originalOwnerFilesVerified"],2)
            private=owner.parent/m.SNAPSHOT_DIR_NAME
            self.assertEqual(stat.S_IMODE(private.stat().st_mode),0o700)
            archive=private/m.ARCHIVE_NAME
            self.assertEqual(stat.S_IMODE(archive.stat().st_mode),0o600)
            with tarfile.open(archive,"r:") as tf:
                names=tf.getnames()
            self.assertIn("owner-private/vc/slashing_protection.sqlite",names)
            self.assertNotIn(str(owner),names)
            self.assertEqual((owner/"vc"/"slashing_protection.sqlite").read_bytes(),
                             b"TEST_FIXTURE_NEVER_REAL_SIGNER\n")

    def test_duplicate_backup_never_overwrites_existing_recovery_state(self):
        with tempfile.TemporaryDirectory() as temp:
            owner=self.sample(Path(temp))
            with patch.object(m,"require_stopped_docker",return_value=None):
                m.snapshot_consistent_original_state(owner,ORIGINAL)
                with self.assertRaises(m.R66Refused):
                    m.snapshot_consistent_original_state(owner,ORIGINAL)

    def test_snapshot_never_displays_sensitive_files_or_uploads(self):
        source=(ROOT/"tools/sse_pos_r66_consistent_owner_recovery_snapshot.py").read_text()
        for forbidden in ('"ssh"', '"scp"', 'http://', 'https://',
                          'docker(["start"', 'docker(["stop"',
                          "print(file_handle.read", "print(source.read",
                          "extractall(", "tf.extract("):
            self.assertNotIn(forbidden,source)
        self.assertIn('os.O_NOFOLLOW,0o600',source)
        self.assertIn('originalOwnerDataUnmodifiedBySnapshot',source)

    def test_existing_user_root_copy_not_created_during_readonly_r65_plan(self):
        source=(ROOT/"tools/sse_pos_r65_original_chain_native_public_p2p_migration.py").read_text()
        plan=source[source.index("def read_only_plan("):source.index("def start_if_stopped(")]
        self.assertNotIn("snapshot_consistent_original_state(",plan)
        apply=source[source.index("def apply("):source.index("def main(")]
        self.assertIn("snapshot_consistent_original_state(",apply)
        self.assertLess(apply.index('docker(["stop","--time","90",name]'),
                        apply.index('snapshot_consistent_original_state('))
        self.assertLess(apply.index('snapshot_consistent_original_state('),
                        apply.index('docker(["rename",name,PRESERVED[name]]'))

if __name__=="__main__":
    unittest.main()
