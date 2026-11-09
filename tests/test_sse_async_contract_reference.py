"""WP-05 regression tests for source-traced epoch shadow and asynchronous probes.

These do not execute Solidity bytecode. Source guards catch visible drift in named
contract gates if running in a full checkout. A Foundry differential test is a
separate required work package before security claims.
"""
import itertools
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from sse_formal_reference import SLA, World, evaluate
from sse_async_contract_reference import (
    BoundedClockReading, EpochShadow, EpochTerms, Outcome, Probe,
    RuleViolation, TimeVerdict, Vote, excess_credits,
)


def terms(**kwargs):
    default = dict(fee=25, reservation=5, admitted_at=100,
                   response_period=10, monitoring_grace=5, evidence_window=8)
    default.update(kwargs)
    return EpochTerms(**default)


def epoch(**kwargs):
    return EpochShadow(terms(**kwargs))


def three_votes(ep, vote, time):
    for m in ('m0', 'm1', 'm2'):
        ep.monitor_vote(time, m, vote)


class ContractTimeRulesTests(unittest.TestCase):
    def test_boundaries_derived_from_admission_block(self):
        t = terms()
        self.assertEqual((t.response_deadline, t.monitoring_close, t.evidence_close),
                         (110, 115, 123))

    def test_ack_at_evidence_close_inclusive(self):
        e = epoch()
        e.acknowledgment(123, authenticated=True)
        self.assertTrue(e.acknowledged)

    def test_ack_one_tick_after_evidence_close_rejected(self):
        with self.assertRaises(RuleViolation):
            epoch().acknowledgment(124, authenticated=True)

    def test_unsigned_ack_rejected_and_no_state_flag(self):
        e = epoch()
        with self.assertRaises(RuleViolation):
            e.acknowledgment(104, authenticated=False)
        self.assertFalse(e.acknowledged)

    def test_duplicate_ack_rejected(self):
        e = epoch()
        e.acknowledgment(104, authenticated=True)
        with self.assertRaises(RuleViolation):
            e.acknowledgment(105, authenticated=True)

    def test_provider_response_at_monitor_close_inclusive(self):
        e = epoch()
        e.provider_response(115, authenticated=True)
        self.assertTrue(e.response_authenticated)

    def test_provider_response_one_tick_late_rejected(self):
        with self.assertRaises(RuleViolation):
            epoch().provider_response(116, authenticated=True)

    def test_provider_response_wrong_signature_rejected(self):
        e = epoch()
        with self.assertRaises(RuleViolation):
            e.provider_response(105, authenticated=False)
        self.assertFalse(e.response_authenticated)

    def test_failure_vote_exact_deadline_accepted(self):
        e = epoch()
        e.monitor_vote(110, 'm0', Vote.FAILURE)
        self.assertEqual(e.failure_votes, 1)

    def test_failure_vote_before_deadline_rejected(self):
        with self.assertRaises(RuleViolation):
            epoch().monitor_vote(109, 'm0', Vote.FAILURE)

    def test_success_vote_without_provider_signed_response_rejected(self):
        with self.assertRaises(RuleViolation):
            epoch().monitor_vote(105, 'm0', Vote.SUCCESS)

    def test_success_vote_after_authenticated_response(self):
        e = epoch()
        e.provider_response(105, authenticated=True)
        e.monitor_vote(105, 'm0', Vote.SUCCESS)
        self.assertEqual(e.success_votes, 1)

    def test_vote_monitor_close_boundary(self):
        e = epoch()
        e.monitor_vote(115, 'm0', Vote.FAILURE)
        with self.assertRaises(RuleViolation):
            e.monitor_vote(116, 'm1', Vote.FAILURE)

    def test_seal_strictly_after_close(self):
        e = epoch()
        with self.assertRaises(RuleViolation):
            e.seal(115)
        self.assertEqual(e.seal(116), Outcome.NONE)

    def test_seal_only_once(self):
        e = epoch()
        e.seal(116)
        with self.assertRaises(RuleViolation):
            e.seal(117)

    def test_cannot_vote_after_sealing(self):
        e = epoch()
        e.seal(116)
        with self.assertRaises(RuleViolation):
            e.monitor_vote(116, 'm0', Vote.FAILURE)

    def test_close_evidence_one_tick_after_close(self):
        e = epoch()
        with self.assertRaises(RuleViolation):
            e.close_evidence(123)
        b = e.close_evidence(124)
        self.assertTrue(e.evidence_closed)
        self.assertEqual(b.unresolved, 25)

    def test_ack_after_monitor_sealed_allowed_but_not_after_evidence_closed(self):
        e = epoch()
        e.seal(116)
        e.acknowledgment(122, authenticated=True)
        b, _, _ = e.settle()
        self.assertEqual(b.guaranteed_provider, 0)
        self.assertEqual(b.unresolved, 25)
        e.close_evidence(124)
        with self.assertRaises(RuleViolation):
            e.acknowledgment(125, authenticated=True)

    def test_bad_timestamps_and_fee_rejected(self):
        for kw in (dict(response_period=0), dict(monitoring_grace=0),
                   dict(evidence_window=0), dict(reservation=26),
                   dict(admitted_at=True), dict(monitors=('m0', 'm0', 'm2', 'm3'))):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                terms(**kw)
        with self.assertRaises(RuleViolation):
            terms(admitted_at=2**64 - 1)

    def test_tx_timestamp_order_rejected(self):
        e = epoch()
        e.provider_response(109, authenticated=True)
        with self.assertRaises(RuleViolation):
            e.acknowledgment(108, authenticated=True)


