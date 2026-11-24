"""R278: exact monitor-2 nonce3 post-send public-only forensics; mocked."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r276_vm4707_monitor1_funding_attempt_forensics as forensic

HASH="0x"+"cd"*32
BLOCK="0x"+"ac"*32


def fixture(*,finalized=26010,included=26020,visible=True,bad_to=False):
    app=forensic.APP
    role,recipient,value=forensic.RECIPIENTS[2]
    assert role=="monitor-2"
    marker={
        "schema":"SSE_R267_SINGLE_ROLE_FUNDING_ATTEMPT_V1",
        "role":role,"source":app,"recipient":recipient,"valueWei":str(value),
        "nonce":3,"gasLimit":forensic.GAS_LIMIT,
        "gasPriceWei":forensic.GAS_PRICE,"txHash":HASH
    }
    tx={
        "hash":HASH,"from":app,"to":app if bad_to else recipient,
        "value":hex(value),"nonce":"0x3",
        "gas":hex(forensic.GAS_LIMIT),
        "gasPrice":hex(forensic.GAS_PRICE),
        "input":"0x","chainId":hex(forensic.CHAIN),
        "blockNumber":hex(included),"blockHash":BLOCK,
    }
    receipt={
        "transactionHash":HASH,"from":app,"to":recipient,
        "status":"0x1","blockNumber":hex(included),"blockHash":BLOCK,
        "gasUsed":hex(forensic.GAS_LIMIT),"contractAddress":None,
    }
    def ask(url,method,args):
        assert url==forensic.RPC
        assert method not in ("eth_sendRawTransaction","eth_sendTransaction")
        if method=="eth_chainId":return hex(forensic.CHAIN)
        if method=="eth_getBlockByNumber":
            if args[0]=="0x0":return {"hash":forensic.GENESIS}
            if args[0]=="latest":return {"number":hex(max(finalized,included)+10)}
            if args[0]=="finalized":return {"number":hex(finalized)}
            if args[0]==hex(included):return {"hash":BLOCK}
        if method=="eth_getTransactionCount":return "0x4" if visible else "0x3"
        if method=="eth_getBalance":
            if args[1]=="latest" or finalized>=included:
                return hex(value if visible else 0)
            return "0x0"
        if method=="eth_getTransactionByHash":return tx if visible else None
        if method=="eth_getTransactionReceipt":return receipt if visible else None
        raise AssertionError("unapproved RPC "+str((method,args)))
    return lambda:forensic.observe(
        role=role,transport=ask,marker_reader=lambda r:marker)


class TestR278Monitor2Finality(unittest.TestCase):
    def test_monitor2_succeeded_but_not_finalized(self):
        out=fixture()()
        self.assertEqual(out["role"],"monitor-2")
        self.assertEqual(out["expectedNonce"],3)
        self.assertEqual(out["transactionStatus"],
                         "MATCHING_TX_SUCCESSFUL_CANONICAL_PENDING_FINALITY")
        self.assertEqual(out["blocksUntilReceiptFinality"],10)
        self.assertFalse(out["allThreeApprovedRoleTransfersFinalized"])
        self.assertFalse(out["transactionsSignedOrSent"])

    def test_monitor2_finalized_all_three_scenario_eligible(self):
        out=fixture(finalized=26025)()
        self.assertEqual(out["transactionStatus"],
                         "MATCHING_TX_SUCCESSFUL_CANONICAL_FINALIZED")
        self.assertEqual(out["recipientFinalizedBalanceWei"],str(forensic.RECIPIENTS[2][2]))
        self.assertTrue(out["allThreeApprovedRoleTransfersFinalized"])
        self.assertFalse(out["monitor2PredecessorFinalizedEligible"])

    def test_consumed_marker_hash_unseen_does_not_authorize_retry(self):
        out=fixture(visible=False)()
        self.assertEqual(out["transactionStatus"],
                         "MARKER_EXISTS_HASH_NOT_VISIBLE_DO_NOT_RESEND")
        self.assertTrue(out["attemptAlreadyConsumedNeverResend"])
        self.assertFalse(out["allThreeApprovedRoleTransfersFinalized"])

    def test_wrong_receiver_is_a_hard_refusal(self):
        with self.assertRaisesRegex(forensic.Refused,"does NOT match"):
            fixture(bad_to=True)()

    def test_role_validation_refuses_consumer_funding(self):
        with self.assertRaisesRegex(forensic.Refused,"approved monitor"):
            forensic.observe(role="consumer",
                transport=lambda *args:(_ for _ in ()).throw(
                    AssertionError("no RPC should occur")),
                marker_reader=lambda *args:(_ for _ in ()).throw(
                    AssertionError("no marker should be read")))


if __name__=="__main__":
    unittest.main()
