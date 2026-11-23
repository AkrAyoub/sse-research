"""R242 owner-only real V2 tx sender unit POLICY tests; mocked, never broadcast."""
import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r242_v2_owner_local_send as m
import sse_pos_r226_adaptive_v2_transaction_planner as v2

MARKET="0x"+"11"*20
LEDGER="0x"+"22"*20
APP="0x"+"33"*20
MANIFEST={
    "market":{"address":MARKET},"ledger":{"address":LEDGER},
    "minimumBondWei":str(10**15)
}
P=v2.build("monitor-register","monitor",{"bondWei":10**15},MARKET,LEDGER)
OFFER={
    "transactionSignedOrSubmitted":False,
    "originalGenesisR206Verified":True,
    "realRpcEthEstimateGasCalled":True,
    "applicationSignerPublic":APP,
    "action":P.action,"target":P.target,"calldata":P.calldata,
    "valueWei":str(P.value_wei),
    "paddedGasLimit":200_000,
    "observedGasPriceWei":"7",
    "estimatedUpperBudgetWei":str(10**15+200_000*7),
    "ownerMaxTotalSpendWei":str(2*10**15),
}

class TestR242NoImplicitNativeEvmTransactions(unittest.TestCase):
    def test_default_live_quote_uses_r206_and_r239_not_keys(self):
        sent=[]
        with patch.object(m,"verify_deployment",return_value={
            "deploymentReceiptSuccessfulAndFinalized":True}) as audit,patch.object(
            m,"quote",return_value={**OFFER,"transactionSignedOrSubmitted":False}) as offer:
            plan,quoted=m.readonly_quote(MANIFEST,
                "http://127.0.0.1:28545","monitor-register","monitor",
                {"bondWei":10**15},APP,2*10**15)
        self.assertEqual(plan.target,MARKET)
        audit.assert_called_once()
        offer.assert_called_once()
        self.assertFalse(quoted["transactionSignedOrSubmitted"])

    def test_minimum_real_bond_nonnegotiable(self):
        with patch.object(m,"verify_deployment",return_value={}):
            with self.assertRaises(m.Refused):
                m.readonly_quote({**MANIFEST,"minimumBondWei":str(2*10**15)},
                    "http://127.0.0.1:28545",
                    "monitor-register","monitor",{"bondWei":10**15},
                    APP,2*10**15)

    def test_refuses_signing_without_fresh_exact_tty_approval(self):
        seen=[]
        def reject(*_):
            seen.append("secret_was_read")
            raise AssertionError("must not access wallet before consent")
        with patch.object(m,"safe_keystore",side_effect=reject):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(m.Refused):
                    m.submit_once(P,OFFER,MANIFEST,"http://127.0.0.1:28545",
                        Path("/hidden/app-wallet"),confirm=lambda p:"NO",
                        get_password=lambda p:reject(),tty=False,
                        transport=lambda *a:reject())
        self.assertEqual(seen,[])

    def test_stale_plan_quote_or_original_wallet_refused_before_consent(self):
        asked=[]
        def ask(_):
            asked.append(True)
            return m.AUTHORIZE
        invalid={**OFFER,"calldata":"0x"}
        with self.assertRaises(m.Refused):
            m.submit_once(P,invalid,MANIFEST,"http://127.0.0.1:28545",
                          Path("/some/key"),confirm=ask,get_password=lambda p:"",
                          tty=False)
        original={**OFFER,"applicationSignerPublic":m.ORIGINAL_GENESIS_EOA}
        with self.assertRaises(m.Refused):
            m.submit_once(P,original,MANIFEST,"http://127.0.0.1:28545",
                          Path("/some/key"),confirm=ask,get_password=lambda p:"",
                          tty=False)
        self.assertEqual(asked,[])

    def test_send_requires_locally_owned_encrypted_app_file(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(m.main([
                "--manifest","/tmp/not-real",
                "--rpc","http://127.0.0.1:28545",
                "--action","monitor-register","--role","monitor",
                "--params-json",'{"bondWei":1000000000000000}',
                "--from-address",APP,"--max-total-wei",str(2*10**15),
                "--send"]),2)

    def test_no_mainnet_or_legacy_v1_actions(self):
        self.assertEqual(m.AUTHORIZE,"AUTHORIZE-ONE-V2-CHAIN31340-TRANSACTION")
        with self.assertRaises(v2.Refused):
            v2.build("old-v1-fund","consumer",{},MARKET,LEDGER)

if __name__=="__main__":
    unittest.main()
