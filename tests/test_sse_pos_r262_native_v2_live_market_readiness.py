"""R262 real onchain read-only market state and escrow readiness, NO SEND."""
from pathlib import Path
import hashlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r262_native_v2_live_market_readiness as m


class TestR262OneShotReadOnlyLiveState(unittest.TestCase):
    def api(self, *, final=25300,market_balance=0,ledger_balance=0,
            active=0,liability=0,wrong_ledger=False):
        calls=[]
        INCLUDED=25339
        BLOCK_HASH="0x"+"f1"*32
        VALUES={
            "activeMonitorCount()":active,"nextRequestId()":1,
            "nextLeaseId()":1,
            "totalServiceEscrow()":liability,
            "totalPendingMonitorFunding()":0,
            "totalMonitorBonds()":0,
            "totalWithdrawable()":0,
            "totalUnspentReserves()":0,
            "totalWithdrawableCredits()":0,
            "minimumBond()":m.BOND_WEI,
        }
        selectors={"0x"+m.keccak(text=k)[:4].hex():v
                   for k,v in VALUES.items()}
        def call(url,method,params):
            self.assertEqual(url,m.RPC)
            self.assertNotIn(method,("eth_sendRawTransaction","eth_sendTransaction"))
            calls.append(method)
            if method=="eth_chainId":return hex(m.CHAIN)
            if method=="eth_getBlockByNumber":
                name=params[0]
                if name=="0x0":return {"hash":m.GENESIS}
                if name=="latest":return {"number":hex(25449)}
                if name=="finalized":return {"number":hex(final)}
                if name==hex(INCLUDED):return {"hash":BLOCK_HASH}
            if method=="eth_getTransactionReceipt":
                return {"status":"0x1","transactionHash":m.TX_HASH,
                        "contractAddress":m.MARKET,
                        "blockNumber":hex(INCLUDED),"blockHash":BLOCK_HASH}
            if method=="eth_call":
                if params[0]["data"]==m.selector("votes()"):
                    who=m.EXPECTED_LEDGER if not wrong_ledger else "0x"+"cc"*20
                    return "0x"+int(who,16).to_bytes(32,"big").hex()
                if params[0]["data"]==m.selector("settlement()"):
                    return "0x"+int(m.MARKET,16).to_bytes(32,"big").hex()
                if params[0]["data"] in selectors:
                    return "0x"+selectors[params[0]["data"]].to_bytes(32,"big").hex()
            if method=="eth_getCode":
                return "0x60016000"
            if method=="eth_getBalance":
                if params[0].lower()==m.MARKET.lower():
                    return hex(market_balance)
                if params[0].lower()==m.EXPECTED_LEDGER.lower():
                    return hex(ledger_balance)
            raise AssertionError("unexpected API "+repr((method,params)))
        return call,calls

    def run_mock(self,**params):
        api,calls=self.api(**params)
        with patch.object(m,"code_sha256",side_effect=[
                m.EXPECTED_MARKET_SHA256,m.EXPECTED_LEDGER_SHA256]),patch.object(
             m,"verify_compiler_runtime",side_effect=[
                {"runtimeSha256":m.EXPECTED_MARKET_SHA256},
                {"runtimeSha256":m.EXPECTED_LEDGER_SHA256}]),patch.object(
             m,"require_slot_value",return_value=None):
            result=m.status({}, {},transport=api)
        return result,calls

    def test_real_latest_contracts_and_role_state_read_only_pending(self):
        result,calls=self.run_mock()
        self.assertEqual(result["remainingBlocksUntilDeploymentFinality"],39)
        self.assertEqual(result["marketState"]["activeMonitorCount"],0)
        self.assertEqual(result["marketState"]["nextRequestId"],1)
        self.assertEqual(result["marketState"]["nextLeaseId"],1)
        self.assertEqual(result["marketLiabilitiesWei"],"0")
        self.assertFalse(result["deploymentIncludedAtFinalizedExecutionHeight"])
        self.assertFalse(result["transactionsSent"])
        self.assertEqual(result["readiness"],
            "LIVE_MARKET_READABLE_FINALITY_NOT_YET_COVERED")
        self.assertNotIn("eth_sendRawTransaction",calls)

    def test_can_report_finality_without_faking_r206_acceptance(self):
        result,_=self.run_mock(final=25364)
        self.assertTrue(result["deploymentIncludedAtFinalizedExecutionHeight"])
        self.assertFalse(result["formalR260R206FinalizedAuditRunByThisTool"])
        self.assertEqual(result["readiness"],
            "FINALITY_HEIGHT_COVERS_DEPLOYMENT_R260_R206_STILL_REQUIRED")

    def test_underfunded_market_escrow_is_refused(self):
        with self.assertRaisesRegex(m.Refused,"does NOT cover"):
            self.run_mock(liability=100,market_balance=0)

    def test_ledger_link_drift_is_refused(self):
        with self.assertRaisesRegex(m.Refused,"votes"):
            self.run_mock(wrong_ledger=True)

    def test_invalid_uint256_abi_and_contract_code_refused(self):
        with self.assertRaises(m.Refused):
            m.code_sha256("0x","market")
        good="0x6001"
        self.assertEqual(m.code_sha256(good,"market"),
                         hashlib.sha256(bytes.fromhex("6001")).hexdigest())
        with self.assertRaises(m.Refused):
            m.uint_call(m.RPC,m.MARKET,"dangerousMethod()",
                        transport=lambda *x:None)
        with self.assertRaisesRegex(m.Refused,"bad ABI"):
            m.uint_call(m.RPC,m.MARKET,"activeMonitorCount()",
                        transport=lambda *x:"0x42")


if __name__=="__main__":
    unittest.main()