class CommitteeAndSettlementRulesTests(unittest.TestCase):
    def test_unknown_monitor_and_invalid_evidence_rejected(self):
        e = epoch()
        with self.assertRaises(RuleViolation):
            e.monitor_vote(110, 'outsider', Vote.FAILURE)
        with self.assertRaises(RuleViolation):
            e.monitor_vote(110, 'm0', Vote.FAILURE, authorized=False)
        with self.assertRaises(RuleViolation):
            e.monitor_vote(110, 'm0', Vote.FAILURE, evidence_present=False)
        self.assertEqual(len(e.votes), 0)

    def test_one_vote_even_opposite_vote_disallowed(self):
        e = epoch()
        e.monitor_vote(110, 'm0', Vote.FAILURE)
        e.provider_response(110, authenticated=True)
        with self.assertRaises(RuleViolation):
            e.monitor_vote(111, 'm0', Vote.SUCCESS)

    def test_two_failures_are_inconclusive(self):
        e = epoch()
        for m in ('m0', 'm1'):
            e.monitor_vote(110, m, Vote.FAILURE)
        self.assertEqual(e.seal(116), Outcome.NONE)
        b, dp, dc = e.settle()
        self.assertEqual((b.unresolved, dp, dc), (25, 0, 0))

    def test_three_failures_issue_refund_without_ack(self):
        e = epoch()
        three_votes(e, Vote.FAILURE, 110)
        self.assertEqual(e.seal(116), Outcome.FAILURE)
        b, dp, dc = e.settle()
        self.assertEqual((b.guaranteed_provider, b.guaranteed_consumer, b.unresolved),
                         (0, 20, 5))
        self.assertEqual((dp, dc), (0, 20))

    def test_three_failures_plus_provider_ack_refund_all(self):
        e = epoch()
        e.acknowledgment(102, authenticated=True)
        three_votes(e, Vote.FAILURE, 110)
        self.assertEqual(e.seal(116), Outcome.FAILURE)
        b, _, dc = e.settle()
        self.assertEqual((b.guaranteed_provider, b.guaranteed_consumer, b.unresolved),
                         (0, 25, 0))
        self.assertEqual(dc, 25)

    def test_three_success_votes_require_response_auth_and_credit_provider(self):
        e = epoch()
        e.provider_response(103, authenticated=True)
        three_votes(e, Vote.SUCCESS, 110)
        self.assertEqual(e.seal(116), Outcome.SUCCESS)
        b, dp, dc = e.settle()
        self.assertEqual((b.guaranteed_provider, b.guaranteed_consumer, b.unresolved),
                         (25, 0, 0))
        self.assertEqual((dp, dc), (25, 0))

    def test_response_first_auth_at_chain_114_can_still_get_success_quorum(self):
        # Response evidence is accepted through monitoringClose=115, NOT only
        # through nominal responseDeadline=110. A genuinely late physical
        # response may therefore satisfy the *on-chain* success path.
        # This is not proof a response included at 114 happened physically
        # at 114: the application must specify a separate event-time rule.
        e = epoch()
        e.provider_response(114, authenticated=True)
        three_votes(e, Vote.SUCCESS, 115)
        self.assertEqual(e.seal(116), Outcome.SUCCESS)
        self.assertEqual(e.settle()[0].guaranteed_provider, 25)
        self.assertEqual(excess_credits(e, World.F), (25, 0))

    def test_two_success_two_failure_remain_unknown(self):
        e = epoch()
        e.provider_response(102, authenticated=True)
        e.monitor_vote(110, 'm0', Vote.SUCCESS)
        e.monitor_vote(110, 'm1', Vote.SUCCESS)
        e.monitor_vote(110, 'm2', Vote.FAILURE)
        e.monitor_vote(110, 'm3', Vote.FAILURE)
        self.assertEqual(e.seal(116), Outcome.NONE)
        self.assertEqual(e.settle()[0].unresolved, 25)

    def test_both_opposite_quorums_impossible_with_four_single_votes(self):
        for combo in itertools.product((Vote.SUCCESS, Vote.FAILURE), repeat=4):
            self.assertFalse(combo.count(Vote.SUCCESS) >= 3 and combo.count(Vote.FAILURE) >= 3)

    def test_seal_outcome_mapped_to_wp02_bounds_for_all_vote_vectors(self):
        for vector in itertools.product((None, Vote.SUCCESS, Vote.FAILURE), repeat=4):
            e = epoch()
            e.provider_response(103, authenticated=True)
            for i, v in enumerate(vector):
                if v is not None:
                    e.monitor_vote(110, f'm{i}', v)
            actual = e.seal(116)
            if vector.count(Vote.SUCCESS) >= 3:
                self.assertEqual(actual, Outcome.SUCCESS)
            elif vector.count(Vote.FAILURE) >= 3:
                self.assertEqual(actual, Outcome.FAILURE)
            else:
                self.assertEqual(actual, Outcome.NONE)
            expected = evaluate(SLA(25, 5), e.admissible_after_contract_filters())
            self.assertEqual(e.settle()[0], expected)

    def test_repeated_settle_is_delta_only(self):
        e = epoch()
        three_votes(e, Vote.FAILURE, 110)
        e.seal(116)
        first = e.settle()
        second = e.settle()
        self.assertEqual((first[2], second[2]), (20, 0))
        self.assertEqual(e.consumer_credited, 20)

    def test_ack_after_first_settlement_refines_failed_history_to_F(self):
        e = epoch()
        three_votes(e, Vote.FAILURE, 110)
        e.seal(116)
        self.assertEqual(e.settle()[2], 20)
        e.acknowledgment(122, authenticated=True)
        b, _, dc = e.settle()
        self.assertEqual(b.unresolved, 0)
        self.assertEqual(dc, 5)
        self.assertEqual(e.consumer_credited, 25)

    def test_settle_requires_sealing(self):
        with self.assertRaises(RuleViolation):
            epoch().settle()


