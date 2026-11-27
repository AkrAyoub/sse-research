"""R299 policy tests: no live chain calls or transactions."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r299_optional_tls_rpc_relay as m

def request(method,params=None):
    return json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params or []}).encode()

class RelayPolicy(unittest.TestCase):
    def test_read_methods(self):
        for method in m.READ-{"eth_getLogs"}:
            self.assertEqual(m.validate(request(method))["method"],method)
    def test_no_admin_or_unlocked_send(self):
        for method in ("admin_addPeer","engine_newPayloadV3","personal_unlockAccount","eth_sendTransaction","debug_traceTransaction"):
            with self.subTest(method=method),self.assertRaises(ValueError):
                m.validate(request(method),True)
    def test_raw_opt_in(self):
        raw=request("eth_sendRawTransaction",["0x0102"])
        with self.assertRaises(ValueError): m.validate(raw)
        self.assertEqual(m.validate(raw,True)["method"],"eth_sendRawTransaction")
        for value in ("0x","0x1","wrong",42):
            with self.assertRaises(ValueError): m.validate(request("eth_sendRawTransaction",[value]),True)
    def test_logs_bounded(self):
        m.validate(request("eth_getLogs",[{"fromBlock":"0x1","toBlock":"0x800"}]))
        for f in ({},{"fromBlock":"0x1","toBlock":"latest"},{"fromBlock":"0x0","toBlock":"0x801"},{"fromBlock":"0x2","toBlock":"0x1"}):
            with self.assertRaises(ValueError): m.validate(request("eth_getLogs",[f]))
    def test_bad_payload(self):
        for raw in (b"[]",b"{}",b'{"jsonrpc":"2.0","id":1,"id":2,"method":"eth_chainId","params":[]}',b"x"*(m.MAX_REQUEST+1)):
            with self.assertRaises(ValueError): m.validate(raw)
    def test_overlay_only(self):
        self.assertEqual(m.overlay("fca0:2328:77e5:740c:ce60::1"),"fca0:2328:77e5:740c:ce60::1")
        for address in ("::1","::","2001:db8::1","10.50.56.8"):
            with self.assertRaises(ValueError): m.overlay(address)
if __name__=="__main__":
    unittest.main()
