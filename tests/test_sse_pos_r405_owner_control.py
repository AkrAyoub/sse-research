"""R405: authorization regression tests; no real service suspension or transactions."""
import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from eth_account import Account
from sse_pos_r399_owner_control_auth import challenge,typed,wallet_payload,verify_and_consume
from sse_pos_r401_provider_control import ProviderControl
from sse_pos_r403_owner_control_web import dispatch

class AuthTests(unittest.TestCase):
    def setUp(self):
        self.owner=Account.create()
        self.other=Account.create()
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store=Path(self.tmp.name)/"nonces"
        self.params={"seconds":15}
        self.d=challenge("test-node",self.owner.address,"provider-interrupt",self.params,now=1000)
    def sig(self,account=None,d=None):
        return "0x"+(account or self.owner).sign_message(typed(d or self.d)).signature.hex().removeprefix("0x")
    def check(self,**overrides):
        kw=dict(d=self.d,signature=self.sig(),params=self.params,node="test-node",owner=self.owner.address,issued=self.d,store=self.store,now=1001)
        kw.update(overrides)
        return verify_and_consume(**kw)
    def test_valid(self):
        self.assertEqual(self.check()["parameters"],self.params)
    def test_replay(self):
        self.check()
        with self.assertRaises(ValueError):self.check()
    def test_wrong_wallet(self):
        with self.assertRaises(ValueError):self.check(signature=self.sig(self.other))
    def test_expired(self):
        with self.assertRaises(ValueError):self.check(now=1121)
    def test_wrong_node(self):
        with self.assertRaises(ValueError):self.check(node="other-node")
    def test_changed_duration(self):
        with self.assertRaises(ValueError):self.check(params={"seconds":60})
    def test_unissued_challenge(self):
        d=challenge("test-node",self.owner.address,"provider-interrupt",self.params,now=1000)
        with self.assertRaises(ValueError):self.check(d=d,signature=self.sig(d=d))
    def test_signed_visible_duration(self):
        self.assertEqual(wallet_payload(self.d)["message"]["durationSeconds"],15)
    def test_invalid_duration(self):
        for value in (0,241,True,"15"):
            with self.assertRaises(ValueError):
                challenge("test-node",self.owner.address,"provider-interrupt",{"seconds":value})
    def test_broker(self):
        with patch("sse_pos_r401_provider_control.identity",return_value="process-identity"),patch("sse_pos_r401_provider_control.pause",return_value="test-recovery.timer") as pause:
            broker=ProviderControl(node="test-node",owner=self.owner.address,pid=123,store=self.store)
            c=dispatch(broker,"/v3/control/challenge",self.params)
            d=c["challenge"]
            with self.assertRaises(ValueError):
                dispatch(broker,"/v3/control/approve",dict(challenge=d,signature=self.sig(self.other,d),parameters=self.params))
            pause.assert_not_called()
            r=dispatch(broker,"/v3/control/approve",dict(challenge=d,signature=self.sig(d=d),parameters=self.params))
            self.assertTrue(r["providerPaused"])
            self.assertFalse(r["recoveryVerified"])
            pause.assert_called_once_with(123,15,expected_identity="process-identity")
            with self.assertRaises(ValueError):
                dispatch(broker,"/v3/control/approve",dict(challenge=d,signature=self.sig(d=d),parameters=self.params))
    def test_unknown_route(self):
        with self.assertRaises(ValueError):dispatch(None,"/shell",{})
if __name__=="__main__":unittest.main()
