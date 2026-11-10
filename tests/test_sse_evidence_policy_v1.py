"""WP-07 research-policy tests; source does not verify off-chain certificates."""
from __future__ import annotations

import itertools
import random
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from sse_formal_reference import World, SLA, ALL_WORLDS, world_sound
from sse_evidence_policy_v1 import (
    VERSION, PolicyError, ConflictingClaims, Binding, PolicyManifest, PolicyMode,
    Assumption, RawKind, FactKind, RawObservation, QualifiedFact,
    PhysicalPolicyState, ChainSnapshot, ChainPolicyState, TimeInterval,
)

B = Binding(7, 2, '0x'+'a'*64)
SLA25 = SLA(25, 5)


def physical(*assumptions):
    manifest = PolicyManifest(B, PolicyMode.PHYSICAL_DELIVERY, 100, 110,
                              frozenset(assumptions))
    return PhysicalPolicyState(manifest, SLA25)


def chain(trusted=True):
    assumptions = frozenset((Assumption.CANONICAL_CHAIN_COMPLETE,)) if trusted else frozenset()
    return ChainPolicyState(PolicyManifest(B, PolicyMode.CHAIN_PUBLICATION, 100, 110,
                                           assumptions), SLA25)


def raw(index, kind):
    return RawObservation(B, 'report-'+str(index), kind, 'monitor-'+str(index))


def fact(index, kind, interval=None):
    kind_to_assumption = {
        FactKind.PHYSICAL_RECEIPT: Assumption.RECEIPT_CERT_SOUND,
        FactKind.PHYSICAL_FULFILLMENT: Assumption.FULFILLMENT_CERT_SOUND,
        FactKind.PHYSICAL_NONFULFILLMENT: Assumption.NONFULFILLMENT_CERT_SOUND,
    }
    return QualifiedFact(B, 'cert-'+str(index), kind, kind_to_assumption[kind],
                         'RESEARCH-UNVERIFIED-ASSUMPTION', interval)


class ManifestAndBindingTests(unittest.TestCase):
    def test_version_rejects_incompatible_policy(self):
        with self.assertRaises(PolicyError):
            PolicyManifest(B, PolicyMode.PHYSICAL_DELIVERY, 100, 110,
                           version='R1-PROVISIONAL-0')

    def test_noncanonical_hash_rejected(self):
        with self.assertRaises(PolicyError):
            Binding(1, 0, '0x'+'A'*64)

    def test_zero_lease_invalid(self):
        with self.assertRaises(PolicyError):
            Binding(0, 0, '0x'+'a'*64)

    def test_noninteger_lease_invalid(self):
        with self.assertRaises(PolicyError):
            Binding(True, 0, '0x'+'a'*64)

    def test_deadline_must_follow_epoch(self):
        with self.assertRaises(PolicyError):
            PolicyManifest(B, PolicyMode.PHYSICAL_DELIVERY, 110, 110)

    def test_wrong_policy_mode_rejected(self):
        with self.assertRaises(PolicyError):
            PhysicalPolicyState(PolicyManifest(B, PolicyMode.CHAIN_PUBLICATION, 100, 110), SLA25)

    def test_invalid_assumption_type_rejected(self):
        with self.assertRaises(PolicyError):
            physical('RECEIPT_CERT_SOUND')

    def test_chain_mode_refuses_physical_assumptions(self):
        with self.assertRaises(PolicyError):
            PolicyManifest(B, PolicyMode.CHAIN_PUBLICATION, 100, 110,
                           frozenset((Assumption.RECEIPT_CERT_SOUND,)))

    def test_delivery_mode_refuses_chain_assumptions(self):
        with self.assertRaises(PolicyError):
            physical(Assumption.CANONICAL_CHAIN_COMPLETE)

    def test_cross_lease_raw_report_rejected(self):
        bad = RawObservation(Binding(8,2,B.sla_hash), 'id', RawKind.MONITOR_TIMEOUT, 'M')
        with self.assertRaises(PolicyError):
            physical().with_raw(bad)

    def test_cross_sla_qualified_fact_rejected(self):
        q = fact(1, FactKind.PHYSICAL_RECEIPT)
        bad = QualifiedFact(Binding(7,2,'0x'+'b'*64),q.evidence_id,q.kind,q.assumption,q.verifier_reference)
        with self.assertRaises(PolicyError):
            physical(Assumption.RECEIPT_CERT_SOUND).with_fact(bad,105)

    def test_conflicting_evidence_ids_rejected(self):
        p = physical().with_raw(raw(1,RawKind.MONITOR_TIMEOUT))
        with self.assertRaises(PolicyError):
            p.with_raw(raw(1,RawKind.MONITOR_SUCCESS))

    def test_identical_raw_report_is_idempotent(self):
        p=physical().with_raw(raw(1,RawKind.MONITOR_TIMEOUT))
        self.assertIs(p.with_raw(raw(1,RawKind.MONITOR_TIMEOUT)), p)


