"""Validate offline textual patch mechanics. NOT EVM compilation."""
import unittest
from apply_wp09g import patch_pool, patch_sampler


MOCK_POOL = '''contract OpenMonitorCommittee {
    uint256 public constant GLOBAL_SAMPLE_LIMIT = 10;
    bool public globalMerkleElectionEnabled;
    bool private entered;
    mapping(uint256 => bool) public pendingGlobalSeedReady;
    event GlobalCommitteeProved(uint256 indexed requestId, bytes32 frozenRoot,
                                uint256 sampled, uint256 validCandidates);
    function globalRosterRoot() external view returns (bytes32) {
        return globalTree[1];
    }
    function finalizeGlobalCommittee(
        uint256 id, address[] calldata accounts, bytes32[][] calldata siblingPaths
    ) external {
        if (!globalMerkleElectionEnabled || !pendingGlobalSeedReady[id])
            revert InvalidPhase();
    }
    function expire(uint256 id) external {
        if (!globalMerkleElectionEnabled) _unlockSnapshot(id);
    }
}
'''
MOCK_SAMPLER = '''/// @dev O(k^2), k <= 10, independent of global roster size.
if (rosterSize < count || count > 10 || count == 0) revert InvalidDraw();
'''


class PatchTests(unittest.TestCase):
    def test_pool_patch_contains_required_guards_and_release(self):
        updated = patch_pool(MOCK_POOL)
        for necessary in (
            'globalBatchedRecoveryEnabled',
            'function enableGlobalBatchedRecovery()',
            '!globalMerkleElectionEnabled',
            'function advanceGlobalRecovery(',
            'function globalRecoveryDrawIndexes(',
            'globalRecoveryLocks[id]',
            'if (globalBatchedRecoveryEnabled) _clearGlobalRecovery(id);',
            'if (globalBatchedRecoveryEnabled) revert InvalidPhase();',
            'delete r.committee;',
            'globalRecoveryCursor[id] = cursor;',
            'GlobalRosterMerkle.verify(',
            'block.timestamp > uint256(r.requestedAt) + randomnessTimeout',
            'r.status = RequestStatus.Expired;',
        ):
            self.assertIn(necessary, updated)
        self.assertNotIn('count > 40', updated)

    def test_sampler_patch_changes_guard_to40(self):
        updated = patch_sampler(MOCK_SAMPLER)
        self.assertIn('k <= 40', updated)
        self.assertIn('count > 40 || count == 0', updated)
        self.assertNotIn('count > 10', updated)

    def test_refuse_bad_branch_or_prior_patch(self):
        with self.assertRaises(ValueError):
            patch_pool(MOCK_POOL.replace('GLOBAL_SAMPLE_LIMIT = 10', 'GLOBAL_SAMPLE_LIMIT = 16'))
        with self.assertRaises(ValueError):
            patch_pool(patch_pool(MOCK_POOL))
        with self.assertRaises(ValueError):
            patch_sampler(patch_sampler(MOCK_SAMPLER))

    def test_no_net_or_github_commands_in_patch(self):
        import inspect
        import apply_wp09g
        src = inspect.getsource(apply_wp09g)
        for forbidden in ('subprocess.', 'requests.', 'urllib.', 'git push', 'gh workflow run', 'gh api', 'forge test --gas-report'):
            self.assertNotIn(forbidden, src)


if __name__ == '__main__':
    unittest.main()
