import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import sse_v4_select_roles as roles
import sse_v4_upgrade_managed_rpc as rpc
class RoleMenu(unittest.TestCase):
    def test_numeric_and_names(self):
        self.assertEqual(roles.parse("3, 4"),"monitor,keeper")
        self.assertEqual(roles.parse("2, Monitor"),"provider,monitor")
    def test_invalid(self):
        for x in ("","5","monitor,3","monitor,","full_node"):
            with self.assertRaises(ValueError):roles.parse(x)
class LegacyRPC(unittest.TestCase):
    def test_known_variants(self):
        home=Path("/home/example")
        tail=["/home/example/sse/tools/sse_pos_r299_optional_tls_rpc_relay.py","client","--remote",rpc.REMOTE,"--cert","/home/example/cert","--fingerprint",rpc.FP]
        for prefix in (["/usr/bin/python3","-B"],["/home/example/.venvs/old/bin/python"],["python"]):
            opts,args=rpc.parse_existing(prefix+tail,"client",home)
            self.assertEqual(opts["--fingerprint"],rpc.FP)
            self.assertEqual(args[0],"client")
        with self.assertRaises(RuntimeError):rpc.parse_existing(["python"]+tail+["--unknown"],"client",home)
        with self.assertRaises(RuntimeError):rpc.parse_existing(["python","/tmp/tools/sse_pos_r299_optional_tls_rpc_relay.py"]+tail[1:],"client",home)
if __name__=="__main__": unittest.main()
