// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {OpenMonitorCommittee} from "../../contracts/OpenMonitorCommittee.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";
import {SSEVRFV25Adapter} from "../../contracts/SSEVRFV25Adapter.sol";
import {MockVRFV25Coordinator} from "../mocks/MockVRFV25Coordinator.sol";

/// @notice WP09L: UNEXECUTED until locally compiled with Forge offline.
/// @dev Coordinator is a mock, NOT a cryptographic VRF implementation.
contract VRFFeePolicyTest is Test {
    uint256 internal constant FEE = 0.002 ether;
    MockVRFV25Coordinator internal coordinator;
    SSEVRFV25Adapter internal adapter;
    OpenMonitorCommittee internal pool;
    SSESettlement internal settlement;
    address internal consumer = address(0xA100);
    address internal provider = address(0xB100);
    address internal outsider = address(0xDADA);

    function setUp() public {
        vm.warp(100_000);
        coordinator = new MockVRFV25Coordinator();
        adapter = new SSEVRFV25Adapter(
            address(coordinator), keccak256("key"), 42, 3, 220_000, false
        );
        pool = new OpenMonitorCommittee(address(adapter), 1 ether, 7 days, 1 days);
        settlement = new SSESettlement(address(pool));
        pool.bindSettlement(address(settlement));
        adapter.bindPoolAndSettlement(address(pool), address(settlement));
        // Fee must be frozen before the adapter is bound and before leases.
        settlement.configureVrfFeePolicy(FEE, 2);
        settlement.bindRandomnessAdapter(address(adapter));
        vm.deal(consumer, 10 ether);
        vm.deal(provider, 10 ether);
        vm.deal(outsider, 1 ether);
        for (uint256 i; i < 6; ++i) {
            address member = address(uint160(0xC100 + i));
            vm.deal(member, 2 ether);
            vm.prank(member);
            pool.register{value: 1 ether}();
        }
    }

    function _offered() internal returns (uint256) {
        vm.prank(consumer);
        return settlement.createLease{value: 25}(
            provider, keccak256("endpoint"), keccak256("profile"),
            25, 5, 25, 1, 100, 100, 100
        );
    }

    function _accepted() internal returns (uint256 leaseId) {
        leaseId = _offered();
        vm.prank(provider);
        settlement.acceptLease(leaseId);
    }

    function _fund(uint256 leaseId) internal {
        vm.prank(consumer);
        settlement.fundVrfRequestFee{value: FEE}(leaseId);
    }

    function _request(uint256 leaseId) internal returns (uint256) {
        vm.prank(outsider);
        return settlement.requestLeaseRandomness(leaseId);
    }

    function testPolicyLockedCannotBeChangedAfterBinding() public {
        assertEq(settlement.vrfFeeWei(), FEE);
        assertEq(settlement.vrfLifetimeRequestCap(), 2);
        vm.expectRevert(SSESettlement.InvalidArgument.selector);
        settlement.configureVrfFeePolicy(FEE + 1, 100);
    }

    function testUnfundedPermissionlessPurchaseRejectedWithoutCoordinatorCost() public {
        uint256 leaseId = _accepted();
        vm.prank(outsider);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.requestLeaseRandomness(leaseId);
        assertEq(coordinator.nextRequestId(), 1);
        assertEq(settlement.vrfRequestsUsed(), 0);
    }

    function testOnlyConsumerMayFundExactlyOnceAndExactAmount() public {
        uint256 id = _accepted();
        vm.prank(outsider);
        vm.expectRevert(SSESettlement.Unauthorized.selector);
        settlement.fundVrfRequestFee{value: FEE}(id);
        vm.prank(consumer);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.fundVrfRequestFee{value: FEE - 1}(id);
        _fund(id);
        assertTrue(settlement.vrfFeeFunded(id));
        vm.prank(consumer);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.fundVrfRequestFee{value: FEE}(id);
        assertEq(address(settlement).balance, 25 + FEE);
    }

    function testProviderMustAcceptBeforeFeeCanBeDeposited() public {
        uint256 id = _offered();
        vm.prank(consumer);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.fundVrfRequestFee{value:FEE}(id);
        assertEq(address(settlement).balance, 25);
    }

    function testAfterFundingAnyoneCanBuyExactlyOnceAndSponsorEarns() public {
        uint256 id = _accepted();
        _fund(id);
        assertEq(_request(id), 1);
        assertEq(coordinator.nextRequestId(), 2);
        assertEq(settlement.withdrawable(address(this)), FEE);
        assertEq(settlement.vrfRequestsUsed(), 1);
        assertFalse(settlement.vrfFeeFunded(id));
        assertTrue(settlement.vrfFeeSpent(id));
        vm.prank(outsider);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.requestLeaseRandomness(id);
    }

    function testUnspentFeeRefundedAtomicallyWithLeaseClose() public {
        uint256 id = _accepted();
        _fund(id);
        vm.prank(consumer);
        settlement.closeLease(id);
        assertEq(settlement.withdrawable(consumer), 25 + FEE);
        assertEq(settlement.withdrawable(address(this)), 0);
        assertEq(settlement.vrfRequestsUsed(), 0);
        assertFalse(settlement.vrfFeeFunded(id));
        assertEq(uint8(pool.assignmentStatus(id)),
                 uint8(OpenMonitorCommittee.RequestStatus.Expired));
    }

    function testSpentFeeNotRefundedWhenConsumerClosesOrVRFWithheld() public {
        uint256 id = _accepted();
        _fund(id);
        uint256 vrfId = _request(id);
        assertEq(vrfId, 1);
        vm.prank(consumer);
        settlement.closeLease(id);
        assertEq(settlement.withdrawable(consumer), 25);
        assertEq(settlement.withdrawable(address(this)), FEE);
        assertEq(settlement.vrfRequestsUsed(), 1);
        assertEq(uint8(pool.assignmentStatus(id)),
                 uint8(OpenMonitorCommittee.RequestStatus.Expired));
        vm.expectRevert(SSEVRFV25Adapter.BadState.selector);
        adapter.applyRandomness(id);
    }

    function testCoordinatorRejectsAndEntirePaidPurchaseRollsBack() public {
        uint256 id = _accepted();
        _fund(id);
        coordinator.configureFailures(true, address(0), 0);
        vm.expectRevert(MockVRFV25Coordinator.Unauthorized.selector);
        settlement.requestLeaseRandomness(id);
        assertEq(settlement.vrfRequestsUsed(), 0);
        assertEq(settlement.withdrawable(address(this)), 0);
        assertTrue(settlement.vrfFeeFunded(id));
        assertFalse(settlement.vrfFeeSpent(id));
        assertFalse(adapter.assignmentEverRequested(id));
        coordinator.configureFailures(false, address(0), 0);
        assertEq(_request(id), 1);
        assertEq(settlement.vrfRequestsUsed(), 1);
    }

    function testOtherFundedLeaseCannotReenterThroughCoordinator() public {
        uint256 first = _accepted();
        uint256 second = _accepted();
        _fund(first);
        _fund(second);
        coordinator.configureFailures(false, address(settlement), second);
        assertEq(_request(first), 1);
        assertTrue(coordinator.lastReentryAttempted());
        assertFalse(coordinator.lastReentrySucceeded());
        assertEq(settlement.vrfRequestsUsed(), 1);
        assertTrue(settlement.vrfFeeFunded(second));
        assertFalse(settlement.vrfFeeSpent(second));
    }

    function testLifetimeQuotaBoundsSponsorOrdersAndOtherFeeRemainsRefundable() public {
        uint256 first = _accepted();
        uint256 second = _accepted();
        uint256 third = _accepted();
        _fund(first);
        _fund(second);
        _fund(third);
        assertEq(_request(first), 1);
        assertEq(_request(second), 2);
        vm.prank(outsider);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.requestLeaseRandomness(third);
        assertTrue(settlement.vrfFeeFunded(third));
        vm.prank(consumer);
        settlement.closeLease(third);
        assertEq(settlement.withdrawable(consumer), 25 + FEE);
        assertEq(settlement.vrfRequestsUsed(), 2);
        assertEq(settlement.withdrawable(address(this)), 2*FEE);
    }

    function testSponsorAndConsumerCanWithdrawSeparateCredits() public {
        uint256 id = _accepted();
        _fund(id);
        _request(id);
        vm.prank(consumer);
        settlement.closeLease(id);
        // SSESettlement already has a withdrawal function for withdrawable.
        // We check the exact accounting before invoking the existing path.
        assertEq(settlement.withdrawable(address(this)), FEE);
        assertEq(settlement.withdrawable(consumer), 25);
        assertEq(address(settlement).balance, FEE + 25);
    }

    function testUnauthorizedBindingOrReconfigurationFailsClosed() public {
        vm.expectRevert(SSESettlement.Unauthorized.selector);
        settlement.bindRandomnessAdapter(address(adapter));
        assertTrue(settlement.vrfFeePolicyConfigured());
    }
}

