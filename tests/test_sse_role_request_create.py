"""Open multi-role request generation without secrets or network calls."""
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_role_request_create import build,write_exclusive
from sse_open_role_requests import RoleRequestError, inspect_request

GEN="0x"+"ab"*32
ADDRESS="0x"+"11"*20

class RoleRequestCreateTests(unittest.TestCase):
    def test_any_role_combination_including_validator(self):
        r=build(node_id="node-abcdefgh",account=ADDRESS,
                roles="validator,monitor,full_node,consumer",
                genesis_hash=GEN,transport="native-p2p",now=1795000000)
        self.assertEqual(r["roles"],["full_node","consumer","monitor","validator"])
        self.assertEqual(r["transportPreference"],"native-p2p")
        self.assertEqual(inspect_request(r,now=1795000001,genesis_hash=GEN),
                         ("full_node","consumer","monitor","validator"))
        self.assertEqual(len(r["nonce"]),66)

    def test_duplicate_roles_or_bad_transport_rejected(self):
        for roles in ("consumer,consumer","validator,admin",""):
            with self.subTest(roles=roles),self.assertRaises(RoleRequestError):
                build(node_id="node-abcdefgh",account=ADDRESS,
                      roles=roles,genesis_hash=GEN,now=1795000000)
        with self.assertRaises(RoleRequestError):
            build(node_id="node-abcdefgh",account=ADDRESS,
                  roles="validator",genesis_hash=GEN,
                  transport="mandatory-owners-tailnet",now=1795000000)

    def test_output_created_once_and_no_wallet_secrets(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/"role-request.json"
            d=build(node_id="node-abcdefgh",account=ADDRESS,
                    roles="observer",genesis_hash=GEN,now=1795000000)
            write_exclusive(file,d)
            self.assertTrue(file.is_file())
            data=file.read_text()
            self.assertIn("observer",data)
            self.assertNotIn("privateKey",data)
            with self.assertRaises(RoleRequestError):
                write_exclusive(file,d)
            self.assertEqual(d,file.read_text() and __import__("json").loads(data))

if __name__=="__main__":
    unittest.main()
