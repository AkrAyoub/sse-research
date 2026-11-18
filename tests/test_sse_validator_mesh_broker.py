"""Offline secure validator-only OAuth invitation broker tests."""
import io
from contextlib import closing
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_validator_mesh_broker import (
    ValidatorInviteError, issue_invitation, redeem_invitation,
    mint_validator_key, ValidatorInvitationApp, TAG
)


def call_wsgi(app, *, path="/v1/mesh/validator", method="POST", body=None):
    raw=json.dumps(body or {}).encode("utf-8")
    env={
        "REQUEST_METHOD":method, "PATH_INFO":path,
        "CONTENT_TYPE":"application/json",
        "CONTENT_LENGTH":str(len(raw)),
        "wsgi.input":io.BytesIO(raw),
    }
    response=[]
    def start(status,headers):
        response.append(status)
    body=b"".join(app(env,start))
    return response[0],json.loads(body)


class ValidatorBrokerTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(":memory:",isolation_level=None)
        self.addCleanup(self.conn.close)

    def test_one_use_invitation_and_wrong_role(self):
        token=issue_invitation(self.conn,"validator-2",now=1000)
        with self.assertRaises(ValidatorInviteError):
            redeem_invitation(self.conn,"validator-1",token,now=1001)
        redeem_invitation(self.conn,"validator-2",token,now=1002)
        with self.assertRaises(ValidatorInviteError):
            redeem_invitation(self.conn,"validator-2",token,now=1003)

    def test_expiration_and_invalid_roles(self):
        token=issue_invitation(self.conn,"validator-3",now=1000)
        with self.assertRaises(ValidatorInviteError):
            redeem_invitation(self.conn,"validator-3",token,now=1600)
        for node in ("validator-5","monitor","provider","root","validator-1,consumer"):
            with self.subTest(node=node),self.assertRaises(ValidatorInviteError):
                issue_invitation(self.conn,node)
        with self.assertRaises(ValidatorInviteError):
            issue_invitation(self.conn,"validator-1",ttl_seconds=86400)

    def test_database_never_stores_token(self):
        token=issue_invitation(self.conn,"validator-1",now=1000)
        row=self.conn.execute("SELECT digest,node_id FROM validator_invitation").fetchone()
        self.assertNotEqual(row[0],token)
        self.assertEqual(len(row[0]),64)
        self.assertEqual(row[1],"validator-1")

    def test_dedicated_oauth_only_mints_validator_tag(self):
        calls=[]
        def fake(url,body,headers):
            calls.append((url,body,headers))
            return {"access_token":"fake-broker-access"} if url.endswith("/oauth/token") else {"key":"tskey-auth-test"}
        key=mint_validator_key("id","secret",post=fake)
        self.assertEqual(key,"tskey-auth-test")
        data=json.loads(calls[1][1])
        opts=data["capabilities"]["devices"]["create"]
        self.assertEqual(opts["tags"],[TAG])
        self.assertFalse(opts["reusable"])
        self.assertFalse(opts["ephemeral"])
        self.assertTrue(opts["preauthorized"])
        self.assertEqual(data["expirySeconds"],300)
        self.assertNotIn("tag:sse-node",json.dumps(opts))

    def test_wsgi_exact_token_and_consumed_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"broker.db"
            with closing(sqlite3.connect(db,isolation_level=None)) as conn:
                token=issue_invitation(conn,"validator-1")
            minted=[]
            def mint(client_id,secret,*,tailnet):
                minted.append((client_id,tailnet))
                return "tskey-auth-short"
            app=ValidatorInvitationApp(db,"id","private",mint=mint)
            payload={"node_id":"validator-1","invitation":token}
            status,body=call_wsgi(app,body=payload)
            self.assertEqual(status,"200 OK")
            self.assertEqual(body["role"],"validator-overlay-only")
            self.assertFalse(body["qbftVotingGranted"])
            self.assertEqual(body["tailnetAuthKey"],"tskey-auth-short")
            status,body=call_wsgi(app,body=payload)
            self.assertEqual(status,"403 Forbidden")
            self.assertEqual(len(minted),1)

    def test_wrong_identity_does_not_burn_invitation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"broker.db"
            with closing(sqlite3.connect(db,isolation_level=None)) as conn:
                token=issue_invitation(conn,"validator-1")
            app=ValidatorInvitationApp(db,"id","secret",
                      mint=lambda *a,**kw:"tskey-auth-short")
            bad={"node_id":"validator-2","invitation":token}
            self.assertEqual(call_wsgi(app,body=bad)[0],"403 Forbidden")
            self.assertEqual(call_wsgi(app,body={**bad,"node_id":"validator-1"})[0],"200 OK")

    def test_rejects_extra_fields_and_get(self):
        app=ValidatorInvitationApp(Path("/no/fake/db"),"id","secret")
        self.assertEqual(call_wsgi(app,method="GET")[0],"405 Method Not Allowed")
        self.assertEqual(call_wsgi(app,body={"node_id":"validator-1","invitation":"fake",
                                            "roles":"monitor"})[0],"403 Forbidden")
        self.assertEqual(call_wsgi(app,path="/v1/mesh/enroll")[0],"404 Not Found")

    def test_upstream_failure_burns_invitation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"broker.db"
            with closing(sqlite3.connect(db,isolation_level=None)) as conn:
                token=issue_invitation(conn,"validator-1")
            app=ValidatorInvitationApp(db,"id","secret",
                      mint=lambda *a,**kw: (_ for _ in ()).throw(ValidatorInviteError("upstream")))
            body={"node_id":"validator-1","invitation":token}
            self.assertEqual(call_wsgi(app,body=body)[0],"403 Forbidden")
            with closing(sqlite3.connect(db,isolation_level=None)) as conn:
                with self.assertRaises(ValidatorInviteError):
                    redeem_invitation(conn,"validator-1",token)


if __name__=="__main__":
    unittest.main()
