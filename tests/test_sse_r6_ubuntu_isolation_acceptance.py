"""R6 source-only Ubuntu isolation acceptance tests (no account changes).

Run safely on Windows and Linux; actual --layout/--as-ui privileges are
separate Ubuntu operator acceptance steps, not simulated success claims.
"""
from __future__ import annotations

import errno
import json
import os
import stat
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))

import sse_r6_ubuntu_isolation_acceptance as check


def fake(uid,gid,mode,size=0):
    return SimpleNamespace(st_uid=uid,st_gid=gid,st_mode=mode,st_size=size)


MON=1001
AGENT=1002
PRIVATE_G=1101
DISPLAY_G=1102


def metadata(**overrides):
    params=dict(monitor_uid=MON,agent_uid=AGENT,monitor_gid=PRIVATE_G,
        display_gid=DISPLAY_G,agent_groups=[1200,DISPLAY_G],
        private_dir=fake(MON,PRIVATE_G,stat.S_IFDIR|0o700),
        journal=fake(MON,PRIVATE_G,stat.S_IFREG|0o600),
        display_dir=fake(MON,DISPLAY_G,stat.S_IFDIR|0o750),
        display_file=fake(MON,DISPLAY_G,stat.S_IFREG|0o640,size=512))
    params.update(overrides)
    return params


class UbuntuIsolationAcceptanceTests(unittest.TestCase):
    def test_preview_is_host_independent_and_never_touches_permissions(self):
        with patch.object(check,"check_layout",
                          side_effect=AssertionError("no layout allowed")), \
             patch.object(check,"check_ui_access",
                          side_effect=AssertionError("no UI allowed")), \
             redirect_stdout(StringIO()) as output:
            self.assertEqual(check.main([]),0)
        plan=json.loads(output.getvalue())
        self.assertFalse(plan["linuxHostVerified"])
        self.assertFalse(plan["systemChangesMade"])
        self.assertFalse(plan["ethereumTransactionsSent"])

    def test_expected_private_and_public_file_modes(self):
        result=check.verify_layout(**metadata())
        self.assertTrue(result["linuxUserSeparationVerified"])
        self.assertFalse(result["uiKernelAccessProbed"])
        self.assertFalse(result["privateJournalShared"])

    def test_bad_private_and_shared_modes_fail_closed(self):
        for field,uid,gid,kind,mode in [
            ("private_dir",MON,PRIVATE_G,stat.S_IFDIR,0o750),
            ("journal",MON,PRIVATE_G,stat.S_IFREG,0o640),
            ("display_dir",MON,DISPLAY_G,stat.S_IFDIR,0o770),
            ("display_file",MON,DISPLAY_G,stat.S_IFREG,0o644),
            ("display_file",MON,PRIVATE_G,stat.S_IFREG,0o640),
            ("journal",AGENT,PRIVATE_G,stat.S_IFREG,0o600),
        ]:
            with self.subTest(field=field,mode=mode,gid=gid),self.assertRaises(check.IsolationError):
                check.verify_layout(**metadata(**{field:fake(uid,gid,kind|mode)}))

    def test_ui_in_private_monitor_group_is_rejected(self):
        with self.assertRaisesRegex(check.IsolationError,"private monitor group"):
            check.verify_layout(**metadata(agent_groups=[DISPLAY_G,PRIVATE_G]))
        with self.assertRaises(check.IsolationError):
            check.verify_layout(**metadata(monitor_uid=AGENT))

    def test_big_display_is_refused(self):
        with self.assertRaises(check.IsolationError):
            check.verify_layout(**metadata(
                display_file=fake(MON,DISPLAY_G,stat.S_IFREG|0o640,size=65537)))

    def test_kernel_level_access_probes_only_readonly_opens(self):
        calls=[]
        def fake_open(path):
            calls.append(str(path))
            if path in ("private-dir","private-journal"):
                raise PermissionError(errno.EACCES,"denied",path)
        with patch.object(check,"_open_readonly_no_follow",side_effect=fake_open):
            result=check.verify_actual_ui_access(
                actual_uid=AGENT,expected_uid=AGENT,
                display_groups=[DISPLAY_G],expected_display_gid=DISPLAY_G,
                public_path="public",private_dir="private-dir",
                private_path="private-journal")
        self.assertEqual(calls,["public","private-dir","private-journal"])
        self.assertTrue(result["uiPrivateJournalOpenDenied"])
        self.assertTrue(result["uiPublicSnapshotReadable"])
        self.assertFalse(result["sensitiveFileContentsRead"])

    def test_running_as_root_or_wrong_identity_refuses_before_file_open(self):
        for uid,groups in [(0,[DISPLAY_G]),(AGENT+2,[DISPLAY_G]),(AGENT,[])]:
            with self.subTest(uid=uid), \
                 patch.object(check,"_open_readonly_no_follow",
                              side_effect=AssertionError("unexpected file open")):
                with self.assertRaises(check.IsolationError):
                    check.verify_actual_ui_access(
                        actual_uid=uid,expected_uid=AGENT,
                        display_groups=groups,expected_display_gid=DISPLAY_G,
                        public_path="public",private_dir="private-dir",
                        private_path="private-journal")

    def test_missing_private_file_is_not_proof_of_denial(self):
        def opening(path):
            if path == "private-dir":
                raise FileNotFoundError(errno.ENOENT,"absent",path)
        with patch.object(check,"_open_readonly_no_follow",side_effect=opening):
            with self.assertRaisesRegex(check.IsolationError,"unproven"):
                check.verify_actual_ui_access(
                    actual_uid=AGENT,expected_uid=AGENT,
                    display_groups=[DISPLAY_G],expected_display_gid=DISPLAY_G,
                    public_path="public",private_dir="private-dir",
                    private_path="private-journal")

    def test_able_to_open_private_journal_is_security_failure(self):
        with patch.object(check,"_open_readonly_no_follow",return_value=None):
            with self.assertRaisesRegex(check.IsolationError,"SECURITY FAILURE"):
                check.verify_actual_ui_access(
                    actual_uid=AGENT,expected_uid=AGENT,
                    display_groups=[DISPLAY_G],expected_display_gid=DISPLAY_G,
                    public_path="public",private_dir="private-dir",
                    private_path="private-journal")

    def test_snapshot_unreadable_is_not_accepted(self):
        with patch.object(check,"_open_readonly_no_follow",
                          side_effect=PermissionError(errno.EACCES,"denied")):
            with self.assertRaisesRegex(check.IsolationError,"cannot read"):
                check.verify_actual_ui_access(
                    actual_uid=AGENT,expected_uid=AGENT,
                    display_groups=[DISPLAY_G],expected_display_gid=DISPLAY_G,
                    public_path="public",private_dir="private-dir",
                    private_path="private-journal")


if __name__=="__main__":
    unittest.main()
