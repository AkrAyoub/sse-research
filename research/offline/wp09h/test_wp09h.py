"""WP09H independent local tests; NO remote calls or hosted CI."""
from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from wp09h_policy import (EvidenceGate, Phase, InvalidRequest, request_digest,
                          receipt_message, OUTPUT_DOMAIN)
from wp09h_experiments import (attacker_hit_probability, binomial_tail,
                                policy_exact, policy_simulated, run_experiment)
from wp09g_recovery import Election, Status, BATCH_LIMIT
from keccak import keccak256


def context(request_id=9, chain=31337, pool=bytes.fromhex('a1'*20)):
    return request_digest(chain_id=chain, pool=pool, request_id=request_id,
                          requested_block=101, snapshot_root=bytes.fromhex('b2'*32),
                          snapshot_count=160, deadline=3600)


def keyset(n=5):
    priv = {f's{i}': Ed25519PrivateKey.from_private_bytes(bytes([i+1])*32)
            for i in range(n)}
    pub = {name: key.public_key() for name, key in priv.items()}
    return priv, pub


def sign(k, digest):
    return k.sign(receipt_message(digest))


class ScopeSafetyTests(unittest.TestCase):
    def test_context_domain_binds_every_dimension(self):
        base=context()
        self.assertNotEqual(base, context(request_id=10))
        self.assertNotEqual(base, context(chain=1))
        self.assertNotEqual(base, context(pool=bytes.fromhex('11'*20)))
        self.assertNotEqual(base, request_digest(chain_id=31337, pool=bytes.fromhex('a1'*20), request_id=9,
            requested_block=102, snapshot_root=bytes.fromhex('b2'*32), snapshot_count=160, deadline=3600))
        self.assertNotEqual(base, request_digest(chain_id=31337, pool=bytes.fromhex('a1'*20), request_id=9,
            requested_block=101, snapshot_root=bytes.fromhex('b3'*32), snapshot_count=160, deadline=3600))
        self.assertNotEqual(base, request_digest(chain_id=31337, pool=bytes.fromhex('a1'*20), request_id=9,
            requested_block=101, snapshot_root=bytes.fromhex('b2'*32), snapshot_count=159, deadline=3600))
        self.assertNotEqual(base, request_digest(chain_id=31337, pool=bytes.fromhex('a1'*20), request_id=9,
            requested_block=101, snapshot_root=bytes.fromhex('b2'*32), snapshot_count=160, deadline=3601))

    def test_invalid_context_rejected(self):
        defaults=dict(chain_id=31337, pool=bytes.fromhex('a1'*20), request_id=1,
                      requested_block=10, snapshot_root=bytes.fromhex('bb'*32), snapshot_count=160,deadline=100)
        for key, invalid in [('chain_id',0),('pool', bytes(20)),('pool',b'x'),
                             ('request_id',0),('snapshot_count',3),('snapshot_root',bytes(32))]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                request_digest(**{**defaults,key:invalid})

    def test_ed25519_signature_authenticates_exact_scope(self):
        priv,pub=keyset()
        d=context()
        signature=sign(priv['s0'],d)
        pub['s0'].verify(signature,receipt_message(d))
        with self.assertRaises(Exception):
            pub['s0'].verify(signature,receipt_message(context(request_id=10)))


