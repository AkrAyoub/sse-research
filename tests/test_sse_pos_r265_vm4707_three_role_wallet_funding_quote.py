"""R265 safe actual native role-funding PREVIEW unit tests; no transaction."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r265_vm4707_three_role_wallet_funding_quote as m


class TestR265RealFundingQuoteNoBroadcast(unittest.TestCase):
    def make_rpc(self, *, source_nonce=1, source_balance=10**18,
                 recipient_balance=0,recipient_nonce=0,
                 gas_estimate=21000,gas_price=1000,
                 genesis=m.GENESIS,status=1):
        calls=[]
        receipt_block=25339
        blockhash="0x"+"a3"*32
        targets={address.lower() for _,address,_ in m.RECIPIENTS}
        def api(url,method,params):
            self.assertEqual(url,m.RPC)
            self.assertNotIn(method,("eth_sendRawTransaction","eth_sendTransaction"))
            calls.append((method,params))
            if method=="eth_chainId":return hex(m.CHAIN)
            if method=="eth_getBlockByNumber":
                if params[0]=="0x0":return {"hash":genesis}
                if params[0]==hex(receipt_block):return {"hash":blockhash}
                if params[0]=="finalized":return {"number":hex(25332)}
                if params[0]=="latest":
                    return {"gasLimit":hex(30000000),"baseFeePerGas":"0x7"}
            if method=="eth_getTransactionReceipt":return {
                "transactionHash":m.TX_HASH,"status":hex(status),
                "contractAddress":m.MARKET,
                "blockNumber":hex(receipt_block),"blockHash":blockhash}
            if method=="eth_getTransactionCount":
                if params[0].lower()==m.APP.lower():return hex(source_nonce)
                if params[0].lower() in targets:return hex(recipient_nonce)
            if method=="eth_getCode":return "0x"
            if method=="eth_gasPrice":return hex(gas_price)
            if method=="eth_getBalance":
                if params[0].lower()==m.APP.lower():return hex(source_balance)
                if params[0].lower() in targets:return hex(recipient_balance)
            if method=="eth_estimateGas":
                self.assertEqual(params[0]["from"],m.APP)
                self.assertEqual(params[0]["data"],"0x")
                self.assertIn(params[0]["to"].lower(),targets)
                return hex(gas_estimate)
            raise AssertionError(f"Unexpected RPC {method} {params}")
        return api,calls

    def test_three_real_public_addresses_preview_budget_no_send(self):
        api,calls=self.make_rpc()
        result=m.quote(m.RPC,transport=api)
        self.assertFalse(result["fundingSpendsAuthorized"])
        self.assertFalse(result["signedOrBroadcastTransactions"])
        self.assertFalse(result["keystoresRead"])
        self.assertEqual(len(result["proposedRecipients"]),3)
        self.assertEqual(result["sourcePendingNonce"],1)
        self.assertEqual(result["proposedTotalNativeTestEthTransferWei"],
                         str(2*10**16))
        self.assertEqual(result["proposedMaximumCumulativeGasFeesWei"],
                         "63000000")
        self.assertEqual(result["proposedMaximumCombinedDebitWei"],
                         str(2*10**16+63000000))
        self.assertFalse(result["realMarketDeploymentFinalized"])
        self.assertTrue(result["realMarketCreationCanonical"])
        self.assertNotIn("eth_sendRawTransaction",[x[0] for x in calls])
        recipients=result["proposedRecipients"]
        self.assertEqual(len({x["publicRecipientAddress"].lower() for x in recipients}),3)
        self.assertTrue(all(x["transactionAuthorized"] is False for x in recipients))

    def test_unexpected_pending_funder_nonce_refuses_possible_earlier_send(self):
        with self.assertRaisesRegex(m.Refused,"pending nonce"):
            m.quote(m.RPC,transport=self.make_rpc(source_nonce=2)[0])

    def test_double_funding_recipient_balance_refused(self):
        with self.assertRaisesRegex(m.Refused,"existing balance"):
            m.quote(m.RPC,transport=self.make_rpc(recipient_balance=1)[0])

    def test_existing_recipient_nonce_refused(self):
        with self.assertRaisesRegex(m.Refused,"existing balance/nonce"):
            m.quote(m.RPC,transport=self.make_rpc(recipient_nonce=1)[0])

    def test_no_estimated_simple_transfer_no_quote(self):
        with self.assertRaisesRegex(m.Refused,"not exactly 21000"):
            m.quote(m.RPC,transport=self.make_rpc(gas_estimate=22000)[0])

    def test_node_fee_over_proposed_cap_refused(self):
        with self.assertRaisesRegex(m.Refused,"exceeds proposed maximum"):
            m.quote(m.RPC,transport=self.make_rpc(gas_price=2000)[0])

    def test_funder_cannot_afford_three_transfers(self):
        with self.assertRaisesRegex(m.Refused,"cannot cover"):
            m.quote(m.RPC,transport=self.make_rpc(source_balance=10**15)[0])

    def test_reverted_deployment_or_wrong_original_genesis_refused(self):
        for opts in ({"status":0},{"genesis":"0x"+"ee"*32}):
            with self.subTest(opts=opts),self.assertRaises(m.Refused):
                m.quote(m.RPC,transport=self.make_rpc(**opts)[0])


if __name__=="__main__":
    unittest.main()
