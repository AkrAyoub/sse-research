// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {OpenMonitorCommittee} from "../../contracts/OpenMonitorCommittee.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";

/// @notice WP09C deterministic future-block selection; DOES NOT prove
/// globally uniform sampling, PoS finality or unbiased block entropy.
contract DelayedBlockEntropyTest is Test {
    OpenMonitorCommittee pool;
    SSESettlement settlement;
    address consumer = address(0xA100);
    address provider = address(0xB100);
    address stranger = address(0xDEAD);
    bytes32 constant FUTURE_HASH = keccak256("test-only-known-future-block");

    function setUp() public {
        vm.roll(100);
        vm.warp(100_000);
        pool = new OpenMonitorCommittee(address(this), 1 ether, 7 days, 1 days);
        pool.enableDelayedBlockEntropy();
        settlement = new SSESettlement(address(pool));
        pool.bindSettlement(address(settlement));
        vm.deal(consumer, 100 ether);
        vm.deal(provider, 100 ether);
        for (uint256 i; i < 5; ++i) {
            address monitor = address(uint160(0xC100 + i));
            vm.deal(monitor, 2 ether);
            vm.prank(monitor);
            pool.register{value: 1 ether}();
        }
    }

    function _lease() internal returns (uint256 leaseId) {
        vm.prank(consumer);
        leaseId = settlement.createLease{value: 25}(
            provider, keccak256("wp09c-endpoint"), keccak256("wp09c-profile"),
            25, 5, 25, 1, 100, 100, 100
        );
    }

    function _reachTarget(uint256 id, bytes32 knownHash) internal {
        uint256 target = pool.assignmentRequestedBlock(id) + pool.DELAYED_ENTROPY_BLOCKS();
        vm.roll(target + 1);
        vm.setBlockhash(target, knownHash);
    }

    function testOptInIsOneWayAndMustPrecedeSettlementBinding() public {
        assertTrue(pool.delayedBlockEntropyEnabled());
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        pool.enableDelayedBlockEntropy();

        OpenMonitorCommittee other =
            new OpenMonitorCommittee(address(this), 1 ether, 7 days, 1 days);
        vm.prank(stranger);
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        other.enableDelayedBlockEntropy();
        SSESettlement otherSettlement = new SSESettlement(address(other));
        other.bindSettlement(address(otherSettlement));
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        other.enableDelayedBlockEntropy();
        assertFalse(other.delayedBlockEntropyEnabled());
    }

    function testSelectionRequiresFutureBlockAndNotTrustedSeedSource() public {
        uint256 id = _lease();
        assertEq(id, 1);
        uint256 target = pool.assignmentRequestedBlock(id) + pool.DELAYED_ENTROPY_BLOCKS();
        assertEq(target, block.number + 4);
        assertEq(pool.snapshotSize(id), 5);

        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        pool.fulfillRandomness(id, 1234);
        vm.prank(stranger);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.fulfillDelayedBlockEntropy(id);

        vm.roll(target);
        vm.setBlockhash(target, FUTURE_HASH);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.fulfillDelayedBlockEntropy(id);

        _reachTarget(id, FUTURE_HASH);
        vm.prank(stranger);
        pool.fulfillDelayedBlockEntropy(id);
        assertEq(uint8(pool.assignmentStatus(id)),
                 uint8(OpenMonitorCommittee.RequestStatus.Assigned));
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.fulfillDelayedBlockEntropy(id);
        assertEq(pool.snapshotSize(id), 0);
        assertEq(pool.standbyRemaining(id), 1);
    }

    function testFrozenSnapshotCommittedBeforeEntropyExistsAndDeterministicReplay() public {
        uint256 id = _lease();
        uint256 requestBlock = pool.assignmentRequestedBlock(id);
        address[] memory original = new address[](5);
        for (uint256 i; i < original.length; ++i) {
            original[i] = pool.candidateAt(i);
            (,,uint32 pending,,,) = pool.candidates(original[i]);
            assertEq(pending, 1);
        }
        bytes32 expected = keccak256(abi.encode(
            block.chainid, address(pool), id, requestBlock, original));
        assertEq(pool.snapshotCommitment(id), expected);
        // The 6th candidate joins after snapshot, cannot enter THIS selection.
        address late = address(0xC200);
        vm.deal(late, 2 ether);
        vm.prank(late);
        pool.register{value: 1 ether}();
        assertEq(pool.candidateCount(), 6);
        assertEq(pool.snapshotSize(id), 5);
        assertEq(pool.snapshotCommitment(id), expected);

        _reachTarget(id, FUTURE_HASH);
        uint256 target = requestBlock + pool.DELAYED_ENTROPY_BLOCKS();
        uint256 seed = uint256(keccak256(abi.encode(
            pool.DELAYED_ENTROPY_DOMAIN(), block.chainid, address(pool), id,
            expected, target, FUTURE_HASH)));
        address[] memory expectedRoster = original;
        for (uint256 i; i < expectedRoster.length; ++i) {
            uint256 j = i + uint256(keccak256(abi.encode(seed, id, i)))
                % (expectedRoster.length - i);
            (expectedRoster[i], expectedRoster[j]) = (expectedRoster[j], expectedRoster[i]);
        }
        vm.prank(stranger);
        pool.fulfillDelayedBlockEntropy(id);
        address[4] memory committee = pool.getCommittee(id);
        for (uint256 i; i < 4; ++i) {
            assertEq(committee[i], expectedRoster[i]);
            assertTrue(committee[i] != late);
            (,,uint32 pending,uint32 locked,,) = pool.candidates(committee[i]);
            assertEq(pending, 0);
            assertEq(locked, 1);
        }
        assertEq(pool.snapshotCommitment(id), expected);
        assertEq(pool.standbyRemaining(id), 1);
    }

    function testDelayedModeStillRequiresFourConfirmationsAndThreeVotes() public {
        uint256 id = _lease();
        vm.prank(provider);
        settlement.acceptLease(id);
        _reachTarget(id, FUTURE_HASH);
        vm.prank(stranger);
        pool.fulfillDelayedBlockEntropy(id);
        settlement.finalizeMonitorCommittee(id);
        address[4] memory committee = pool.getCommittee(id);
        for (uint256 i; i < 3; ++i) {
            vm.prank(committee[i]);
            settlement.confirmMonitorAssignment(id);
        }
        vm.prank(consumer);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.admitEpoch(id, keccak256("too-early"));
        vm.prank(committee[3]);
        settlement.confirmMonitorAssignment(id);
        vm.prank(consumer);
        settlement.admitEpoch(id, keccak256("challenge"));
        SSESettlement.Epoch memory ep = settlement.getEpoch(id, 0);
        vm.warp(uint256(ep.responseDeadline) + 1);
        for (uint256 i; i < 3; ++i) {
            vm.prank(committee[i]);
            settlement.submitMonitorVoteDirect(
                id, 0, SSESettlement.Outcome.Failure,
                keccak256(abi.encode(i, "wp09c-test-only"))
            );
        }
        vm.warp(uint256(ep.evidenceClose) + 1);
        settlement.closeEpochEvidence(id, 0);
        SSESettlement.Epoch memory closed = settlement.getEpoch(id, 0);
        assertEq(uint8(closed.outcome), uint8(SSESettlement.Outcome.Failure));
        assertEq(closed.consumerCredited, 20);
        assertEq(closed.unresolvedExposure, 5);
    }

    function testExpiredBlockhashFailsClosedAndConsumerCanAbortRefund() public {
        uint256 id = _lease();
        uint256 target = pool.assignmentRequestedBlock(id) + pool.DELAYED_ENTROPY_BLOCKS();
        vm.roll(target + 257); // more than 256 blocks past target
        vm.setBlockhash(target, FUTURE_HASH);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.fulfillDelayedBlockEntropy(id);
        // Timed-out assignments must release pending bond locks, as before.
        vm.warp(block.timestamp + pool.randomnessTimeout() + 1);
        pool.expire(id);
        assertEq(uint8(pool.assignmentStatus(id)),
                 uint8(OpenMonitorCommittee.RequestStatus.Expired));
        for (uint256 i; i < 5; ++i) {
            (,,uint32 pending,uint32 assignments,,) = pool.candidates(pool.candidateAt(i));
            assertEq(pending, 0);
            assertEq(assignments, 0);
        }
        vm.prank(consumer);
        settlement.closeLease(id);
        assertEq(settlement.withdrawable(consumer), 25);
        // An expired PRE-SELECTION request had no assigned committee to
        // release. expire() already unlocked its pending snapshot bonds.
        // Trying the assigned-committee release path must fail closed.
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        settlement.releaseCommitteeAfterEvidence(id);
        assertEq(uint8(pool.assignmentStatus(id)),
                 uint8(OpenMonitorCommittee.RequestStatus.Expired));
    }

    function testMissingFutureBlockHashCannotBeSubstitutedWithArbitrarySeed() public {
        uint256 id = _lease();
        uint256 target = pool.assignmentRequestedBlock(id) + pool.DELAYED_ENTROPY_BLOCKS();
        vm.roll(target + 1);
        vm.setBlockhash(target, bytes32(0));
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.fulfillDelayedBlockEntropy(id);
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        pool.fulfillRandomness(id, 0xBAD);
        assertEq(pool.snapshotSize(id), 5);
    }

    function testRandomnessTimeoutAlsoLimitsDelayedFulfillment() public {
        uint256 id = _lease();
        _reachTarget(id, FUTURE_HASH);
        vm.warp(block.timestamp + pool.randomnessTimeout() + 1);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.fulfillDelayedBlockEntropy(id);
        pool.expire(id);
        assertEq(pool.snapshotSize(id), 0);
    }

    function testLegacyRandomnessSourceStillWorksWhenOptInIsNotEnabled() public {
        OpenMonitorCommittee legacy =
            new OpenMonitorCommittee(address(this), 1 ether, 7 days, 1 days);
        SSESettlement legacySettlement = new SSESettlement(address(legacy));
        legacy.bindSettlement(address(legacySettlement));
        for (uint256 i; i < 4; ++i) {
            address monitor = address(uint160(0xD100 + i));
            vm.deal(monitor, 2 ether);
            vm.prank(monitor);
            legacy.register{value: 1 ether}();
        }
        vm.prank(consumer);
        legacySettlement.createLease{value: 25}(
            provider, keccak256("legacy-endpoint"), keccak256("legacy-profile"),
            25, 5, 25, 1, 100, 100, 100
        );
        assertFalse(legacy.delayedBlockEntropyEnabled());
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        legacy.fulfillDelayedBlockEntropy(1);
        vm.prank(stranger);
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        legacy.fulfillRandomness(1, 3);
        legacy.fulfillRandomness(1, 3);
        assertEq(uint8(legacy.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.Assigned));
        assertEq(legacy.standbyRemaining(1), 0);
    }
}
