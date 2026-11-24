"""R276: public-only exact nonce2 marker forensic, no real RPC or secrets."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r276_vm4707_monitor1_funding_attempt_forensics as r

HASH="0x"+"bc"*32
BLOCK_HASH="0x"+"11"*32


def marker():
    return {
        "schema":"SSE_R267_SINGLE_ROLE_FUNDING_ATTEMPT_V1",
        "role":"monitor-1","source":r.APP,
        "recipient":r.RECIPIENTS[1][1],
        "valueWei":str(r.RECIPIENTS[1][2]),
        "nonce":2,"gasLimit":r.GAS_LIMIT,"gasPriceWei":r.GAS_PRICE,
        "txHash":HASH
    }


class TestR276ConsumedMonitor1PublicForensics(unittest.TestCase):
    def rig(self,*,visible=True,included=True,finalized_height=25570,
            included_height=25590,receipt_status=1,bad_tx=False,bad_block=False):
        d=marker()
        tx={
            "hash":HASH,"from":r.APP,"to":r.RECIPIENTS[1][1],
            "value":hex(r.RECIPIENTS[1][2]),
            "nonce":hex(2),
            "gas":hex(r.GAS_LIMIT),"gasPrice":hex(r.GAS_PRICE),
            "input":"0x","chainId":hex(r.CHAIN),
            "blockNumber":hex(included_height) if included else None,
            "blockHash":BLOCK_HASH if included else None,
        }
        if bad_tx:
            tx["value"]=hex(r.RECIPIENTS[1][2]+1)
        receipt={
            "transactionHash":HASH,
            "from":r.APP,"to":r.RECIPIENTS[1][1],
            "status":hex(receipt_status),
            "blockNumber":hex(included_height),
            "blockHash":BLOCK_HASH,
            "gasUsed":hex(r.GAS_LIMIT),
            "contractAddress":None,
        }
        methods=[]
        def transport(url,method,args):
            self.assertEqual(url,r.RPC)
            self.assertNotIn(method,("eth_sendRawTransaction",
                                     "eth_sendTransaction"))
            methods.append(method)
            if method=="eth_chainId":return hex(r.CHAIN)
            if method=="eth_getBlockByNumber":
                if args[0]=="0x0":return {"hash":r.GENESIS}
                if args[0]=="latest":return {"number":hex(max(finalized_height,included_height)+10)}
                if args[0]=="finalized":return {"number":hex(finalized_height)}
                if args[0]==hex(included_height):
                    return {"hash":"0x"+"22"*32 if bad_block else BLOCK_HASH}
            if method=="eth_getTransactionCount":
                self.assertEqual(args[0].lower(),r.APP.lower())
                return hex(3 if included else 2)
            if method=="eth_getBalance":
                self.assertEqual(args[0].lower(),r.RECIPIENTS[1][1].lower())
                if args[1]=="latest":return hex(r.RECIPIENTS[1][2] if included else 0)
                return hex(r.RECIPIENTS[1][2] if finalized_height>=included_height else 0)
            if method=="eth_getTransactionByHash":
                return tx if visible else None
            if method=="eth_getTransactionReceipt":
                return receipt if visible and included else None
            raise AssertionError("unexpected "+repr((method,args)))
        return lambda:r.observe(transport=transport,marker_reader=lambda role:d),methods

    def test_marker_exists_tx_absent_never_infer_unbroadcast(self):
        run,calls=self.rig(visible=False)
        report=run()
        self.assertEqual(report["transactionStatus"],
                         "MARKER_EXISTS_HASH_NOT_VISIBLE_DO_NOT_RESEND")
        self.assertFalse(report["monitor2PredecessorFinalizedEligible"])
        self.assertTrue(report["txVisibilityIsNotProofOfWhetherAttemptBroadcast"])
        self.assertFalse(report["transactionsSignedOrSent"])
        self.assertNotIn("eth_sendRawTransaction",calls)

    def test_exact_tx_pending_receipt_not_visible(self):
        run,_=self.rig(visible=True,included=False)
        report=run()
        self.assertEqual(report["transactionStatus"],
                         "MATCHING_SIGNED_TX_VISIBLE_NOT_INCLUDED")
        self.assertFalse(report["monitor2PredecessorFinalizedEligible"])

    def test_exact_receipt_successful_canonical_pending(self):
        run,_=self.rig()
        report=run()
        self.assertEqual(report["transactionStatus"],
                         "MATCHING_TX_SUCCESSFUL_CANONICAL_PENDING_FINALITY")
        self.assertEqual(report["blocksUntilReceiptFinality"],20)
        self.assertEqual(report["recipientFinalizedBalanceWei"],"0")
        self.assertFalse(report["monitor2PredecessorFinalizedEligible"])

    def test_finalized_exact_receipt_and_balance_entitles_monitor2_preflight(self):
        run,_=self.rig(finalized_height=25596)
        report=run()
        self.assertEqual(report["transactionStatus"],
                         "MATCHING_TX_SUCCESSFUL_CANONICAL_FINALIZED")
        self.assertEqual(report["blocksUntilReceiptFinality"],0)
        self.assertTrue(report["monitor2PredecessorFinalizedEligible"])
        self.assertEqual(report["recipientFinalizedBalanceWei"],str(r.RECIPIENTS[1][2]))

    def test_reverted_status_not_treated_as_success_or_eligible(self):
        run,_=self.rig(finalized_height=25596,receipt_status=0)
        report=run()
        self.assertEqual(report["transactionStatus"],
                         "MATCHING_TX_CANONICAL_REVERTED_DO_NOT_RESEND")
        self.assertFalse(report["monitor2PredecessorFinalizedEligible"])

    def test_tx_with_wrong_value_and_noncanonical_receipt_refused(self):
        for opts in ({"bad_tx":True},{"bad_block":True}):
            with self.subTest(opts=opts):
                run,_=self.rig(**opts)
                with self.assertRaises(r.Refused):
                    run()

    def test_mismatching_one_time_marker_refused_before_rpc(self):
        d=marker();d["nonce"]=3
        with self.assertRaisesRegex(r.Refused,"disagrees"):
            r.observe(transport=lambda *args:(_ for _ in ()).throw(
                AssertionError("should not call RPC")),marker_reader=lambda role:d)

    def test_missing_private_public_metadata_marker_refuses_not_broadcast(self):
        with self.assertRaisesRegex(r.Refused,"missing"):
            r.observe(transport=lambda *args:(_ for _ in ()).throw(
                AssertionError("should not call RPC")),
                marker_reader=lambda role:(_ for _ in ()).throw(
                    FileNotFoundError("marker")))

if __name__=="__main__":
    unittest.main()
