"""R41 strict in-container JSON-RPC and same-validator staged restart tests."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_g2_resume_r41 as m

class R41ExistingChainSafeResume(unittest.TestCase):
    def test_existing_exact_identity(self):
        self.assertEqual(m.EL,"sse31340-g2-el-r40")
        self.assertEqual(m.BN,"sse31340-g2-bn")
        self.assertEqual(m.VC,"sse31340-g2-vc")
        self.assertEqual(m.EXPECTED_CHAIN,hex(31340))
        self.assertEqual(m.EXPECTED_GENESIS,"1795219212")
    def test_rpc_probe_only_readonly_inside_fixed_container(self):
        s=m.wire("POST",8545,"/",{"jsonrpc":"2.0","method":"eth_chainId"})
        self.assertIn("/dev/tcp/127.0.0.1/8545",s)
        self.assertIn("Host: localhost",s)
        with self.assertRaises(m.Refuse):
            m.wire("POST",8545,"/eth_sendTransaction",{})
    def test_http_parse_good(self):
        x=b'HTTP/1.1 200 OK\r\n\r\n{"jsonrpc":"2.0","result":"0x7a6c"}'
        self.assertEqual(m.parse_http(x)[1]["result"],"0x7a6c")
    def test_http_refusal_does_not_leak_payload(self):
        status,obj=m.parse_http(b"HTTP/1.1 403 Forbidden\r\n\r\nSECRET_MUST_NOT_LEAK")
        self.assertEqual(status,"HTTP_403")
        self.assertIsNone(obj)
    def test_chainid_exact_match(self):
        x=b'HTTP/1.1 200 OK\r\n\r\n{"jsonrpc":"2.0","result":"0x7a6c"}'
        with patch.object(m,"docker",return_value=x):
            self.assertTrue(m.inside(m.EL)["identityVerified"])
        with patch.object(m,"docker",return_value=x.replace(b"7a6c",b"1")):
            self.assertFalse(m.inside(m.EL)["identityVerified"])
    def test_beacon_genesis_exact_match(self):
        x=b'HTTP/1.1 200 OK\r\n\r\n{"data":{"genesis_time":"1795219212"}}'
        with patch.object(m,"docker",return_value=x):
            self.assertTrue(m.inside(m.BN)["identityVerified"])
        with patch.object(m,"docker",return_value=x.replace(b"1795219212",b"1")):
            self.assertFalse(m.inside(m.BN)["identityVerified"])
    def test_plan_does_not_start_any_service(self):
        with patch.object(m,"require_existing"),patch.object(m,"inside",return_value={"status":"HTTP_200","identityVerified":True}):
            self.assertTrue(m.plan("a"*40)["noContainersCreatedOrStartedByPlan"])
    def test_validator_only_after_genesis(self):
        s=(ROOT/"tools/sse_pos_g2_resume_r41.py").read_text("utf-8")
        self.assertIn('docker(["start", BN])',s)
        self.assertIn('docker(["start", VC])',s)
        self.assertLess(s.index('if not ready["identityVerified"]:'),s.index('docker(["start", VC])'))
        self.assertNotIn('"rm"',s)
        self.assertNotIn('"run"',s)
        self.assertNotIn('"kill"',s)
if __name__=="__main__":
    unittest.main()
