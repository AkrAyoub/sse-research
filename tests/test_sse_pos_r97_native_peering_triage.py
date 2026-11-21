"""R97 regression tests: no real Docker/RPC required."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r97_native_peering_triage as m

class NativePeeringTriageTests(unittest.TestCase):
    def test_zero_peers_never_ready(self):
        v=m.evaluate({"result":"0x0"},{"data":{"connected":"0"}},
            {"data":{"is_syncing":True,"is_optimistic":False,"el_offline":False}},
            {"explicit_bootnodes":True},{"explicit_bootnodes":True})
        self.assertEqual(v["readiness"],"PEERING_NOT_VERIFIED")
        self.assertFalse(v["native_peering_verified"])
        self.assertFalse(v["live_consensus_verified"])
    def test_peers_not_equivalent_finality(self):
        v=m.evaluate({"result":"0x1"},{"data":{"connected":"1"}},
            {"data":{"is_syncing":False,"is_optimistic":False,"el_offline":False}},
            {},{})
        self.assertTrue(v["native_peering_verified"])
        self.assertFalse(v["live_consensus_verified"])
    def test_rejects_malformed_counts(self):
        with self.assertRaises(ValueError):
            m.evaluate({"result":0},{"data":{"connected":"1"}},{"data":{}},{},{})
    def test_seed_presence_only_no_record_leak(self):
        records=["--bootnodes=enode://PUBLIC_RECORD","--discovery-enabled=true",
                 "--p2p-ipv6-outbound-enabled=true"]
        v=m.seeds(records,"el")
        self.assertTrue(v["explicit_bootnodes"])
        self.assertNotIn("PUBLIC_RECORD",str(v))
        b=m.seeds(["--boot-nodes=enr:PUBLIC_RECORD","--quic-port6=9001"],"bn")
        self.assertTrue(b["explicit_bootnodes"])
        self.assertTrue(b["quic_ipv6_9001"])
    def test_known_roles(self):
        self.assertEqual(set(m.ROLES),{"owner","observer"})
        self.assertEqual(m.ROLES["owner"][2:],(18545,15052))
        self.assertEqual(m.ROLES["observer"][2:],(28545,25052))
if __name__=="__main__":
    unittest.main()