class ConservativeDeliveryTests(unittest.TestCase):
    def test_no_observations_all_three_histories(self):
        d = physical().decision()
        self.assertEqual(d.histories, ALL_WORLDS)
        self.assertEqual((d.funds.guaranteed_provider,d.funds.guaranteed_consumer,d.funds.unresolved),(0,0,25))

    def test_four_honest_timeouts_cannot_rule_out_success(self):
        p=physical()
        for i in range(4): p=p.with_raw(raw(i, RawKind.MONITOR_TIMEOUT))
        d=p.decision()
        self.assertEqual(d.histories,ALL_WORLDS)
        self.assertTrue(world_sound(World.S,d.histories))
        self.assertEqual(d.raw_report_count,4)

    def test_four_success_reports_cannot_rule_out_failure(self):
        p=physical().with_raw(raw(0,RawKind.PROVIDER_SIGNED_RESPONSE))
        for i in range(4): p=p.with_raw(raw(i+1,RawKind.MONITOR_SUCCESS))
        self.assertIn(World.F,p.histories)

    def test_signed_ack_without_admission_assumption_does_not_exclude_n(self):
        self.assertIn(World.N,physical().with_raw(raw(0,RawKind.PROVIDER_SIGNED_ACK)).histories)

    def test_untrusted_consumer_claim_does_not_establish_delivery(self):
        self.assertEqual(physical().with_raw(raw(1,RawKind.CONSUMER_CLAIM)).histories,ALL_WORLDS)

    def test_unqualified_fact_fails_instead_of_minting_proof(self):
        with self.assertRaises(PolicyError):
            physical().with_fact(fact(1,FactKind.PHYSICAL_FULFILLMENT,TimeInterval(105,107)),111)

    def test_receipt_cert_under_explicit_assumption_excludes_n(self):
        p=physical(Assumption.RECEIPT_CERT_SOUND).with_fact(fact(1,FactKind.PHYSICAL_RECEIPT),105)
        self.assertEqual(p.histories,frozenset((World.F,World.S)))
        self.assertEqual(p.decision().funds.unresolved,25)

    def test_timely_fulfillment_certificate_produces_s(self):
        p=physical(Assumption.FULFILLMENT_CERT_SOUND).with_fact(
            fact(2,FactKind.PHYSICAL_FULFILLMENT,TimeInterval(106,109)),112)
        self.assertEqual(p.histories,frozenset((World.S,)))
        self.assertEqual(p.decision().funds.guaranteed_provider,25)

    def test_uncertain_deadline_does_not_establish_success(self):
        p=physical(Assumption.FULFILLMENT_CERT_SOUND).with_fact(
            fact(2,FactKind.PHYSICAL_FULFILLMENT,TimeInterval(108,112)),112)
        self.assertEqual(p.histories,ALL_WORLDS)
        self.assertEqual(len(p.facts),1)

    def test_certainly_late_completion_does_not_establish_success(self):
        p=physical(Assumption.FULFILLMENT_CERT_SOUND).with_fact(
            fact(2,FactKind.PHYSICAL_FULFILLMENT,TimeInterval(111,113)),113)
        self.assertEqual(p.histories,ALL_WORLDS)

    def test_fulfillment_without_time_interval_rejected(self):
        with self.assertRaises(PolicyError):
            physical(Assumption.FULFILLMENT_CERT_SOUND).with_fact(
                fact(2,FactKind.PHYSICAL_FULFILLMENT),112)

    def test_boundary_at_deadline_is_timely(self):
        p=physical(Assumption.FULFILLMENT_CERT_SOUND).with_fact(
            fact(2,FactKind.PHYSICAL_FULFILLMENT,TimeInterval(109,110)),111)
        self.assertEqual(p.histories,frozenset((World.S,)))

    def test_exhaustive_nonfulfillment_certificate_before_deadline_inconclusive(self):
        p=physical(Assumption.NONFULFILLMENT_CERT_SOUND).with_fact(
            fact(2,FactKind.PHYSICAL_NONFULFILLMENT),109)
        self.assertEqual(p.histories,ALL_WORLDS)

    def test_exhaustive_nonfulfillment_after_deadline_excludes_s(self):
        p=physical(Assumption.NONFULFILLMENT_CERT_SOUND).with_fact(
            fact(2,FactKind.PHYSICAL_NONFULFILLMENT),111)
        self.assertEqual(p.histories,frozenset((World.N,World.F)))
        self.assertEqual((p.decision().funds.guaranteed_consumer,p.decision().funds.unresolved),(20,5))

    def test_receipt_plus_nonfulfillment_yields_f(self):
        p=physical(Assumption.NONFULFILLMENT_CERT_SOUND,Assumption.RECEIPT_CERT_SOUND)
        p=p.with_fact(fact(2,FactKind.PHYSICAL_RECEIPT),101)
        p=p.with_fact(fact(3,FactKind.PHYSICAL_NONFULFILLMENT),111)
        self.assertEqual(p.histories,frozenset((World.F,)))
        self.assertEqual(p.decision().funds.guaranteed_consumer,25)

    def test_conflicting_fulfillment_and_nonfulfillment_halts_without_changing_old_state(self):
        p=physical(Assumption.NONFULFILLMENT_CERT_SOUND,Assumption.FULFILLMENT_CERT_SOUND)
        p=p.with_fact(fact(2,FactKind.PHYSICAL_FULFILLMENT,TimeInterval(103,109)),111)
        with self.assertRaises(ConflictingClaims):
            p.with_fact(fact(3,FactKind.PHYSICAL_NONFULFILLMENT),112)
        self.assertEqual(p.histories,frozenset((World.S,)))

    def test_duplicate_fact_is_idempotent(self):
        p=physical(Assumption.RECEIPT_CERT_SOUND).with_fact(fact(1,FactKind.PHYSICAL_RECEIPT),104)
        self.assertIs(p.with_fact(fact(1,FactKind.PHYSICAL_RECEIPT),105),p)

    def test_fact_before_epoch_rejected(self):
        with self.assertRaises(PolicyError):
            physical(Assumption.RECEIPT_CERT_SOUND).with_fact(fact(1,FactKind.PHYSICAL_RECEIPT),99)

    def test_wrong_assumption_for_fact_rejected(self):
        q=QualifiedFact(B,'cert-3',FactKind.PHYSICAL_RECEIPT,
                        Assumption.FULFILLMENT_CERT_SOUND,'toy-verifier')
        with self.assertRaises(PolicyError):
            physical(Assumption.RECEIPT_CERT_SOUND,Assumption.FULFILLMENT_CERT_SOUND).with_fact(q,105)

    def test_inverted_interval_rejected(self):
        with self.assertRaises(PolicyError):
            TimeInterval(111,110)

    def test_uncertain_clock_boundary_exact(self):
        d=TimeInterval(109,111)
        self.assertFalse(d.is_certainly_timely(110))
        self.assertFalse(d.is_certainly_late(110))

    def test_qualifier_safety_depends_on_world_assumption(self):
        p=physical(Assumption.NONFULFILLMENT_CERT_SOUND).with_fact(
            fact(3,FactKind.PHYSICAL_NONFULFILLMENT),111)
        # If a verifier lies, the same formally correct intersection is unsound.
        self.assertFalse(world_sound(World.S,p.histories))
        self.assertEqual(p.decision().funds.guaranteed_consumer,20)

    def test_monotonicity_conservation_under_all_qualified_fact_sequences(self):
        kinds=(FactKind.PHYSICAL_RECEIPT,FactKind.PHYSICAL_NONFULFILLMENT,
               FactKind.PHYSICAL_FULFILLMENT)
        p0=physical(Assumption.RECEIPT_CERT_SOUND,Assumption.NONFULFILLMENT_CERT_SOUND,
                    Assumption.FULFILLMENT_CERT_SOUND)
        for n in range(1,4):
            for perm in itertools.permutations(kinds,n):
                p=p0
                for i,kind in enumerate(perm):
                    evt=TimeInterval(102,106) if kind==FactKind.PHYSICAL_FULFILLMENT else None
                    try:
                        nxt=p.with_fact(fact(i,kind,evt),111)
                    except ConflictingClaims:
                        break
                    self.assertTrue(nxt.histories.issubset(p.histories))
                    b=nxt.decision().funds
                    self.assertEqual(b.guaranteed_provider+b.guaranteed_consumer+b.unresolved,25)
                    p=nxt

    def test_randomized_fee_conservation_across_policy_refinements(self):
        rng=random.Random(20261110)
        for _ in range(250):
            fee=rng.randrange(1,10**18)
            r=rng.randrange(fee+1)
            base=PhysicalPolicyState(physical(Assumption.NONFULFILLMENT_CERT_SOUND).manifest, SLA(fee,r))
            p=base.with_fact(fact(1,FactKind.PHYSICAL_NONFULFILLMENT),111)
            b=p.decision().funds
            self.assertEqual(b.guaranteed_provider+b.guaranteed_consumer+b.unresolved,fee)
            self.assertLessEqual(b.guaranteed_consumer,fee)


