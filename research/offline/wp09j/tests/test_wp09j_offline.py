"""Offline structural/patcher checks; do NOT interpret as EVM compilation."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apply_wp09j import patch_pool, patch_settlement, one

SOURCE = (ROOT / 'contracts' / 'SSEVRFV25Adapter.sol').read_text()
MOCK = (ROOT / 'contracts' / 'MockVRFV25Coordinator.sol').read_text()
FOUNDRY = (ROOT / 'foundry_test' / 'VRFAdapterIntegration.t.sol').read_text()


class WP09JOfflinePatchTests(unittest.TestCase):
    def test_patch_getter_addition(self):
        original = 'contract X {\n    function assignmentStatus(uint256 id) external view returns (RequestStatus) { return assignments[id].status; }\n}'
        changed = patch_pool(original)
        self.assertIn('function assignmentRequestedAt(uint256 id)', changed)
        self.assertIn('return assignments[id].requestedAt;', changed)
        self.assertEqual(changed.count('function assignmentStatus('), 1)

    def test_patch_rejects_unknown_pool_version(self):
        with self.assertRaises(ValueError):
            patch_pool('pragma solidity ^0.8.24;')

    def test_patch_rejects_duplicate_anchors(self):
        with self.assertRaises(ValueError):
            patch_pool('    function assignmentStatus(uint256 id) external view returns (RequestStatus) { return assignments[id].status; }\n' * 2)

    def test_settlement_patch_preserves_legacy_and_adds_hook(self):
        fixture = '\n'.join([
            'contract SSESettlement is EIP712 {',
            '    address public resourceBoard;',
            '    event ResourceBoardBound(address indexed board);',
            '    function bindResourceBoard(address board) external {',
            '        return;',
            '    }',
            '    function finalizeMonitorCommittee(uint256 leaseId) external {',
            '        return;',
            '    }',
            '}',
        ])
        changed = patch_settlement(fixture)
        self.assertIn('interface ISSEVRFAdapter', changed)
        self.assertIn('ISSEVRFAdapter public randomnessAdapter;', changed)
        self.assertIn('function bindRandomnessAdapter(address adapter)', changed)
        self.assertIn('function requestLeaseRandomness(uint256 leaseId)', changed)
        self.assertIn('nextLeaseId != 1', changed)
        self.assertIn('committeePool.assignmentStatus(lease.assignmentId)', changed)
        self.assertIn('function bindResourceBoard(address board)', changed)
        self.assertEqual(changed.count('function finalizeMonitorCommittee(uint256 leaseId)'), 1)

    def test_settlement_patch_is_fail_closed_and_idempotence_rejected(self):
        fixture = '\n'.join([
            'contract SSESettlement is EIP712 {',
            '    address public resourceBoard;',
            '    event ResourceBoardBound(address indexed board);',
            '    function bindResourceBoard(address board) external { }',
            '    function finalizeMonitorCommittee(uint256 leaseId) external { }',
            '}',
        ])
        result = patch_settlement(fixture)
        with self.assertRaises(ValueError):
            patch_settlement(result)
        with self.assertRaises(ValueError):
            patch_settlement('not the SSE contract')

    def test_adapter_fixed_coordinator_source_and_one_request(self):
        self.assertIn('address public immutable pinnedCoordinator;', SOURCE)
        self.assertIn('msg.sender != pinnedCoordinator', SOURCE)
        self.assertIn('assignmentEverRequested[assignmentId]', SOURCE)
        self.assertIn('assignmentEverRequested[assignmentId] = true;', SOURCE)
        self.assertIn('pool.assignmentRequestedAt(assignmentId)', SOURCE)
        self.assertIn('pool.randomnessTimeout()', SOURCE)
        self.assertIn('deadline <= block.timestamp', SOURCE)
        self.assertNotIn('function setCoordinator', SOURCE)

    def test_callback_does_not_call_pool_or_revert_on_invalid_payload(self):
        start = SOURCE.index('function rawFulfillRandomWords(')
        end = SOURCE.index('function apply(', start)
        fragment = SOURCE[start:end]
        self.assertIn('if (msg.sender != pinnedCoordinator) revert Unauthorized();', fragment)
        self.assertIn('emit CallbackIgnored(vrfId, r.state);', fragment)
        self.assertNotIn('pool.', fragment)
        self.assertNotIn('byVrfId[vrfId] =', fragment)

    def test_proof_validation_is_not_claimed_for_local_mock(self):
        self.assertIn('verifies NO cryptographic VRF', MOCK)
        self.assertIn('NOT an on-chain VRF prover/verifier', SOURCE)
        self.assertIn('MockVRFV25Coordinator', FOUNDRY)

    def test_application_checks_still_valid_assignment_and_snapshot(self):
        start = SOURCE.index('function apply(')
        end = SOURCE.index('function expire(', start)
        fragment = SOURCE[start:end]
        self.assertIn('r.state != State.Ready', fragment)
        self.assertIn('pool.assignmentStatus(assignmentId)', fragment)
        self.assertIn('pool.snapshotCommitment(assignmentId) != r.snapshotHash', fragment)
        self.assertIn('block.chainid', fragment)
        self.assertIn('vrfId, r.snapshotHash, r.output', fragment)
        self.assertIn('pool.fulfillRandomness(assignmentId, seed)', fragment)

    def test_expire_never_requests_new_entropy(self):
        fragment = SOURCE[SOURCE.index('function expire('):]
        self.assertIn('r.state = State.Expired;', fragment)
        self.assertNotIn('requestRandomWords(', fragment)
        self.assertNotIn('fulfillRandomness(', fragment)

    def test_versioned_coordinator_abi_preserved(self):
        for fragment in (
            'uint256 subId;', 'uint16 requestConfirmations;',
            'uint32 callbackGasLimit;', 'uint32 numWords;', 'bytes extraArgs;',
            'VRF ExtraArgsV1', 'requestRandomWords(VRFV25Request.RandomWordsRequest calldata req)',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, SOURCE)

    def test_mock_is_not_upgradeable_and_has_no_paid_rpc(self):
        self.assertIn('operator = msg.sender', MOCK)
        self.assertIn('revert Unauthorized()', MOCK)
        self.assertNotIn('http:', MOCK)
        self.assertNotIn('https:', MOCK)

    def test_foundry_test_has_real_contract_lifecycle_coverage(self):
        for name in (
            'testFullLeaseVRFRequestCallbackApplyAndFourConfirmations',
            'testSpoofedDuplicateUnknownAndMalformedCallbacksFailClosed',
            'testNoRerollOnTimeoutAndEscrowRefund',
            'testCallbackReadyButApplyTimeoutCannotBeBypassed',
            'testOnlySettlementMayRequestAndBindingCannotBeReconfigured',
            'testNonexistentOrClosedLeaseCannotStartPaidRequest',
            'testVerifiedVRFCallbackStagesGlobalSeedThenHistoricalMerkleProofFinalizes',
        ):
            with self.subTest(name=name):
                self.assertIn('function ' + name, FOUNDRY)

    def test_package_has_no_ci_workflow(self):
        self.assertFalse(list(ROOT.rglob('*.yml')))
        self.assertFalse(list(ROOT.rglob('*.yaml')))
        self.assertFalse(list(ROOT.rglob('.github')))


if __name__ == '__main__':
    unittest.main()

# Added black-box patch generation regression; separate read-only input/output.
class WP09JPatchIOTests(unittest.TestCase):
    def make_repo(self, root):
        import subprocess
        repo = root / 'source'
        (repo / 'contracts').mkdir(parents=True)
        pool = (repo / 'contracts/OpenMonitorCommittee.sol')
        pool.write_text('contract OpenMonitorCommittee {\n' +
                        '    function assignmentStatus(uint256 id) external view returns (RequestStatus) { return assignments[id].status; }\n' +
                        '}\n')
        settlement = (repo / 'contracts/SSESettlement.sol')
        settlement.write_text('\n'.join([
            'contract SSESettlement is EIP712 {',
            '    address public resourceBoard;',
            '    event ResourceBoardBound(address indexed board);',
            '    function bindResourceBoard(address board) external { }',
            '    function finalizeMonitorCommittee(uint256 leaseId) external { }',
            '}',
        ]))
        return repo

    def test_separate_output_generation_never_modifies_input(self):
        import subprocess
        import json
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            repo = self.make_repo(home)
            originals = {p.name: p.read_bytes() for p in (repo / 'contracts').iterdir()}
            out = home / 'patched'
            result = subprocess.run([
                sys.executable, str(ROOT / 'apply_wp09j.py'),
                '--repo', str(repo), '--out', str(out),
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Source tree untouched', result.stdout)
            for p in (repo / 'contracts').iterdir():
                self.assertEqual(p.read_bytes(), originals[p.name])
            self.assertTrue((out / 'contracts/SSEVRFV25Adapter.sol').is_file())
            self.assertTrue((out / 'contracts/MockVRFV25Coordinator.sol').is_file())
            self.assertTrue((out / 'foundry/test/VRFAdapterIntegration.t.sol').is_file())
            self.assertIn('+    function assignmentRequestedAt',
                          (out / 'wp09j_changes.patch').read_text())
            self.assertEqual(json.loads((out / 'manifest.json').read_text())['mode'],
                             'offline-output-only')

    def test_refuses_nonempty_target_without_overwriting(self):
        import subprocess
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            repo = self.make_repo(home)
            out = home / 'patched'
            out.mkdir()
            sentinel = out / 'important.txt'
            sentinel.write_text('never touch')
            result = subprocess.run([
                sys.executable, str(ROOT / 'apply_wp09j.py'),
                '--repo', str(repo), '--out', str(out),
            ], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(sentinel.read_text(), 'never touch')

    def test_refuses_output_inside_repository(self):
        import subprocess
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            repo = self.make_repo(home)
            out = repo / 'WP09J'
            result = subprocess.run([
                sys.executable, str(ROOT / 'apply_wp09j.py'),
                '--repo', str(repo), '--out', str(out),
            ], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())
