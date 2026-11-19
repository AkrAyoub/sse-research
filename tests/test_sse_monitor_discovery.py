"""R5/R4 monitor discovery: offline event, fork, role, and checkpoint tests.

No Ethereum transaction, Docker, private signing key or remote system.
"""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
sys.path.insert(0,str(ROOT/"services"/"monitor-agent"))

from sse_monitor_discovery import (
    DiscoveryError, MonitorDiscovery, parse_log, candidate_for_event,
    TOPIC_COMMITTEE, TOPIC_EPOCH)
import monitor_discovery

CHAIN=31337
SETTLEMENT="0x"+"12"*20
CONSUMER="0x"+"21"*20
PROVIDER="0x"+"31"*20
MONITOR="0x"+"41"*20
MONITORS=[MONITOR]+["0x"+str(x)*40 for x in (5,6,7)]
REQUEST="0x"+"ab"*32
BLOCK_HASH=lambda n:"0x"+format(n+1,"064x")
TX="0x"+"dd"*32
ROLES={"schema":"sse-node-roles-v1","nodeId":"mixed-node-a",
       "roles":["provider","monitor","observer"],
       "wallets":{"provider":"0x"+"23"*20,"monitor":MONITOR}}


def event(topic,block,lease=1,seq=0):
    word=lambda value:"0x"+format(value,"064x")
    return {
        "address":SETTLEMENT,"removed":False,
        "topics":[topic,word(lease),word(seq)],
        "data":REQUEST if topic==TOPIC_EPOCH else "0x",
        "blockNumber":hex(block),"blockHash":BLOCK_HASH(block),
        "transactionHash":TX,"logIndex":hex(block),
    }


def snapshot(lease=1,epoch=0):
    return {"schema":"sse-onchain-inspection-v1","readOnly":True,
       "status":"EPOCH_FOUND","blockHashPinned":True,
       "domainSeparatorMatches":True,"chainId":CHAIN,
       "settlementAddress":SETTLEMENT,"leaseId":lease,"epochId":epoch,
       "blockTimestamp":100,
       "lease":{"stateName":"Active","consumer":CONSUMER,"provider":PROVIDER,
           "assignmentId":7,"marketplaceRequestId":2,"totalEscrow":100,
           "slaPolicyHash":"0x"+"aa"*32,
           "resourceProfileHash":"0x"+"bb"*32,
           "monitors":MONITORS,"monitorConfirmations":4},
       "epoch":{"exists":True,"requestHash":REQUEST,"monitoringClose":500,
                "monitoringSealed":False,"evidenceClosed":False}}


class FakeRPC:
    def __init__(self,head=10,logs=None):
        self.head=head
        self.logs=logs or []
        self.changed={}
        self.calls=[]
    def request(self,method,args):
        self.calls.append((method,args))
        if method=="eth_chainId":return hex(CHAIN)
        if method=="eth_blockNumber":return hex(self.head)
        if method=="eth_getBlockByNumber":
            n=int(args[0],16)
            return {"number":hex(n),"hash":self.changed.get(n,BLOCK_HASH(n))}
        if method=="eth_getLogs":
            filt=args[0]
            begin,end=int(filt["fromBlock"],16),int(filt["toBlock"],16)
            assert filt["address"]==SETTLEMENT
            assert filt["topics"]==[[TOPIC_COMMITTEE,TOPIC_EPOCH]]
            return [x for x in self.logs if begin<=int(x["blockNumber"],16)<=end]
        raise AssertionError("unexpected RPC method "+method)


class MonitorDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/"monitor.sqlite"
        self.scanner=MonitorDiscovery(self.db,ROLES,CHAIN,SETTLEMENT,5,
                                      confirmations=2,max_blocks=4)
        self.rpc=FakeRPC(10,[event(TOPIC_COMMITTEE,6,seq=7),event(TOPIC_EPOCH,7)])
        self.inspector=lambda rpc,settlement,lease,epoch,**kwargs:snapshot(lease,epoch)

    def test_two_events_discovered_and_persist_over_restart(self):
        outcome=self.scanner.scan(self.rpc,inspector=self.inspector)
        self.assertEqual([e["kind"] for e in outcome["new"]],
                         ["COMMITTEE_ASSIGNED","EPOCH_ADMITTED"])
        self.assertEqual(outcome["status"]["lastBlock"],8)
        self.assertFalse(outcome["finalityVerified"])
        self.assertFalse(outcome["transactionsSent"])
        self.assertEqual(outcome["new"][0]["state"],"REVIEW_CONFIRMATION")
        self.assertEqual(outcome["new"][1]["state"],"REVIEW_EVIDENCE_CAPTURE")
        other=MonitorDiscovery(self.db,ROLES,CHAIN,SETTLEMENT,5,
                               confirmations=2,max_blocks=4)
        self.assertEqual(len(other.status()["notifications"]),2)
        self.assertEqual(other.scan(self.rpc,self.inspector)["new"],[])

    def test_unselected_and_local_counterparty_not_reported(self):
        for role in ("provider","consumer"):
            node=deepcopy(ROLES)
            if role=="consumer":
                node["roles"].append("consumer")
                node["wallets"]["consumer"]=CONSUMER
            else:
                node["wallets"]["provider"]=PROVIDER
            own=MonitorDiscovery(Path(self.temp.name)/(role+".sqlite"),
                                 node,CHAIN,SETTLEMENT,5)
            result=own.scan(self.rpc,self.inspector)
            self.assertEqual(result["new"],[])
        bad=deepcopy(snapshot())
        bad["lease"]["monitors"][0]="0x"+"99"*20
        self.assertIsNone(candidate_for_event(ROLES,
            parse_log(event(TOPIC_EPOCH,7),SETTLEMENT,5,8),
            bad,chain_id=CHAIN,settlement=SETTLEMENT))

    def test_bad_or_reorganized_logs_do_not_commit_cursor(self):
        bad=event(TOPIC_EPOCH,7)
        bad["blockHash"]="0x"+"fa"*32
        rpc=FakeRPC(10,[bad])
        with self.assertRaises(DiscoveryError):
            self.scanner.scan(rpc,self.inspector)
        self.assertEqual(self.scanner.status()["lastBlock"],4)
        with self.assertRaises(DiscoveryError):
            parse_log({**event(TOPIC_EPOCH,7),"removed":True},SETTLEMENT,5,8)
        with self.assertRaises(DiscoveryError):
            parse_log({**event(TOPIC_EPOCH,7),"data":"0x"},SETTLEMENT,5,8)

    def test_cursor_reorg_blocks_restart_without_erasure(self):
        self.scanner.scan(self.rpc,self.inspector)
        self.rpc.changed[8]="0x"+"de"*32
        with self.assertRaisesRegex(DiscoveryError,"reorged"):
            self.scanner.scan(self.rpc,self.inspector)
        self.assertEqual(len(self.scanner.status()["notifications"]),2)

    def test_no_full_genesis_scan_and_confirmation_delay(self):
        rpc=FakeRPC(6,[event(TOPIC_EPOCH,6)])
        result=self.scanner.scan(rpc,self.inspector)
        self.assertTrue(result["waitingForBlocks"])
        self.assertEqual(result["new"],[])
        self.assertFalse(any(x[0]=="eth_getLogs" for x in rpc.calls))
        rpc.head=8
        result=self.scanner.scan(rpc,self.inspector)
        self.assertTrue(result["new"])

    def test_stale_epoch_not_automatically_voted(self):
        stale=snapshot();stale["epoch"]["monitoringSealed"]=True
        result=self.scanner.scan(self.rpc,
              lambda *args,**kw:stale)
        self.assertEqual(len(result["new"]),1)
        self.assertEqual(result["new"][0]["kind"],"COMMITTEE_ASSIGNED")
        self.assertEqual(result["status"]["lastBlock"],8)

    def test_new_journal_is_restart_safe_and_owner_only_on_posix(self):
        second=MonitorDiscovery(self.db,ROLES,CHAIN,SETTLEMENT,5,
                                confirmations=2,max_blocks=4)
        self.assertEqual(second.status()["lastBlock"],4)
        if os.name=="posix":
            self.assertEqual(stat.S_IMODE(self.db.stat().st_mode) & 0o077,0)

    def test_oversized_event_ids_are_refused_before_sqlite(self):
        huge=event(TOPIC_EPOCH,7,lease=2**63)
        with self.assertRaises(DiscoveryError):
            parse_log(huge,SETTLEMENT,5,8)
        self.assertEqual(self.scanner.status()["lastBlock"],4)

    def test_wrong_journal_identity_and_chain_rejected(self):
        with self.assertRaises(DiscoveryError):
            MonitorDiscovery(self.db,ROLES,CHAIN,SETTLEMENT,6)
        with self.assertRaises(DiscoveryError):
            MonitorDiscovery(self.db,ROLES,CHAIN+1,SETTLEMENT,5)
        wrong=FakeRPC(10)
        wrong.request=lambda name,args: "0x1" if name=="eth_chainId" else "0xa"
        with self.assertRaises(DiscoveryError):
            self.scanner.scan(wrong,self.inspector)

    def test_cli_preview_never_opens_rpc_or_writes_db(self):
        roles=Path(self.temp.name)/"roles.json"
        roles.write_text(json.dumps(ROLES))
        db=Path(self.temp.name)/"fresh.sqlite"
        args=["--node-roles-file",str(roles),"--journal",str(db),
              "--rpc-url","http://127.0.0.1:8545",
              "--settlement",SETTLEMENT,"--chain-id",str(CHAIN),
              "--start-block","5"]
        with patch.object(monitor_discovery,"RPC",
                          side_effect=AssertionError("RPC accessed in plan")), \
             redirect_stdout(StringIO()) as out:
            self.assertEqual(monitor_discovery.main(args),0)
        plan=json.loads(out.getvalue())
        self.assertFalse(plan["rpcCalled"])
        self.assertFalse(plan["journalWritten"])
        self.assertFalse(db.exists())


if __name__=="__main__":
    unittest.main()
