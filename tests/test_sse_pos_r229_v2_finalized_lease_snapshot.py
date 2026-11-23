"""R229 bounded on-chain V2 lease snapshot: mock transport policy tests."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r229_v2_finalized_lease_snapshot as mod

MARKET="0x"+"11"*20
LEDGER="0x"+"22"*20
CONSUMER="0x"+"44"*20
PROVIDER="0x"+"55"*20
SEATS=["0x"+f"{i:040x}" for i in range(100,104)]
HASH="0x"+"ab"*32
RESPONSE="0x"+"cd"*32
MANIFEST={"market":{"address":MARKET},"ledger":{"address":LEDGER}}
ATTESTED={"finalizedExecutionHeight":12345}

def encoded_word(value,kind):
    if kind=="bool":
        raw=int(value)
    elif kind=="address" or kind=="bytes32":
        return bytes.fromhex(value[2:]).rjust(32,b"\x00")
    else:
        raw=value
    return raw.to_bytes(32,"big")

def pack(fields,mapping):
    return "0x"+b"".join(
        encoded_word(mapping[name],kind) for name,kind in fields).hex()

def fixture():
    lease={
        "consumer":CONSUMER,"provider":PROVIDER,
        "profileHash":HASH,"policyHash":HASH,"endpointHash":HASH,
        "snapshotRoot":HASH,"requestId":1,"epochFeeWei":100,
        "maxEpochs":1,"nextEpoch":1,"closedEpochs":1,
        "serviceRemainingWei":0,"monitorBudgetWei":400,
        "perMonitorEpochRewardWei":100,"requiredFaultTolerance":1,
        "gasBoundSeats":4,"eligibleCount":9,"confirmationSeconds":3600,
        "responseSeconds":100,"monitoringSeconds":100,
        "entropyBlock":102,"phase":4,"providerAccepted":True,
    }
    committee={
        "consumer":CONSUMER,"provider":PROVIDER,
        "eligibilitySnapshotRoot":HASH,
        "seats":4,"quorum":3,"requiredFaultTolerance":1,
        "confirmationDeadline":100000,"initialized":True,
        "ready":True,"confirmationExpired":False,
        "rewardPerReportWei":100,"originalReportBudgetWei":400,
        "unspentReportBudgetWei":100,"maxPayableEpochs":1,
        "openedEpochs":1,"sealedEpochs":1,"reportingClosed":False,
    }
    market_epoch={
        "requestHash":HASH,"responseHash":RESPONSE,
        "feeWei":100,"nonce":0,"exists":True,"resolved":True,
    }
    ledger_epoch={
        "requestHash":HASH,"responseHash":RESPONSE,
        "responseDeadline":1200,"monitoringClose":1300,
        "successVotes":3,"failureVotes":0,"totalVotes":3,
        "exists":True,"responseAuthenticated":True,
        "monitoringSealed":True,"outcome":1,
    }
    def dynamic_addresses():
        return "0x"+(
            (32).to_bytes(32,"big")+
            len(SEATS).to_bytes(32,"big")+
            b"".join(encoded_word(a,"address") for a in SEATS)
        ).hex()
    return {
        "lease(uint256)":pack(mod.MARKET_LEASE,lease),
        "committee(uint256)":pack(mod.LEDGER_COMMITTEE,committee),
        "selected(uint256)":dynamic_addresses(),
        "escrowAccounting()":pack((
            ("balanceWei","uint256"),("outstandingWei","uint256"),
            ("fullyCovered","bool")),{
                "balanceWei":900,"outstandingWei":700,"fullyCovered":True}),
        "epoch(uint256,uint256)|market":pack(mod.MARKET_EPOCH,market_epoch),
        "epoch(uint256,uint256)|ledger":pack(mod.LEDGER_EPOCH,ledger_epoch),
    }

def sample(mapping,lease_id=5,epoch_id=0):
    def mocked_query(transport,url,address,signature,args,block):
        key=signature if signature!="epoch(uint256,uint256)" else (
            signature+("|market" if address==MARKET else "|ledger"))
        return mapping[key]
    with patch.object(mod,"query",side_effect=mocked_query):
        return mod.inspect(MANIFEST,"http://127.0.0.1:28545",
                           lease_id,epoch_id,attestation=ATTESTED)

class TestR229FinalizedLease(unittest.TestCase):
    def test_full_original_chain_lease_and_committee_snapshot(self):
        result=sample(fixture())
        self.assertEqual(result["finalizedExecutionHeight"],12345)
        self.assertEqual(result["lease"]["phase"],4)
        self.assertEqual(result["selectedMonitors"],SEATS)
        self.assertEqual(result["committee"]["quorum"],3)
        self.assertEqual(result["epoch"]["ledger"]["successVotes"],3)
        self.assertTrue(result["marketEscrowAccounting"]["fullyCovered"])
        self.assertFalse(result["actualDockerDeliveryVerified"])
        self.assertFalse(result["onChainMonitorVotesImplyTruth"])
        self.assertFalse(result["signedOrBroadcast"])

    def test_refuse_nonexistent_lease(self):
        x=fixture()
        bad=dict(mod.decode_struct(x["lease(uint256)"],mod.MARKET_LEASE))
        bad["consumer"]="0x"+"00"*20
        x["lease(uint256)"]=pack(mod.MARKET_LEASE,bad)
        with self.assertRaises(mod.Refused):
            sample(x)

    def test_refuse_committee_quorum_policy_violation(self):
        x=fixture()
        bad=dict(mod.decode_struct(x["committee(uint256)"],mod.LEDGER_COMMITTEE))
        bad["quorum"]=2
        x["committee(uint256)"]=pack(mod.LEDGER_COMMITTEE,bad)
        with self.assertRaises(mod.Refused):
            sample(x)

    def test_refuse_insufficient_actual_escrow(self):
        x=fixture()
        x["escrowAccounting()"]=pack((
            ("balanceWei","uint256"),("outstandingWei","uint256"),
            ("fullyCovered","bool")),{
                "balanceWei":10,"outstandingWei":20,"fullyCovered":False})
        with self.assertRaises(mod.Refused):
            sample(x)

    def test_refuse_forged_epoch_evidence_votes(self):
        x=fixture()
        bad=dict(mod.decode_struct(x["epoch(uint256,uint256)|ledger"],mod.LEDGER_EPOCH))
        bad["totalVotes"]=4
        x["epoch(uint256,uint256)|ledger"]=pack(mod.LEDGER_EPOCH,bad)
        with self.assertRaises(mod.Refused):
            sample(x)

    def test_refuse_noncanonical_abi_bool_address_and_array(self):
        with self.assertRaises(mod.Refused):
            mod.read_word((2).to_bytes(32,"big"),"bool")
        with self.assertRaises(mod.Refused):
            mod.read_word(b"\xff"*32,"address")
        with self.assertRaises(mod.Refused):
            mod.decode_addresses("0x"+(64).to_bytes(32,"big").hex()+
                                  (0).to_bytes(32,"big").hex())
        with self.assertRaises(mod.Refused):
            mod.decode_struct("0x00",mod.MARKET_EPOCH)

    def test_eth_call_pinned_finalized_height_only(self):
        seen=[]
        def mock_rpc(url,method,args):
            seen.append((url,method,args))
            return "0x"+"00"*32
        mod.query(mock_rpc,"http://127.0.0.1:28545",MARKET,
                  "lease(uint256)",(5,),12345)
        self.assertEqual(seen[0][1],"eth_call")
        self.assertEqual(seen[0][2][1],hex(12345))
        self.assertEqual(seen[0][2][0]["to"],MARKET)
        self.assertEqual(seen[0][2][0]["data"][:10],"0x"+
                         mod.keccak256(b"lease(uint256)")[:4].hex())

    def test_invalid_id_or_epoch_rejected_before_calls(self):
        with self.assertRaises(mod.Refused):
            mod.inspect(MANIFEST,"http://127.0.0.1:28545",
                        True,0,attestation=ATTESTED)
        with self.assertRaises(mod.Refused):
            mod.inspect(MANIFEST,"http://127.0.0.1:28545",
                        1,-1,attestation=ATTESTED)

if __name__=="__main__":
    unittest.main()
