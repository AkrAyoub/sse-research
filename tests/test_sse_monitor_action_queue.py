"""R5: owner-reviewed, nonexecuting monitor work queue regressions.

The stored assignment/epoch event ledger is read via SQLite mode=ro;
review refuses stale, wrong-monitor, or reorganized RPC views. No signing,
container, network deployment or Ethereum transaction is performed.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout,redirect_stderr
from copy import deepcopy
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
sys.path.insert(0,str(ROOT/"tests"))
sys.path.insert(0,str(ROOT/"services"/"monitor-agent"))

from test_sse_monitor_discovery import (ROLES,CHAIN,SETTLEMENT,PROVIDER,
    CONSUMER,MONITOR,FakeRPC,event,snapshot)
from sse_monitor_discovery import (MonitorDiscovery,DiscoveryError,
    TOPIC_COMMITTEE,TOPIC_EPOCH)
from sse_monitor_action_queue import MonitorActionQueue
import monitor_discovery


class MonitorReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir=Path(self.temp.name)
        self.path=self.dir/"events.sqlite"
        self.node=deepcopy(ROLES)
        self.scanner=MonitorDiscovery(self.path,self.node,CHAIN,SETTLEMENT,5,
                                      confirmations=2,max_blocks=4)
        self.rpc=FakeRPC(10,[event(TOPIC_COMMITTEE,6,seq=7),
                             event(TOPIC_EPOCH,7)])
        self.scanner.scan(self.rpc,lambda r,a,l,e,**kw:snapshot(l,e))

    def _review(self, inspector=None, role=None):
        q=MonitorActionQueue(role or self.node,self.path,CHAIN,SETTLEMENT)
        if inspector is None:
            inspector=lambda *a,**kw:snapshot()
        return q.review(self.rpc,inspector)

    def test_persistent_notifications_review_current_lease_not_cached_state(self):
        def inspector(rpc,addr,lease,epoch,**kw):
            state=snapshot(lease,epoch)
            if epoch==0:
                # Same EVM epoch index could apply to both committee and
                # admitted-epoch notifications. Need separate inspection
                # state to prove decisions depend on LIVE chain, not SQLite.
                pass
            return state
        result=self._review(inspector)
        self.assertEqual(result["schema"],"sse-monitor-work-queue-v1")
        self.assertEqual(result["totalNotifications"],2)
        self.assertEqual(len(result["tasks"]),2)
        self.assertEqual([x["status"] for x in result["tasks"]],
                         ["REVIEW_EVIDENCE_CAPTURE","NO_LONGER_ACTIONABLE"])
        self.assertEqual(result["tasks"][0]["proposal"]["params"],
                         {"leaseId":1,"epochId":0})
        self.assertFalse(result["signerLoaded"])
        self.assertFalse(result["transactionsSent"])
        self.assertFalse(result["finalityVerified"])
        self.assertTrue(all(x["approvalRequired"] and not x["votesSubmitted"]
                            for x in result["tasks"]))

    def test_committee_confirmation_requires_accepted_not_ready(self):
        state=snapshot()
        state["lease"]["stateName"]="Accepted"
        state["lease"]["monitorConfirmations"]=2
        result=self._review(lambda *args,**kw:state)
        first=[x for x in result["tasks"] if x["kind"]=="COMMITTEE_ASSIGNED"][0]
        self.assertEqual(first["status"],"REVIEW_CONFIRMATION")
        self.assertEqual(first["proposal"],
                         {"role":"monitor","action":"monitor-confirm",
                          "params":{"leaseId":1}})
        self.assertFalse(first["individualConfirmationKnown"])

    def test_sealed_epoch_not_prompted_and_role_conflict_suppresses_actions(self):
        closed=snapshot()
        closed["epoch"]["monitoringSealed"]=True
        result=self._review(lambda *a,**kw:closed)
        self.assertTrue(all(x["proposal"] is None for x in result["tasks"]))
        other=deepcopy(ROLES)
        other["wallets"]["provider"]=PROVIDER
        result=self._review(lambda *a,**kw:snapshot(),role=other)
        self.assertTrue(all(x["proposal"] is None for x in result["tasks"]))

    def test_wrong_chain_and_journal_identity_fail_closed(self):
        other=deepcopy(ROLES)
        other["wallets"]["monitor"]="0x"+"fc"*20
        with self.assertRaises(DiscoveryError):
            MonitorActionQueue(other,self.path,CHAIN,SETTLEMENT).review(self.rpc)
        wrong=FakeRPC(10)
        wrong.request=lambda name,args: "0x1" if name=="eth_chainId" else "0xa"
        with self.assertRaises(DiscoveryError):
            MonitorActionQueue(self.node,self.path,CHAIN,SETTLEMENT).review(wrong)

    def test_reorg_of_event_block_refused_even_if_cursor_hash_unchanged(self):
        self.rpc.changed[7]="0x"+"aa"*32
        with self.assertRaisesRegex(DiscoveryError,"archived monitor event reorged"):
            self._review()

    def test_reorg_of_cursor_refused_before_task_inspection(self):
        self.rpc.changed[8]="0x"+"cc"*32
        with patch("sse_monitor_action_queue.inspect_chain",
                   side_effect=AssertionError("must not inspect fork")):
            with self.assertRaisesRegex(DiscoveryError,"cursor was reorged"):
                MonitorActionQueue(self.node,self.path,CHAIN,SETTLEMENT).review(self.rpc)

    def test_review_never_modifies_existing_sqlite(self):
        before=self.path.read_bytes()
        self._review()
        self.assertEqual(before,self.path.read_bytes())

    def test_nonexistent_journal_does_not_create_any_file(self):
        missing=self.dir/"no.sqlite"
        with self.assertRaises(DiscoveryError):
            MonitorActionQueue(self.node,missing,CHAIN,SETTLEMENT)
        self.assertFalse(missing.exists())

    def test_review_limit_cannot_be_unbounded(self):
        for value in (0,65,-1,True,None):
            with self.subTest(limit=value),self.assertRaises(DiscoveryError):
                MonitorActionQueue(self.node,self.path,CHAIN,SETTLEMENT,limit=value)

    def test_review_cli_requires_explicit_flag_and_never_loads_signer(self):
        roles=self.dir/"roles.json"
        roles.write_text(json.dumps(self.node))
        args=["--node-roles-file",str(roles),
              "--journal",str(self.path),
              "--rpc-url","http://127.0.0.1:8545",
              "--settlement",SETTLEMENT,"--chain-id",str(CHAIN),
              "--start-block","5"]
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(monitor_discovery.main(args),0)
        self.assertFalse(json.loads(out.getvalue())["rpcCalled"])
        fake=type("FakeResult",(),{"review":lambda self,rpc:{"tasks":[],"readOnly":True}})()
        with patch.object(monitor_discovery,"RPC",return_value=self.rpc), \
             patch.object(monitor_discovery,"MonitorActionQueue",return_value=fake) as q, \
             redirect_stdout(StringIO()) as out:
            self.assertEqual(monitor_discovery.main(args+["--review"]),0)
        self.assertEqual(json.loads(out.getvalue())["tasks"],[])
        q.assert_called_once()


if __name__=="__main__":
    unittest.main()
