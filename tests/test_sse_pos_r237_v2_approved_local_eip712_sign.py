"""R237 local EIP712 wallet consent: mocks prove authorization, never real secrets."""
from pathlib import Path
import json
import os
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r237_v2_approved_local_eip712_sign as m

MARKET="0x"+"11"*20
LEDGER="0x"+"22"*20
GENESIS="0x13fb73aace8a11be2899d047635a757a224ce00b"
E0A="0x"+"44"*20
HASH="0x"+"ab"*32
PAYLOAD={
    "leaseId":1,"epochId":0,"requestHash":HASH,"responseHash":HASH
}
MANIFEST={
    "market":{"address":MARKET},"ledger":{"address":LEDGER},
    "deploymentTxHash":"0x"+"ff"*32,
}

FINISHED_PROVENANCE={
    "lease":{"provider":E0A,"consumer":"0x"+"55"*20,
             "phase":4,"providerAccepted":True},
    "epoch":{"market":{"exists":True,"requestHash":HASH,"feeWei":3,
                       "nonce":0,"resolved":False},
             "ledger":{"responseAuthenticated":False,
                       "monitoringSealed":False,"outcome":0,"responseHash":HASH}},
    "committee":{"ready":True},
    "selectedMonitors":[E0A],
}

class TestR237ApprovedSigningGate(unittest.TestCase):
    def test_dry_run_has_only_public_intent_no_encrypted_wallet(self):
        intent=m.public_intent("provider-response",PAYLOAD,MARKET,LEDGER,E0A,"provider")
        self.assertFalse(intent["privateKeyRead"])
        self.assertFalse(intent["transactionSignedOrSubmitted"])
        self.assertEqual(intent["typedData"]["domain"]["chainId"],31340)
        self.assertEqual(intent["expectedSigner"],E0A)

    def test_refuses_original_owner_wallet_even_for_lab_data(self):
        with self.assertRaises(m.Refused):
            m.public_intent("provider-response",PAYLOAD,MARKET,LEDGER,GENESIS,"provider")
        with self.assertRaises(m.Refused):
            m.public_intent("provider-response",PAYLOAD,MARKET,LEDGER,E0A,"monitor")
        self.assertEqual(m.public_intent(
            "residual-allocation",{
                "leaseId":1,"epochId":0,"consumerShare":1,
                "providerShare":2,"nonce":0,"expiry":5000
            },MARKET,LEDGER,E0A,"consumer")["role"],"consumer")

    def test_refuses_wrong_public_manifest_and_unapproved_tty(self):
        intent=m.public_intent("provider-response",PAYLOAD,MARKET,LEDGER,E0A,"provider")
        bad={**MANIFEST,"market":{"address":LEDGER}}
        with self.assertRaises(m.Refused):
            m.sign_authorized(intent,Path("/no/wallet"),bad,"http://127.0.0.1:28545",
                              confirm=lambda p:"",get_password=lambda p:"",
                              expected_tty=False)
        with patch.object(m.sys,"stdin",new=type("NonTty",(),{"isatty":lambda self:False})()):
            with self.assertRaises(m.Refused):
                m.sign_authorized(intent,Path("/no/wallet"),MANIFEST,
                                  "http://127.0.0.1:28545",
                                  confirm=lambda p:"",get_password=lambda p:"")

    def test_keystore_requires_nonroot_private_directory_and_encryption(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"wallet.json"
            # pathlib.Path(...) returns the concrete OS subclass PosixPath
            # on Linux; production owner-local keystores must be accepted.
            self.assertIsInstance(path,Path)
            self.assertIsNot(type(path),Path)
            raw={"crypto":{"cipher":"aes-128-ctr","ciphertext":"a"*240,
                            "cipherparams":{},"kdf":"scrypt","kdfparams":{},"mac":"a"*64},
                 "id":"id","version":3}
            path.write_text(json.dumps(raw))
            os.chmod(td,0o700)
            os.chmod(path,0o600)
            with patch.object(m.os,"geteuid",return_value=0),self.assertRaises(m.Refused):
                m.safe_keystore(path)
            # No accidental reliance on caller environment in mocked euid.
            uid=os.geteuid()
            if uid!=0:
                self.assertEqual(m.safe_keystore(path)["version"],3)
            os.chmod(path,0o644)
            with self.assertRaises(m.Refused):
                m.safe_keystore(path)

    def test_no_signing_when_user_declines_consent(self):
        intent=m.public_intent("provider-response",PAYLOAD,MARKET,LEDGER,E0A,"provider")
        with patch.object(m,"verify",return_value={
            "deploymentReceiptSuccessfulAndFinalized":True
        }), patch.object(m,"inspect_finalized_lease",
                         return_value=FINISHED_PROVENANCE), patch.object(
                         m,"safe_keystore",return_value={"version":3}):
            with self.assertRaises(m.Refused):
                m.sign_authorized(intent,Path("/private/not-read"),MANIFEST,
                                  "http://127.0.0.1:28545",
                                  confirm=lambda p:"NO",get_password=lambda p:"",
                                  expected_tty=False)

    def test_actual_finalized_public_role_gate_blocks_forged_eoa(self):
        intent=m.public_intent("provider-response",PAYLOAD,MARKET,LEDGER,E0A,"provider")
        self.assertTrue(m.verify_public_role_state(intent,FINISHED_PROVENANCE))
        with self.assertRaises(m.Refused):
            m.verify_public_role_state(intent,{
                **FINISHED_PROVENANCE,"lease":{
                    **FINISHED_PROVENANCE["lease"],"provider":"0x"+"66"*20}})
        with self.assertRaises(m.Refused):
            m.verify_public_role_state(intent,{
                **FINISHED_PROVENANCE,"epoch":{
                    **FINISHED_PROVENANCE["epoch"],
                    "market":{"exists":True,"requestHash":"0x"+"ff"*32}}})
        with self.assertRaises(m.Refused):
            m.verify_public_role_state(intent,{
                **FINISHED_PROVENANCE,"epoch":{
                    **FINISHED_PROVENANCE["epoch"],
                    "ledger":{**FINISHED_PROVENANCE["epoch"]["ledger"],
                              "responseAuthenticated":True}}})

    def test_offline_cli_cannot_use_keys_unless_sign_flag(self):
        import io
        import contextlib
        args=["--kind","provider-response","--role","provider",
              "--message-json",json.dumps(PAYLOAD),
              "--market",MARKET,"--ledger",LEDGER,
              "--expected-signer",E0A]
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(m.main(args),0)
        self.assertFalse(json.loads(out.getvalue())["privateKeyRead"])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(m.main(args+["--keystore","/tmp/notreal"]),2)
            self.assertEqual(m.main(args+["--sign"]),2)

if __name__=="__main__":
    unittest.main()
