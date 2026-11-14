// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {OpenMonitorCommittee} from "../../contracts/OpenMonitorCommittee.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";

contract MonitorConfirmationRecoveryTest is Test {
    OpenMonitorCommittee pool;
    SSESettlement settlement;

    address consumer = address(0xA100);
    address provider = address(0xB100);
    uint256 constant MIN_BOND = 1 ether;
    address[5] candidates;

    function setUp() public {
        vm.warp(100_000);
        pool = new OpenMonitorCommittee(address(this), MIN_BOND, 7 days, 1 days);
        settlement = new SSESettlement(address(pool));
        pool.bindSettlement(address(settlement));
        vm.deal(consumer, 1 ether);
        vm.deal(provider, 1 ether);
        for (uint256 i; i < 5; ++i) {
            address monitor = address(uint160(0xC100 + i));
            candidates[i] = monitor;
            vm.deal(monitor, 2 ether);
            vm.prank(monitor);
            pool.register{value: MIN_BOND}();
        }
    }

    function _fundAndAssign() internal returns (uint256 leaseId, address[4] memory selected) {
        vm.prank(consumer);
        leaseId = settlement.createLease{value: 25}(
            provider,
            keccak256("local-provider-endpoint"),
            keccak256("tiny-profile"),
            25, 5, 25, 1, 100, 100, 100
        );
        vm.prank(provider);
        settlement.acceptLease(leaseId);
        pool.fulfillRandomness(1, 0xC0FFEE);
        settlement.finalizeMonitorCommittee(leaseId);
        selected = pool.getCommittee(1);
        assertEq(pool.standbyRemaining(1), 1);
        assertEq(settlement.monitorConfirmationDeadline(leaseId),
                 block.timestamp + settlement.MONITOR_CONFIRMATION_TIMEOUT());
    }

    function _confirmThree(uint256 leaseId, address[4] memory selected) internal {
        for (uint256 i; i < 3; ++i) {
            vm.prank(selected[i]);
            settlement.confirmMonitorAssignment(leaseId);
        }
        SSESettlement.Lease memory pending = settlement.getLease(leaseId);
        assertEq(pending.monitorConfirmations, 3);
        assertEq(uint8(pending.state), uint8(SSESettlement.LeaseState.Accepted));
    }

    function _standby(address[4] memory selected) internal view returns (address result) {
        for (uint256 j; j < candidates.length; ++j) {
            bool included;
            for (uint256 k; k < selected.length; ++k) {
                if (candidates[j] == selected[k]) { included = true; break; }
            }
            if (!included) return candidates[j];
        }
        revert("expected one standby");
    }

    function testThreeConfirmationsRecoverByRandomlyChosenStandbyAndAdmitEpoch() public {
        (uint256 leaseId, address[4] memory selected) = _fundAndAssign();
        _confirmThree(leaseId, selected);
        address missing = selected[3];
        address standby = _standby(selected);

        // Three-of-four are NOT enough for an epoch, even though later
        // monitoring *votes* use a separate 3-of-4 quorum.
        vm.prank(consumer);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.admitEpoch(leaseId, keccak256("request-before-ready"));

        // Nobody can skip the original confirmation window.
        uint256 deadline = settlement.monitorConfirmationDeadline(leaseId);
        vm.warp(deadline);
        vm.expectRevert(SSESettlement.OutsideWindow.selector);
        settlement.replaceNoShowMonitor(leaseId);
        vm.warp(deadline + 1);

        address stranger = address(0xDADA);
        vm.prank(stranger); // no centralized administrator needed
        settlement.replaceNoShowMonitor(leaseId);
        SSESettlement.Lease memory recovered = settlement.getLease(leaseId);
        assertEq(recovered.monitors[3], standby);
        assertEq(recovered.monitorConfirmations, 3);
        assertEq(uint8(recovered.state), uint8(SSESettlement.LeaseState.Accepted));
        for (uint256 i; i < 3; ++i) assertEq(recovered.monitors[i], selected[i]);
        assertEq(pool.getCommittee(1)[3], standby);
        assertEq(pool.standbyRemaining(1), 0);
        assertEq(settlement.monitorConfirmationDeadline(leaseId),
                 block.timestamp + settlement.MONITOR_CONFIRMATION_TIMEOUT());
        assertEq(recovered.totalEscrow, 25);
        assertEq(recovered.uncommittedEscrow, 25);
        assertEq(settlement.withdrawable(provider), 0);
        assertEq(settlement.withdrawable(standby), 0);
        assertEq(settlement.withdrawable(missing), 0);

        // No-show cannot confirm after losing the seat.
        vm.prank(missing);
        vm.expectRevert(SSESettlement.Unauthorized.selector);
        settlement.confirmMonitorAssignment(leaseId);
        vm.prank(standby);
        settlement.confirmMonitorAssignment(leaseId);
        SSESettlement.Lease memory ready = settlement.getLease(leaseId);
        assertEq(ready.monitorConfirmations, 4);
        assertEq(uint8(ready.state), uint8(SSESettlement.LeaseState.Ready));

        vm.prank(consumer);
        settlement.admitEpoch(leaseId, keccak256("request-after-ready"));
        assertEq(settlement.getLease(leaseId).nextEpochId, 1);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.replaceNoShowMonitor(leaseId);
    }

    function testCannotRotateBeforeTimeoutOrUnconfirmedPoolDirectly() public {
        (uint256 leaseId, address[4] memory selected) = _fundAndAssign();
        _confirmThree(leaseId, selected);
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        pool.replaceUnconfirmed(1, selected[3]);
        vm.expectRevert(SSESettlement.OutsideWindow.selector);
        settlement.replaceNoShowMonitor(leaseId);
        for (uint256 i; i < 3; ++i) {
            vm.prank(selected[i]);
            vm.expectRevert(SSESettlement.InvalidState.selector);
            settlement.confirmMonitorAssignment(leaseId);
        }
        vm.prank(selected[3]);
        settlement.confirmMonitorAssignment(leaseId);
        assertEq(uint8(settlement.getLease(leaseId).state),
                 uint8(SSESettlement.LeaseState.Ready));
        vm.warp(block.timestamp + 7 days);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.replaceNoShowMonitor(leaseId);
    }

    function testReplacementGetsFullNewTimeWindowAndUnusedReserveCannotBeReplayed() public {
        (uint256 leaseId, address[4] memory selected) = _fundAndAssign();
        _confirmThree(leaseId, selected);
        vm.warp(settlement.monitorConfirmationDeadline(leaseId) + 1);
        settlement.replaceNoShowMonitor(leaseId);
        uint256 renewed = settlement.monitorConfirmationDeadline(leaseId);

        vm.expectRevert(SSESettlement.OutsideWindow.selector);
        settlement.replaceNoShowMonitor(leaseId);
        vm.warp(renewed + 1);
        vm.expectRevert(OpenMonitorCommittee.InsufficientCandidates.selector);
        settlement.replaceNoShowMonitor(leaseId);
        assertEq(pool.standbyRemaining(1), 0);
        assertEq(settlement.getLease(leaseId).monitorConfirmations, 3);

        // No successful replacement or monitor quorum must mint a payout.
        assertEq(settlement.withdrawable(provider), 0);
        assertEq(settlement.withdrawable(consumer), 0);
    }

    function testStandbyCanExitAndConsumerCanAbortWithoutServiceEpoch() public {
        (uint256 leaseId, address[4] memory selected) = _fundAndAssign();
        address standby = _standby(selected);
        _confirmThree(leaseId, selected);

        // Standby is not force-locked just for being on a replacement list.
        vm.prank(standby);
        pool.requestExit();
        vm.warp(settlement.monitorConfirmationDeadline(leaseId) + 1);
        vm.expectRevert(OpenMonitorCommittee.InsufficientCandidates.selector);
        settlement.replaceNoShowMonitor(leaseId);
        assertEq(settlement.getLease(leaseId).nextEpochId, 0);

        // Existing V1 abort path remains available when no standby can help.
        vm.prank(consumer);
        settlement.closeLease(leaseId);
        assertEq(settlement.withdrawable(consumer), 25);
        settlement.releaseCommitteeAfterEvidence(leaseId);
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.Released));
        assertEq(pool.standbyRemaining(1), 0);
        for (uint256 i; i < 4; ++i) {
            (,,, uint32 activeAssignments,,) = pool.candidates(selected[i]);
            assertEq(activeAssignments, 0);
        }
        uint256 balanceBefore = consumer.balance;
        vm.prank(consumer);
        settlement.withdraw();
        assertEq(consumer.balance, balanceBefore + 25);
        assertEq(address(settlement).balance, 0);
    }

    function testPostRecoveryReleasesExactlyCurrentFourBonds() public {
        (uint256 leaseId, address[4] memory selected) = _fundAndAssign();
        _confirmThree(leaseId, selected);
        address standby = _standby(selected);
        vm.warp(settlement.monitorConfirmationDeadline(leaseId) + 1);
        settlement.replaceNoShowMonitor(leaseId);

        (,,, uint32 removedAssignments,,) = pool.candidates(selected[3]);
        (,,, uint32 standbyAssignments,,) = pool.candidates(standby);
        assertEq(removedAssignments, 0);
        assertEq(standbyAssignments, 1);

        vm.prank(consumer);
        settlement.closeLease(leaseId);
        settlement.releaseCommitteeAfterEvidence(leaseId);
        (,,, uint32 afterStandby,,) = pool.candidates(standby);
        (,,, uint32 afterMissing,,) = pool.candidates(selected[3]);
        assertEq(afterStandby, 0);
        assertEq(afterMissing, 0);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        vm.prank(address(settlement));
        pool.releaseAssignment(1);
    }
}
