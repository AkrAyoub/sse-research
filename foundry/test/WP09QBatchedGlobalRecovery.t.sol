// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {OpenMonitorCommittee} from "../../contracts/OpenMonitorCommittee.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";
import {GlobalRosterMerkle} from "../../contracts/GlobalRosterMerkle.sol";

/// @notice WP-09Q experimental batched recovery; use only in local Foundry.
/// @dev Uses the deterministic trusted-seed test source, NOT a production VRF.
contract WP09QBatchedGlobalRecoveryTest is Test {
    uint256 internal constant CAPACITY = 1 << 20;
    uint256 internal constant ROSTER = 40;
    address internal constant CONSUMER = address(0xA100);
    address internal constant PROVIDER = address(0xB100);

    OpenMonitorCommittee internal pool;
    SSESettlement internal settlement;
    mapping(uint256 => bytes32) internal historicalTree;
    address[] internal roster;

    function setUp() public {
        vm.warp(100_000);
        vm.roll(100);
        pool = new OpenMonitorCommittee(address(this), 1 ether, 7 days, 1 days);
        pool.enableGlobalMerkleElection();
        pool.enableGlobalBatchedRecovery();
        settlement = new SSESettlement(address(pool));
        pool.bindSettlement(address(settlement));
        vm.deal(CONSUMER, 10 ether);
        for (uint256 i; i < ROSTER; ++i) {
            address member = address(uint160(0xC100 + i));
            roster.push(member);
            GlobalRosterMerkle.write(historicalTree, i, member);
            vm.deal(member, 2 ether);
            vm.prank(member);
            pool.register{value: 1 ether}();
        }
        assertEq(pool.globalRosterRoot(), historicalTree[1]);
    }

    function _leaseAndSeed() internal returns (uint256 leaseId) {
        vm.prank(CONSUMER);
        leaseId = settlement.createLease{value: 25}(
            PROVIDER, keccak256("endpoint"), keccak256("profile"),
            25, 5, 25, 1, 100, 100, 100
        );
        vm.prank(PROVIDER);
        settlement.acceptLease(leaseId);
        pool.fulfillRandomness(leaseId, 745261);
        assertTrue(pool.pendingGlobalSeedReady(leaseId));
    }

    function _proofs(uint256 id, uint256 start, uint256 count)
        internal view returns (address[] memory accounts, bytes32[][] memory siblings)
    {
        uint256[] memory indexes = pool.globalRecoveryDrawIndexes(id);
        accounts = new address[](count);
        siblings = new bytes32[][](count);
        for (uint256 j; j < count; ++j) {
            uint256 index = indexes[start+j];
            accounts[j] = roster[index];
            siblings[j] = new bytes32[](20);
            uint256 node = CAPACITY + index;
            for (uint256 k; k < 20; ++k) {
                siblings[j][k] = historicalTree[node ^ 1];
                node >>= 1;
            }
        }
    }

    function _advance(uint256 id, uint256 start, uint256 count) internal {
        (address[] memory accounts, bytes32[][] memory siblings) =
            _proofs(id, start, count);
        pool.advanceGlobalRecovery(id, accounts, siblings);
    }

    function _firstSelected(uint256 id) internal view returns (address) {
        uint256[] memory indexes = pool.globalRecoveryDrawIndexes(id);
        return roster[indexes[0]];
    }

    function testDeployedRuntimeSizeAndRemainingHeadroom() public {
        uint256 poolRuntime = address(pool).code.length;
        uint256 settlementRuntime = address(settlement).code.length;
        console2.log("WP09Q|pool_runtime_bytes", poolRuntime);
        console2.log("WP09Q|settlement_runtime_bytes", settlementRuntime);
        assertLt(poolRuntime, 24_576);
        assertLt(settlementRuntime, 24_576);
    }

    function test40OrderedLeavesInFiveBatchesBuildsFourSeatsAndStandbys() public {
        uint256 id = _leaseAndSeed();
        assertEq(pool.GLOBAL_RECOVERY_DRAW_LIMIT(), 40);
        assertEq(pool.GLOBAL_RECOVERY_BATCH_LIMIT(), 8);
        for (uint256 start; start < ROSTER; start += 8) {
            _advance(id, start, 8);
            assertEq(pool.globalRecoveryCursor(id), start + 8);
        }
        assertEq(uint8(pool.assignmentStatus(id)),
                 uint8(OpenMonitorCommittee.RequestStatus.Assigned));
        assertEq(pool.globalRecoveryLocks(id), 0);
        assertFalse(pool.pendingGlobalSeedReady(id));
        assertEq(pool.standbyRemaining(id), 36);
        address[4] memory committee = pool.getCommittee(id);
        for (uint256 i; i < 4; ++i) {
            (,,,uint32 active,,) = pool.candidates(committee[i]);
            assertEq(active, 1);
        }
        settlement.finalizeMonitorCommittee(id);
        SSESettlement.Lease memory recorded = settlement.getLease(id);
        assertEq(recorded.monitors[0], committee[0]);
    }

    function testLegacyGlobalFinalizeCannotBypass40IndexProofs() public {
        uint256 id = _leaseAndSeed();
        (address[] memory accounts, bytes32[][] memory siblings) = _proofs(id, 0, 8);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.finalizeGlobalCommittee(id, accounts, siblings);
        assertEq(pool.globalRecoveryCursor(id), 0);
    }

    function testOutOfOrderAndTamperedHistoricalProofRevertAtomically() public {
        uint256 id = _leaseAndSeed();
        (address[] memory accounts, bytes32[][] memory siblings) = _proofs(id, 8, 8);
        vm.expectRevert(OpenMonitorCommittee.InvalidGlobalProof.selector);
        pool.advanceGlobalRecovery(id, accounts, siblings);
        assertEq(pool.globalRecoveryCursor(id), 0);
        (accounts, siblings) = _proofs(id, 0, 8);
        accounts[0] = address(0xBAAD);
        vm.expectRevert(OpenMonitorCommittee.InvalidGlobalProof.selector);
        pool.advanceGlobalRecovery(id, accounts, siblings);
        assertEq(pool.globalRecoveryCursor(id), 0);
        assertEq(pool.globalRecoveryLocks(id), 0);
    }

    function testCannotReplayBatchOrSubmitMoreThanEight() public {
        uint256 id = _leaseAndSeed();
        _advance(id, 0, 8);
        (address[] memory accounts, bytes32[][] memory siblings) = _proofs(id, 0, 8);
        vm.expectRevert(OpenMonitorCommittee.InvalidGlobalProof.selector);
        pool.advanceGlobalRecovery(id, accounts, siblings);
        (accounts, siblings) = _proofs(id, 8, 9);
        vm.expectRevert(OpenMonitorCommittee.InvalidInput.selector);
        pool.advanceGlobalRecovery(id, accounts, siblings);
        assertEq(pool.globalRecoveryCursor(id), 8);
        assertEq(pool.globalRecoveryLocks(id), 4);
    }

    function testCloseDuringPartialProofReleasesProvisionalBondsImmediately() public {
        uint256 id = _leaseAndSeed();
        address first = _firstSelected(id);
        _advance(id, 0, 8);
        (,,,uint32 lockedBefore,,) = pool.candidates(first);
        assertEq(lockedBefore, 1);
        vm.prank(CONSUMER);
        settlement.closeLease(id);
        assertEq(uint8(pool.assignmentStatus(id)),
                 uint8(OpenMonitorCommittee.RequestStatus.Expired));
        assertEq(pool.globalRecoveryLocks(id), 0);
        assertEq(pool.globalRecoveryCursor(id), 0);
        (,,,uint32 lockedAfter,,) = pool.candidates(first);
        assertEq(lockedAfter, 0);
        assertEq(settlement.withdrawable(CONSUMER), 25);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        _advance(id, 8, 8);
    }

    function testProvisionalSelectedMonitorCannotExitMidProof() public {
        uint256 id = _leaseAndSeed();
        address first = _firstSelected(id);
        _advance(id, 0, 8);
        vm.prank(first);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.requestExit();
    }

    function testThirtySevenHistoricalIdentitiesExitThenFailClosedWithoutReroll() public {
        uint256 id = _leaseAndSeed();
        uint256[] memory indexes = pool.globalRecoveryDrawIndexes(id);
        for (uint256 i; i < 37; ++i) {
            vm.prank(roster[indexes[i]]);
            pool.requestExit();
        }
        for (uint256 offset; offset < ROSTER; offset += 8) {
            _advance(id, offset, 8);
        }
        assertEq(uint8(pool.assignmentStatus(id)),
                 uint8(OpenMonitorCommittee.RequestStatus.Expired));
        assertEq(pool.globalRecoveryLocks(id), 0);
        assertFalse(pool.pendingGlobalSeedReady(id));
        vm.prank(CONSUMER);
        settlement.closeLease(id);
        assertEq(settlement.withdrawable(CONSUMER), 25);
    }

    function testBenchRecoveryFiveSuccessfulProofBatches() public {
        uint256 id = _leaseAndSeed();
        for (uint256 offset; offset < ROSTER; offset += 8) {
            (address[] memory accounts, bytes32[][] memory siblings) =
                _proofs(id, offset, 8);
            uint256 beforeGas = gasleft();
            pool.advanceGlobalRecovery(id, accounts, siblings);
            uint256 gasUsed = beforeGas - gasleft();
            console2.log("WP09Q|proofs_in_batch", uint256(8));
            console2.log("WP09Q|batch_offset", offset);
            console2.log("WP09Q|batch_call_gas", gasUsed);
        }
        assertEq(uint8(pool.assignmentStatus(id)),
                 uint8(OpenMonitorCommittee.RequestStatus.Assigned));
    }

    function testTimeoutDuringPartialProofReleasesProvisionalBonds() public {
        uint256 id = _leaseAndSeed();
        address first = _firstSelected(id);
        _advance(id, 0, 8);
        vm.warp(block.timestamp + pool.randomnessTimeout() + 1);
        pool.expire(id);
        assertEq(uint8(pool.assignmentStatus(id)),
                 uint8(OpenMonitorCommittee.RequestStatus.Expired));
        (,,,uint32 lockedAfter,,) = pool.candidates(first);
        assertEq(lockedAfter, 0);
        vm.prank(CONSUMER);
        settlement.closeLease(id);
        assertEq(settlement.withdrawable(CONSUMER), 25);
    }
}
