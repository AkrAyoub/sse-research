// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {IVRFV25CoordinatorSSE, SSEVRFV25Adapter} from "../../contracts/SSEVRFV25Adapter.sol";
import {ScalableMonitorCommitteeV2} from "../../contracts/ScalableMonitorCommitteeV2.sol";
import {SSELeaseControllerV2} from "../../contracts/SSELeaseControllerV2.sol";

/// @notice Local integration-only stand-in. It DOES NOT verify a Chainlink VRF proof.
/// Anyone may instruct this contract to deliver an arbitrary word; never deploy it
/// with real funds or claim it establishes unbiased randomness.
contract WP12InsecureLocalCoordinator is IVRFV25CoordinatorSSE {
    uint256 public nextId = 500;
    mapping(uint256 => address) public requestedBy;

    function requestRandomWords(RandomWordsRequest calldata request)
        external returns (uint256 id)
    {
        require(request.numWords == 1 && request.subId != 0, "bad config");
        id = ++nextId;
        requestedBy[id] = msg.sender;
    }

    function deliver(uint256 id, uint256 word) external {
        address consumer = requestedBy[id];
        require(consumer != address(0), "unknown request");
        uint256[] memory words = new uint256[](1);
        words[0] = word;
        SSEVRFV25Adapter(consumer).rawFulfillRandomWords(id, words);
    }
}

