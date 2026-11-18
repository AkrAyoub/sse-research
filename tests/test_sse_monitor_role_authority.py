"""Read-only monitor bond / active status check with two RPC views."""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_monitor_role_authority import monitor_eligibility,MonitorAuthorityError

RPCS=["http://127.0.0.1:18545","http://127.0.0.1:18546"]
GEN="0x"+"ab"*32
POOL="0x"+"ee"*20
WALLET="0x"+"12"*20

def qword(n):return f"{n:064x}"
def chain(url,method,params):
    if method=="eth_chainId":return "0x7a6a"
    if method=="eth_getBlockByNumber":return {"hash":GEN}
    raise AssertionError(method)
def contract(url,method,params):
    if method=="eth_getCode":return "0x6001600055"
    if method=="eth_call":
        data=params[0]["data"]
        if len(data)>10: return "0x"+"".join(map(qword,[1000,0,0,0,1,1]))
        return "0x"+qword(500)
    raise AssertionError(method)

class MonitorAuthorityTests(unittest.TestCase):
    def test_bond_meets_minimum_but_not_authorized_per_lease(self):
        result=monitor_eligibility(RPCS,chain_id=31338,genesis_hash=GEN,
                                   pool=POOL,wallet=WALLET,
                                   chain_call=chain,contract_call=contract)
        self.assertTrue(result["globallyBondEligibleObserved"])
        self.assertEqual(result["observedBondWei"],1000)
        self.assertFalse(result["selectedMonitorForLease"])
        self.assertFalse(result["authorizationForAnySpecificLeaseProved"])
        self.assertFalse(result["ethereumTransactionsSent"])

    def test_underbonded_or_inactive_not_eligible(self):
        for bond,active in [(200,1),(1000,0)]:
            def modified(url,method,params):
                if method=="eth_call" and len(params[0]["data"])>10:
                    return "0x"+"".join(map(qword,[bond,0,0,0,active,1]))
                return contract(url,method,params)
            result=monitor_eligibility(RPCS,chain_id=31338,genesis_hash=GEN,
                                       pool=POOL,wallet=WALLET,
                                       chain_call=chain,contract_call=modified)
            self.assertFalse(result["globallyBondEligibleObserved"])

    def test_two_rpc_views_disagreement_is_not_authorization(self):
        def drift(url,method,params):
            if url==RPCS[1] and method=="eth_call" and len(params[0]["data"])>10:
                return "0x"+"".join(map(qword,[999,0,0,0,1,1]))
            return contract(url,method,params)
        with self.assertRaises(MonitorAuthorityError):
            monitor_eligibility(RPCS,chain_id=31338,genesis_hash=GEN,
                                pool=POOL,wallet=WALLET,
                                chain_call=chain,contract_call=drift)

    def test_wrong_chain_or_genesis_or_single_url_denied(self):
        with self.assertRaises(MonitorAuthorityError):
            monitor_eligibility(RPCS[:1],chain_id=31338,genesis_hash=GEN,
                                pool=POOL,wallet=WALLET,
                                chain_call=chain,contract_call=contract)
        with self.assertRaises(MonitorAuthorityError):
            monitor_eligibility(RPCS,chain_id=31337,genesis_hash=GEN,
                                pool=POOL,wallet=WALLET,
                                chain_call=chain,contract_call=contract)
        def wronggen(url,method,params):
            if method=="eth_getBlockByNumber":
                return {"hash":"0x"+"cd"*32}
            return chain(url,method,params)
        with self.assertRaises(MonitorAuthorityError):
            monitor_eligibility(RPCS,chain_id=31338,genesis_hash=GEN,
                                pool=POOL,wallet=WALLET,
                                chain_call=wronggen,contract_call=contract)

if __name__=="__main__":
    unittest.main()
