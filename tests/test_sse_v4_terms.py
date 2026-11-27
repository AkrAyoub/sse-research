"""Static-shape tests for V4 encoders. SOURCE-ONLY: written 2026-11-27, not executed.
Cross-checking against compiled Solidity is deferred (DRV-V4-PARITY)."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_v4_terms as t

Z = "0x" + "11" * 32
REQ = {"consumer": "0x" + "aa" * 20, "status": 2, "fixedEpochs": 3, "maxEpochs": 3, "seats": 4,
       "standbys": 2, "faultTolerance": 1, "biddingClose": 1000, "profileHash": Z, "policyHash": Z,
       "artifactCommitment": Z, "maxEpochFee": 100, "perReportReward": 10, "awardedBid": 0}
BID = {"provider": "0x" + "bb" * 20, "withdrawn": False, "epochs": 3, "expiry": 2000, "epochFee": 100,
       "endpointHash": Z, "offerHash": Z}
TERMS = {"acceptSeconds": 86400, "confirmationRoundSeconds": 600, "responseSeconds": 100,
         "monitoringSeconds": 100, "evidenceSeconds": 1000, "idleSeconds": 86400, "reservationFee": 20,
         "exposureBudget": 150, "conditionalQuorumPolicy": True, "responseAdmitsReceipt": False}
MARKET = "0x" + "cc" * 20


class TermsTest(unittest.TestCase):
    def test_terms_hash_deterministic_and_sensitive(self):
        h = t.terms_hash(31340, MARKET, 1, 0, REQ, BID, TERMS)
        self.assertEqual(len(h), 32)
        self.assertEqual(h, t.terms_hash(31340, MARKET, 1, 0, dict(REQ), dict(BID), dict(TERMS)))
        changed = dict(TERMS, responseAdmitsReceipt=True)
        self.assertNotEqual(h, t.terms_hash(31340, MARKET, 1, 0, REQ, BID, changed))
        self.assertNotEqual(h, t.terms_hash(31340, MARKET, 2, 0, REQ, BID, TERMS))

    def test_rejects_unawarded_request(self):
        with self.assertRaises(ValueError):
            t.terms_hash(31340, MARKET, 1, 0, dict(REQ, status=1), BID, TERMS)
        with self.assertRaises(ValueError):
            t.terms_hash(31340, MARKET, 1, 1, REQ, BID, TERMS)

    def test_vote_digest_binds_response_for_both_verdicts(self):
        d = t.domain_separator(t.LEDGER_NAME, 31340, MARKET)
        r1, r2 = "0x" + "22"*32, "0x" + "33"*32
        for outcome in (1, 2):
            a = t.vote_digest(d, 1, 0, Z, outcome, r1, Z)
            b = t.vote_digest(d, 1, 0, Z, outcome, r2, Z)
            self.assertNotEqual(a, b)
            with self.assertRaises(ValueError):
                t.vote_digest(d, 1, 0, Z, outcome, "0x" + "00" * 32, Z)
        with self.assertRaises(ValueError):
            t.vote_digest(d, 1, 0, Z, 0, r1, Z)

    def test_response_ack_and_both_votes_match_independent_encoder(self):
        from eth_account.messages import encode_typed_data
        from sse_challenge import keccak256
        ledger = "0x" + "dd" * 20
        response = "0x" + "22" * 32
        evidence = "0x" + "33" * 32
        context = dict(leaseId=7, epochId=2, requestHash=Z)
        base = [("leaseId", "uint256"), ("epochId", "uint256"), ("requestHash", "bytes32")]
        md = t.domain_separator(t.MARKET_NAME, 31340, MARKET)
        ld = t.domain_separator(t.LEDGER_NAME, 31340, ledger)
        cases = [
            (t.MARKET_NAME, MARKET, "ProviderResponse", base + [("responseHash", "bytes32")],
             dict(context, responseHash=response), t.response_digest(md, 7, 2, Z, response)),
            (t.MARKET_NAME, MARKET, "ProviderAck", base, context, t.ack_digest(md, 7, 2, Z)),
        ]
        for outcome in (1, 2):
            cases.append((t.LEDGER_NAME, ledger, "MonitorVote",
                          base + [("outcome", "uint8"), ("responseHash", "bytes32"), ("evidenceHash", "bytes32")],
                          dict(context, outcome=outcome, responseHash=response, evidenceHash=evidence),
                          t.vote_digest(ld, 7, 2, Z, outcome, response, evidence)))
        for name, contract, primary, fields, data, actual in cases:
            with self.subTest(primary=primary, outcome=data.get("outcome")):
                msg = encode_typed_data(
                    domain_data=dict(name=name, version="1", chainId=31340, verifyingContract=contract),
                    message_types={primary: [{"name": k, "type": v} for k, v in fields]},
                    message_data=data)
                self.assertEqual(actual, keccak256(b"\x19" + msg.version + msg.header + msg.body))

    def test_residual_digest_matches_independent_typed_data_encoder(self):
        from eth_account.messages import encode_typed_data
        a = dict(unresolvedAmount=20, providerShare=7, consumerShare=13, nonce=0, expiry=1000)
        fields = [("leaseId", "uint256"), ("epochId", "uint256"), ("requestHash", "bytes32")]
        fields += [(k, "uint256") for k in a]
        msg = encode_typed_data(
            domain_data={"name": t.MARKET_NAME, "version": "1", "chainId": 31340, "verifyingContract": MARKET},
            message_types={"ResidualAgreement": [{"name": k, "type": v} for k, v in fields]},
            message_data=dict(leaseId=1, epochId=0, requestHash=Z, **a))
        from sse_challenge import keccak256
        expected = keccak256(b"\x19" + msg.version + msg.header + msg.body)
        domain = t.domain_separator(t.MARKET_NAME, 31340, MARKET)
        self.assertEqual(t.allocation_digest(domain, 1, 0, Z, a), expected)
        for bad in (dict(a, consumerShare=12), dict(a, nonce=-1), dict(a, providerShare=True)):
            with self.assertRaises(ValueError):
                t.allocation_digest(domain, 1, 0, Z, bad)
        with self.assertRaises(ValueError):
            t.allocation_digest(domain, 0, 0, Z, a)

    def test_v4_ledger_domain_short_and_version_bound(self):
        self.assertEqual(t.LEDGER_NAME, "SSEAdaptiveCommitteeVotesV4")
        self.assertLessEqual(len(t.LEDGER_NAME.encode()), 31)
        old = t.domain_separator("SSEAdaptiveCommitteeVotesV4Candidate", 31340, MARKET)
        new = t.domain_separator(t.LEDGER_NAME, 31340, MARKET)
        self.assertNotEqual(old, new)

    def test_domains_differ(self):
        self.assertNotEqual(t.domain_separator(t.MARKET_NAME, 31340, MARKET),
                            t.domain_separator(t.LEDGER_NAME, 31340, MARKET))


if __name__ == "__main__":
    unittest.main()