contract SSEV2IntegratedScenarioTest is Test {
    uint256 internal constant CONSUMER_KEY = 0xA11CE;
    uint256 internal constant PROVIDER_KEY = 0xB0B;
    uint256 internal constant ATTACKER_KEY = 0xBAD;
    bytes32 internal constant SLA = keccak256("SSE HTTP SLA -- experiment only");
    bytes32 internal constant PROFILE = keccak256("HTTP body contract");
    bytes32 internal constant ENDPOINT = keccak256("localhost signed HTTP endpoint");

    WP12InsecureLocalCoordinator internal coordinator;
    SSEVRFV25Adapter internal adapter;
    ScalableMonitorCommitteeV2 internal pool;
    SSELeaseControllerV2 internal escrow;
    address internal consumer;
    address internal provider;

    function setUp() public {
        vm.warp(120_000);
        consumer = vm.addr(CONSUMER_KEY);
        provider = vm.addr(PROVIDER_KEY);
        vm.deal(consumer, 5 ether);

        coordinator = new WP12InsecureLocalCoordinator();
        adapter = new SSEVRFV25Adapter(
            address(coordinator), address(this), keccak256("test vrf lane"),
            777, 3, 300_000, false
        );
        pool = new ScalableMonitorCommitteeV2(
            address(adapter), address(adapter), 1 ether, 0.1 ether, 1 days
        );
        escrow = new SSELeaseControllerV2(address(pool));
        adapter.bindPool(address(pool));
        pool.bindController(address(escrow));
    }

    function committeeTerms() internal view returns (ScalableMonitorCommitteeV2.Terms memory t) {
        t.consumer = consumer;
        t.provider = provider;
        t.size = 4;
        t.quorum = 3;
        t.reserves = 2;
        t.enrollmentPeriod = 15;
        t.randomnessPeriod = 30;
        t.selectionPeriod = 30;
        t.confirmationPeriod = 30;
        t.servicePeriod = 200;
    }

    function leaseTerms() internal view returns (SSELeaseControllerV2.Terms memory t) {
        t.provider = provider;
        t.endpointHash = ENDPOINT;
        t.profileHash = PROFILE;
        t.slaPolicyHash = SLA;
        t.epochFee = 100;
        t.maxEpochs = 3;
        t.exposureBudget = 100;
        t.epochWindow = 20;
        t.acceptanceWindow = 10;
    }

    function monitorAt(uint256 index) internal pure returns (address) {
        return address(uint160(0xD000 + index));
    }

    function offerAndAccept() internal returns (uint256 leaseId, uint256 assignmentId) {
        vm.prank(consumer);
        leaseId = escrow.createLease{value: 300}(leaseTerms(), committeeTerms());
        assignmentId = escrow.getLease(leaseId).assignmentId;
        vm.prank(provider);
        escrow.acceptLease(leaseId);
    }

    function enroll(uint256 assignmentId, uint256 count) internal {
        for (uint256 i; i < count; ++i) {
            address monitor = monitorAt(i);
            vm.deal(monitor, 3 ether);
            vm.startPrank(monitor);
            pool.register{value: 1 ether}();
            pool.join{value: 0.1 ether}(assignmentId);
            vm.stopPrank();
        }
    }

    function selectFromCoordinator(uint256 assignmentId, uint256 arbitraryMockWord)
        internal returns (uint256 requestId)
    {
        vm.warp(pool.enrollmentDeadline(assignmentId) + 1);
        pool.sealEnrollment(assignmentId);
        requestId = adapter.requestRandomness(assignmentId);
        coordinator.deliver(requestId, arbitraryMockWord);
        adapter.finalizeRandomness(assignmentId);
        while (pool.selectionCursor(assignmentId) < pool.enrolledCount(assignmentId)) {
            pool.processSelection(assignmentId, 16);
        }
        pool.finalizeSelection(assignmentId);
    }

    function confirmAll(uint256 assignmentId) internal {
        for (uint256 i; i < pool.selectedCount(assignmentId); ++i) {
            vm.prank(pool.seatAt(assignmentId, i));
            pool.confirm(assignmentId);
        }
    }

    function ready(uint256 entrants)
        internal returns (uint256 leaseId, uint256 assignmentId, uint256 vrfRequest)
    {
        (leaseId, assignmentId) = offerAndAccept();
        enroll(assignmentId, entrants);
        vrfRequest = selectFromCoordinator(assignmentId, 0x123456);
        confirmAll(assignmentId);
        escrow.activateLease(leaseId);
    }

    function admit(uint256 leaseId, bytes32 requestHash) internal returns (uint256 epochId) {
        vm.prank(consumer);
        epochId = escrow.admitEpoch(leaseId, requestHash);
    }

    function allocation(uint256 leaseId, uint256 epochId, uint256 providerShare)
        internal view returns (SSELeaseControllerV2.Allocation memory a)
    {
        SSELeaseControllerV2.Epoch memory ep = escrow.getEpoch(leaseId, epochId);
        a.leaseId = leaseId;
        a.epochId = epochId;
        a.requestHash = ep.requestHash;
        a.providerShare = providerShare;
        a.consumerShare = ep.fee - providerShare;
        a.nonce = ep.nonce;
        a.expiry = block.timestamp + 30 days;
    }

    function digest(SSELeaseControllerV2.Allocation memory a)
        internal view returns (bytes32)
    {
        bytes32 payloadHash = keccak256(abi.encode(
            escrow.ALLOCATION_TYPEHASH(), a.leaseId, a.epochId, a.requestHash,
            a.providerShare, a.consumerShare, a.nonce, a.expiry
        ));
        return keccak256(abi.encodePacked("\x19\x01", escrow.domainSeparator(), payloadHash));
    }

    function sign(uint256 key, bytes32 hash) internal returns (bytes memory sig) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(key, hash);
        return abi.encodePacked(r, s, v);
    }

    function allocateAgreed(SSELeaseControllerV2.Allocation memory a) internal {
        bytes32 h = digest(a);
        bytes memory consumerSig = sign(CONSUMER_KEY, h);
        bytes memory providerSig = sign(PROVIDER_KEY, h);
        escrow.allocateEpoch(a, consumerSig, providerSig);
    }

    function assertConservation(uint256 leaseId) internal view {
        SSELeaseControllerV2.Lease memory l = escrow.getLease(leaseId);
        assertEq(l.uncommitted + l.pending + l.providerCredited +
                 l.consumerCredited + l.unusedRefunded, l.escrow);
    }

    function testCompleteVRFCommitteeFundingTwoEpochsAndWithdrawals() public {
        (uint256 leaseId, uint256 assignmentId, uint256 vrfId) = ready(8);
        assertEq(vrfId, adapter.requestForAssignment(assignmentId));
        assertEq(uint8(pool.status(assignmentId)), uint8(ScalableMonitorCommitteeV2.Status.Active));
        assertEq(uint8(escrow.getLease(leaseId).state), uint8(SSELeaseControllerV2.State.Live));
        assertEq(pool.selectedCount(assignmentId), 4);
        assertEq(pool.confirmedCount(assignmentId), 4);
        assertEq(escrow.withdrawable(provider), 0);

        uint256 epoch0 = admit(leaseId, keccak256("consumer challenge 0"));
        assertEq(epoch0, 0);
        assertEq(escrow.getLease(leaseId).pending, 100);
        assertEq(escrow.withdrawable(provider), 0);
        allocateAgreed(allocation(leaseId, epoch0, 70));
        assertEq(escrow.withdrawable(provider), 70);
        assertConservation(leaseId);

        uint256 epoch1 = admit(leaseId, keccak256("consumer challenge 1"));
        assertEq(epoch1, 1);
        assertEq(escrow.getLease(leaseId).pending, 100);
        assertConservation(leaseId);

        // An unresolved admitted fee remains protected even if monitoring ends.
        vm.warp(pool.serviceDeadline(assignmentId));
        vm.prank(address(0xABCD));
        pool.expire(assignmentId);
        vm.prank(address(0xABCD));
        escrow.endAdmissions(leaseId);
        assertEq(escrow.getLease(leaseId).pending, 100);
        assertEq(escrow.getLease(leaseId).unusedRefunded, 100);
        assertEq(escrow.withdrawable(provider), 70);
        assertEq(escrow.withdrawable(consumer), 130);
        assertConservation(leaseId);

        // Both parties later consent to the other epoch. This is NOT an SLA verdict.
        allocateAgreed(allocation(leaseId, epoch1, 20));
        escrow.finishLease(leaseId);
        assertEq(escrow.withdrawable(provider), 90);
        assertEq(escrow.withdrawable(consumer), 210);
        assertEq(uint8(escrow.getLease(leaseId).state), uint8(SSELeaseControllerV2.State.Closed));
        assertConservation(leaseId);

        uint256 providerBefore = provider.balance;
        vm.prank(provider);
        escrow.withdraw();
        assertEq(provider.balance, providerBefore + 90);
        uint256 consumerBefore = consumer.balance;
        vm.prank(consumer);
        escrow.withdraw();
        assertEq(consumer.balance, consumerBefore + 210);
        assertEq(address(escrow).balance, 0);

        // Settlement does not burn honest monitor ticket bonds.
        for (uint256 i; i < 8; ++i) pool.settleTicket(assignmentId, monitorAt(i));
        for (uint256 i; i < 8; ++i) assertEq(pool.withdrawable(monitorAt(i)), 0.1 ether);
    }

    function testMonitoringAndVRFAloneNeverAuthorizePayout() public {
        (uint256 leaseId, uint256 assignmentId,) = ready(6);
        assertEq(pool.confirmedCount(assignmentId), 4);
        admit(leaseId, keccak256("response observed on monitor, not consumer"));
        assertEq(escrow.withdrawable(provider), 0);
        assertEq(escrow.withdrawable(consumer), 0);
        SSELeaseControllerV2.Allocation memory a = allocation(leaseId, 0, 100);
        bytes32 h = digest(a);
        bytes memory fakeConsumerSig = sign(ATTACKER_KEY, h);
        bytes memory realProviderSig = sign(PROVIDER_KEY, h);
        vm.expectRevert(SSELeaseControllerV2.InvalidSignatures.selector);
        escrow.allocateEpoch(a, fakeConsumerSig, realProviderSig);
        assertEq(escrow.getLease(leaseId).pending, 100);
        assertEq(escrow.withdrawable(provider), 0);

        vm.warp(pool.serviceDeadline(assignmentId));
        pool.expire(assignmentId);
        escrow.endAdmissions(leaseId);
        assertEq(escrow.getLease(leaseId).pending, 100);
        assertEq(escrow.withdrawable(provider), 0);
        vm.expectRevert(SSELeaseControllerV2.InvalidState.selector);
        escrow.finishLease(leaseId);
        assertConservation(leaseId);
    }

    function testMissingCoordinatorResponseCausesRefundNotFalseActivation() public {
        (uint256 leaseId, uint256 assignmentId) = offerAndAccept();
        enroll(assignmentId, 5);
        vm.warp(pool.enrollmentDeadline(assignmentId) + 1);
        pool.sealEnrollment(assignmentId);
        uint256 req = adapter.requestRandomness(assignmentId);
        assertEq(req, 501);
        vm.warp(pool.seedDeadline(assignmentId) + 1);
        pool.expire(assignmentId);
        assertEq(uint8(pool.status(assignmentId)), uint8(ScalableMonitorCommitteeV2.Status.Aborted));
        vm.expectRevert(SSELeaseControllerV2.InvalidState.selector);
        escrow.activateLease(leaseId);
        vm.prank(address(0xFEED));
        escrow.cancelFailedSetup(leaseId);
        assertEq(escrow.withdrawable(consumer), 300);
        assertEq(escrow.withdrawable(provider), 0);
        for (uint256 i; i < 5; ++i) pool.settleTicket(assignmentId, monitorAt(i));
        assertEq(address(escrow).balance, 300);
        assertConservation(leaseId);
    }

    function testLateCallbackCannotReviveAbortedFundedLease() public {
        (uint256 leaseId, uint256 assignmentId) = offerAndAccept();
        enroll(assignmentId, 5);
        vm.warp(pool.enrollmentDeadline(assignmentId) + 1);
        pool.sealEnrollment(assignmentId);
        uint256 req = adapter.requestRandomness(assignmentId);
        vm.warp(pool.seedDeadline(assignmentId) + 1);
        coordinator.deliver(req, 123);
        vm.expectRevert(SSEVRFV25Adapter.InvalidState.selector);
        adapter.finalizeRandomness(assignmentId);
        pool.expire(assignmentId);
        escrow.cancelFailedSetup(leaseId);
        assertEq(escrow.withdrawable(consumer), 300);
        assertEq(escrow.withdrawable(provider), 0);
    }

    function testFakeVRFCallbackCannotActivateFundedLease() public {
        (uint256 leaseId, uint256 assignmentId) = offerAndAccept();
        enroll(assignmentId, 6);
        vm.warp(pool.enrollmentDeadline(assignmentId) + 1);
        pool.sealEnrollment(assignmentId);
        uint256 req = adapter.requestRandomness(assignmentId);
        uint256[] memory invented = new uint256[](1);
        invented[0] = 777;
        vm.expectRevert(SSEVRFV25Adapter.Unauthorized.selector);
        adapter.rawFulfillRandomWords(req, invented);
        vm.expectRevert(SSEVRFV25Adapter.InvalidState.selector);
        adapter.finalizeRandomness(assignmentId);
        vm.expectRevert(SSELeaseControllerV2.InvalidState.selector);
        escrow.activateLease(leaseId);
        assertEq(escrow.withdrawable(provider), 0);
    }

    function testNoShowReserveCanCompleteFundedLeaseAfterReplacement() public {
        (uint256 leaseId, uint256 assignmentId) = offerAndAccept();
        enroll(assignmentId, 7);
        selectFromCoordinator(assignmentId, 321);
        for (uint256 i; i < 3; ++i) {
            vm.prank(pool.seatAt(assignmentId, i));
            pool.confirm(assignmentId);
        }
        address absent = pool.seatAt(assignmentId, 3);
        address reserve = pool.rankedAt(assignmentId, 4);
        vm.expectRevert(SSELeaseControllerV2.InvalidState.selector);
        escrow.activateLease(leaseId);
        vm.warp(pool.confirmationDeadline(assignmentId) + 1);
        pool.replaceNoShows(assignmentId);
        assertEq(pool.seatAt(assignmentId, 3), reserve);
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidPhase.selector);
        vm.prank(absent);
        pool.confirm(assignmentId);
        vm.prank(reserve);
        pool.confirm(assignmentId);
        escrow.activateLease(leaseId);
        assertEq(uint8(escrow.getLease(leaseId).state), uint8(SSELeaseControllerV2.State.Live));
        pool.settleTicket(assignmentId, absent);
        assertEq(pool.withdrawable(consumer), 0.1 ether);
        assertEq(escrow.withdrawable(provider), 0);
    }

    function testRawMonitorStateCannotBypassExposureCap() public {
        (uint256 leaseId,,) = ready(6);
        admit(leaseId, keccak256("epoch A unresolved"));
        vm.expectRevert(SSELeaseControllerV2.ExposureExceeded.selector);
        vm.prank(consumer);
        escrow.admitEpoch(leaseId, keccak256("epoch B blocked"));
        assertEq(escrow.getLease(leaseId).pending, 100);
        assertEq(escrow.withdrawable(provider), 0);
        assertConservation(leaseId);
    }
}
