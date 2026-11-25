"""R297 authorization and ordering regressions; no real RPC or keystore."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r297_four_standby_native_funding as m

class TestR297(unittest.TestCase):
    def test_exact_approved_scope(self):
        self.assertEqual(m.NEW_ROLES,("vm4711-monitor","vm4712-monitor","vm4713-monitor","vm4714-provider"))
        self.assertEqual(m.APPROVED_TOTAL_WEI,20_000_000_084_000_000)
        self.assertEqual(sum(v+m.GAS_LIMIT*m.GAS_PRICE for _,_,v in m.RECIPIENTS[3:]),m.APPROVED_TOTAL_WEI)
        self.assertEqual([m.role_index(r)+1 for r in m.NEW_ROLES],[4,5,6,7])
        for role in m.NEW_ROLES:
            m.require_new_role(role)
    def test_old_and_unknown_role_cannot_send(self):
        for role in ("consumer","monitor-1","monitor-2","unknown"):
            with self.subTest(role=role),self.assertRaises(m.Refused):
                m.preflight(role)
            with self.assertRaises(m.Refused):
                m.send_once(role)
    def test_legacy_markers_preserved(self):
        with patch.object(m,"owner_private_paths",return_value=(Path("/tmp/adaptive-v2-deployer.keystore.json"),Path("/tmp/deploy"))):
            self.assertEqual(m.private_paths("monitor-2")[2].name,".r267-one-time-monitor-2-funding-attempted.json")
            self.assertEqual(m.private_paths(m.NEW_ROLES[0])[2].name,".r297-one-time-vm4711-monitor-funding-attempted.json")
    def test_consumed_attempt_refuses_before_rpc(self):
        with tempfile.TemporaryDirectory() as temp:
            marker=Path(temp)/"consumed"
            marker.touch()
            with patch.object(m,"private_paths",return_value=(Path(temp)/"key",Path(temp)/"deploy",marker)):
                with self.assertRaisesRegex(m.Refused,"NEVER RETRY"):
                    m.preflight(m.NEW_ROLES[0],transport=lambda *a: self.fail("RPC called"))
    def test_every_predecessor_required(self):
        role=m.NEW_ROLES[-1]
        audit={"chainId":31340,"deploymentReceiptSuccessfulAndFinalized":True,"runtimeCodeSha256Verified":True,"mutualMarketLedgerBindingsVerified":True,"finalizedExecutionHeight":26000}
        manifest={"deployer":m.APP,"market":{"address":m.MARKET},"minimumBondWei":str(m.BOND)}
        seen=[]
        def prior(url,r,height,**kw):
            seen.append(r)
            if r==m.NEW_ROLES[2]:
                raise m.Pending("not finalized")
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(m,"private_paths",return_value=(Path(temp)/"key",Path(temp)/"deploy",Path(temp)/"unused")),patch.object(m,"load_manifest",return_value=manifest):
                with self.assertRaises(m.Pending):
                    m.preflight(role,transport=lambda *a:self.fail("RPC after pending predecessor"),verify_fn=lambda *a,**kw:audit,prior_fn=prior)
        self.assertEqual(seen,[r for r,_,_ in m.RECIPIENTS[:-1]])
    def test_exact_prompt(self):
        self.assertEqual(m.consent_phrase(m.NEW_ROLES[0]),"FUND-ONE-R297-CHAIN31340-VM4711-MONITOR-NONCE4-EXACT-WEI5000000000000000")
    def test_budget_drift_refused(self):
        with patch.object(m,"MAX_TOTAL_WEI",m.APPROVED_TOTAL_WEI+1):
            with self.assertRaises(m.Refused):
                m.require_new_role(m.NEW_ROLES[0])

if __name__=="__main__":
    unittest.main()
