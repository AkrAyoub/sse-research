"""R227 source-only finalized V2 event audit policy tests (mock RPC only)."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_pos_r227_v2_finalized_event_audit as mod

MARKET="0x"+"11"*20
LEDGER="0x"+"22"*20
BLOCK="0x"+"ab"*32
TX="0x"+"cd"*32
HASH="0x"+"ef"*32
MANIFEST={
    "market":{"address":MARKET},
    "ledger":{"address":LEDGER},
}
ATTESTED={"deploymentBlock":100,"finalizedExecutionHeight":102}


def word(value,kind):
    if kind=="address":
        return bytes.fromhex(value[2:]).rjust(32,b"\0")
    if kind=="bytes32":
        return bytes.fromhex(value[2:])
    return value.to_bytes(32,"big")


def event(role,sig,indexed_values,data_values,*,block=101,index=0):
    specs={"market":mod.MARKET_EVENTS,"ledger":mod.LEDGER_EVENTS}
    match=next(x for x in specs[role] if x[0]==sig)
    assert len(indexed_values)==len(match[1])
    assert len(data_values)==len(match[2])
    return {
        "address":MARKET if role=="market" else LEDGER,
        "topics":[mod.event_topic(sig)]+[
            "0x"+word(value,field[1]).hex()
            for field,value in zip(match[1],indexed_values)],
        "data":"0x"+b"".join(
            word(value,field[1]) for field,value in zip(match[2],data_values)).hex(),
        "blockNumber":hex(block),"blockHash":BLOCK,
        "transactionHash":TX,"logIndex":hex(index),"removed":False,
    }


class FakeRpc:
    def __init__(self,logs):
        self.logs=logs
        self.calls=[]
    def __call__(self,url,method,args):
        self.calls.append((method,args))
        if method=="eth_getLogs":
            start=int(args[0]["fromBlock"],16)
            end=int(args[0]["toBlock"],16)
            return [log for log in self.logs
                    if start<=int(log["blockNumber"],16)<=end]
        if method=="eth_getBlockByNumber":
            return {"number":args[0],"hash":BLOCK}
        raise AssertionError("unexpected RPC method")


class TestR227FinalizedOnchainEvidence(unittest.TestCase):
    def test_known_ethereum_keccak_event_topic(self):
        self.assertEqual(mod.event_topic("Transfer(address,address,uint256)"),
                         "0xddf252ad1be2c89b69c2b068fc378daa"
                         "952ba7f163c4a11628f55a4df523b3ef")

    def test_all_market_and_ledger_event_selectors_unique(self):
        specs=mod.specs()
        self.assertEqual(len(specs["market"]),len(mod.MARKET_EVENTS))
        self.assertEqual(len(specs["ledger"]),len(mod.LEDGER_EVENTS))
        self.assertEqual(len(specs["market"]),16)
        self.assertEqual(len(specs["ledger"]),12)

    def test_frozen_market_and_real_monitor_vote_in_finalized_blocks(self):
        a=event("market","LeaseFunded(uint256,uint256,address,address,uint256,uint256)",
                [7,4],[MARKET,LEDGER,300,50])
        b=event("ledger","VoteRecorded(uint256,uint256,address,uint8,bytes32)",
                [7,0,MARKET],[2,HASH],index=1)
        rpc=FakeRpc([b,a])
        result=mod.audit_events(MANIFEST,"http://127.0.0.1:28545",
                                transport=rpc,verified=ATTESTED)
        self.assertEqual(result["eventCount"],2)
        self.assertEqual(result["events"][0]["event"],"LeaseFunded")
        self.assertEqual(result["events"][1]["event"],"VoteRecorded")
        self.assertEqual(result["events"][1]["fields"]["outcome"],2)
        self.assertEqual(result["events"][1]["fields"]["evidenceHash"],HASH)
        self.assertTrue(result["fullDeploymentHistoryCovered"])
        self.assertTrue(result["canonicalBlockHashVerifiedPerEvent"])
        self.assertFalse(result["monitorEvidenceTruthVerified"])
        self.assertFalse(result["ethereumTransactionSignedOrSubmitted"])
        self.assertEqual([c[0] for c in rpc.calls].count("eth_getBlockByNumber"),1)

    def test_finalized_idle_expiry_event_discloses_reserved_and_refunded(self):
        raw=event("market","LeaseIdleExpired(uint256,uint256,uint256)",
                  [17],[300,600])
        result=mod.parse_log(raw,{"market":MARKET,"ledger":LEDGER},mod.specs())
        self.assertEqual(result["fields"],{
            "leaseId":"17","unresolvedFeeWei":"300","refundedUnusedWei":"600"})

    def test_proposer_block_hash_spoofed_canonical_event_rejected(self):
        log=event("market","LeaseCancelled(uint256)",[7],[])
        log["blockHash"]="0x"+"dd"*32
        with self.assertRaises(mod.Refused):
            mod.audit_events(MANIFEST,"http://127.0.0.1:28545",
                             transport=FakeRpc([log]),verified=ATTESTED)

    def test_unrecognized_event_topic_refused(self):
        log=event("market","LeaseCancelled(uint256)",[7],[])
        log["topics"][0]="0x"+"01"*32
        with self.assertRaises(mod.Refused):
            mod.parse_log(log,{"market":MARKET,"ledger":LEDGER},mod.specs())

    def test_bad_indexed_encoding_and_removed_log_rejected(self):
        log=event("ledger","SeatSelected(uint256,address)",[9,MARKET],[])
        log["topics"][2]="0x"+"ff"*32
        with self.assertRaises(mod.Refused):
            mod.parse_log(log,{"market":MARKET,"ledger":LEDGER},mod.specs())
        log=event("market","LeaseCancelled(uint256)",[7],[])
        log["removed"]=True
        with self.assertRaises(mod.Refused):
            mod.parse_log(log,{"market":MARKET,"ledger":LEDGER},mod.specs())

    def test_duplicate_tx_log_index_refused(self):
        log=event("market","LeaseCancelled(uint256)",[7],[])
        with self.assertRaises(mod.Refused):
            mod.audit_events(MANIFEST,"http://127.0.0.1:28545",
                             transport=FakeRpc([log,log.copy()]),verified=ATTESTED)

    def test_outside_finalized_window_and_range_refused(self):
        with self.assertRaises(mod.Refused):
            mod.audit_events(MANIFEST,"http://127.0.0.1:28545",
                             start=99,transport=FakeRpc([]),verified=ATTESTED)
        with self.assertRaises(mod.Refused):
            mod.audit_events(MANIFEST,"http://127.0.0.1:28545",
                             start=103,transport=FakeRpc([]),verified=ATTESTED)
        big={"deploymentBlock":1,"finalizedExecutionHeight":50002}
        with self.assertRaises(mod.Refused):
            mod.audit_events(MANIFEST,"http://127.0.0.1:28545",
                             transport=FakeRpc([]),verified=big)

    def test_one_event_raw_data_word_exact_match(self):
        log=event("ledger","MonitoringSealed(uint256,uint256,uint8)",
                  [5,2],[1])
        result=mod.parse_log(log,{"market":MARKET,"ledger":LEDGER},mod.specs())
        self.assertEqual(result["fields"],{
            "leaseId":"5","epochId":"2","outcome":1})
        log["data"]="0x"+(3).to_bytes(32,"big").hex()
        with self.assertRaises(mod.Refused):
            mod.parse_log(log,{"market":MARKET,"ledger":LEDGER},mod.specs())

    def test_finite_batched_read_for_empty_chain(self):
        rpc=FakeRpc([])
        attested={"deploymentBlock":100,"finalizedExecutionHeight":700}
        result=mod.audit_events(MANIFEST,"http://127.0.0.1:28545",
                                transport=rpc,verified=attested)
        self.assertEqual(result["eventCount"],0)
        self.assertEqual([name for name,_ in rpc.calls],["eth_getLogs"]*3)
        self.assertFalse(result["providerPhysicalWorkVerified"])

if __name__=="__main__":
    unittest.main()
