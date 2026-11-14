"""No GitHub, no external RPC, no EVM/solc. Exact Solidity patch anchors,
plus local state machine security regression checks. NOT Solidity compilation.
"""
from __future__ import annotations
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apply_wp09k import patch_pool, patch_settlement
from harden_source import harden_adapter, harden_settlement_patch, harden_pool_patch
from wp09k_policy_model import Election, EntropyState, PoolState, PolicyError

ADAPTER = (ROOT / 'contracts/SSEVRFV25Adapter.sol').read_text()
MOCK = (ROOT / 'contracts/MockVRFV25Coordinator.sol').read_text()
FOUNDRY = (ROOT / 'foundry_test/VRFAdapterIntegration.t.sol').read_text()

POOL_FIXTURE = '''contract OpenMonitorCommittee {
    event AssignmentExpired(uint256 indexed requestId);
    function expire(uint256 id) external { }
    function assignmentStatus(uint256 id) external view returns (RequestStatus) { return assignments[id].status; }
}'''
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


class WP09KSourcePatchTests(unittest.TestCase):
    def test_pool_cancel_hook_and_getter(self):
        s = patch_pool(POOL_FIXTURE)
        for token in ['function cancelUnassigned(uint256 id) external onlySettlement',
                      '_unlockSnapshot(id)', 'delete pendingGlobalSeedReady[id]',
                      'delete pendingGlobalSeed[id]', 'r.status = RequestStatus.Released;',
                      '--candidates[r.committee[i]].activeAssignments',
                      'function assignmentRequestedAt(uint256 id)', 'AssignmentCancelled(']:
            with self.subTest(token=token): self.assertIn(token, s)

    def test_settlement_paid_request_guard_and_atomic_close(self):
        s = patch_settlement(SETTLEMENT_FIXTURE)
        for token in ['msg.sender != bootstrapper',
                      'function isLeaseRandomnessOpen(uint256 leaseId, uint256 assignmentId)',
                      'lease.state == LeaseState.Accepted',
                      'committeePool.cancelUnassigned(lease.assignmentId);',
                      'randomnessAdapter.requestSeed(leaseId, lease.assignmentId)']:
            with self.subTest(token=token): self.assertIn(token, s)

    def test_adapter_checks_close_at_request_and_application(self):
        self.assertIn('!ISSEVRFSettlement(settlement).isLeaseRandomnessOpen(leaseId, assignmentId)', ADAPTER)
        self.assertIn('!ISSEVRFSettlement(settlement).isLeaseRandomnessOpen(\n                leaseForAssignment[assignmentId], assignmentId)', ADAPTER)
        self.assertIn('mapping(uint256 => uint256) public leaseForAssignment;', ADAPTER)

    def test_adapter_precommits_before_external_coordinator_request(self):
        before = ADAPTER.index('assignmentEverRequested[assignmentId] = true;')
        external = ADAPTER.index('IVRFV25Coordinator(pinnedCoordinator).requestRandomWords(req);')
        self.assertLess(before, external)
        self.assertIn('if (vrfId == 0 || byVrfId[vrfId].state != State.None)', ADAPTER)

    def test_any_unknown_existing_version_fails_closed(self):
        for func, src in [(patch_pool, 'unknown pool'), (patch_settlement, 'unknown settlement')]:
            with self.subTest(func=func.__name__):
                with self.assertRaises(ValueError): func(src)
        with self.assertRaises(ValueError): patch_pool(patch_pool(POOL_FIXTURE))
        with self.assertRaises(ValueError): patch_settlement(patch_settlement(SETTLEMENT_FIXTURE))

    def test_patch_generation_keeps_source_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            repo = d/'source'
            (repo/'contracts').mkdir(parents=True)
            (repo/'contracts'/'OpenMonitorCommittee.sol').write_text(POOL_FIXTURE)
            (repo/'contracts'/'SSESettlement.sol').write_text(SETTLEMENT_FIXTURE)
            before = {p.name: p.read_bytes() for p in (repo/'contracts').iterdir()}
            out = d/'output'
            cp = subprocess.run([sys.executable, str(ROOT/'apply_wp09k.py'),
                                 '--repo',str(repo),'--out',str(out)],
                                capture_output=True,text=True)
            self.assertEqual(cp.returncode, 0, cp.stderr)
            self.assertIn('Source tree untouched', cp.stdout)
            for p in (repo/'contracts').iterdir():
                self.assertEqual(p.read_bytes(), before[p.name])
            self.assertTrue((out/'wp09k_changes.patch').is_file())
            self.assertIn('function cancelUnassigned(', (out/'contracts/OpenMonitorCommittee.sol').read_text())
            self.assertIn('isLeaseRandomnessOpen', (out/'contracts/SSESettlement.sol').read_text())
            self.assertIn('requestSeed(uint256 leaseId', (out/'contracts/SSEVRFV25Adapter.sol').read_text())
            manifest = json.loads((out/'manifest.json').read_text())
            self.assertEqual(manifest['github_actions'],'never called')
            again = subprocess.run([sys.executable,str(ROOT/'apply_wp09k.py'),
                                    '--repo',str(repo),'--out',str(out)],capture_output=True,text=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual(before, {p.name:p.read_bytes() for p in (repo/'contracts').iterdir()})

    def test_patcher_does_not_write_inside_source(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            cp = subprocess.run([sys.executable,str(ROOT/'apply_wp09k.py'),
                                 '--repo',str(repo),'--out',str(repo/'nested')],capture_output=True,text=True)
            self.assertNotEqual(cp.returncode,0)
            self.assertIn('Refusing output inside', cp.stderr+cp.stdout)

    def test_foundry_tests_cover_cost_and_close_races(self):
        for name in [
            'testSubscriptionSpendRequiresSponsorAndProviderAcceptance',
            'testCloseDuringPendingVRFBlocksLateSeedApplicationAndRefunds',
            'testCloseAfterSeedAppliedBeforeCommitteeCopyReleasesBondLocks',
            'testCloseBeforeVRFRequestReleasesAllPendingSnapshotLocks',
            'testCloseAfterSeedStagedBeforeGlobalProofPreventsBondLock',
            'testCoordinatorReentryCannotSpendSecondVRFRequest',
            'testCoordinatorFailureRollsBackRequestAndAllowsSingleRetry',
            'testOnlySettlementCanCancelPendingOrSelectedAssignment',
        ]:
            with self.subTest(name=name): self.assertIn('function '+name+'(',FOUNDRY)

    def test_mock_failure_attack_hooks_are_explicitly_not_production(self):
        for x in ('INSECURE test hooks', 'rejectRequests', 'reentrySettlement', 'lastReentrySucceeded'):
            self.assertIn(x, MOCK)
        self.assertIn('verifies NO cryptographic VRF', MOCK)

    def test_no_cloud_ci_or_network_code_in_package(self):
        self.assertFalse(list(ROOT.rglob('.github')))
        self.assertFalse(list(ROOT.rglob('*.yml')))
        self.assertFalse(list(ROOT.rglob('*.yaml')))
        self.assertNotIn('github.com', ADAPTER.lower())


class WP09KPolicyTests(unittest.TestCase):
    def test_preacceptance_and_unsponsored_request_never_charge(self):
        e = Election()
        for who in ('sponsor','consumer','provider','outsider'):
            with self.assertRaises(PolicyError): e.request(who,110)
        e.accept('provider')
        for who in ('consumer','provider','outsider'):
            with self.assertRaises(PolicyError): e.request(who,110)
        self.assertEqual(e.charged_requests,0)
        e.request('sponsor',110)
        self.assertEqual(e.charged_requests,1)
        e.invariants()

    def test_failed_coordinator_purchase_rolls_back_entire_request(self):
        e = Election()
        e.accept('provider')
        with self.assertRaises(PolicyError):e.request('sponsor',120,coordinator_reverts=True)
        self.assertFalse(e.used_request)
        self.assertEqual(e.charged_requests,0)
        e.request('sponsor',120)
        self.assertEqual(e.charged_requests,1)
        with self.assertRaises(PolicyError):e.request('sponsor',121)
        e.invariants()

    def test_closed_lease_cannot_consume_queued_callback(self):
        e=Election()
        e.accept('provider')
        e.request('sponsor',115)
        self.assertTrue(e.callback('coordinator',120))
        e.close('consumer')
        with self.assertRaises(PolicyError):e.apply(121)
        self.assertEqual(e.candidate_pending_locks,0)
        self.assertEqual(e.consumer_refund,25)
        self.assertEqual(e.pool_state,PoolState.EXPIRED)
        e.invariants()

    def test_closed_after_non_global_selection_releases_four_locks(self):
        e=Election()
        e.accept('provider')
        e.request('sponsor',115)
        e.callback('coordinator',116)
        e.apply(117)
        self.assertEqual(e.active_assignment_locks,4)
        e.close('consumer')
        self.assertEqual(e.pool_state,PoolState.RELEASED)
        with self.assertRaises(PolicyError):e.copy_committee()
        e.invariants()

    def test_closed_after_staged_global_seed_clears_it(self):
        e=Election(global_merkle=True)
        e.accept('provider')
        e.request('sponsor',115)
        e.callback('coordinator',116)
        e.apply(117)
        self.assertTrue(e.staged_seed)
        e.close('consumer')
        with self.assertRaises(PolicyError):e.finalize_global(118)
        e.invariants()

    def test_wrong_callback_source_or_malformed_payload_no_apply(self):
        e=Election()
        e.accept('provider')
        e.request('sponsor',115)
        with self.assertRaises(PolicyError):e.callback('outsider',118)
        self.assertFalse(e.callback('coordinator',119,words=3))
        self.assertTrue(e.callback('coordinator',120))
        self.assertFalse(e.callback('coordinator',121))
        e.apply(123)
        with self.assertRaises(PolicyError):e.apply(124)
        e.invariants()

    def test_after_deadline_does_not_reroll_or_apply(self):
        e=Election()
        e.accept('provider')
        e.request('sponsor',110)
        self.assertFalse(e.callback('coordinator',201))
        with self.assertRaises(PolicyError):e.request('sponsor',202)
        e.expire(201)
        e.expire_adapter(201)
        e.close('consumer')
        e.invariants()

    def test_close_never_increases_total_escrow(self):
        for use_global in (False,True):
            e=Election(global_merkle=use_global)
            e.close('consumer')
            self.assertEqual(e.consumer_refund,25)
            self.assertEqual(e.escrow,0)
            e.invariants()

    def test_long_deterministic_random_traces_protect_invariants(self):
        rng=random.Random(9011)
        attempted=0
        for i in range(1500):
            e=Election(global_merkle=bool(i%2))
            for step in range(32):
                time=100+rng.randint(0,160)
                action=rng.choice(('accept','request','callback','apply','global',
                                   'copy','close','expire','expire_adapter'))
                try:
                    if action=='accept':e.accept(rng.choice(('provider','consumer')))
                    elif action=='request':e.request(rng.choice(('sponsor','consumer','outsider')),time,
                                                      coordinator_reverts=(rng.random()<.06))
                    elif action=='callback':e.callback(rng.choice(('coordinator','outsider')),time,
                                                       words=rng.choice((1,1,1,0,2)))
                    elif action=='apply':e.apply(time)
                    elif action=='global':e.finalize_global(time,valid_proofs=rng.random()>.03)
                    elif action=='copy':e.copy_committee()
                    elif action=='close':e.close(rng.choice(('consumer','provider')))
                    elif action=='expire':e.expire(time)
                    elif action=='expire_adapter':e.expire_adapter(time)
                except PolicyError:pass
                e.invariants()
                attempted+=1
        self.assertEqual(attempted,48000)


if __name__=='__main__':unittest.main()
