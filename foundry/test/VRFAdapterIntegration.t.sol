// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {SSEVRFV25Adapter} from "../../contracts/SSEVRFV25Adapter.sol";
import {MockVRFV25Coordinator} from "../../contracts/MockVRFV25Coordinator.sol";
import {OpenMonitorCommittee} from "../../contracts/OpenMonitorCommittee.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";
import {GlobalRosterMerkle} from "../../contracts/GlobalRosterMerkle.sol";

/// @notice Requires a local Foundry toolchain. Mock coordinator proves NO VRF.
/// @dev This file is authored but NOT run in the ChatGPT execution environment.
contract VRFAdapterIntegrationTest is Test {
    uint256 internal constant VRF_FEE = 0.001 ether;
    MockVRFV25Coordinator internal coordinator;
    SSEVRFV25Adapter internal adapter;
    OpenMonitorCommittee internal pool;
    SSESettlement internal settlement;

    address internal consumer = address(0xA100);
    address internal provider = address(0xB100);
    address internal outsider = address(0xDEAD);
    address[6] internal monitors;
    mapping(uint256 => bytes32) private historicalTree;
    uint256 private constant CAPACITY = 1 << 20;

    function setUp() public {
        vm.warp(100_000);
        vm.roll(100);
        coordinator = new MockVRFV25Coordinator();
        adapter = new SSEVRFV25Adapter(
            address(coordinator), keccak256("mock-keyhash"), 42, 3, 220_000, false
        );
        pool = new OpenMonitorCommittee(address(adapter), 1 ether, 7 days, 1 days);
        settlement = new SSESettlement(address(pool));
        pool.bindSettlement(address(settlement));
        adapter.bindPoolAndSettlement(address(pool), address(settlement));
        settlement.configureVrfFeePolicy(VRF_FEE, 50);
        settlement.bindRandomnessAdapter(address(adapter));
        vm.deal(consumer, 10 ether);
        vm.deal(provider, 10 ether);
        vm.deal(outsider, 1 ether);
        for (uint256 i; i < 6; ++i) {
            address account = address(uint160(0xC100 + i));
            monitors[i] = account;
            vm.deal(account, 2 ether);
            vm.prank(account);
            pool.register{value: 1 ether}();
        }
    }

    function _createOfferedLease() internal returns (uint256 leaseId) {
        vm.prank(consumer);
        leaseId = settlement.createLease{value: 25}(
            provider, keccak256("endpoint"), keccak256("profile"),
            25, 5, 25, 1, 100, 100, 100
        );
    }

    function _createLease() internal returns (uint256 leaseId) {
        leaseId = _createOfferedLease();
        vm.prank(provider);
        settlement.acceptLease(leaseId);
    }

    function _fund(uint256 leaseId) internal {
        // A reverted coordinator request preserves the prepaid fee.
        if (!settlement.vrfFeeFunded(leaseId)) {
            vm.prank(consumer);
            settlement.fundVrfRequestFee{value: VRF_FEE}(leaseId);
        }
    }

    function _request(uint256 leaseId) internal returns (uint256 vrfId) {
        _fund(leaseId);
        vrfId = settlement.requestLeaseRandomness(leaseId);
    }

    function _deliver(uint256 vrfId, uint256 word) internal {
        uint256[] memory result = new uint256[](1);
        result[0] = word;
        coordinator.deliver(vrfId, result);
    }

    function testFullLeaseVRFRequestCallbackApplyAndFourConfirmations() public {
        uint256 leaseId = _createLease();
        uint256 vrfId = _request(leaseId);
        assertEq(vrfId, 1);
        MockVRFV25Coordinator.RequestRecord memory req = coordinator.getRequest(vrfId);
        assertEq(req.consumer, address(adapter));
        assertEq(req.subId, 42);
        assertEq(req.confirmations, 3);
        assertEq(req.callbackGasLimit, 220_000);
        assertEq(req.extraArgs.length, 36);
        assertTrue(adapter.assignmentEverRequested(1));
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.requestLeaseRandomness(leaseId);

        _deliver(vrfId, 1234567);
        (,,, SSEVRFV25Adapter.State ready,) = adapter.byVrfId(vrfId);
        assertEq(uint8(ready), uint8(SSEVRFV25Adapter.State.Ready));
        vm.prank(outsider);
        adapter.applyRandomness(1);
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.Assigned));
        (,,, SSEVRFV25Adapter.State applied,) = adapter.byVrfId(vrfId);
        assertEq(uint8(applied), uint8(SSEVRFV25Adapter.State.Applied));
        vm.expectRevert(SSEVRFV25Adapter.BadState.selector);
        adapter.applyRandomness(1);

        settlement.finalizeMonitorCommittee(leaseId);
        address[4] memory committee = pool.getCommittee(1);
        for (uint256 i; i < 3; ++i) {
            vm.prank(committee[i]);
            settlement.confirmMonitorAssignment(leaseId);
        }
        vm.prank(consumer);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.admitEpoch(leaseId, keccak256("request-before-four-confirmations"));
        vm.prank(committee[3]);
        settlement.confirmMonitorAssignment(leaseId);
        vm.prank(consumer);
        settlement.admitEpoch(leaseId, keccak256("after-four-confirmations"));
        assertEq(settlement.getLease(leaseId).nextEpochId, 1);
    }

    function testSpoofedDuplicateUnknownAndMalformedCallbacksFailClosed() public {
        uint256 leaseId = _createLease();
        uint256 vrfId = _request(leaseId);
        uint256[] memory words = new uint256[](1);
        words[0] = 999;
        vm.prank(outsider);
        vm.expectRevert(SSEVRFV25Adapter.Unauthorized.selector);
        adapter.rawFulfillRandomWords(vrfId, words);
        coordinator.deliverUnknown(address(adapter), 99999, words); // ignore
        uint256[] memory empty = new uint256[](0);
        coordinator.deliver(vrfId, empty); // ignore; does not revert
        (,,, SSEVRFV25Adapter.State stillRequested,) = adapter.byVrfId(vrfId);
        assertEq(uint8(stillRequested), uint8(SSEVRFV25Adapter.State.Requested));
        coordinator.deliver(vrfId, words);
        coordinator.deliver(vrfId, words); // duplicate ignored
        adapter.applyRandomness(1);
        coordinator.deliver(vrfId, words); // after application ignored
        (,,, SSEVRFV25Adapter.State state,) = adapter.byVrfId(vrfId);
        assertEq(uint8(state), uint8(SSEVRFV25Adapter.State.Applied));
    }

    function testNoRerollOnTimeoutAndEscrowRefund() public {
        uint256 leaseId = _createLease();
        uint256 vrfId = _request(leaseId);
        vm.warp(block.timestamp + pool.randomnessTimeout() + 1);
        _deliver(vrfId, 123);
        (,,, SSEVRFV25Adapter.State pending,) = adapter.byVrfId(vrfId);
        assertEq(uint8(pending), uint8(SSEVRFV25Adapter.State.Requested));
        vm.expectRevert(SSEVRFV25Adapter.BadState.selector);
        adapter.applyRandomness(1);
        adapter.expire(1);
        pool.expire(1);
        (,,, SSEVRFV25Adapter.State expired,) = adapter.byVrfId(vrfId);
        assertEq(uint8(expired), uint8(SSEVRFV25Adapter.State.Expired));
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.requestLeaseRandomness(leaseId);
        vm.prank(consumer);
        settlement.closeLease(leaseId);
        assertEq(settlement.withdrawable(consumer), 25);
    }

    function testCallbackReadyButApplyTimeoutCannotBeBypassed() public {
        uint256 leaseId = _createLease();
        uint256 vrfId = _request(leaseId);
        _deliver(vrfId, 321);
        vm.warp(block.timestamp + pool.randomnessTimeout() + 1);
        vm.expectRevert(SSEVRFV25Adapter.BadState.selector);
        adapter.applyRandomness(1);
        adapter.expire(1);
        pool.expire(1);
        vm.expectRevert(SSEVRFV25Adapter.BadState.selector);
        adapter.applyRandomness(1);
    }

    function testOnlySettlementMayRequestAndBindingCannotBeReconfigured() public {
        uint256 leaseId = _createLease();
        vm.prank(outsider);
        vm.expectRevert(SSEVRFV25Adapter.Unauthorized.selector);
        adapter.requestSeed(leaseId, 1);
        vm.expectRevert(SSESettlement.Unauthorized.selector);
        settlement.bindRandomnessAdapter(address(adapter));
        vm.expectRevert(SSEVRFV25Adapter.Unauthorized.selector);
        adapter.bindPoolAndSettlement(address(pool), address(settlement));
        assertEq(address(adapter.pool()), address(pool));
        assertEq(adapter.settlement(), address(settlement));
        assertTrue(leaseId != 0);
    }

    /// @notice WP09L: only the accepted consumer can prepay; after prepayment,
    /// anyone can request the one permitted coordinator purchase.
    function testSubscriptionSpendRequiresSponsorAndProviderAcceptance() public {
        uint256 leaseId = _createOfferedLease();
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.requestLeaseRandomness(leaseId); // no prepaid fee
        vm.prank(provider);
        settlement.acceptLease(leaseId);
        vm.prank(outsider);
        vm.expectRevert(SSESettlement.Unauthorized.selector);
        settlement.fundVrfRequestFee{value: VRF_FEE}(leaseId);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.requestLeaseRandomness(leaseId); // still no prepaid fee
        vm.prank(consumer);
        settlement.fundVrfRequestFee{value: VRF_FEE}(leaseId);
        vm.prank(outsider);
        uint256 vrfId = settlement.requestLeaseRandomness(leaseId);
        assertEq(vrfId, 1);
        assertEq(coordinator.nextRequestId(), 2);
        assertEq(adapter.leaseForAssignment(1), leaseId);
        assertEq(settlement.vrfRequestsUsed(), 1);
    }

    /// @notice Closing a lease while VRF is pending MUST NOT lock otherwise
    /// idle monitor bonds, even if the coordinator already returned a seed.
    function testCloseDuringPendingVRFBlocksLateSeedApplicationAndRefunds() public {
        uint256 leaseId = _createLease();
        uint256 vrfId = _request(leaseId);
        assertTrue(settlement.isLeaseRandomnessOpen(leaseId, 1));
        _deliver(vrfId, 98765);
        vm.prank(consumer);
        settlement.closeLease(leaseId);
        assertFalse(settlement.isLeaseRandomnessOpen(leaseId, 1));
        vm.expectRevert(SSEVRFV25Adapter.BadState.selector);
        adapter.applyRandomness(1);
        assertEq(settlement.withdrawable(consumer), 25);
        // Closing an unfinalized lease atomically CANCELS pool selection.
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.Expired));
        for (uint256 i; i < 6; ++i) {
            (,,uint32 pending,uint32 locked,,) = pool.candidates(monitors[i]);
            assertEq(locked, 0);
            assertEq(pending, 0);
        }
        vm.warp(block.timestamp + pool.randomnessTimeout() + 1);
        adapter.expire(1);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.expire(1);
        for (uint256 i; i < 6; ++i) {
            (,,uint32 pending,uint32 locked,,) = pool.candidates(monitors[i]);
            assertEq(pending, 0);
            assertEq(locked, 0);
        }
    }

    /// @notice Coordinator failed purchase must not consume the one-request
    /// allowance: EVM reverts all checks/effects atomically.
    function testCoordinatorFailureRollsBackRequestAndAllowsSingleRetry() public {
        uint256 leaseId = _createLease();
        _fund(leaseId);
        coordinator.configureFailures(true, address(0), 0);
        vm.expectRevert(MockVRFV25Coordinator.Unauthorized.selector);
        settlement.requestLeaseRandomness(leaseId);
        assertFalse(adapter.assignmentEverRequested(1));
        assertEq(adapter.leaseForAssignment(1), 0);
        assertEq(coordinator.nextRequestId(), 1);
        coordinator.configureFailures(false, address(0), 0);
        assertEq(_request(leaseId), 1);
        assertTrue(adapter.assignmentEverRequested(1));
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.requestLeaseRandomness(leaseId);
    }

    /// @notice Mock coordinator attempts to reenter subscription-spend path.
    /// A real public coordinator should not do this; guard must reject it.
    function testCoordinatorReentryCannotSpendSecondVRFRequest() public {
        uint256 leaseId = _createLease();
        coordinator.configureFailures(false, address(settlement), leaseId);
        uint256 vrfId = _request(leaseId);
        assertEq(vrfId, 1);
        assertTrue(coordinator.lastReentryAttempted());
        assertFalse(coordinator.lastReentrySucceeded());
        assertTrue(adapter.assignmentEverRequested(1));
        assertEq(coordinator.nextRequestId(), 2);
    }

    function testCloseBeforeVRFRequestReleasesAllPendingSnapshotLocks() public {
        uint256 leaseId = _createOfferedLease();
        for (uint256 i; i < 6; ++i) {
            (,,uint32 pending,,,) = pool.candidates(monitors[i]);
            assertEq(pending, 1);
        }
        vm.prank(consumer);
        settlement.closeLease(leaseId);
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.Expired));
        assertEq(coordinator.nextRequestId(), 1); // no subscription charge
        for (uint256 i; i < 6; ++i) {
            (,,uint32 pending,uint32 active,,) = pool.candidates(monitors[i]);
            assertEq(pending, 0);
            assertEq(active, 0);
        }
    }

    function testCloseAfterSeedAppliedBeforeCommitteeCopyReleasesBondLocks() public {
        uint256 leaseId = _createLease();
        uint256 vrfId = _request(leaseId);
        _deliver(vrfId, 2353);
        adapter.applyRandomness(1);
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.Assigned));
        address[4] memory committee = pool.getCommittee(1);
        for (uint256 i; i < 4; ++i) {
            (,,,uint32 active,,) = pool.candidates(committee[i]);
            assertEq(active, 1);
        }
        vm.prank(consumer);
        settlement.closeLease(leaseId);
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.Released));
        assertEq(settlement.withdrawable(consumer), 25);
        for (uint256 i; i < 4; ++i) {
            (,,,uint32 active,,) = pool.candidates(committee[i]);
            assertEq(active, 0);
        }
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.finalizeMonitorCommittee(leaseId);
    }

    function testOnlySettlementCanCancelPendingOrSelectedAssignment() public {
        _createOfferedLease();
        vm.prank(outsider);
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        pool.cancelUnassigned(1);
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.AwaitingRandomness));
    }

    function testNonexistentOrClosedLeaseCannotStartPaidRequest() public {
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.requestLeaseRandomness(999);
        uint256 leaseId = _createLease();
        vm.prank(consumer);
        settlement.closeLease(leaseId);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.requestLeaseRandomness(leaseId);
        assertEq(coordinator.nextRequestId(), 1);
    }
}

