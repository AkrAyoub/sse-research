"""WP09L local economic model + exact anchor source patch tests; NO Solidity EVM."""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'policy_reference'))
from wp09l_fee_model import VrfFeeLedger, PolicyError, adversarial_traces
from wp09l_source import patch_settlement
from apply_wp09k import patch_settlement as patch_wp09k_settlement
from apply_wp09l import generate

SETTLEMENT_FIXTURE = '''contract SSESettlement is EIP712 {
    address public resourceBoard;
    event ResourceBoardBound(address indexed board);
    function bindResourceBoard(address board) external { }
    function finalizeMonitorCommittee(uint256 leaseId) external { }
    function closeLease(uint256 leaseId) external onlyConsumer(leaseId) {
        Lease storage lease = leases[leaseId];
        if (lease.state == LeaseState.Closed) revert InvalidState();
        uint256 unused = lease.uncommittedEscrow;
    }
}'''
POOL_FIXTURE = '''contract OpenMonitorCommittee {
    event AssignmentExpired(uint256 indexed requestId);
    function expire(uint256 id) external { }
    function assignmentStatus(uint256 id) external view returns (RequestStatus) { return assignments[id].status; }
}'''

class FeePatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sol = patch_settlement(patch_wp09k_settlement(SETTLEMENT_FIXTURE))

    def test_patch_contains_locked_fee_and_cap(self):
        for k in ('configureVrfFeePolicy', 'feeWei == 0', 'maxLifetimeRequests == 0',
                  'vrfFeePolicyConfigured = true', 'vrfLifetimeRequestCap'):
            with self.subTest(k=k): self.assertIn(k, self.sol)

    def test_policy_configured_before_adapter_binding(self):
        self.assertIn('!vrfFeePolicyConfigured ||', self.sol)
        self.assertIn('address(randomnessAdapter) != address(0) || nextLeaseId != 1', self.sol)

    def test_only_consumer_can_fund_exact_fee_once(self):
        for token in ('fundVrfRequestFee(uint256 leaseId) external payable onlyConsumer(leaseId)',
                      'msg.value != vrfFeeWei', 'vrfFeeFunded[leaseId] = true;',
                      'vrfFeeSpent[leaseId]', 'vrfRequestsUsed >= vrfLifetimeRequestCap'):
            self.assertIn(token, self.sol)

    def test_purchase_is_permissionless_but_prefunded(self):
        start = self.sol.index('function requestLeaseRandomness(uint256 leaseId)')
        end = self.sol.index('function isLeaseRandomnessOpen', start)
        fragment = self.sol[start:end]
        self.assertNotIn('msg.sender != bootstrapper', fragment)
        self.assertIn('!vrfFeeFunded[leaseId]', fragment)
        self.assertIn('!vrfFeePolicyConfigured', fragment)
        self.assertIn('vrfPurchaseEntered', fragment)

    def test_state_accounting_before_external_call(self):
        s = self.sol
        start = s.index('function requestLeaseRandomness(uint256 leaseId)')
        frag = s[start:s.index('function isLeaseRandomnessOpen',start)]
        external = frag.index('randomnessAdapter.requestSeed(leaseId, lease.assignmentId)')
        for token in ('vrfFeeSpent[leaseId] = true;', '++vrfRequestsUsed;',
                      'withdrawable[bootstrapper] += vrfFeeWei;', 'vrfPurchaseEntered = true;'):
            self.assertLess(frag.index(token), external)
        self.assertGreater(frag.index('vrfPurchaseEntered = false;'), external)

    def test_close_refunds_only_unspent_fee(self):
        self.assertIn('if (vrfFeeFunded[leaseId] && !vrfFeeSpent[leaseId])',self.sol)
        self.assertIn('withdrawable[lease.consumer] += vrfFeeWei;',self.sol)
        self.assertIn('committeePool.cancelUnassigned(lease.assignmentId);',self.sol)
        self.assertIn('emit VrfFeeRefunded(',self.sol)

    def test_unknown_input_fails_closed_and_double_patch_fails(self):
        with self.assertRaises(ValueError):patch_settlement('NOT A CONTRACT')
        with self.assertRaises(ValueError):patch_settlement(self.sol)

    def test_generator_does_not_overwrite_repo_or_existing_out(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            repo=root/'source'
            (repo/'contracts').mkdir(parents=True)
            for filename, data in [('SSESettlement.sol',SETTLEMENT_FIXTURE),
                                   ('OpenMonitorCommittee.sol',POOL_FIXTURE)]:
                (repo/'contracts'/filename).write_text(data)
            before={p.name:p.read_bytes() for p in (repo/'contracts').iterdir()}
            generated=generate(repo,root/'output')
            self.assertEqual(len(generated),5)
            after={p.name:p.read_bytes() for p in (repo/'contracts').iterdir()}
            self.assertEqual(before,after)
            with self.assertRaises(ValueError):generate(repo,root/'output')
            with self.assertRaises(ValueError):generate(repo,repo/'patch')

    def test_artifact_has_no_cloud_workflows(self):
        self.assertFalse(list(ROOT.rglob('.github')))
        self.assertFalse(list(ROOT.rglob('*.yml')))
        self.assertFalse(list(ROOT.rglob('*.yaml')))


class EconomicPolicyTests(unittest.TestCase):
    def setUp(self):
        self.p=VrfFeeLedger(7,2)
        self.one=self.p.create('consumer','provider')
        self.p.accept(self.one,'provider')

    def test_no_unauthorized_or_wrong_payment(self):
        for who,amount in [('attacker',7),('consumer',6),('consumer',8)]:
            with self.assertRaises(PolicyError):self.p.fund(self.one,who,amount)
        self.p.invariants()

    def test_no_purchase_without_funding(self):
        with self.assertRaises(PolicyError):self.p.buy(self.one,'attacker')
        self.assertEqual(self.p.requests,0)
        self.p.invariants()

    def test_exact_fee_and_anyone_can_trigger_one_purchase(self):
        self.p.fund(self.one,'consumer',7)
        self.p.buy(self.one,'attacker')
        self.assertEqual(self.p.credits.get('sponsor'),7)
        self.assertEqual(self.p.requests,1)
        self.p.invariants()

    def test_duplicate_fee_and_purchase_rejected(self):
        self.p.fund(self.one,'consumer',7)
        with self.assertRaises(PolicyError):self.p.fund(self.one,'consumer',7)
        self.p.buy(self.one,'attacker')
        with self.assertRaises(PolicyError):self.p.buy(self.one,'sponsor')
        with self.assertRaises(PolicyError):self.p.fund(self.one,'consumer',7)
        self.p.invariants()

    def test_failed_purchase_does_not_charge_fee_or_quota(self):
        self.p.fund(self.one,'consumer',7)
        with self.assertRaises(PolicyError):self.p.buy(self.one,'attacker',coordinator_reverts=True)
        self.assertEqual(self.p.credits.get('sponsor',0),0)
        self.assertEqual(self.p.requests,0)
        self.assertEqual(self.p.leases[self.one].prepaid,7)
        self.p.buy(self.one,'attacker')
        self.p.invariants()

    def test_prepaid_fee_is_refunded_on_close_before_purchase(self):
        self.p.fund(self.one,'consumer',7)
        self.p.close(self.one,'consumer')
        self.assertEqual(self.p.credits.get('consumer'),32)
        self.assertEqual(self.p.credits.get('sponsor',0),0)
        self.assertEqual(self.p.requests,0)
        self.p.invariants()

    def test_fee_is_not_refunded_after_paid_request_times_out(self):
        self.p.fund(self.one,'consumer',7)
        self.p.buy(self.one,'outsider')
        self.p.close(self.one,'consumer')
        self.assertEqual(self.p.credits.get('consumer'),25)
        self.assertEqual(self.p.credits.get('sponsor'),7)
        self.assertEqual(self.p.requests,1)
        self.p.invariants()

    def test_lifetime_quota_prevents_excess_purchases(self):
        for i in range(2):
            id=self.p.create('consumer','provider'); self.p.accept(id,'provider')
            self.p.fund(id,'consumer',7); self.p.buy(id,'attacker')
        self.assertEqual(self.p.requests,2)
        with self.assertRaises(PolicyError):self.p.fund(self.one,'consumer',7)
        self.p.invariants()

    def test_pending_fee_refunded_if_quota_consumed_elsewhere(self):
        self.p.fund(self.one,'consumer',7)
        for _ in range(2):
            id=self.p.create('consumer','provider'); self.p.accept(id,'provider')
            self.p.fund(id,'consumer',7); self.p.buy(id,'attacker')
        with self.assertRaises(PolicyError):self.p.buy(self.one,'attacker')
        self.p.close(self.one,'consumer')
        self.assertEqual(self.p.credits.get('consumer'),32)
        self.p.invariants()

    def test_reentrant_other_lease_cannot_spend_again(self):
        other=self.p.create('consumer','provider'); self.p.accept(other,'provider')
        self.p.fund(other,'consumer',7)
        self.p.fund(self.one,'consumer',7)
        self.p.buy(self.one,'attacker',reentry_lease=other)
        self.assertEqual(self.p.requests,1)
        self.assertEqual(self.p.leases[other].prepaid,7)
        self.p.invariants()

    def test_consumer_and_sponsor_withdraw_accounting(self):
        self.p.fund(self.one,'consumer',7)
        self.p.buy(self.one,'attacker')
        self.p.close(self.one,'consumer')
        self.assertEqual(self.p.withdraw('sponsor'),7)
        self.assertEqual(self.p.withdraw('consumer'),25)
        self.assertEqual(self.p.balance,0)
        self.p.invariants()

    def test_wrong_provider_acceptance_and_close_caller(self):
        other=self.p.create('consumer','provider')
        with self.assertRaises(PolicyError):self.p.accept(other,'outsider')
        with self.assertRaises(PolicyError):self.p.close(other,'attacker')
        self.p.invariants()

    def test_malformed_price_or_zero_cap_rejected(self):
        for fee, cap in [(0,1),(-1,1),(1,0),(1,-2)]:
            with self.assertRaises(PolicyError):VrfFeeLedger(fee,cap)

    def test_no_double_close_refund(self):
        self.p.close(self.one,'consumer')
        with self.assertRaises(PolicyError):self.p.close(self.one,'consumer')
        self.assertEqual(self.p.credits.get('consumer'),25)
        self.p.invariants()

    def test_randomized_conservation_and_quota(self):
        self.assertEqual(adversarial_traces(500,72),36000)

if __name__=='__main__':unittest.main()