class AdversarialTraceTests(unittest.TestCase):
    def test_three_honest_timeouts_can_refund_even_when_real_S(self):
        e = epoch()
        for i in range(3):
            p = Probe(f'm{i}', sent_at=103, timeout_at=109, response_arrival=113)
            self.assertTrue(p.honest_timeout)
            e.monitor_vote(110, p.monitor, Vote.FAILURE)
        e.seal(116)
        e.settle()
        self.assertEqual(excess_credits(e, World.S), (0, 20))

    def test_one_byzantine_vote_plus_two_honest_timeouts_still_problem(self):
        e = epoch()
        for i in (0, 1):
            self.assertTrue(Probe(f'm{i}', 103, 109, None).honest_timeout)
            e.monitor_vote(110, f'm{i}', Vote.FAILURE)
        # Third vote is from a *selected* signer, but its local claim is a lie.
        e.monitor_vote(110, 'm2', Vote.FAILURE)
        e.seal(116)
        e.settle()
        self.assertEqual(excess_credits(e, World.S), (0, 20))

    def test_signed_response_plus_three_success_reports_not_consumer_delivery(self):
        e = epoch()
        e.provider_response(105, authenticated=True)
        three_votes(e, Vote.SUCCESS, 106)
        e.seal(116)
        e.settle()
        # Real F (e.g. generated output never delivered); valid signing alone
        # does not imply consumer received correct bytes before SLA deadline.
        self.assertEqual(excess_credits(e, World.F), (25, 0))

    def test_fake_ack_without_request_receipt_causes_N_world_exclusion(self):
        e = epoch()
        e.acknowledgment(105, authenticated=True)
        self.assertNotIn(World.N, e.admissible_after_contract_filters())
        # The provider can sign a hash it knows without the HTTP request
        # physically reaching the promised service process.

    def test_late_transport_is_observationally_same_as_nondelivery_at_timeout(self):
        p1 = Probe('m0', 103, 108, response_arrival=112)
        p2 = Probe('m0', 103, 108, response_arrival=None)
        self.assertTrue(p1.honest_timeout)
        self.assertTrue(p2.honest_timeout)
        self.assertNotEqual(p1.response_arrival, p2.response_arrival)

    def test_waiting_until_chain_deadline_does_not_fix_earlier_probe_truth(self):
        p = Probe('m0', 101, 107, response_arrival=109)
        self.assertTrue(p.honest_timeout)
        e = epoch()
        e.monitor_vote(110, 'm0', Vote.FAILURE)  # allowed by chain gate
        self.assertEqual(e.failure_votes, 1)

    def test_unknown_clock_interval_straddles_deadline(self):
        reading = BoundedClockReading(110, 2)
        self.assertEqual((reading.earliest, reading.latest), (108, 112))
        self.assertEqual(reading.compare_deadline(110), TimeVerdict.UNKNOWN)

    def test_clock_inequalities_are_inclusive_at_deadline(self):
        self.assertEqual(BoundedClockReading(108, 2).compare_deadline(110),
                         TimeVerdict.CERTAIN_TIMELY)
        self.assertEqual(BoundedClockReading(113, 2).compare_deadline(110),
                         TimeVerdict.CERTAIN_LATE)
        self.assertEqual(BoundedClockReading(112, 2).compare_deadline(110),
                         TimeVerdict.UNKNOWN)

    def test_small_uncertainty_does_not_justify_unsafe_claim_without_bound_auth(self):
        # Even max_error=0 is a *claim* until the source is authenticated and
        # an actual clock-error guarantee has been justified by the SLA.
        self.assertEqual(BoundedClockReading(110, 0).compare_deadline(110),
                         TimeVerdict.CERTAIN_TIMELY)

    def test_invalid_probe_and_clock_inputs(self):
        with self.assertRaises(RuleViolation):
            Probe('m0', sent_at=10, timeout_at=9)
        with self.assertRaises(RuleViolation):
            Probe('m0', sent_at=10, timeout_at=11, response_arrival=8)
        with self.assertRaises(RuleViolation):
            BoundedClockReading(10, -1)


