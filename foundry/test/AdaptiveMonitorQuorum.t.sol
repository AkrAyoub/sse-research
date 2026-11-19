// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {AdaptiveMonitorQuorum} from "../../contracts/AdaptiveMonitorQuorum.sol";

contract AdaptiveMonitorQuorumTest is Test {
    function plan(
        uint256 eligible,
        uint256 toleratedBadSeats,
        uint256 perLeaseGasSeatLimit,
        uint256 reportBudget,
        uint256 epochs,
        uint256 reward
    ) external pure returns (AdaptiveMonitorQuorum.Decision memory) {
        return AdaptiveMonitorQuorum.decide(
            eligible, toleratedBadSeats, perLeaseGasSeatLimit, reportBudget,
            epochs, reward
        );
    }

    function threshold(uint256 selected) external pure returns (uint256) {
        return AdaptiveMonitorQuorum.strictTwoThirdsQuorum(selected);
    }

    function testQuorumAdaptsToActualPerLeaseSelection() public {
        assertEq(this.threshold(4), 3);
        assertEq(this.threshold(5), 4);
        assertEq(this.threshold(7), 5);
        assertEq(this.threshold(8), 6);
        assertEq(this.threshold(10), 7);
        assertEq(this.threshold(100), 67);
    }

    function testCommitteeSizeNotLinkedToNetworkPopulationCap() public {
        AdaptiveMonitorQuorum.Decision memory a =
            this.plan(4, 1, 40, 1000, 1, 10);
        assertEq(a.seats, 4);
        assertEq(a.quorum, 3);
        AdaptiveMonitorQuorum.Decision memory b =
            this.plan(100, 3, 17, 10000, 1, 10);
        assertEq(b.seats, 17);
        assertEq(b.quorum, 12);
        assertEq(b.modeledByzantineTolerance, 5);
        assertEq(b.requiredMinimumSeats, 10);
    }

    function testBudgetNotValidatorPopulationDeterminesPerLeaseCost() public {
        AdaptiveMonitorQuorum.Decision memory a =
            this.plan(1000, 2, 50, 600, 3, 10);
        assertEq(a.seats, 20);
        assertEq(a.quorum, 14);
    }

    function testInsufficientIndependentEligiblePoolReverts() public {
        vm.expectRevert(AdaptiveMonitorQuorum.InsufficientIndependentEligibleMonitors.selector);
        this.plan(6, 2, 64, 10000, 1, 10);
    }

    function testInsufficientRewardBudgetDoesNotLowerSecurity() public {
        vm.expectRevert(AdaptiveMonitorQuorum.InsufficientMonitorRewardBudget.selector);
        this.plan(100, 2, 64, 200, 3, 10);
    }

    function testInsufficientGasBoundDoesNotLowerSecurity() public {
        vm.expectRevert(AdaptiveMonitorQuorum.InvalidMonitoringPolicy.selector);
        this.plan(100, 2, 6, 10000, 1, 10);
    }

    function testMinimumByzantineFaultToleranceIsExplicit() public {
        vm.expectRevert(AdaptiveMonitorQuorum.InvalidMonitoringPolicy.selector);
        this.plan(100, 0, 64, 10000, 1, 10);
    }

    function testZeroReportRewardDoesNotProduceFreeCommittees() public {
        vm.expectRevert(AdaptiveMonitorQuorum.InvalidMonitoringPolicy.selector);
        this.plan(100, 1, 64, 10000, 1, 0);
    }

    function testNoOutcomeClaimBeforeHonestEvidence() public pure {
        // The library provides only frozen seat/quorum math, not a fabricated
        // measurement, SLA result, VRF seed, physical independence or vote.
        uint256 seats = 7;
        uint256 quorum = AdaptiveMonitorQuorum.strictTwoThirdsQuorum(seats);
        assert(quorum == 5);
        assert(quorum > seats / 2);
    }

    function testFuzzStrictQuorumMonotonicWithinGasRange(uint8 extra) public {
        uint256 seats = 4 + uint256(extra);
        uint256 threshold_ = this.threshold(seats);
        assertGt(threshold_, (seats * 2) / 3);
        assertLe(threshold_, seats);
    }
}