/// @notice Independent end-to-end Merkle proof selection after a coordinator
/// callback, without letting callers choose the sampled candidate indexes.
contract VRFAdapterGlobalMerkleTest is Test {
    MockVRFV25Coordinator internal coordinator;
    SSEVRFV25Adapter internal adapter;
    OpenMonitorCommittee internal pool;
    SSESettlement internal settlement;
    mapping(uint256 => bytes32) private historicalTree;
    address[] private historicalRoster;
    uint256 private constant CAPACITY = 1 << 20;

    function setUp() public {
        vm.warp(100_000);
        coordinator = new MockVRFV25Coordinator();
        adapter = new SSEVRFV25Adapter(address(coordinator), keccak256("key"), 42, 3, 220_000, false);
        pool = new OpenMonitorCommittee(address(adapter), 1 ether, 7 days, 1 days);
        pool.enableGlobalMerkleElection();
        settlement = new SSESettlement(address(pool));
        pool.bindSettlement(address(settlement));
        adapter.bindPoolAndSettlement(address(pool), address(settlement));
        settlement.configureVrfFeePolicy(0.001 ether, 10);
        settlement.bindRandomnessAdapter(address(adapter));
        for (uint256 i; i < 6; ++i) {
            address monitor = address(uint160(0xC100 + i));
            historicalRoster.push(monitor);
            GlobalRosterMerkle.write(historicalTree, i, monitor);
            vm.deal(monitor, 2 ether);
            vm.prank(monitor);
            pool.register{value: 1 ether}();
        }
        vm.deal(address(0xA100), 10 ether);
    }

    function testVerifiedVRFCallbackStagesGlobalSeedThenHistoricalMerkleProofFinalizes() public {
        vm.prank(address(0xA100));
        uint256 leaseId = settlement.createLease{value: 25}(
            address(0xB100), keccak256("endpoint"), keccak256("profile"),
            25, 5, 25, 1, 100, 100, 100
        );
        vm.prank(address(0xB100));
        settlement.acceptLease(leaseId);
        vm.prank(address(0xA100));
        settlement.fundVrfRequestFee{value: 0.001 ether}(leaseId);
        uint256 vrfId = settlement.requestLeaseRandomness(leaseId);
        uint256[] memory word = new uint256[](1);
        word[0] = 777;
        coordinator.deliver(vrfId, word);
        adapter.applyRandomness(1);
        assertTrue(pool.pendingGlobalSeedReady(1));
        assertEq(pool.globalSnapshotRoot(1), historicalTree[1]);
        uint256[] memory indexes = pool.globalDrawIndexes(1);
        address[] memory accounts = new address[](indexes.length);
        bytes32[][] memory proofs = new bytes32[][](indexes.length);
        for (uint256 i; i < indexes.length; ++i) {
            accounts[i] = historicalRoster[indexes[i]];
            proofs[i] = new bytes32[](20);
            uint256 cursor = CAPACITY + indexes[i];
            for (uint256 level; level < 20; ++level) {
                proofs[i][level] = historicalTree[cursor ^ 1];
                cursor >>= 1;
            }
        }
        pool.finalizeGlobalCommittee(1, accounts, proofs);
        assertFalse(pool.pendingGlobalSeedReady(1));
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.Assigned));
        address[4] memory selected = pool.getCommittee(1);
        for (uint256 i; i < 4; ++i) {
            assertEq(selected[i], accounts[i]);
        }
        assertEq(pool.standbyRemaining(1), 2);
    }

    function testCloseAfterSeedStagedBeforeGlobalProofPreventsBondLock() public {
        address consumer = address(0xA100);
        address provider = address(0xB100);
        vm.prank(consumer);
        uint256 leaseId = settlement.createLease{value: 25}(
            provider, keccak256("endpoint"), keccak256("profile"),
            25, 5, 25, 1, 100, 100, 100
        );
        vm.prank(provider);
        settlement.acceptLease(leaseId);
        vm.prank(address(0xA100));
        settlement.fundVrfRequestFee{value: 0.001 ether}(leaseId);
        uint256 vrfId = settlement.requestLeaseRandomness(leaseId);
        uint256[] memory word = new uint256[](1);
        word[0] = 888;
        coordinator.deliver(vrfId, word);
        adapter.applyRandomness(1);
        assertTrue(pool.pendingGlobalSeedReady(1));
        uint256[] memory indexes = pool.globalDrawIndexes(1);
        address[] memory accounts = new address[](indexes.length);
        bytes32[][] memory proofs = new bytes32[][](indexes.length);
        for (uint256 i; i < indexes.length; ++i) {
            accounts[i] = historicalRoster[indexes[i]];
            proofs[i] = new bytes32[](20);
            uint256 cursor = CAPACITY + indexes[i];
            for (uint256 level; level < 20; ++level) {
                proofs[i][level] = historicalTree[cursor ^ 1];
                cursor >>= 1;
            }
        }
        vm.prank(consumer);
        settlement.closeLease(leaseId);
        assertFalse(pool.pendingGlobalSeedReady(1));
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.Expired));
        assertEq(settlement.withdrawable(consumer), 25);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.finalizeGlobalCommittee(1, accounts, proofs);
        for (uint256 i; i < historicalRoster.length; ++i) {
            (,,uint32 pending,uint32 locked,,) = pool.candidates(historicalRoster[i]);
            assertEq(pending, 0);
            assertEq(locked, 0);
        }
    }
}
