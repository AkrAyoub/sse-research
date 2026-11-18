"""Offline tests of fresh-node headless join and non-escalation guarantees."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_validator_mesh_join as m


class ValidatorJoinTests(unittest.TestCase):
    def test_dry_run_is_not_join_and_requires_restricted_tag(self):
        p=m.plan("validator-2","https://enroll.tail123.ts.net")
        self.assertEqual(p["nodeId"],"validator-2")
        self.assertEqual(p["aclTag"],"tag:sse-validator")
        self.assertFalse(p["tailnetJoined"])
        self.assertFalse(p["qbftVotingGranted"])
        self.assertFalse(p["ethereumTransactionsSent"])

    def test_rejects_invalid_id_url_and_token_location(self):
        for ident in ("consumer","validator-5","provider","validator-1,monitor"):
            with self.subTest(ident=ident),self.assertRaises(ValueError):
                m.plan(ident,"https://enroll.tail123.ts.net")
        for url in ("http://enroll.tail123.ts.net","https://admin:secret@bad.test",
                    "https://enroll.tail123.ts.net/path"):
            with self.subTest(url=url),self.assertRaises(ValueError):
                m.plan("validator-1",url)
        with self.assertRaises(m.JoinError):
            m.plan("validator-1","https://enroll.tail123.ts.net",
                   invitation_file="/tmp/other.token")

    def test_existing_authenticated_tailnet_never_reenrolled(self):
        for state in (
            {"BackendState":"Running","Self":{"Online":True}},
            {"BackendState":"Running","Self":{"Online":False}},
        ):
            with self.subTest(state=state),self.assertRaises(m.JoinError):
                m.already_connected(state)
        self.assertFalse(m.already_connected({"BackendState":"NeedsLogin"}))
        self.assertFalse(m.already_connected({"BackendState":"Stopped"}))
        with self.assertRaises(m.JoinError):
            m.already_connected({"BackendState":"Starting"})

    def test_preexisting_device_fails_before_fetch_or_auth_file(self):
        cfg=m.plan("validator-1","https://enroll.tail123.ts.net")
        calls=[]
        def run(argv):
            calls.append(argv)
            return json.dumps({"BackendState":"Running","Self":{
                "Online":True,"ID":"n-existing","TailscaleIPs":["100.65.29.101"]}})
        def refuse(*a,**kw):
            raise AssertionError("must not fetch or inspect credentials on joined VM")
        # Requires root normally, but overridden to simulate this unit scenario.
        with patch.object(m.shutil,"which",return_value="/usr/bin/tailscale"):
            with self.assertRaises(m.JoinError):
                m.join(cfg,fetch=refuse,call=run,check_file=refuse,
                       require_root=lambda:None)
        self.assertEqual(calls,[["tailscale","status","--json"]])

    def test_tampered_plan_rejected_before_privilege(self):
        cfg=m.plan("validator-1","https://enroll.tail123.ts.net")
        altered={**cfg,"aclTag":"tag:admin"}
        with self.assertRaises(m.JoinError):
            m.join(altered,require_root=lambda: (_ for _ in ()).throw(
                AssertionError("privileged action forbidden")))

    def test_invalid_broker_response_never_accepted(self):
        # Guard the exact client-side response contract, including QBFT no-vote.
        from unittest.mock import patch
        class Result:
            status=200
            def __init__(self,data): self.data=json.dumps(data).encode()
            def __enter__(self): return self
            def __exit__(self,*a): return False
            def read(self,limit): return self.data[:limit]
        class Opener:
            def __init__(self,data): self.data=data
            def open(self,req,timeout=10): return Result(self.data)
        base={
            "nodeId":"validator-1","role":"validator-overlay-only",
            "tailnetAuthKey":"tskey-auth-abc","expiresInSeconds":300,
            "qbftVotingGranted":False,
        }
        with patch.object(m,"build_opener",return_value=Opener(base)):
            self.assertEqual(m.request_key("https://enroll.tail123.ts.net",
                     "validator-1","v"*40),"tskey-auth-abc")
        for change in (
            {"role":"monitor"},
            {"nodeId":"validator-4"},
            {"qbftVotingGranted":True},
            {"tailnetAuthKey":"invalid"},
        ):
            with self.subTest(change=change),patch.object(
                m,"build_opener",return_value=Opener({**base,**change})):
                with self.assertRaises(m.JoinError):
                    m.request_key("https://enroll.tail123.ts.net",
                                  "validator-1","v"*40)


if __name__=="__main__":
    unittest.main()
