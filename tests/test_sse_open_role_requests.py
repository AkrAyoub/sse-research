"""Signed open role requests verify identity without awarding privileges."""
import copy
import secrets
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from eth_account import Account
import sse_open_role_requests as app

GEN="0x"+"ab"*32
KEY=(1).to_bytes(32,"big")
ACTOR=Account.from_key(KEY).address
TIME=1795000000

def request(roles=None,transport="auto"):
    return {
        "schema":app.SCHEMA,"chainId":31338,"genesisHash":GEN,
        "nodeId":"open-node-12345","account":ACTOR,
        "roles":list(roles or ["observer","provider","validator"]),
        "transportPreference":transport,"nonce":"0x"+"c1"*32,
        "issuedAt":TIME-1,"expiresAt":TIME+300,
    }

def signed(data):
    signature = Account.sign_message(
        app.signing_message(data),private_key=KEY).signature
    return {"request":data,"walletSignature":"0x"+bytes(signature).hex()}

class RoleRequestTests(unittest.TestCase):
    def test_valid_mixed_roles_are_requests_not_authorizations(self):
        envelope=signed(request())
        result=app.verify(envelope,now=TIME,genesis_hash=GEN)
        self.assertEqual(result["requestedRoles"],["observer","provider","validator"])
        self.assertTrue(result["walletSignatureVerified"])
        self.assertFalse(result["eligibilityVerified"])
        self.assertEqual(result["rolesActivated"],[])
        self.assertFalse(result["validatorVoteGranted"])
        self.assertFalse(result["networkTransportEstablished"])
        self.assertFalse(result["ethereumTransactionsSent"])
        self.assertIn("consensus-specific admission",
                      result["eligibilityRequirements"]["validator"])

    def test_all_supported_roles_can_be_requested_with_wallet_proof(self):
        req=request(list(app.ROLES))
        r=app.verify(signed(req),now=TIME,genesis_hash=GEN)
        self.assertEqual(r["requestedRoles"],list(app.ROLES))
        self.assertEqual(len(r["eligibilityRequirements"]),6)

    def test_untrusted_transport_is_not_privilege_grant(self):
        for transport in ("native-p2p","relay","tailscale","existing-tailnet","auto"):
            with self.subTest(transport=transport):
                r=app.verify(signed(request(transport=transport)),
                             now=TIME,genesis_hash=GEN)
                self.assertFalse(r["networkTransportEstablished"])
                self.assertFalse(r["validatorVoteGranted"])

    def test_role_tampering_or_wrong_key_or_chain_invalidates_signature(self):
        base=signed(request())
        for changes in (
            {"roles":["observer","provider"]},
            {"nodeId":"open-node-99999"},
            {"transportPreference":"tailscale"},
            {"nonce":"0x"+"aa"*32},
            {"genesisHash":"0x"+"de"*32},
            {"account":"0x"+"2"*40},
        ):
            with self.subTest(changes=changes):
                altered=copy.deepcopy(base)
                altered["request"].update(changes)
                with self.assertRaises(app.RoleRequestError):
                    app.verify(altered,now=TIME)

    def test_rejects_expired_wrong_genesis_and_replay_claims(self):
        envelope=signed(request())
        with self.assertRaises(app.RoleRequestError):
            app.verify(envelope,now=TIME+301)
        with self.assertRaises(app.RoleRequestError):
            app.verify(envelope,now=TIME,genesis_hash="0x"+"ff"*32)
        self.assertEqual(app.verify(envelope,now=TIME)["rolesActivated"],[])

    def test_duplicate_unknown_noncanonical_roles_rejected(self):
        for roles in (["monitor","monitor"],["validator","god"],[],
                      ["validator","observer"],["observer","consumer","consumer"]):
            with self.subTest(roles=roles):
                with self.assertRaises(app.RoleRequestError):
                    app.inspect_request(request(roles),now=TIME)
        self.assertEqual(app.requested_roles("validator,consumer"),
                         ("consumer","validator"))

    def test_signature_from_other_account_does_not_prove_identity(self):
        d=request()
        env=signed(d)
        env["walletSignature"]="0x"+Account.sign_message(
            app.signing_message(d),private_key=(2).to_bytes(32,"big")
        ).signature.hex().removeprefix("0x")
        with self.assertRaises(app.RoleRequestError):
            app.verify(env,now=TIME)

if __name__=="__main__":
    unittest.main()