class QuorumGateTests(unittest.TestCase):
    def setUp(self):
        self.priv,self.pub=keyset()
        self.digest=context()
        self.g=EvidenceGate(self.digest,self.pub,threshold=3,opened_at=0,deadline=3600)

    def submit(self,signer,now=10):
        self.g.submit_receipt(signer,sign(self.priv[signer],self.digest),now=now)

    def test_one_and_two_receipts_not_ready(self):
        self.submit('s0');self.submit('s1')
        self.assertEqual(self.g.phase,Phase.COLLECTING)
        with self.assertRaisesRegex(InvalidRequest,'quorum'):
            self.g.finalize(b'valid',now=100,verify_unique_proof=lambda d,p:True)

    def test_any_three_authenticated_receipts_reach_quorum(self):
        for idx in [2,0,4]:self.submit(f's{idx}')
        self.assertEqual(self.g.phase,Phase.READY)
        self.assertEqual([x[0] for x in self.g.receipt_certificate()],['s0','s2','s4'])

    def test_unknown_signer_does_not_advance(self):
        with self.assertRaisesRegex(InvalidRequest,'unknown'):
            self.g.submit_receipt('fictitious',sign(self.priv['s0'],self.digest),now=10)
        self.assertEqual(len(self.g.receipts),0)

    def test_forged_receipt_does_not_advance(self):
        with self.assertRaisesRegex(InvalidRequest,'wrong signature'):
            self.g.submit_receipt('s0',sign(self.priv['s1'],self.digest),now=10)
        self.assertEqual(self.g.phase,Phase.COLLECTING)

    def test_replay_to_another_lease_is_rejected(self):
        another=EvidenceGate(context(request_id=10),self.pub,3,0,3600)
        with self.assertRaisesRegex(InvalidRequest,'scope'):
            another.submit_receipt('s0',sign(self.priv['s0'],self.digest),now=10)

    def test_duplicate_signer_cannot_forge_quorum(self):
        self.submit('s0')
        with self.assertRaisesRegex(InvalidRequest,'duplicate'):
            self.submit('s0')
        self.assertEqual(len(self.g.receipts),1)

    def test_bad_signature_length_rejected(self):
        with self.assertRaisesRegex(InvalidRequest,'length'):
            self.g.submit_receipt('s0',b'bad',now=10)

    def test_receipts_after_expiry_not_accepted(self):
        with self.assertRaisesRegex(InvalidRequest,'deadline'):
            self.submit('s0',3601)
        self.g.expire(now=3601)
        self.assertEqual(self.g.phase,Phase.EXPIRED)
        with self.assertRaisesRegex(InvalidRequest,'terminal'):
            self.submit('s0',3600)

    def test_expiry_clears_partial_quorum(self):
        self.submit('s0')
        with self.assertRaisesRegex(InvalidRequest,'not expirable'):
            self.g.expire(now=3600)
        self.g.expire(now=3601)
        self.assertEqual(self.g.receipts,{})
        with self.assertRaises(InvalidRequest):
            self.g.expire(now=3602)

    def test_invalid_unique_proof_does_not_publish(self):
        for signer in ['s0','s1','s2']:self.submit(signer)
        with self.assertRaisesRegex(InvalidRequest,'external unique'):
            self.g.finalize(b'wrong-proof',now=10,verify_unique_proof=lambda d,p:False)
        self.assertEqual(self.g.phase,Phase.READY)
        self.assertIsNone(self.g.output_seed)

    def test_verified_unique_proof_is_subset_order_independent(self):
        proof=b'TEST-ORACLE-ONLY-unique-public-proof-for-lease-9'
        # A TEST MOCK accepting one literal proof for the digest, not a VRF!
        checker=lambda d,p: d==self.digest and p==proof
        for s in ['s2','s0','s1']:self.submit(s)
        first=self.g.finalize(proof,now=100,verify_unique_proof=checker)
        other=EvidenceGate(self.digest,self.pub,3,0,3600)
        for s in ['s4','s3','s2']:other.submit_receipt(s,sign(self.priv[s],self.digest),now=100)
        self.assertEqual(first,other.finalize(proof,now=100,verify_unique_proof=checker))
        self.assertEqual(first,int.from_bytes(keccak256(OUTPUT_DOMAIN+self.digest+keccak256(proof)),'big'))
        with self.assertRaisesRegex(InvalidRequest,'quorum'):
            self.g.finalize(proof,now=200,verify_unique_proof=checker)

    def test_no_receipt_set_can_choose_an_arbitrary_seed(self):
        proof=b'unique-mock-output'
        checker=lambda d,p: p==proof
        for s in ['s0','s1','s2']:self.submit(s)
        result=self.g.finalize(proof,now=10,verify_unique_proof=checker)
        self.assertEqual(type(result),int)
        self.assertEqual(result,self.g.output_seed)
        self.assertNotEqual(result,0)

    def test_ready_without_proof_still_expires(self):
        for s in ['s0','s1','s2']:self.submit(s)
        self.assertEqual(self.g.phase,Phase.READY)
        self.g.expire(now=3601)
        self.assertEqual(self.g.phase,Phase.EXPIRED)

    def test_invalid_quorum_parameter_rejected(self):
        with self.assertRaises(ValueError):EvidenceGate(self.digest,self.pub,6,0,3600)
        with self.assertRaises(ValueError):EvidenceGate(self.digest,self.pub,0,0,3600)
        with self.assertRaises(ValueError):EvidenceGate(self.digest,self.pub,3,100,100)