class SoliditySourceTraceabilityTests(unittest.TestCase):
    """Source guards, NOT Solidity bytecode-execution or differential equivalence."""
    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).resolve().parents[1] / 'contracts' / 'SSESettlement.sol'
        if not cls.path.is_file():
            raise unittest.SkipTest('Solidity source absent from isolated model archive')
        cls.source = cls.path.read_text(encoding='utf-8')

    def test_exact_time_gate_predicates_still_present(self):
        for gate in (
            'block.timestamp > ep.evidenceClose || ep.evidenceClosed',
            'block.timestamp > ep.monitoringClose || ep.monitoringSealed',
            'block.timestamp < ep.responseDeadline',
            'block.timestamp <= ep.monitoringClose',
            'block.timestamp <= ep.evidenceClose',
        ):
            with self.subTest(gate=gate):
                self.assertIn(gate, self.source)

    def test_quorum_and_history_filters_remain(self):
        for rule in (
            'COMMITTEE_SIZE = 4', 'QUORUM = 3',
            'if (ep.successVotes >= QUORUM)', 'else if (ep.failureVotes >= QUORUM)',
            'if (ep.acknowledged) mask &= HISTORY_F | HISTORY_S;',
            'if (ep.outcome == Outcome.Failure) mask &= HISTORY_N | HISTORY_F;',
            'if (ep.outcome == Outcome.Success) mask &= HISTORY_S;',
        ):
            with self.subTest(rule=rule):
                self.assertIn(rule, self.source)


if __name__ == '__main__':
    unittest.main()
