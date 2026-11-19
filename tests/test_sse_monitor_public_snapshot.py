"""R5 nonsecret monitor-to-node-console snapshot handoff tests.

No Docker, Ethereum transaction or signer keys. A review is only a current
nonexecuting RPC-derived *display*, not a monitor approval.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout,redirect_stderr
from io import StringIO

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
sys.path.insert(0,str(ROOT/"services"/"monitor-agent"))

from sse_monitor_public_snapshot import (
    SnapshotError,make_snapshot,write_snapshot,read_snapshot)
import monitor_discovery

spec=importlib.util.spec_from_file_location(
    "role_agent_snapshot_ui",ROOT/"services"/"role-agent"/"agent.py")
agent=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=agent
spec.loader.exec_module(agent)

MONITOR="0x"+"41"*20
NODE="provider-node-a"


def review():
    return {"schema":"sse-monitor-work-queue-v1","nodeId":NODE,
       "monitor":MONITOR,"cursorBlock":100,"cursorBlockHash":"0x"+"ab"*32,
       "totalNotifications":2,"visibleNotifications":2,"moreNotificationsExist":False,
       "readOnly":True,"signerLoaded":False,"transactionsSent":False,
       "autoCapturePerformed":False,"finalityVerified":False,
       "tasks":[
           {"kind":"EPOCH_ADMITTED","leaseId":8,"sequenceId":1,
            "status":"REVIEW_EVIDENCE_CAPTURE",
            "approvalRequired":True,"proposal":{
                "role":"monitor","action":"monitor-capture-once",
                "params":{"leaseId":8,"epochId":1}}},
           {"kind":"COMMITTEE_ASSIGNED","leaseId":8,"sequenceId":3,
            "status":"NO_LONGER_ACTIONABLE","proposal":None}
       ]}


class MonitorSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.file=self.dir/"status.json"

    def test_atomic_nonsecret_snapshot_discards_untrusted_proposals(self):
        status=write_snapshot(self.file,review())
        self.assertEqual(status["schema"],"sse-monitor-work-display-v1")
        self.assertFalse(status["ownerApprovalGranted"])
        self.assertFalse(status["votesSubmitted"])
        self.assertFalse(status["transactionsSent"])
        self.assertNotIn("proposal",json.dumps(status))
        self.assertEqual(len(status["tasks"]),2)
        self.assertEqual(read_snapshot(self.file,node_id=NODE,
                                       monitor_address=MONITOR),status)
        self.assertFalse(list(self.dir.glob(".sse-monitor-display-*")))

    def test_node_or_wallet_mismatch_refused(self):
        write_snapshot(self.file,review())
        with self.assertRaises(SnapshotError):
            read_snapshot(self.file,node_id="other-node",
                          monitor_address=MONITOR)
        with self.assertRaises(SnapshotError):
            read_snapshot(self.file,node_id=NODE,
                          monitor_address="0x"+"33"*20)

    def test_expired_and_clock_skewed_snapshot_refused(self):
        past=datetime.now(timezone.utc)-timedelta(seconds=300)
        write_snapshot(self.file,review(),generated_at=past)
        with self.assertRaisesRegex(SnapshotError,"expired"):
            read_snapshot(self.file,node_id=NODE,monitor_address=MONITOR)
        future=datetime.now(timezone.utc)+timedelta(minutes=10)
        write_snapshot(self.file,review(),generated_at=future)
        with self.assertRaisesRegex(SnapshotError,"clock skewed"):
            read_snapshot(self.file,node_id=NODE,monitor_address=MONITOR)

    def test_tampered_authority_flag_and_extra_fields_refused(self):
        original=write_snapshot(self.file,review())
        for mutation in (
            lambda x:x.update(transactionsSent=True),
            lambda x:x.update(ownerApprovalGranted=True),
            lambda x:x["tasks"][0].update(privateKey="danger"),
            lambda x:x.update(roleSigner="0x"+"ee"*32),
            lambda x:x.update(nodeId="unrelated-node"),
        ):
            item=json.loads(json.dumps(original))
            mutation(item)
            self.file.write_text(json.dumps(item))
            with self.subTest(item=item),self.assertRaises(SnapshotError):
                read_snapshot(self.file,node_id=NODE,monitor_address=MONITOR)

    def test_missing_file_and_symlink_refused(self):
        with self.assertRaises(SnapshotError):
            read_snapshot(self.file,node_id=NODE,monitor_address=MONITOR)
        other=self.dir/"other.json"
        other.write_text("{}")
        try:
            self.file.symlink_to(other)
        except (OSError,NotImplementedError):
            self.skipTest("symlinks unavailable in this environment")
        with self.assertRaises(SnapshotError):
            read_snapshot(self.file,node_id=NODE,monitor_address=MONITOR)

    def test_preview_without_explicit_review_cannot_write_snapshot(self):
        node={"schema":"sse-node-roles-v1","nodeId":NODE,
              "roles":["monitor","observer"],"wallets":{"monitor":MONITOR}}
        mf=self.dir/"roles.json"
        mf.write_text(json.dumps(node))
        args=["--node-roles-file",str(mf),
              "--journal",str(self.dir/"event.sqlite"),
              "--rpc-url","http://127.0.0.1:8545",
              "--settlement","0x"+"12"*20,
              "--chain-id","31337","--start-block","0",
              "--export-review-snapshot",str(self.file)]
        with patch.object(monitor_discovery,"RPC",
                          side_effect=AssertionError("must not open RPC")), \
             redirect_stderr(StringIO()):
            self.assertEqual(monitor_discovery.main(args),1)
        self.assertFalse(self.file.exists())

    def test_explicit_review_exports_only_verified_public_results(self):
        node={"schema":"sse-node-roles-v1","nodeId":NODE,
              "roles":["monitor","observer"],"wallets":{"monitor":MONITOR}}
        mf=self.dir/"roles.json";mf.write_text(json.dumps(node))
        args=["--node-roles-file",str(mf),
              "--journal",str(self.dir/"event.sqlite"),
              "--rpc-url","http://127.0.0.1:8545",
              "--settlement","0x"+"12"*20,
              "--chain-id","31337","--start-block","0",
              "--review","--export-review-snapshot",str(self.file)]
        fake=type("FakeQueue",(),{"review":lambda self,rpc:review()})()
        with patch.object(monitor_discovery,"MonitorActionQueue",return_value=fake), \
             patch.object(monitor_discovery,"RPC",return_value=object()), \
             redirect_stdout(StringIO()):
            self.assertEqual(monitor_discovery.main(args),0)
        self.assertEqual(len(read_snapshot(self.file,node_id=NODE,
                                           monitor_address=MONITOR)["tasks"]),2)


class MonitorConsoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.path=self.dir/"snapshot.json"
        write_snapshot(self.path,review())
        self.token="q"*40
        env={"SSE_NODE_ID":NODE,"SSE_ROLES":"provider,monitor",
             "SSE_NODE_UI_TOKEN":self.token,
             "SSE_NODE_SETTINGS_FILE":str(self.dir/"preferences.json"),
             "SSE_MONITOR_WORK_SNAPSHOT_FILE":str(self.path),
             "SSE_MONITOR_WALLET":MONITOR}
        self.conf=agent.config(env)
        self.conf["port"]=0
        self.server=agent.make_server(self.conf)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.close)
        self.url="http://127.0.0.1:"+str(self.server.server_address[1])

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def get(self,token=None,origin=None):
        headers={}
        if token is not None:
            headers["Authorization"]="Bearer "+token
        if origin is not None:
            headers["Origin"]=origin
        request=urllib.request.Request(
            self.url+"/v1/monitor-work",headers=headers,method="GET")
        try:
            with urllib.request.urlopen(request,timeout=3) as response:
                return response.status,json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code,json.load(exc)

    def test_node_ui_authenticated_monitor_review_nonexecuting(self):
        code,payload=self.get(self.token)
        self.assertEqual(code,200)
        self.assertEqual(payload["nodeId"],NODE)
        self.assertEqual(len(payload["tasks"]),2)
        self.assertTrue(payload["displayOnly"])
        self.assertFalse(payload["ownerApprovalGranted"])
        self.assertFalse(payload["signerLoaded"])
        with urllib.request.urlopen(self.url+"/ui",timeout=3) as resp:
            html=resp.read().decode("utf-8")
        self.assertIn("Monitor work review",html)
        self.assertIn("/v1/monitor-work",html)

    def test_unauthenticated_cross_origin_and_wrong_token_refused(self):
        for kwargs in ({},{"token":"bad"*11},
                       {"token":self.token,"origin":"https://attacker.example"}):
            with self.subTest(kwargs=kwargs):
                status,payload=self.get(**kwargs)
                self.assertEqual(status,403)
                self.assertNotIn("tasks",payload)

    def test_stale_snapshot_returns_service_unavailable_not_old_tasks(self):
        write_snapshot(self.path,review(),
                       generated_at=datetime.now(timezone.utc)-timedelta(hours=2))
        code,payload=self.get(self.token)
        self.assertEqual(code,503)
        self.assertNotIn("tasks",payload)
        self.assertIn("stale",payload["error"])

    def test_monitor_display_config_requires_local_role_token_and_wallet(self):
        base={"SSE_NODE_ID":NODE,"SSE_ROLES":"provider,monitor",
              "SSE_MONITOR_WORK_SNAPSHOT_FILE":str(self.path),
              "SSE_MONITOR_WALLET":MONITOR}
        for change in (
            {"SSE_ROLES":"observer"},
            {"SSE_MONITOR_WALLET":""},
            {"SSE_MONITOR_WALLET":"0x"+"00"*20},
            {"SSE_MONITOR_WORK_SNAPSHOT_FILE":"relative/snapshot.json"},
        ):
            env={**base,**change}
            with self.subTest(change=change),self.assertRaises(ValueError):
                agent.config(env)
        with self.assertRaises(ValueError):
            agent.config({**base,"SSE_NODE_UI_TOKEN":self.token})


if __name__=="__main__":
    unittest.main()
