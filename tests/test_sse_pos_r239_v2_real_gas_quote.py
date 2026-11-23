"""R239 exact real-node V2 affordability quote read-only mocked RPC tests."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r239_v2_real_gas_quote as q
import sse_pos_r226_adaptive_v2_transaction_planner as v2

MARKET="0x"+"11"*20
LEDGER="0x"+"22"*20
APP="0x"+"33"*20
M={"market":{"address":MARKET},"ledger":{"address":LEDGER},
   "minimumBondWei":"1000000000000000"}
PROOF={
    "deploymentReceiptSuccessfulAndFinalized":True,
    "deploymentBlock":100,
}
p=v2.build("monitor-register","monitor",{"bondWei":10**15},MARKET,LEDGER)

class RealMock:
    def __init__(self,price=7,balance=10**18,estimate=123456):
        self.calls=[]
        self.price=price
        self.balance=balance
        self.estimate=estimate
    def __call__(self,url,method,args):
        self.calls.append((url,method,args))
        if method=="eth_estimateGas":
            return hex(self.estimate)
        if method=="eth_gasPrice":
            return hex(self.price)
        if method=="eth_getBalance":
            return hex(self.balance)
        if method=="eth_getBlockByNumber":
            return {"number":hex(18000),"gasLimit":hex(30_000_000)}
        raise AssertionError("no other real RPC methods allowed")

class TestR239ActualQuoteSource(unittest.TestCase):
    def test_real_json_rpc_estimate_and_balance_quoted_without_key(self):
        rpc=RealMock()
        r=q.quote(p,APP,M,"http://127.0.0.1:28545",
                  max_total_wei=2*10**15,transport=rpc,attestation=PROOF)
        self.assertEqual(r["actualNativeBalanceWeiAtFinalized"],str(10**18))
        self.assertTrue(r["realRpcEthEstimateGasCalled"])
        self.assertEqual(r["valueWei"],str(10**15))
        self.assertGreater(r["paddedGasLimit"],rpc.estimate)
        self.assertFalse(r["transactionSignedOrSubmitted"])
        self.assertFalse(r["walletSecretAccessed"])
        self.assertEqual([c[1] for c in rpc.calls],
            ["eth_estimateGas","eth_gasPrice","eth_getBalance","eth_getBlockByNumber"])
        call=rpc.calls[0][2][0]
        self.assertEqual(call["from"],APP)
        self.assertEqual(call["to"],MARKET)
        self.assertEqual(call["value"],hex(10**15))

    def test_refuses_underfunded_app_even_if_latest_unfinalized_funds(self):
        with self.assertRaises(q.Refused):
            q.quote(p,APP,M,"http://127.0.0.1:28545",
                    max_total_wei=2*10**15,
                    transport=RealMock(balance=100),attestation=PROOF)

    def test_refuses_over_budget_and_original_genesis_signer(self):
        with self.assertRaises(q.Refused):
            q.quote(p,APP,M,"http://127.0.0.1:28545",
                    max_total_wei=10**14,transport=RealMock(),attestation=PROOF)
        with self.assertRaises(q.Refused):
            q.quote(p,q.GENESIS_EOA,M,"http://127.0.0.1:28545",
                    max_total_wei=10**16,transport=RealMock(),attestation=PROOF)

    def test_refuses_gas_limit_or_r206_deployment_unverified(self):
        with self.assertRaises(q.Refused):
            q.quote(p,APP,M,"http://127.0.0.1:28545",
                    max_total_wei=10**17,transport=RealMock(estimate=30_000_000),
                    attestation=PROOF)
        with self.assertRaises(q.Refused):
            q.quote(p,APP,M,"http://127.0.0.1:28545",
                    max_total_wei=10**17,transport=RealMock(),
                    attestation={"deploymentReceiptSuccessfulAndFinalized":False})

    def test_refuse_target_outside_immutable_market_ledger(self):
        forged=v2.Plan("evil","monitor","0x"+"99"*20,"0x",0,True)
        with self.assertRaises(q.Refused):
            q.quote(forged,APP,M,"http://127.0.0.1:28545",
                    max_total_wei=10**17,transport=RealMock(),attestation=PROOF)

    def test_estimation_is_not_authorization_for_physical_evidence(self):
        r=q.quote(p,APP,M,"http://127.0.0.1:28545",
                  max_total_wei=10**17,transport=RealMock(),attestation=PROOF)
        self.assertTrue(r["notAGuaranteeOfFutureFeesOrExecution"])
        self.assertFalse(r["independentPhysicalSlaVerified"])

if __name__=="__main__":
    unittest.main()
