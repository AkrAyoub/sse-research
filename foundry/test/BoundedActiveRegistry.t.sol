// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {OpenMonitorCommittee} from "../../contracts/OpenMonitorCommittee.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";

/// @notice WP09B: bounded rotating snapshots scale registration count, not
/// global fairness, Sybil resistance or V1's 4-of-3 committee semantics.
contract BoundedActiveRegistryTest is Test {
    OpenMonitorCommittee pool;
    SSESettlement settlement;

    address consumer = address(0xA101);
    address provider = address(0xB101);
    uint256 constant MIN_BOND = 1 ether;

    function setUp() public {
        vm.warp(100_000);
        pool = new OpenMonitorCommittee(address(this), MIN_BOND, 7 days, 1 days);
        settlement = new SSESettlement(address(pool));
        pool.bindSettlement(address(settlement));
        vm.deal(consumer, 10 ether);
        vm.deal(provider, 10 ether);
    }

    function _candidate(uint256 i) internal pure returns (address) {
        return address(uint160(0xC100 + i));
    }

    function _register(uint256 count) internal {
        for (uint256 i; i < count; ++i) {
            address monitor = _candidate(i);
            vm.deal(monitor, 2 ether);
            vm.prank(monitor);
            pool.register{value: MIN_BOND}();
        }
    }

    function _lease() internal returns (uint256 leaseId) {
        vm.prank(consumer);
        leaseId = settlement.createLease{value: 25}(
            provider, keccak256("wp09b-endpoint"), keccak256("wp09b-profile"),
            25, 5, 25, 1, 100, 100, 100
        );
    }

    function testNo32IdentityLifetimeCapAndBoundedSnapshotWith160Actives() public {
        _register(160);
        assertEq(pool.candidateCount(), 160);
        assertEq(pool.totalRegistrations(), 160);
        assertEq(pool.MAX_SNAPSHOT_SCAN(), 64);
        for (uint256 i; i < 160; ++i) {
            assertEq(pool.candidateAt(i), _candidate(i));
            assertEq(pool.activeSlot(_candidate(i)), i + 1);
        }

        uint256 start = gasleft();
        uint256 leaseId = _lease();
        uint256 usedGas = start - gasleft();
        assertEq(leaseId, 1);
        assertLt(usedGas, 8_500_000);
        assertEq(pool.snapshotSize(1), 64);
        assertEq(pool.nextSnapshotCursor(), 64);
        for (uint256 i; i < 160; ++i) {
            (,, uint32 pending, uint32 locked, bool active,) = pool.candidates(_candidate(i));
            assertEq(pending, i < 64 ? 1 : 0);
            assertEq(locked, 0);
            assertTrue(active);
        }
        uint256 fulfillStart = gasleft();
        pool.fulfillRandomness(1, 0xD00D);
        assertLt(fulfillStart - gasleft(), 8_500_000);
        assertEq(pool.snapshotSize(1), 0);
        assertEq(pool.standbyRemaining(1), 60);
        address[4] memory selected = pool.getCommittee(1);
        for (uint256 i; i < 4; ++i) {
            assertTrue(uint160(selected[i]) >= uint160(_candidate(0)));
            assertTrue(uint160(selected[i]) < uint160(_candidate(64)));
        }
        vm.prank(consumer);
        settlement.closeLease(1);
        settlement.releaseCommitteeAfterEvidence(1);
        assertEq(pool.standbyRemaining(1), 0);
    }

    function testRotatingWindowsIncludeDistantIdentitiesAcrossRequests() public {
        _register(96);
        _lease();
        assertEq(pool.snapshotSize(1), 64);
        assertEq(pool.nextSnapshotCursor(), 64);
        _lease();
        assertEq(pool.snapshotSize(2), 64);
        assertEq(pool.nextSnapshotCursor(), 32);
        _lease();
        assertEq(pool.snapshotSize(3), 64);
        assertEq(pool.nextSnapshotCursor(), 0);
        for (uint256 i; i < 96; ++i) {
            // 64-wide round-robin over 96 actives: every identity appears in
            // two snapshots across three requests; no candidate is invisible.
            (,, uint32 pending,,,) = pool.candidates(_candidate(i));
            assertEq(pending, 2);
        }
        for (uint256 id = 1; id <= 3; ++id) {
            vm.warp(block.timestamp + 1 days + 1);
            pool.expire(id);
            assertEq(uint8(pool.assignmentStatus(id)),
                     uint8(OpenMonitorCommittee.RequestStatus.Expired));
        }
        for (uint256 i; i < 96; ++i) {
            (,, uint32 pending,,,) = pool.candidates(_candidate(i));
            assertEq(pending, 0);
        }
    }

    function testExitIsConstantTimeAndSwapPopUpdatesIndex() public {
        _register(70);
        address exiting = _candidate(3);
        address moved = _candidate(69);
        vm.prank(exiting);
        pool.requestExit();
        assertEq(pool.candidateCount(), 69);
        assertEq(pool.totalRegistrations(), 70);
        assertEq(pool.candidateAt(3), moved);
        assertEq(pool.activeSlot(moved), 4);
        assertEq(pool.activeSlot(exiting), 0);
        (,,,, bool stillActive,) = pool.candidates(exiting);
        assertFalse(stillActive);
        vm.prank(exiting);
        vm.expectRevert(OpenMonitorCommittee.InvalidInput.selector);
        pool.register{value: MIN_BOND}();

        // A new identity can enter after any number of previous registrations.
        address newcomer = _candidate(200);
        vm.deal(newcomer, 2 ether);
        vm.prank(newcomer);
        pool.register{value: MIN_BOND}();
        assertEq(pool.candidateCount(), 70);
        assertEq(pool.totalRegistrations(), 71);
        assertEq(pool.activeSlot(newcomer), 70);

        vm.warp(block.timestamp + 7 days);
        vm.prank(exiting);
        pool.withdrawBond();
        assertEq(exiting.balance, 2 ether);
        vm.prank(exiting);
        pool.register{value: MIN_BOND}();
        assertEq(pool.candidateCount(), 71);
        assertEq(pool.totalRegistrations(), 71);
        assertEq(pool.activeSlot(exiting), 71);
    }

    function testPendingAndAssignedMembersCannotEvadeLocksByExit() public {
        _register(70);
        _lease();
        vm.prank(_candidate(0));
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.requestExit();
        // Outside the bounded scan, this active candidate is not pending.
        vm.prank(_candidate(67));
        pool.requestExit();
        assertEq(pool.candidateCount(), 69);
        assertEq(pool.activeSlot(_candidate(67)), 0);
        assertEq(pool.snapshotSize(1), 64);

        pool.fulfillRandomness(1, 0xC0FFEE);
        address[4] memory selected = pool.getCommittee(1);
        for (uint256 i; i < 4; ++i) {
            vm.prank(selected[i]);
            vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
            pool.requestExit();
        }
        // Standbys are unlocked when randomness arrives.
        address standby;
        for (uint256 i; i < 64; ++i) {
            address monitor = _candidate(i);
            bool chosen;
            for (uint256 j; j < 4; ++j) if (selected[j] == monitor) chosen = true;
            if (!chosen) { standby = monitor; break; }
        }
        assertTrue(standby != address(0));
        vm.prank(standby);
        pool.requestExit();
        vm.prank(consumer);
        settlement.closeLease(1);
        settlement.releaseCommitteeAfterEvidence(1);
        for (uint256 i; i < 4; ++i) {
            (,,,uint32 assignments,,) = pool.candidates(selected[i]);
            assertEq(assignments, 0);
        }
    }

    function testConsumerProviderExcludedEvenIfBondedAndStandbysCannotExitWhilePending() public {
        _register(5);
        vm.prank(consumer);
        pool.register{value: MIN_BOND}();
        vm.prank(provider);
        pool.register{value: MIN_BOND}();
        assertEq(pool.candidateCount(), 7);
        _lease();
        assertEq(pool.snapshotSize(1), 5);
        (,,uint32 consumerPending,,,) = pool.candidates(consumer);
        (,,uint32 providerPending,,,) = pool.candidates(provider);
        assertEq(consumerPending, 0);
        assertEq(providerPending, 0);
        pool.fulfillRandomness(1, 99);
        address[4] memory selected = pool.getCommittee(1);
        for (uint256 i; i < 4; ++i) {
            assertTrue(selected[i] != consumer && selected[i] != provider);
        }
        assertEq(pool.standbyRemaining(1), 1);
    }

    function testInsufficientEligibleAfterPartyExclusionRollsBackAssignment() public {
        _register(3);
        vm.prank(consumer);
        pool.register{value: MIN_BOND}();
        vm.prank(provider);
        pool.register{value: MIN_BOND}();
        vm.prank(consumer);
        vm.expectRevert(OpenMonitorCommittee.InsufficientCandidates.selector);
        settlement.createLease{value: 25}(
            provider, keccak256("small-endpoint"), keccak256("small-profile"),
            25, 5, 25, 1, 100, 100, 100
        );
        assertEq(pool.nextAssignmentId(), 1);
        assertEq(pool.nextSnapshotCursor(), 0);
        assertEq(settlement.nextLeaseId(), 1);
        assertEq(address(settlement).balance, 0);
    }

    function testWindowCursorNormalizesWhenRosterShrinksFrom65To64() public {
        _register(65);
        _lease();
        assertEq(pool.nextSnapshotCursor(), 64);
        // The 65th candidate was not snapshotted; it may exit freely.
        vm.prank(_candidate(64));
        pool.requestExit();
        assertEq(pool.candidateCount(), 64);
        assertEq(pool.activeSlot(_candidate(64)), 0);
        assertEq(pool.nextSnapshotCursor(), 0);
        _lease();
        assertEq(pool.snapshotSize(2), 64);
        assertEq(pool.nextSnapshotCursor(), 0);
    }

    function testWindowCursorCannotBeAdvancedByFailedRequest() public {
        _register(4);
        _lease();
        assertEq(pool.nextSnapshotCursor(), 0);
        // With a 4-entry pool this wraps deterministically.
        // A bad consumer/provider pair does not change cursor.
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        pool.requestAssignment(consumer, provider);
        assertEq(pool.nextSnapshotCursor(), 0);
    }
}