class IntegrationWithWP09G(unittest.TestCase):
    def test_successful_unique_output_transitions_to_batched_monitor_assignment(self):
        priv,pub=keyset()
        digest=context(request_id=1)
        gate=EvidenceGate(digest,pub,3,opened_at=0,deadline=3600)
        for s in ['s0','s2','s4']:
            gate.submit_receipt(s,sign(priv[s],digest),now=10)
        proof=b'FIXED-MOCK-UNIQUE-PROOF-NOT-A-REAL-VRF'
        seed=gate.finalize(proof,now=12,verify_unique_proof=lambda d,p:d==digest and p==proof)
        addresses=tuple('0x'+format(1000+i,'040x') for i in range(160))
        election=Election(addresses,1,'0xconsumer','0xprovider')
        election.fulfill_entropy(seed,verified=True,now=13)
        while election.status==Status.AWAITING_PROOFS:
            selected=election.indexes[election.proof_cursor:election.proof_cursor+BATCH_LIMIT]
            election.batch([(i,election.snapshot[i]) for i in selected],now=20+election.proof_cursor)
        self.assertEqual(election.status,Status.ASSIGNED)
        self.assertEqual(len(election.committee),4)
        self.assertEqual(len(election.standbys),36)
        self.assertEqual(sum(election.locked.values()),4)

    def test_threshold_timeout_causes_fail_closed_bond_clean_state(self):
        priv,pub=keyset()
        digest=context(request_id=1)
        gate=EvidenceGate(digest,pub,3,0,3600)
        for s in ['s0','s1']:
            gate.submit_receipt(s,sign(priv[s],digest),now=100)
        gate.expire(now=3601)
        addresses=tuple('0x'+format(1000+i,'040x') for i in range(160))
        election=Election(addresses,1,'0xconsumer','0xprovider')
        election.expire(now=3601)
        self.assertEqual(election.status,Status.EXPIRED)
        self.assertEqual(sum(election.locked.values()),0)


class AdversarialMathTests(unittest.TestCase):
    def test_ideal_unbiased_global_hit_exact_hypergeometric(self):
        hit=attacker_hit_probability()
        self.assertGreater(hit,.68)
        self.assertLess(hit,.70)

    def test_all_honest_threshold_is_unbiased_conditional_on_publication(self):
        hit=attacker_hit_probability()
        case=policy_exact(5,3,0,.95,hit)
        self.assertAlmostEqual(case['attacker_hit_among_published'],hit,12)
        self.assertAlmostEqual(case['forced_publish_probability'],binomial_tail(5,3,.95),12)

    def test_single_adversary_can_block_and_selectively_publish(self):
        hit=attacker_hit_probability()
        case=policy_exact(1,1,1,1.0,hit)
        self.assertAlmostEqual(case['publish_probability'],hit)
        self.assertAlmostEqual(case['attacker_hit_among_published'],1.0)

    def test_three_compromised_of_five_can_grind_publication(self):
        hit=attacker_hit_probability()
        case=policy_exact(5,3,3,.95,hit)
        self.assertAlmostEqual(case['attacker_hit_among_published'],1.0)
        self.assertAlmostEqual(case['publish_probability'],hit)

    def test_two_compromised_of_five_can_bias_when_one_honest_unavailable(self):
        hit=attacker_hit_probability()
        case=policy_exact(5,3,2,.95,hit)
        self.assertGreater(case['attacker_hit_among_published'],hit)
        self.assertLess(case['attacker_hit_among_published'],1.0)
        self.assertGreater(case['forced_publish_probability'],0)

    def test_monte_carlo_matches_exact_conditional_bias(self):
        hit=attacker_hit_probability()
        for params in [(5,3,0,.95),(5,3,2,.95),(5,3,3,.95)]:
            expected=policy_exact(*params,hit)
            measured=policy_simulated(*params,trials=15000,seed=456)
            self.assertLess(abs(expected['publish_probability']-measured['publish_probability']),.016)
            self.assertLess(abs(expected['attacker_hit_among_published']-measured['attacker_hit_among_published']),.016)

    def test_choose_between_two_public_outputs_increases_favorable_probability(self):
        hit=attacker_hit_probability()
        self.assertGreater(1-(1-hit)**2,hit)
        self.assertLess(1-(1-hit)**2,1)
        # A naively chosen seed failover isn't a safe withholding mitigation.

    def test_bad_math_params_raise(self):
        for args in [(5,6,0,.9,.7),(5,3,6,.9,.7),(5,3,0,1.1,.7),(0,1,0,.9,.7)]:
            with self.subTest(args=args),self.assertRaises(ValueError):
                policy_exact(*args)
        with self.assertRaises(ValueError):binomial_tail(3,1,-.1)

    def test_generate_metrics_without_git_network_or_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            result=run_experiment(Path(directory),trials=1000)
            self.assertEqual(len(result['scenarios']),8)
            self.assertTrue((Path(directory)/'results.json').exists())
            self.assertTrue((Path(directory)/'threshold_bias_metrics.csv').exists())


if __name__=='__main__':unittest.main()
