"""R228 exact EIP-712 domains for V2, not V1, plus evidence-only commitments."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r228_v2_typed_data as m

MARKET="0x"+"11"*20
LEDGER="0x"+"22"*20
HASH="0x"+"ab"*32
OTHER_HASH="0x"+"cd"*32

PROVIDER={
    "leaseId":1,"epochId":0,
    "requestHash":HASH,"responseHash":OTHER_HASH,
}
VOTE={
    **PROVIDER,"outcome":1,"evidenceHash":HASH
}
RESIDUAL={
    "leaseId":1,"epochId":0,"consumerShare":500,"providerShare":300,
    "nonce":0,"expiry":123456,
}

class TestR228RealV2SignatureSchema(unittest.TestCase):
    def test_provider_message_exact_market_domain(self):
        t=m.typed_data("provider-response",PROVIDER,MARKET,LEDGER)
        self.assertEqual(t["domain"],{
            "name":"SSEAdaptiveMarketV2","version":"1","chainId":31340,
            "verifyingContract":MARKET})
        self.assertEqual(t["primaryType"],"ProviderResponse")
        self.assertEqual(t["types"]["ProviderResponse"],[
            {"name":"leaseId","type":"uint256"},
            {"name":"epochId","type":"uint256"},
            {"name":"requestHash","type":"bytes32"},
            {"name":"responseHash","type":"bytes32"},
        ])
        self.assertEqual(t["message"],PROVIDER)

    def test_monitor_vote_exact_ledger_domain(self):
        t=m.typed_data("monitor-vote",VOTE,MARKET,LEDGER)
        self.assertEqual(t["domain"]["name"],"SSEAdaptiveCommitteeVotes")
        self.assertEqual(t["domain"]["verifyingContract"],LEDGER)
        self.assertEqual(t["primaryType"],"MonitorVote")
        self.assertEqual([f["name"] for f in t["types"]["MonitorVote"]],[
            "leaseId","epochId","requestHash","outcome","responseHash","evidenceHash"
        ])

    def test_residual_allocation_exact_market_domain(self):
        t=m.typed_data("residual-allocation",RESIDUAL,MARKET,LEDGER)
        self.assertEqual(t["domain"]["name"],"SSEAdaptiveMarketV2")
        self.assertEqual(t["domain"]["verifyingContract"],MARKET)
        self.assertEqual([f["name"] for f in t["types"]["ResidualAllocation"]],[
            "leaseId","epochId","consumerShare","providerShare","nonce","expiry"
        ])

    def test_success_failure_protocol_invariants(self):
        for bad in [
            {**VOTE,"outcome":3},
            {**VOTE,"outcome":True},
            {**VOTE,"responseHash":m.ZERO},
            {**VOTE,"outcome":2},
            {**VOTE,"evidenceHash":m.ZERO},
        ]:
            with self.subTest(bad=bad),self.assertRaises(m.Refused):
                m.typed_data("monitor-vote",bad,MARKET,LEDGER)
        failure={**VOTE,"outcome":2,"responseHash":m.ZERO}
        self.assertEqual(m.typed_data("monitor-vote",failure,MARKET,LEDGER)
                         ["message"]["responseHash"],m.ZERO)

    def test_reject_v1_domain_or_wrong_contract_or_structure(self):
        with self.assertRaises(m.Refused):
            m.typed_data("provider-response",PROVIDER,MARKET,MARKET)
        with self.assertRaises(m.Refused):
            m.typed_data("provider-response",{**PROVIDER,"newField":3},MARKET,LEDGER)
        with self.assertRaises(m.Refused):
            m.typed_data("provider-response",{**PROVIDER,"leaseId":0},MARKET,LEDGER)
        with self.assertRaises(m.Refused):
            m.typed_data("residual-allocation",{**RESIDUAL,"expiry":0},MARKET,LEDGER)
        with self.assertRaises(m.Refused):
            m.typed_data("residual-allocation",{**RESIDUAL,"consumerShare":2**256-1,
                                                "providerShare":1},MARKET,LEDGER)

    def test_signed_public_eoa_recovers_only_exact_domain_and_scope(self):
        try:
            from eth_account import Account
            from eth_account.messages import encode_typed_data
        except ImportError:
            self.skipTest("eth-account not installed locally")
        ephemeral=Account.create()
        envelope=m.typed_data("provider-response",PROVIDER,MARKET,LEDGER)
        signed=Account.sign_message(encode_typed_data(full_message=envelope),
                                    private_key=ephemeral.key)
        public_signature="0x"+bytes(signed.signature).hex()
        self.assertTrue(m.verify_public_signer("provider-response",PROVIDER,
                                               MARKET,LEDGER,public_signature,
                                               ephemeral.address))
        self.assertFalse(m.verify_public_signer("provider-response",PROVIDER,
                                                LEDGER,MARKET,public_signature,
                                                ephemeral.address))
        self.assertFalse(m.verify_public_signer("provider-response",
                         {**PROVIDER,"requestHash":OTHER_HASH},MARKET,LEDGER,
                         public_signature,ephemeral.address))

    def test_evidence_digest_order_invariant_but_not_sla_truth(self):
        observation={
            "leaseId":1,"epochId":0,"monitor":MARKET,
            "observedAtUtc":"2026-11-23T16:00:00Z",
            "endpoint":"https://example.net","method":"POST",
            "responseSha256":"aa"*32,"rawObservationSha256":"bb"*32,
            "latencyMs":177,"httpStatus":200,"source":"actual-probe-record"
        }
        one=m.evidence_commitment(observation)
        self.assertEqual(one,m.evidence_commitment(dict(reversed(
            list(observation.items())))))
        self.assertRegex(one,r"^0x[0-9a-f]{64}$")
        with self.assertRaises(m.Refused):
            m.evidence_commitment({**observation,"outcome":"Success"})
        with self.assertRaises(m.Refused):
            m.evidence_commitment({**observation,"latencyMs":-2})
        with self.assertRaises(m.Refused):
            m.evidence_commitment({**observation,"monitor":"bad"})

if __name__=="__main__":
    unittest.main()
