"""Pinned source release gate, untrusted branch advancement, safe rollback."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_r9_release_update as updater

A="a"*40
B="b"*40


class RevisionUpdateTests(unittest.TestCase):
    def test_expected_exact_private_origin_and_no_live_chain(self):
        plan=updater.validate_plan(
            current=A,expected_current=A,target=B,
            git_origin=updater.REMOTE,source_dirty="",
            live_rpc=False,os_native=True,is_root=False)
        self.assertEqual(plan["mode"],"DRY_RUN")
        self.assertFalse(plan["willNotModifyChainState"] is False)
        self.assertFalse(plan["ethereumTransactionsSent"])

    def test_dirty_chain_origin_or_root_refused(self):
        bad=[
            dict(source_dirty=" M contracts/SSESettlement.sol"),
            dict(live_rpc=True),
            dict(git_origin="https://evil.example/repo.git"),
            dict(is_root=True),
            dict(os_native=False),
            dict(current=B),
            dict(target="main"),
        ]
        base=dict(current=A,expected_current=A,target=B,
                  git_origin=updater.REMOTE,
                  source_dirty="",live_rpc=False,os_native=True,is_root=False)
        for changes in bad:
            with self.subTest(changes=changes),self.assertRaises(updater.UpdateError):
                updater.validate_plan(**{**base,**changes})

    def test_rollback_after_test_gate_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/".git").mkdir()
            logs=root/"logs"
            logs.mkdir()
            head=[A]
            actions=[]
            def fake_run(args, repo):
                actions.append(args)
                if args==["git","rev-parse","HEAD"]:return head[0]
                if args==["git","remote","get-url","origin"]:return updater.REMOTE
                if args==["git","status","--porcelain","--untracked-files=no"]:return ""
                if args==["git","rev-parse","FETCH_HEAD"]:return B
                if args[:3]==["git","switch","--detach"]:
                    head[0]=args[3]
                    return ""
                if args[:2]==["git","fetch"]:
                    return ""
                raise AssertionError("unexpected Git operation "+str(args))
            def fail_test(args,repo,log_dir,label):
                self.assertEqual(head[0],B)
                raise updater.UpdateError("synthetic failing security test")
            with patch.object(updater,"_ubuntu",return_value=True), \
                 patch.object(updater.os,"geteuid",return_value=1000,create=True), \
                 patch.object(updater,"_port_busy",return_value=False):
                prepared=updater.plan(root,current=A,target=B,run=fake_run)
                with self.assertRaises(updater.UpdateError):
                    updater.apply(root,prepared,log_dir=logs,
                                  run=fake_run,test=fail_test)
            self.assertEqual(head[0],A)
            self.assertIn(["git","switch","--detach",A],actions)
            self.assertNotIn(["git","reset","--hard"],actions)

    def test_reject_remote_branch_moved_after_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/".git").mkdir()
            run_calls=[]
            def fake_run(args, repo):
                run_calls.append(args)
                if args==["git","rev-parse","HEAD"]:return A
                if args==["git","remote","get-url","origin"]:return updater.REMOTE
                if args==["git","status","--porcelain","--untracked-files=no"]:return ""
                if args==["git","rev-parse","FETCH_HEAD"]:return "c"*40
                if args[:2]==["git","fetch"]:return ""
                raise AssertionError("must not checkout unapproved SHA")
            with patch.object(updater,"_ubuntu",return_value=True), \
                 patch.object(updater.os,"geteuid",return_value=1000,create=True), \
                 patch.object(updater,"_port_busy",return_value=False):
                prepared=updater.plan(root,current=A,target=B,run=fake_run)
                with self.assertRaises(updater.UpdateError):
                    updater.apply(root,prepared,log_dir=root,
                                  run=fake_run)
            self.assertFalse(any(args[:2]==["git","switch"] for args in run_calls))

    def test_no_docker_or_wallet_actions_anywhere(self):
        source=(ROOT/"tools"/"sse_r9_release_update.py").read_text()
        for text in ("docker compose up","cast send","git reset --hard",
                     "git clean -fd","git push","sudo tailscale up"):
            self.assertNotIn(text,source)


if __name__=="__main__":
    unittest.main()
