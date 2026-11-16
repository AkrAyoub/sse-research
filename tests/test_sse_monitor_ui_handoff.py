"""R6 offline smoke checks: group-only public handoff, isolated role units.

No systemd or VM changes, no signer, no on-chain transaction. POSIX-only
file mode checks run on Linux/macOS and are skipped in Windows Python.
"""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout,redirect_stderr
from io import StringIO

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
sys.path.insert(0,str(ROOT/"tests"))

from test_sse_monitor_public_snapshot import MONITOR, NODE, review
from sse_monitor_public_snapshot import (
    SnapshotError,read_snapshot,write_snapshot)
from sse_monitor_ui_handoff_plan import render_handoff_plan,main

NODE_ROLES={"schema":"sse-node-roles-v1","nodeId":NODE,
            "roles":["provider","monitor","observer"],
            "wallets":{"provider":"0x"+"11"*20,"monitor":MONITOR}}
ARGS={
    "python":"/opt/sse/runtime/abcdef/bin/python",
    "checkout":"/opt/sse/releases/abcdef",
    "manifest":"/etc/sse/node-roles.json",
    "journal":"/var/lib/sse-monitor/events.sqlite",
    "rpc_url":"http://127.0.0.1:8545",
    "settlement":"0x"+"33"*20,
    "chain_id":31337,
    "start_block":12,
}


class HandoffUnitTests(unittest.TestCase):
    def test_service_timer_and_node_dropin_preserve_separate_users(self):
        plan=render_handoff_plan(NODE_ROLES,**ARGS)
        self.assertEqual(plan["kind"],"SSE_R6_MONITOR_UI_ISOLATED_HANDOFF_PLAN")
        self.assertEqual(set(plan["units"]),{
            "sse-monitor-review-export.service",
            "sse-monitor-review-export.timer",
            "sse-vm-role-agent.service.d/20-monitor-display.conf"})
        service=plan["units"]["sse-monitor-review-export.service"]
        timer=plan["units"]["sse-monitor-review-export.timer"]
        dropin=plan["units"]["sse-vm-role-agent.service.d/20-monitor-display.conf"]
        for item in ("Type=oneshot","User=ssemonitor",
                     "Group=ssemonitor-display",
                     "RuntimeDirectory=sse-monitor-display",
                     "RuntimeDirectoryMode=0750",
                     "RuntimeDirectoryPreserve=yes",
                     "--review","--shared-display-group-read",
                     "--export-review-snapshot /run/sse-monitor-display/tasks.json",
                     "--journal /var/lib/sse-monitor/events.sqlite",
                     "NoNewPrivileges=yes","ReadWritePaths=/run/sse-monitor-display"):
            self.assertIn(item,service)
        self.assertIn("OnUnitActiveSec=45s",timer)
        self.assertIn("Persistent=no",timer)
        self.assertIn("Unit=sse-monitor-review-export.service",timer)
        self.assertIn("SupplementaryGroups=ssemonitor-display",dropin)
        self.assertIn("SSE_MONITOR_WORK_SNAPSHOT_FILE=/run/sse-monitor-display/tasks.json",dropin)
        self.assertIn("SSE_MONITOR_WALLET="+MONITOR,dropin)
        self.assertNotIn("--execute",service)
        self.assertNotIn("--capture",service)
        self.assertNotIn("--watch",service)
        self.assertNotIn("monitor-vote",service)
        self.assertFalse(plan["privateMonitorJournalShared"])
        self.assertFalse(plan["privateSigningKeysShared"])
        self.assertFalse(plan["servicesStarted"])
        self.assertFalse(plan["unitFilesWritten"])
        self.assertFalse(plan["ethereumTransactionsSent"])

    def test_node_without_monitor_fails_no_handoff(self):
        without={"schema":"sse-node-roles-v1","nodeId":NODE,
                 "roles":["provider","observer"],
                 "wallets":{"provider":NODE_ROLES["wallets"]["provider"]}}
        with self.assertRaises(ValueError):
            render_handoff_plan(without,**ARGS)

    def test_unsafe_rpc_path_and_refresh_refused(self):
        bad=[
            {"checkout":"/opt/sse/../etc"},
            {"journal":"/tmp/public.sqlite"},
            {"rpc_url":"http://public.example:8545"},
            {"rpc_url":"http://127.0.0.1:8545;reboot"},
            {"python":"python3"},
            {"chain_id":0},
            {"refresh_seconds":121},
            {"refresh_seconds":0},
            {"refresh_seconds":True},
            {"refresh_seconds":1.5},
        ]
        for patch_args in bad:
            with self.subTest(patch_args=patch_args),self.assertRaises((ValueError,TypeError)):
                render_handoff_plan(NODE_ROLES,**{**ARGS,**patch_args})

    def test_pure_cli_only_prints_draft_units(self):
        with tempfile.TemporaryDirectory() as td:
            manifest=Path(td)/"node.json"
            manifest.write_text(json.dumps(NODE_ROLES))
            args=[
                "--roles-file",str(manifest),
                "--python",ARGS["python"],
                "--checkout",ARGS["checkout"],
                "--manifest",ARGS["manifest"],
                "--journal",ARGS["journal"],
                "--rpc-url",ARGS["rpc_url"],
                "--settlement",ARGS["settlement"],
                "--chain-id",str(ARGS["chain_id"]),
                "--start-block",str(ARGS["start_block"])
            ]
            with redirect_stdout(StringIO()) as stdout:
                self.assertEqual(main(args),0)
            data=json.loads(stdout.getvalue())
            self.assertEqual(len(data["units"]),3)
            self.assertFalse(data["unitFilesWritten"])
            self.assertFalse(data["servicesStarted"])
            self.assertFalse(data["automaticVotesEnabled"])


class GroupSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir=Path(self.temp.name)
        self.file=self.dir/"tasks.json"

    def test_default_remains_strictly_private(self):
        write_snapshot(self.file,review())
        self.assertEqual(
            len(read_snapshot(self.file,node_id=NODE,monitor_address=MONITOR)["tasks"]),2)
        if os.name=="posix":
            self.assertEqual(stat.S_IMODE(self.file.stat().st_mode),0o600)

    def test_reject_shared_read_without_posix_or_suitable_directory(self):
        # Default temporary dirs are 0700 and must reject cross-user export.
        with self.assertRaises(SnapshotError):
            write_snapshot(self.file,review(),shared_group_read=True)
        self.assertFalse(self.file.exists())

    @unittest.skipUnless(os.name=="posix","POSIX group mode acceptance requires Linux/macOS")
    def test_explicit_group_public_only_export_uses_0640(self):
        os.chmod(self.dir,0o750)
        published=write_snapshot(self.file,review(),shared_group_read=True)
        self.assertEqual(stat.S_IMODE(self.file.stat().st_mode),0o640)
        self.assertEqual(self.file.stat().st_gid,os.getegid())
        self.assertEqual(read_snapshot(self.file,node_id=NODE,monitor_address=MONITOR),
                         published)
        self.assertNotIn("proposal",self.file.read_text())

    @unittest.skipUnless(os.name=="posix","POSIX group mode acceptance requires Linux/macOS")
    def test_group_writable_or_world_accessible_directory_refused(self):
        for mode in (0o770,0o755,0o775,0o777,0o700):
            os.chmod(self.dir,mode)
            with self.subTest(mode=mode),self.assertRaises(SnapshotError):
                write_snapshot(self.file,review(),shared_group_read=True)
            self.assertFalse(self.file.exists())
        os.chmod(self.dir,0o750)
        with patch("sse_monitor_public_snapshot.os.getegid",
                   return_value=os.getegid()+500):
            with self.assertRaises(SnapshotError):
                write_snapshot(self.file,review(),shared_group_read=True)

    def test_type_flag_fails_closed(self):
        for malformed in ("yes",1,None,[]):
            with self.subTest(flag=malformed),self.assertRaises(SnapshotError):
                write_snapshot(self.file,review(),shared_group_read=malformed)
        self.assertFalse(self.file.exists())


if __name__=="__main__":
    unittest.main()