class ChainPublicationTests(unittest.TestCase):
    def test_initial_chain_unknown_and_n_is_not_a_possible_outcome(self):
        p=chain(); d=p.decision()
        self.assertEqual(d.histories,frozenset((World.F,World.S)))
        self.assertEqual(d.funds.unresolved,25)

    def test_chain_requires_explicit_finality_assumption(self):
        with self.assertRaises(PolicyError):
            chain(False).advance(ChainSnapshot(B,110))

    def test_canonical_early_response_succeeds(self):
        p=chain().advance(ChainSnapshot(B,115,105))
        self.assertEqual(p.histories,frozenset((World.S,)))
        self.assertEqual(p.decision().funds.guaranteed_provider,25)

    def test_canonical_response_at_deadline_succeeds(self):
        p=chain().advance(ChainSnapshot(B,110,110))
        self.assertEqual(p.histories,frozenset((World.S,)))

    def test_nonfinalized_response_cannot_pay_provider(self):
        p=chain().advance(ChainSnapshot(B,103,106))
        self.assertEqual(p.histories,frozenset((World.F,World.S)))

    def test_finalized_absence_until_before_deadline_remains_unknown(self):
        p=chain().advance(ChainSnapshot(B,109))
        self.assertEqual(p.histories,frozenset((World.F,World.S)))

    def test_finalized_absence_through_deadline_proves_contractual_failure(self):
        p=chain().advance(ChainSnapshot(B,110))
        self.assertEqual(p.histories,frozenset((World.F,)))
        self.assertEqual(p.decision().funds.guaranteed_consumer,25)

    def test_late_response_is_contractually_unsuccessful(self):
        p=chain().advance(ChainSnapshot(B,115,111))
        self.assertEqual(p.histories,frozenset((World.F,)))
        self.assertEqual(p.decision().funds.guaranteed_consumer,25)

    def test_cross_epoch_chain_snapshot_rejected(self):
        b=Binding(7,3,B.sla_hash)
        with self.assertRaises(PolicyError):
            chain().advance(ChainSnapshot(b,110,109))

    def test_purported_response_preceding_epoch_rejected(self):
        with self.assertRaises(PolicyError):
            chain().advance(ChainSnapshot(B,115,99))

    def test_canonical_finality_regression_rejected(self):
        p=chain().advance(ChainSnapshot(B,109))
        with self.assertRaises(PolicyError):
            p.advance(ChainSnapshot(B,108))

    def test_later_contradictory_snapshot_halts(self):
        p=chain().advance(ChainSnapshot(B,110))
        with self.assertRaises(ConflictingClaims):
            p.advance(ChainSnapshot(B,115,108))

    def test_chain_pub_not_a_compute_or_delivery_proof(self):
        # A formal *semantic* limitation: the policy has no physical-world
        # input for CPU allocation or consumer receipt.
        p=chain().advance(ChainSnapshot(B,115,105))
        self.assertEqual(p.histories,frozenset((World.S,)))
        self.assertNotIn(World.N,p.histories)
        self.assertEqual(p.manifest.mode,PolicyMode.CHAIN_PUBLICATION)


if __name__=='__main__':
    unittest.main()
