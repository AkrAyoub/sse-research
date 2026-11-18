import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apply_wp09q import patch_pool, patch_sampler, patch_settlement, RECOVERY_API

POOL_STUB = '''
    uint256 public constant GLOBAL_SAMPLE_LIMIT = 10;
    bool public globalMerkleElectionEnabled;
    bool private entered;
    mapping(uint256 => bool) public pendingGlobalSeedReady;
    event GlobalCommitteeProved(uint256 indexed requestId, bytes32 frozenRoot,
    function globalRosterRoot() external view returns (bytes32) {
    function finalizeGlobalCommittee(
        uint256 id, address[] calldata accounts, bytes32[][] calldata siblingPaths
    ) external {
    function cancelUnassigned(uint256 id) external onlySettlement {
        Assignment storage r = assignments[id];
        RequestStatus previous = r.status;
        if (previous == RequestStatus.AwaitingRandomness) {
            if (!globalMerkleElectionEnabled) _unlockSnapshot(id);
    function expire(uint256 id) external {
        Assignment storage r = assignments[id];
        if (r.status != RequestStatus.AwaitingRandomness ||
            block.timestamp <= uint256(r.requestedAt) + randomnessTimeout) revert InvalidPhase();
        if (!globalMerkleElectionEnabled) _unlockSnapshot(id);
'''
SAMPLER_STUB = '/// @dev O(k^2), k <= 10\nif (rosterSize < count || count > 10 || count == 0) revert InvalidDraw();'
SETTLEMENT_STUB = '''
    function closeLease(uint256 leaseId) external onlyConsumer(leaseId) {
        if (address(randomnessAdapter) != address(0) &&
            lease.monitors[0] == address(0)) {
            committeePool.cancelUnassigned(lease.assignmentId);
        }
    }
'''

class PatchGuards(unittest.TestCase):
    def test_pool_opt_in_gated(self):
        s = patch_pool(POOL_STUB)
        self.assertIn('globalBatchedRecoveryEnabled',s)
        self.assertIn('!globalMerkleElectionEnabled || globalBatchedRecoveryEnabled',s)
        self.assertIn('totalRegistrations != 0',s)
        self.assertIn('settlement != address(0)',s)

    def test_bound_40_and_batch_8(self):
        s = patch_pool(POOL_STUB)
        self.assertIn('GLOBAL_RECOVERY_DRAW_LIMIT = 40',s)
        self.assertIn('GLOBAL_RECOVERY_BATCH_LIMIT = 8',s)
        self.assertIn('length > GLOBAL_RECOVERY_BATCH_LIMIT',s)
        self.assertIn('cursor + length > total',s)

    def test_seed_and_proof_binding(self):
        s = patch_pool(POOL_STUB)
        self.assertIn('GlobalRosterSampler.draw(',s)
        self.assertIn('pendingGlobalSeed[id]',s)
        self.assertIn('GlobalRosterMerkle.verify(globalSnapshotRoot[id], index, account, siblings)',s)
        self.assertIn('revert InvalidGlobalProof()',s)

    def test_legacy_path_disabled_only_when_optin(self):
        s = patch_pool(POOL_STUB)
        self.assertIn('if (globalBatchedRecoveryEnabled) revert InvalidPhase();',s)
        self.assertIn('GLOBAL_SAMPLE_LIMIT = 10',s)

    def test_cancel_cleans_partial_locks(self):
        s = patch_pool(POOL_STUB)
        self.assertIn('if (globalBatchedRecoveryEnabled) _clearGlobalRecovery(id);',s)
        self.assertIn('function cancelUnassigned',s)
        self.assertIn('function _clearGlobalRecovery',s)

    def test_expire_cleans_partial_locks(self):
        s = patch_pool(POOL_STUB)
        block = s.split('    function expire(uint256 id) external {')[1]
        self.assertIn('if (globalBatchedRecoveryEnabled) _clearGlobalRecovery(id);',block)

    def test_failed_finalization_fails_closed(self):
        self.assertIn('r.status = RequestStatus.Expired;',RECOVERY_API)
        self.assertIn('_clearGlobalRecovery(id);',RECOVERY_API)
        self.assertIn('if (cursor != total) return;',RECOVERY_API)

    def test_selected_seats_bond_locked(self):
        self.assertIn('++c.activeAssignments;',RECOVERY_API)
        self.assertIn('--candidates[r.committee[i]].activeAssignments;',RECOVERY_API)

    def test_sampler_lifts_only_upper_bound(self):
        s = patch_sampler(SAMPLER_STUB)
        self.assertIn('count > 40',s)
        self.assertIn('k <= 40',s)
        self.assertNotIn('count > 10',s)

    def test_settlement_cancel_even_without_adapter(self):
        s = patch_settlement(SETTLEMENT_STUB)
        self.assertIn('if (lease.monitors[0] == address(0))',s)
        self.assertNotIn('if (address(randomnessAdapter) != address(0) &&',s)

    def test_double_patch_rejected(self):
        with self.assertRaises(ValueError):
            patch_pool(patch_pool(POOL_STUB))

    def test_wrong_anchor_rejected(self):
        with self.assertRaises(ValueError):
            patch_pool(POOL_STUB.replace('GLOBAL_SAMPLE_LIMIT = 10','GLOBAL_SAMPLE_LIMIT = 11'))

    def test_wrong_settlement_anchor_rejected(self):
        with self.assertRaises(ValueError):
            patch_settlement(SETTLEMENT_STUB.replace('lease.monitors[0] == address(0)','lease.monitors[1] == address(0)'))

    def _fixture_repo(self, root):
        for name, body in [
            ('contracts/OpenMonitorCommittee.sol', POOL_STUB),
            ('contracts/GlobalRosterSampler.sol', SAMPLER_STUB),
            ('contracts/SSESettlement.sol', SETTLEMENT_STUB),
        ]:
            path = root/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(body,encoding='utf-8')

    def test_cli_check_does_not_modify_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self._fixture_repo(root)
            p=subprocess.run([sys.executable, str(ROOT/'apply_wp09q.py'),
                              '--repo',str(root),'--check'],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('DRY RUN',p.stdout)
            self.assertEqual((root/'contracts/OpenMonitorCommittee.sol').read_text(),POOL_STUB)
            self.assertFalse((root/'foundry/test/WP09QBatchedGlobalRecovery.t.sol').exists())

    def test_cli_apply_installs_files_and_local_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self._fixture_repo(root)
            p=subprocess.run([sys.executable,str(ROOT/'apply_wp09q.py'),
                              '--repo',str(root),'--apply'],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('PATCHED three local .sol files',p.stdout)
            self.assertTrue((root/'foundry/test/WP09QBatchedGlobalRecovery.t.sol').exists())
            self.assertEqual((root/'.local/wp09q/prepatch/contracts/SSESettlement.sol').read_text(),SETTLEMENT_STUB)

    def test_cli_rejects_double_apply_without_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self._fixture_repo(root)
            cmd=[sys.executable,str(ROOT/'apply_wp09q.py'),'--repo',str(root),'--apply']
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,0)
            self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)

    def test_test_source_presence(self):
        s=(ROOT/'foundry/test/WP09QBatchedGlobalRecovery.t.sol').read_text()
        for name in ['test40OrderedLeavesInFiveBatchesBuildsFourSeatsAndStandbys',
                     'testOutOfOrderAndTamperedHistoricalProofRevertAtomically',
                     'testCloseDuringPartialProofReleasesProvisionalBondsImmediately',
                     'testTimeoutDuringPartialProofReleasesProvisionalBonds']:
            self.assertIn(name,s)

if __name__ == '__main__':
    unittest.main()