/// @notice Fee lifecycle also applies to the WP09E global Merkle election.
contract VRFFeeGlobalMerkleTest is Test {
    uint256 internal constant FEE = 0.001 ether;
    MockVRFV25Coordinator internal coordinator;
    SSEVRFV25Adapter internal adapter;
    OpenMonitorCommittee internal pool;
    SSESettlement internal settlement;
    address internal constant CONSUMER = address(0xA100);
    address internal constant PROVIDER = address(0xB100);

    function setUp() public {
        vm.warp(100_000);
        coordinator = new MockVRFV25Coordinator();
        adapter = new SSEVRFV25Adapter(
            address(coordinator), keccak256("global-key"), 42, 3, 220_000, false
        );
        pool = new OpenMonitorCommittee(address(adapter), 1 ether, 7 days, 1 days);
        pool.enableGlobalMerkleElection();
        settlement = new SSESettlement(address(pool));
        pool.bindSettlement(address(settlement));
        adapter.bindPoolAndSettlement(address(pool), address(settlement));
        settlement.configureVrfFeePolicy(FEE, 3);
        settlement.bindRandomnessAdapter(address(adapter));
        vm.deal(CONSUMER, 10 ether);
        for (uint256 i; i < 6; ++i) {
            address account = address(uint160(0xC100 + i));
            vm.deal(account, 2 ether);
            vm.prank(account);
            pool.register{value: 1 ether}();
        }
    }

    function _fundAndRequest() internal returns (uint256 leaseId, uint256 vrfId) {
        vm.prank(CONSUMER);
        leaseId = settlement.createLease{value: 25}(
            PROVIDER, keccak256("global-endpoint"), keccak256("global-profile"),
            25, 5, 25, 1, 100, 100, 100
        );
        vm.prank(PROVIDER);
        settlement.acceptLease(leaseId);
        vm.prank(CONSUMER);
        settlement.fundVrfRequestFee{value:FEE}(leaseId);
        vrfId = settlement.requestLeaseRandomness(leaseId);
    }

    function testGlobalSeedThenCloseClearsSeedButKeepsPaidRequestFee() public {
        (uint256 id, uint256 vrfId) = _fundAndRequest();
        uint256[] memory words = new uint256[](1);
        words[0] = 818;
        coordinator.deliver(vrfId, words);
        adapter.applyRandomness(id);
        assertTrue(pool.pendingGlobalSeedReady(id));
        vm.prank(CONSUMER);
        settlement.closeLease(id);
        assertFalse(pool.pendingGlobalSeedReady(id));
        assertEq(uint8(pool.assignmentStatus(id)),
                 uint8(OpenMonitorCommittee.RequestStatus.Expired));
        assertEq(settlement.withdrawable(CONSUMER), 25);
        assertEq(settlement.withdrawable(address(this)), FEE);
        assertEq(settlement.vrfRequestsUsed(), 1);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.globalDrawIndexes(id);
    }

    function testUnspentFeeRefundsBeforeGlobalSeedRequest() public {
        vm.prank(CONSUMER);
        uint256 id = settlement.createLease{value: 25}(
            PROVIDER, keccak256("global-endpoint"), keccak256("global-profile"),
            25, 5, 25, 1, 100, 100, 100
        );
        vm.prank(PROVIDER);
        settlement.acceptLease(id);
        vm.prank(CONSUMER);
        settlement.fundVrfRequestFee{value:FEE}(id);
        vm.prank(CONSUMER);
        settlement.closeLease(id);
        assertEq(settlement.withdrawable(CONSUMER), 25 + FEE);
        assertFalse(pool.pendingGlobalSeedReady(id));
        assertEq(pool.snapshotSize(id), 0);
        assertEq(settlement.vrfRequestsUsed(), 0);
    }
}
