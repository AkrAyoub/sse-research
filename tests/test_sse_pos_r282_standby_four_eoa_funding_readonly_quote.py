"""R282 four real host-role EOA quote, offline mocked RPC only."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r282_standby_four_eoa_funding_readonly_quote as mod


def predecessor(*,state="MATCHING_TX_SUCCESSFUL_CANONICAL_FINALIZED",
                nonce=4,genesis=True,**kwargs):
    return {
        "chainId":31340,"role":"monitor-2",
        "originalGenesisVerified":genesis,
        "transactionStatus":state,
        "sourceLatestNonce":nonce,
        "sourcePendingNonce":nonce,
        "allThreeApprovedRoleTransfersFinalized":state=="MATCHING_TX_SUCCESSFUL_CANONICAL_FINALIZED",
    }


class TestR282ActualFourRoleFundsQuoteNoSend(unittest.TestCase):
    def rig(self,*,prior=None,one_funded=None,nonce=4,price=1000,
            balance=999000000000000000,bad_gas=None,contract=None):
        events=[]
        def original(*,role,transport):
            self.assertEqual(role,"monitor-2")
            return prior if prior is not None else predecessor()
        def rpc(url,method,args):
            self.assertEqual(url,mod.RPC)
            self.assertNotIn(method,("eth_sendRawTransaction","eth_sendTransaction",
                                     "personal_unlockAccount","eth_signTransaction"))
            events.append((method,args))
            if method=="eth_getTransactionCount":
                if args[0].lower()==mod.APP.lower():return hex(nonce)
                return "0x0"
            if method=="eth_getCode":
                return "0x1" if contract is not None and args[0].lower()==contract.lower() else "0x"
            if method=="eth_gasPrice":return hex(price)
            if method=="eth_getBlockByNumber":return {
                "gasLimit":hex(30_000_000),"baseFeePerGas":"0x1"}
            if method=="eth_getBalance":
                if args[0].lower()==mod.APP.lower():return hex(balance)
                return hex(1 if one_funded is not None and args[0].lower()==one_funded.lower() else 0)
            if method=="eth_estimateGas":
                to=args[0]["to"].lower()
                return hex(22_000 if bad_gas is not None and to==bad_gas.lower()
                           else 21_000)
            raise AssertionError("unexpected RPC: "+repr((method,args)))
        return lambda:mod.preview(transport=rpc,prior_fn=original),events

    def test_pending_monitor2_yields_NO_real_quote_and_no_extra_rpc(self):
        run,events=self.rig(prior=predecessor(
            state="MATCHING_TX_SUCCESSFUL_CANONICAL_PENDING_FINALITY"))
        result=run()
        self.assertEqual(result["status"],
            "MONITOR2_NOT_FINALIZED_NO_STANDBY_FUNDING_QUOTE")
        self.assertFalse(result["newStandbyFundingAuthorized"])
        self.assertFalse(result["realRpcGasBalanceAndRecipientQuoteVerified"])
        self.assertEqual(events,[])

    def test_four_exact_clean_actual_recipient_quotes(self):
        run,events=self.rig()
        result=run()
        self.assertEqual(result["status"],
            "READONLY_SCENARIO_QUOTE_ELIGIBLE_FOR_SEPARATE_APPROVAL")
        self.assertEqual(result["sourceNextNonce"],4)
        self.assertTrue(result["realRpcGasBalanceAndRecipientQuoteVerified"])
        self.assertEqual(len(result["proposedTransfers"]),4)
        self.assertEqual([v["proposedSourceNonce"] for v in result["proposedTransfers"]],
                         [4,5,6,7])
        self.assertEqual(result["maximumFourTransactionDebitsWei"],
                         str(4*(5_000_000_000_000_000+21_000_000)))
        self.assertFalse(result["newStandbyFundingAuthorized"])
        self.assertFalse(result["transactionsSignedOrSent"])
        self.assertEqual(
            len([x for x in events if x[0]=="eth_estimateGas"]),4)

    def test_changed_source_nonce_or_prior_refused(self):
        for opts in ({"nonce":5},{"prior":predecessor(nonce=5)},
                     {"prior":predecessor(genesis=False)}):
            with self.subTest(opts=opts):
                run,_=self.rig(**opts)
                with self.assertRaises(mod.Refused):
                    run()

    def test_any_recipient_previously_funded_or_contract_refused(self):
        victim=mod.RECIPIENTS[2][1]
        for opts in ({"one_funded":victim},{"contract":victim}):
            with self.subTest(opts=opts):
                run,_=self.rig(**opts)
                with self.assertRaisesRegex(mod.Refused,"not a clean"):
                    run()

    def test_bad_gas_or_chain_price_or_source_balance_refused(self):
        for opts in (
            {"bad_gas":mod.RECIPIENTS[0][1]},
            {"price":1001},
            {"balance":mod.MAX_TOTAL_WEI-1},
        ):
            with self.subTest(opts=opts):
                run,_=self.rig(**opts)
                with self.assertRaises(mod.Refused):
                    run()

    def test_parent_monitor2_reverted_not_eligible(self):
        run,events=self.rig(prior=predecessor(
            state="MATCHING_TX_CANONICAL_REVERTED_DO_NOT_RESEND"))
        output=run()
        self.assertEqual(output["monitor2TransactionStatus"],
            "MATCHING_TX_CANONICAL_REVERTED_DO_NOT_RESEND")
        self.assertFalse(output["newStandbyFundingAuthorized"])
        self.assertEqual(events,[])


if __name__=="__main__":
    unittest.main()
