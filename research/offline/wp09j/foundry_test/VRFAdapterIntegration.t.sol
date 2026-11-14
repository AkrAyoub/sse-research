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
        settlement.bindRandomnessAdapter(address(adapter));
        vm.deal(consumer, 10 ether);
        vm.deal(provider, 10 ether);
        for (uint256 i; i < 6; ++i) {
            address account = address(uint160(0xC100 + i));
            monitors[i] = account;
            vm.deal(account, 2 ether);
            vm.prank(account);
            pool.register{value: 1 ether}();
        }
    }

    function _createLease() internal returns (uint256 leaseId) {
        vm.prank(consumer);
        leaseId = settlement.createLease{value: 25}(
            provider, keccak256("endpoint"), keccak256("profile"),
            25, 5, 25, 1, 100, 100, 100
        );
    }

    function _request(uint256 leaseId) internal returns (uint256 vrfId) {
        vm.prank(outsider);
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
        vm.expectRevert(SSEVRFV25Adapter.BadState.selector);
        settlement.requestLeaseRandomness(leaseId);

        _deliver(vrfId, 1234567);
        (,,, SSEVRFV25Adapter.State ready,) = adapter.byVrfId(vrfId);
        assertEq(uint8(ready), uint8(SSEVRFV25Adapter.State.Ready));
        vm.prank(outsider);
        adapter.apply(1);
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.Assigned));
        (,,, SSEVRFV25Adapter.State applied,) = adapter.byVrfId(vrfId);
        assertEq(uint8(applied), uint8(SSEVRFV25Adapter.State.Applied));
        vm.expectRevert(SSEVRFV25Adapter.BadState.selector);
        adapter.apply(1);

        vm.prank(provider);
        settlement.acceptLease(leaseId);
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
        adapter.apply(1);
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
        adapter.apply(1);
        adapter.expire(1);
        pool.expire(1);
        (,,, SSEVRFV25Adapter.State expired,) = adapter.byVrfId(vrfId);
        assertEq(uint8(expired), uint8(SSEVRFV25Adapter.State.Expired));
        vm.expectRevert(SSEVRFV25Adapter.BadState.selector);
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
        adapter.apply(1);
        adapter.expire(1);
        pool.expire(1);
        vm.expectRevert(SSEVRFV25Adapter.BadState.selector);
        adapter.apply(1);
    }

    function testOnlySettlementMayRequestAndBindingCannotBeReconfigured() public {
        uint256 leaseId = _createLease();
        vm.prank(outsider);
        vm.expectRevert(SSEVRFV25Adapter.Unauthorized.selector);
        adapter.requestSeed(1);
        vm.expectRevert(SSESettlement.Unauthorized.selector);
        settlement.bindRandomnessAdapter(address(adapter));
        vm.expectRevert(SSEVRFV25Adapter.Unauthorized.selector);
        adapter.bindPoolAndSettlement(address(pool), address(settlement));
        assertEq(address(adapter.pool()), address(pool));
        assertEq(adapter.settlement(), address(settlement));
        assertTrue(leaseId != 0);
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
        uint256 vrfId = settlement.requestLeaseRandomness(leaseId);
        uint256[] memory word = new uint256[](1);
        word[0] = 777;
        coordinator.deliver(vrfId, word);
        adapter.apply(1);
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
}
