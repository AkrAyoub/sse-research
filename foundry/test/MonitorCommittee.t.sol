// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import "forge-std/Test.sol";
import {OpenMonitorCommittee} from "../../contracts/OpenMonitorCommittee.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";

contract MonitorCommitteeTest is Test {
    OpenMonitorCommittee pool;
    SSESettlement sse;
    address consumer = address(0xA100);
    address provider = address(0xB100);
    address[5] monitors;

    function setUp() public {
        vm.warp(10_000);
        pool = new OpenMonitorCommittee(address(this), 1 ether, 7 days, 1 days);
        sse = new SSESettlement(address(pool));
        pool.bindSettlement(address(sse));
        vm.deal(consumer, 100 ether);
        vm.deal(provider, 100 ether);
        for (uint256 i; i < 5; ++i) {
            monitors[i] = address(uint160(0xC100 + i));
            vm.deal(monitors[i], 2 ether);
            vm.prank(monitors[i]);
            pool.register{value: 1 ether}();
        }
    }

    function createAndAccept() internal returns (uint256 leaseId) {
        vm.prank(consumer);
        leaseId = sse.createLease{value: 25}(
            provider, keccak256("endpoint"), keccak256("profile"),
            25, 5, 25, 1, 100, 100, 100
        );
        vm.prank(provider);
        sse.acceptLease(leaseId);
    }

    function testNonAuthorizedSeedRejectedAndNoPrematureCommittee() public {
        uint256 leaseId = createAndAccept();
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        sse.finalizeMonitorCommittee(leaseId);
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        vm.prank(address(0xDEAD));
        pool.fulfillRandomness(1, 23);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        vm.prank(monitors[0]);
        pool.requestExit();
    }

    function testAssignmentAndLocksThenReleaseAfterEvidenceClosure() public {
        uint256 leaseId = createAndAccept();
        pool.fulfillRandomness(1, 0xC0FFEE);
        sse.finalizeMonitorCommittee(leaseId);
        address[4] memory committee = pool.getCommittee(1);
        for (uint256 i; i < 4; ++i) {
            vm.prank(committee[i]);
            sse.confirmMonitorAssignment(leaseId);
            vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
            vm.prank(committee[i]);
            pool.requestExit();
        }
        vm.prank(consumer);
        sse.admitEpoch(leaseId, keccak256("request"));
        SSESettlement.Epoch memory ep = sse.getEpoch(leaseId, 0);
        vm.warp(uint256(ep.responseDeadline) + 1);
        for (uint256 i; i < 3; ++i) {
            vm.prank(committee[i]);
            sse.submitMonitorVoteDirect(leaseId, 0, SSESettlement.Outcome.Failure, keccak256(abi.encode(i)));
        }
        vm.warp(uint256(ep.evidenceClose) + 1);
        sse.closeEpochEvidence(leaseId, 0);
        SSESettlement.Epoch memory epAfter = sse.getEpoch(leaseId, 0);

        assertEq(epAfter.consumerCredited, 20);
        assertEq(epAfter.providerCredited, 0);
        assertEq(epAfter.unresolvedExposure, 5);

        assertEq(sse.withdrawable(consumer), 20);
        assertEq(sse.withdrawable(provider), 0);
        assertEq(address(sse).balance, 25);

        uint256 balanceBefore = consumer.balance;

        vm.prank(consumer);
        sse.withdraw();

        assertEq(consumer.balance, balanceBefore + 20);
        assertEq(sse.withdrawable(consumer), 0);
        assertEq(address(sse).balance, 5);

        vm.prank(consumer);
        sse.closeLease(leaseId);

        sse.releaseCommitteeAfterEvidence(leaseId);
        for (uint256 i; i < 4; ++i) {
            vm.prank(committee[i]);
            pool.requestExit();
        }
    }

    function testRandomnessTimeoutReleasesPendingLocks() public {
        createAndAccept();
        vm.warp(block.timestamp + 1 days + 1);
        pool.expire(1);
        vm.prank(monitors[0]);
        pool.requestExit();
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.fulfillRandomness(1, 99);
    }

    function testNoConsumerOrProviderOnCommittee() public {
        vm.prank(consumer);
        pool.register{value: 1 ether}();
        vm.prank(provider);
        pool.register{value: 1 ether}();
        createAndAccept();
        pool.fulfillRandomness(1, 123);
        address[4] memory committee = pool.getCommittee(1);
        for (uint256 i; i < 4; ++i) {
            assertTrue(committee[i] != consumer && committee[i] != provider);
        }
    }
}
