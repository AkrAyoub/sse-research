"""No-network tests of one-time SSE mesh bootstrap broker and tagged key minting."""
import importlib.util
import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("sse_mesh_broker",ROOT/"tools"/"sse_mesh_broker.py")
b=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=b
spec.loader.exec_module(b)


class MeshBrokerTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:",isolation_level=None)
        self.addCleanup(self.db.close)

    def test_single_use_only(self):
        tok=b.issue_token(self.db,"provider-01","provider",now=1000)
        b.redeem_token(self.db,"provider-01","provider",tok,now=1001)
        with self.assertRaises(b.EnrollmentError):
            b.redeem_token(self.db,"provider-01","provider",tok,now=1002)

    def test_expired_tokens_fail(self):
        tok=b.issue_token(self.db,"monitor-01","monitor",now=1000)
        with self.assertRaises(b.EnrollmentError):
            b.redeem_token(self.db,"monitor-01","monitor",tok,now=1600)

    def test_wrong_roles_does_not_consume_valid_token(self):
        tok=b.issue_token(self.db,"node-a","provider",now=1000)
        with self.assertRaises(b.EnrollmentError):
            b.redeem_token(self.db,"node-a","monitor",tok,now=1001)
        b.redeem_token(self.db,"node-a","provider",tok,now=1002)

    def test_wrong_node_does_not_consume_valid_token(self):
        tok=b.issue_token(self.db,"node-a","provider",now=1000)
        with self.assertRaises(b.EnrollmentError):
            b.redeem_token(self.db,"node-b","provider",tok,now=1001)
        b.redeem_token(self.db,"node-a","provider",tok,now=1002)

    def test_invalid_roles_and_names_fail(self):
        for name,roles in [("../bad","provider"),("node-a","provider,provider"),
                           ("node-a","validator"),("node-a","monitor,")]:
            with self.subTest(name=name,roles=roles), self.assertRaises(b.EnrollmentError):
                b.issue_token(self.db,name,roles)

    def test_db_stores_only_digest(self):
        tok=b.issue_token(self.db,"node-a","observer",now=1000)
        row=self.db.execute("select digest,node_id from enrollment").fetchone()
        self.assertNotEqual(row[0],tok)
        self.assertEqual(len(row[0]),64)
        self.assertEqual(row[1],"node-a")

    def test_oauth_flow_scoped_and_nonreusable(self):
        calls=[]
        def stub(url,body,headers):
            calls.append((url,body,headers))
            if url.endswith("/oauth/token"):
                return {"access_token":"access-test"}
            return {"key":"tskey-auth-short-test"}
        key=b.mint_tailscale_auth_key("id","secret",post=stub)
        self.assertEqual(key,"tskey-auth-short-test")
        self.assertEqual(len(calls),2)
        config=json.loads(calls[1][1])
        rule=config["capabilities"]["devices"]["create"]
        self.assertFalse(rule["reusable"])
        self.assertFalse(rule["ephemeral"])
        self.assertTrue(rule["preauthorized"])
        self.assertEqual(rule["tags"],["tag:sse-node"])
        self.assertEqual(config["expirySeconds"],300)

    def test_reject_bad_upstream_auth_key_and_tag(self):
        def mock(url,body,headers):
            return {"access_token":"ok"} if url.endswith("/oauth/token") else {"key":"no"}
        with self.assertRaises(b.EnrollmentError):
            b.mint_tailscale_auth_key("id","secret",post=mock)
        with self.assertRaises(b.EnrollmentError):
            b.mint_tailscale_auth_key("id","secret",tag="tag:admin",post=mock)

if __name__=="__main__":
    unittest.main()
