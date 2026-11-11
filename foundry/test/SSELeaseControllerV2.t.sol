// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {ScalableMonitorCommitteeV2, IVerifiedMonitorRandomnessV2}
    from "../../contracts/ScalableMonitorCommitteeV2.sol";
import {SSELeaseControllerV2} from "../../contracts/SSELeaseControllerV2.sol";

/// @dev Mock seed verifier only. NOT a secure VRF.
contract WP10MockSeed is IVerifiedMonitorRandomnessV2 {
    function verify(bytes32 commitment, bytes32 seed, bytes calldata proof) external pure returns (bool) {
        return keccak256(proof) == keccak256(abi.encode(keccak256(abi.encode(commitment, seed))));
    }
}

contract SSELeaseControllerV2Test is Test {
    ScalableMonitorCommitteeV2 pool;
    SSELeaseControllerV2 controller;
    WP10MockSeed verifier;
    uint256 constant CONSUMER_KEY = 0xA11CE;
    uint256 constant PROVIDER_KEY = 0xB0B;
    uint256 constant WRONG_KEY = 0xBAD;
    bytes32 constant SEED = keccak256("WP10_SEED");
    bytes32 constant SLA = keccak256("http-delivery-sla-1");
    bytes32 constant PROFILE = keccak256("http-response-profile");
    bytes32 constant ENDPOINT = keccak256("loopback-endpoint");
    address consumer;
    address provider;

    function setUp() public {
        vm.warp(100_000);
        consumer = vm.addr(CONSUMER_KEY);
        provider = vm.addr(PROVIDER_KEY);
        vm.deal(consumer, 100 ether);
        verifier = new WP10MockSeed();
        pool = new ScalableMonitorCommitteeV2(address(this), address(verifier),
                                              1 ether, 0.1 ether, 1 days);
        controller = new SSELeaseControllerV2(address(pool));
        pool.bindController(address(controller));
    }

    function cterms() internal view returns (ScalableMonitorCommitteeV2.Terms memory t) {
        t.consumer = consumer;
        t.provider = provider;
        t.size = 4;
        t.quorum = 3;
        t.reserves = 2;
        t.enrollmentPeriod = 10;
        t.randomnessPeriod = 10;
        t.selectionPeriod = 10;
        t.confirmationPeriod = 10;
        t.servicePeriod = 100;
    }
    function terms() internal view returns (SSELeaseControllerV2.Terms memory t) {
        t.provider = provider;
        t.endpointHash = ENDPOINT;
        t.profileHash = PROFILE;
        t.slaPolicyHash = SLA;
        t.epochFee = 100;
        t.maxEpochs = 3;
        t.exposureBudget = 100;
        t.epochWindow = 5;
        t.acceptanceWindow = 8;
    }
    function makeOffer() internal returns (uint256 id) {
        vm.prank(consumer);
        id = controller.createLease{value: 300}(terms(), cterms());
    }
    function registerAndJoin(uint256 assignmentId, uint256 count) internal {
        for (uint256 i; i < count; ++i) {
            address mon = address(uint160(0x300 + i));
            vm.deal(mon, 2 ether);
            vm.startPrank(mon);
            pool.register{value:1 ether}();
            pool.join{value:0.1 ether}(assignmentId);
            vm.stopPrank();
        }
    }
    function makeLive() internal returns (uint256 leaseId, uint256 assignment) {
        leaseId=makeOffer();
        SSELeaseControllerV2.Lease memory lease=controller.getLease(leaseId);
        assignment=lease.assignmentId;
        vm.prank(provider);
        controller.acceptLease(leaseId);
        registerAndJoin(assignment, 6);
        vm.warp(pool.enrollmentDeadline(assignment)+1);
        pool.sealEnrollment(assignment);
        pool.supplyRandomness(assignment, SEED,
            abi.encode(keccak256(abi.encode(pool.assignmentCommitment(assignment), SEED))));
        pool.processSelection(assignment, 16);
        pool.finalizeSelection(assignment);
        for(uint256 i;i<4;++i) {
            vm.prank(pool.seatAt(assignment,i));
            pool.confirm(assignment);
        }
        controller.activateLease(leaseId);
    }
    function admit(uint256 leaseId, bytes32 req) internal returns (uint256) {
        vm.prank(consumer);
        return controller.admitEpoch(leaseId, req);
    }
    function allocation(uint256 leaseId, uint256 epochId, uint256 providerPart, uint256 consumerPart)
        internal view returns (SSELeaseControllerV2.Allocation memory a) {
        SSELeaseControllerV2.Epoch memory ep=controller.getEpoch(leaseId,epochId);
        a.leaseId=leaseId;
        a.epochId=epochId;
        a.requestHash=ep.requestHash;
        a.providerShare=providerPart;
        a.consumerShare=consumerPart;
        a.nonce=ep.nonce;
        a.expiry=block.timestamp+365 days;
    }
    function digestFor(SSELeaseControllerV2 target, SSELeaseControllerV2.Allocation memory a)
        internal view returns(bytes32) {
        return keccak256(abi.encodePacked("\x19\x01", target.domainSeparator(),
            keccak256(abi.encode(
                target.ALLOCATION_TYPEHASH(),a.leaseId,a.epochId,a.requestHash,
                a.providerShare,a.consumerShare,a.nonce,a.expiry
            ))));
    }
    function sign(uint256 key, bytes32 digest) internal pure returns (bytes memory) {
        // Foundry's vm.sign is non-pure in the interface: actual helper below.
        key; digest; return "";
    }
    function signature(uint256 key, bytes32 digest) internal returns(bytes memory) {
        (uint8 v, bytes32 r, bytes32 s)=vm.sign(key, digest);
        return abi.encodePacked(r,s,v);
    }
    function signatures(SSELeaseControllerV2.Allocation memory a)
        internal returns(bytes memory consumerSig, bytes memory providerSig) {
        bytes32 hash=digestFor(controller,a);
        consumerSig=signature(CONSUMER_KEY,hash);
        providerSig=signature(PROVIDER_KEY,hash);
    }
    function allocate(SSELeaseControllerV2.Allocation memory a) internal {
        (bytes memory c,bytes memory p)=signatures(a);
        controller.allocateEpoch(a,c,p);
    }

    function testFundedLeaseBindsExactAssignmentAndEscrow() public {
        uint256 id=makeOffer();
        SSELeaseControllerV2.Lease memory l=controller.getLease(id);
        assertEq(l.consumer,consumer);
        assertEq(l.provider,provider);
        assertEq(l.escrow,300);
        assertEq(l.uncommitted,300);
        assertEq(l.slaPolicyHash,SLA);
        assertEq(l.profileHash,PROFILE);
        assertEq(uint8(pool.status(l.assignmentId)),uint8(ScalableMonitorCommitteeV2.Status.Enrollment));
        assertEq(address(controller).balance,300);
    }
    function testRejectMismatchedConsumerProviderOrPolicy() public {
        ScalableMonitorCommitteeV2.Terms memory ct=cterms();
        ct.consumer=vm.addr(WRONG_KEY);
        vm.expectRevert(SSELeaseControllerV2.InvalidArgument.selector);
        vm.prank(consumer);
        controller.createLease{value:300}(terms(),ct);
        SSELeaseControllerV2.Terms memory t=terms();
        t.slaPolicyHash=bytes32(0);
        vm.expectRevert(SSELeaseControllerV2.InvalidArgument.selector);
        vm.prank(consumer);
        controller.createLease{value:300}(t,cterms());
        vm.expectRevert(SSELeaseControllerV2.InsufficientFunding.selector);
        vm.prank(consumer);
        controller.createLease{value:299}(terms(),cterms());
    }
    function testProviderOnlyAcceptsDuringEnrollment() public {
        uint256 id=makeOffer();
        vm.expectRevert(SSELeaseControllerV2.Unauthorized.selector);
        vm.prank(consumer);
        controller.acceptLease(id);
        vm.prank(provider);
        controller.acceptLease(id);
        vm.expectRevert(SSELeaseControllerV2.InvalidState.selector);
        vm.prank(provider);
        controller.acceptLease(id);
    }
    function testUnauthorizedEarlyActivationCannotBypassCommittee() public {
        uint256 id=makeOffer();
        vm.prank(provider);
        controller.acceptLease(id);
        vm.expectRevert(SSELeaseControllerV2.InvalidState.selector);
        vm.prank(consumer);
        controller.activateLease(id);
    }
    function testActiveCommitteeEnablesBoundedEpoch() public {
        (uint256 id,)=makeLive();
        uint256 e=admit(id,keccak256("challenge1"));
        assertEq(e,0);
        SSELeaseControllerV2.Epoch memory ep=controller.getEpoch(id,e);
        assertEq(ep.fee,100);
        assertEq(ep.requestHash,keccak256("challenge1"));
        assertEq(ep.allocated,false);
        SSELeaseControllerV2.Lease memory l=controller.getLease(id);
        assertEq(l.pending,100);
        assertEq(l.uncommitted,200);
        assertEq(controller.withdrawable(provider),0);
    }
    function testOnlyConsumerCanAdmitAndCannotDuplicateRequest() public {
        (uint256 id,)=makeLive();
        bytes32 request=keccak256("single");
        vm.expectRevert(SSELeaseControllerV2.Unauthorized.selector);
        vm.prank(provider);
        controller.admitEpoch(id,request);
        admit(id,request);
        vm.expectRevert(SSELeaseControllerV2.InvalidState.selector);
        vm.prank(consumer);
        controller.admitEpoch(id,request);
    }
    function testExposureBudgetBlocksSecondPendingEpoch() public {
        (uint256 id,)=makeLive();
        admit(id,keccak256("one"));
        vm.expectRevert(SSELeaseControllerV2.ExposureExceeded.selector);
        vm.prank(consumer);
        controller.admitEpoch(id,keccak256("two"));
        allocate(allocation(id,0,70,30));
        assertEq(admit(id,keccak256("two")),1);
        assertEq(controller.getLease(id).pending,100);
    }
    function testBilateralSignaturesPayExactSplitAndConserveEscrow() public {
        (uint256 id,)=makeLive();
        admit(id,keccak256("req"));
        allocate(allocation(id,0,70,30));
        SSELeaseControllerV2.Lease memory l=controller.getLease(id);
        assertEq(l.pending,0);
        assertEq(l.uncommitted,200);
        assertEq(l.consumerCredited,30);
        assertEq(l.providerCredited,70);
        assertEq(l.pending+l.uncommitted+l.consumerCredited+l.providerCredited+l.unusedRefunded,300);
        assertEq(controller.withdrawable(provider),70);
        assertEq(controller.withdrawable(consumer),30);
        assertEq(address(controller).balance,300);
    }
    function testNoAllocationWithoutBothCorrectSignatures() public {
        (uint256 id,)=makeLive();
        admit(id,keccak256("req"));
        SSELeaseControllerV2.Allocation memory a=allocation(id,0,70,30);
        (bytes memory c,bytes memory p)=signatures(a);
        vm.expectRevert(SSELeaseControllerV2.InvalidSignatures.selector);
        controller.allocateEpoch(a,c,signature(WRONG_KEY,digestFor(controller,a)));
        vm.expectRevert(SSELeaseControllerV2.InvalidSignatures.selector);
        controller.allocateEpoch(a,signature(WRONG_KEY,digestFor(controller,a)),p);
        assertEq(controller.getLease(id).pending,100);
    }
    function testTamperedAllocationCannotReuseSignatures() public {
        (uint256 id,)=makeLive();
        admit(id,keccak256("req"));
        SSELeaseControllerV2.Allocation memory a=allocation(id,0,70,30);
        (bytes memory c,bytes memory p)=signatures(a);
        a.providerShare=71;
        a.consumerShare=29;
        vm.expectRevert(SSELeaseControllerV2.InvalidSignatures.selector);
        controller.allocateEpoch(a,c,p);
    }
    function testAllocationReplayAndNonceConflictRejected() public {
        (uint256 id,)=makeLive();
        admit(id,keccak256("req"));
        SSELeaseControllerV2.Allocation memory a=allocation(id,0,70,30);
        allocate(a);
        vm.expectRevert(SSELeaseControllerV2.InvalidArgument.selector);
        allocate(a);
        assertEq(controller.getEpoch(id,0).nonce,1);
    }
    function testExpiredAndOverAllocatedSignaturesRejected() public {
        (uint256 id,)=makeLive();
        admit(id,keccak256("req"));
        SSELeaseControllerV2.Allocation memory a=allocation(id,0,101,0);
        vm.expectRevert(SSELeaseControllerV2.InvalidArgument.selector);
        controller.allocateEpoch(a,new bytes(65),new bytes(65));
        a.providerShare=70; a.consumerShare=30;
        a.expiry=block.timestamp-1;
        vm.expectRevert(SSELeaseControllerV2.InvalidArgument.selector);
        controller.allocateEpoch(a,new bytes(65),new bytes(65));
    }
    function testPreAcceptanceTimeoutReturnsWholeEscrowWithoutAdmittedEpochs() public {
        uint256 id=makeOffer();
        vm.warp(controller.getLease(id).acceptanceDeadline+1);
        vm.prank(address(0xDEAD));
        controller.cancelFailedSetup(id);
        assertEq(controller.withdrawable(consumer),300);
        assertEq(controller.getLease(id).uncommitted,0);
        assertEq(uint8(controller.getLease(id).state),uint8(SSELeaseControllerV2.State.Cancelled));
        vm.expectRevert(SSELeaseControllerV2.InvalidState.selector);
        controller.cancelFailedSetup(id);
    }
    function testAcceptedButUnderfilledAssignmentCanBeCancelled() public {
        uint256 id=makeOffer();
        vm.prank(provider);
        controller.acceptLease(id);
        uint256 assignment=controller.getLease(id).assignmentId;
        vm.warp(pool.enrollmentDeadline(assignment)+1);
        pool.sealEnrollment(assignment);
        controller.cancelFailedSetup(id);
        assertEq(controller.withdrawable(consumer),300);
    }
    function testNoUnilateralRefundOfAdmittedEpochAfterServiceDeadline() public {
        (uint256 id,uint256 assignment)=makeLive();
        admit(id,keccak256("still unresolved"));
        vm.warp(pool.serviceDeadline(assignment));
        vm.prank(address(0xABCD));
        controller.endAdmissions(id);
        SSELeaseControllerV2.Lease memory l=controller.getLease(id);
        assertEq(l.pending,100);
        assertEq(l.unusedRefunded,200);
        assertEq(controller.withdrawable(consumer),200);
        assertEq(controller.withdrawable(provider),0);
        vm.expectRevert(SSELeaseControllerV2.InvalidState.selector);
        controller.finishLease(id);
        allocate(allocation(id,0,80,20));
        controller.finishLease(id);
        assertEq(uint8(controller.getLease(id).state),uint8(SSELeaseControllerV2.State.Closed));
    }
    function testPermissionlessPoolExpiryCannotForceMoneyAllocation() public {
        (uint256 id,uint256 assignment)=makeLive();
        admit(id,keccak256("r"));
        vm.warp(pool.serviceDeadline(assignment));
        vm.prank(address(0x1234));
        pool.expire(assignment);
        assertEq(uint8(pool.status(assignment)),uint8(ScalableMonitorCommitteeV2.Status.Released));
        assertEq(controller.withdrawable(provider),0);
        controller.endAdmissions(id);
        assertEq(controller.getLease(id).pending,100);
    }
    function testFutureAdmissionCannotExtendPastBondLifetime() public {
        (uint256 id,uint256 assignment)=makeLive();
        vm.warp(pool.serviceDeadline(assignment)-4);
        vm.expectRevert(SSELeaseControllerV2.InvalidState.selector);
        vm.prank(consumer);
        controller.admitEpoch(id,keccak256("late"));
    }
    function testCannotStopAdmissionsPrematurely() public {
        (uint256 id,)=makeLive();
        vm.expectRevert(SSELeaseControllerV2.InvalidState.selector);
        controller.endAdmissions(id);
    }
    function testWithdrawOnceAfterAgreement() public {
        (uint256 id,)=makeLive();
        admit(id,keccak256("r"));
        allocate(allocation(id,0,40,60));
        uint256 beforeBalance=provider.balance;
        vm.prank(provider);
        controller.withdraw();
        assertEq(provider.balance,beforeBalance+40);
        assertEq(controller.withdrawable(provider),0);
        vm.expectRevert(SSELeaseControllerV2.NoWithdrawal.selector);
        vm.prank(provider);
        controller.withdraw();
    }
    function testSignaturesBoundToChainId() public {
        (uint256 id,)=makeLive();
        admit(id,keccak256("r"));
        SSELeaseControllerV2.Allocation memory a=allocation(id,0,40,60);
        (bytes memory c,bytes memory p)=signatures(a);
        vm.chainId(block.chainid+1);
        vm.expectRevert(SSELeaseControllerV2.InvalidSignatures.selector);
        controller.allocateEpoch(a,c,p);
    }
    function testFuzzFullSplitConservation(uint8 portion) public {
        (uint256 id,)=makeLive();
        admit(id,keccak256("r"));
        uint256 providerPart=uint256(portion)%101;
        allocate(allocation(id,0,providerPart,100-providerPart));
        SSELeaseControllerV2.Lease memory l=controller.getLease(id);
        assertEq(l.pending + l.uncommitted + l.providerCredited +
                 l.consumerCredited + l.unusedRefunded, l.escrow);
    }
}
