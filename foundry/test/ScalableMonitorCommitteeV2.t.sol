// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import "forge-std/Test.sol";
import {ScalableMonitorCommitteeV2, IVerifiedMonitorRandomnessV2}
    from "../../contracts/ScalableMonitorCommitteeV2.sol";

/// @dev Mock proves interface plumbing ONLY, not VRF unbiasability.
contract MockRandomnessVerifierV2 is IVerifiedMonitorRandomnessV2 {
    function verify(bytes32 commitment, bytes32 seed, bytes calldata proof)
        external pure returns (bool) {
        return keccak256(proof) == keccak256(abi.encode(keccak256(abi.encode(commitment, seed))));
    }
}
contract MockMonitorControllerV2 {
    function request(ScalableMonitorCommitteeV2 pool, ScalableMonitorCommitteeV2.Terms memory t)
        external returns (uint256) { return pool.requestAssignment(t); }
    function release(ScalableMonitorCommitteeV2 pool, uint256 id) external { pool.releaseAssignment(id); }
}
contract ScalableMonitorCommitteeV2Test is Test {
    ScalableMonitorCommitteeV2 pool;
    MockMonitorControllerV2 controller;
    MockRandomnessVerifierV2 verifier;
    address consumer=address(0xC001);
    address provider=address(0xB002);
    bytes32 constant SEED=keccak256("R3_V2_TEST_SEED");

    function setUp() public {
        vm.warp(100_000);
        verifier=new MockRandomnessVerifierV2();
        controller=new MockMonitorControllerV2();
        pool=new ScalableMonitorCommitteeV2(address(this),address(verifier),1 ether,0.1 ether,1 days);
        pool.bindController(address(controller));
    }
    function terms(uint8 k,uint8 q,uint8 spare)
        internal view returns (ScalableMonitorCommitteeV2.Terms memory t) {
        t.consumer=consumer; t.provider=provider;
        t.size=k; t.quorum=q; t.reserves=spare;
        t.enrollmentPeriod=10; t.randomnessPeriod=10; t.selectionPeriod=10;
        t.confirmationPeriod=10; t.servicePeriod=100;
    }
    function actor(uint256 i) internal pure returns(address) {
        return address(uint160(0x100000+i));
    }
    function enroll(uint256 id,uint256 i) internal {
        address who=actor(i);
        vm.deal(who,2 ether);
        vm.startPrank(who);
        pool.register{value:1 ether}();
        pool.join{value:0.1 ether}(id);
        vm.stopPrank();
    }
    function joined(uint256 n,uint8 k,uint8 q,uint8 spare)
        internal returns(uint256 id) {
        id=controller.request(pool,terms(k,q,spare));
        for(uint256 i;i<n;++i) enroll(id,i);
    }
    function seed(uint256 id) internal {
        vm.warp(pool.enrollmentDeadline(id)+1);
        pool.sealEnrollment(id);
        pool.supplyRandomness(id,SEED,abi.encode(keccak256(abi.encode(pool.assignmentCommitment(id),SEED))));
    }
    function choose(uint256 id) internal {
        while(pool.selectionCursor(id)<pool.enrolledCount(id)) pool.processSelection(id,16);
        pool.finalizeSelection(id);
    }
    function ready(uint256 n,uint8 k,uint8 q,uint8 spare) internal returns(uint256 id) {
        id=joined(n,k,q,spare);
        seed(id);
        choose(id);
    }
    function confirmAll(uint256 id) internal {
        for(uint256 i;i<pool.selectedCount(id);++i) {
            vm.prank(pool.seatAt(id,i));
            pool.confirm(id);
        }
    }

    function testNoLifetime32IdentityCapAndBoundedSelection() public {
        uint256 id=joined(96,4,3,2);
        assertEq(pool.registeredIdentities(),96);
        assertEq(pool.enrolledCount(id),96);
        seed(id);
        pool.processSelection(id,16);
        assertEq(pool.selectionCursor(id),16);
        for(uint256 i;i<5;++i) pool.processSelection(id,16);
        pool.finalizeSelection(id);
        assertEq(pool.selectedCount(id),4);
        assertEq(pool.rankingSize(id),6);
    }
    function testMaxBatchLimitEnforced() public {
        uint256 id=joined(30,5,4,2);
        seed(id);
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidPhase.selector);
        pool.processSelection(id,17);
        pool.processSelection(id,16);
        assertEq(pool.selectionCursor(id),16);
        pool.processSelection(id,16);
        pool.finalizeSelection(id);
    }
    function testRankingMatchesGlobalScoreRegardlessOfBatchSize() public {
        uint256 id=joined(27,4,3,3);
        seed(id);
        pool.processSelection(id,1);
        pool.processSelection(id,7);
        pool.processSelection(id,16);
        pool.processSelection(id,16);
        pool.finalizeSelection(id);
        address[] memory ranked=new address[](27);
        uint256[] memory scores=new uint256[](27);
        for(uint256 i;i<27;++i) {
            ranked[i]=actor(i);
            scores[i]=uint256(keccak256(abi.encode(SEED,id,ranked[i])));
        }
        for(uint256 i;i<27;++i) for(uint256 j=i+1;j<27;++j) {
            if(scores[j]<scores[i] || (scores[j]==scores[i] && ranked[j]<ranked[i])) {
                (scores[i],scores[j])=(scores[j],scores[i]);
                (ranked[i],ranked[j])=(ranked[j],ranked[i]);
            }
        }
        for(uint256 i;i<7;++i) assertEq(pool.rankedAt(id,i),ranked[i]);
        for(uint256 i;i<4;++i) assertEq(pool.seatAt(id,i),ranked[i]);
    }
    function testOnlyBoundControllerMayCreateAndRelease() public {
        vm.expectRevert(ScalableMonitorCommitteeV2.Unauthorized.selector);
        pool.requestAssignment(terms(4,3,1));
        uint256 id=ready(5,4,3,1);
        confirmAll(id);
        vm.expectRevert(ScalableMonitorCommitteeV2.Unauthorized.selector);
        pool.releaseAssignment(id);
        controller.release(pool,id);
        assertEq(uint8(pool.status(id)),uint8(ScalableMonitorCommitteeV2.Status.Released));
    }
    function testRejectBadCommitteeAndThreshold() public {
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidInput.selector);
        controller.request(pool,terms(4,2,1));
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidInput.selector);
        controller.request(pool,terms(17,10,0));
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidInput.selector);
        controller.request(pool,terms(4,3,13));
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidInput.selector);
        controller.request(pool,terms(4,5,0));
    }
    function testConsumerAndProviderExcluded() public {
        uint256 id=controller.request(pool,terms(4,3,1));
        address[2] memory parties=[consumer,provider];
        for(uint256 i;i<2;++i) {
            vm.deal(parties[i],2 ether);
            vm.startPrank(parties[i]);
            pool.register{value:1 ether}();
            vm.expectRevert(ScalableMonitorCommitteeV2.InvalidPhase.selector);
            pool.join{value:0.1 ether}(id);
            vm.stopPrank();
        }
    }
    function testDuplicateTicketAndWrongBondRefused() public {
        uint256 id=controller.request(pool,terms(4,3,1));
        vm.deal(actor(0),2 ether);
        vm.startPrank(actor(0));
        pool.register{value:1 ether}();
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidPhase.selector);
        pool.join{value:0.05 ether}(id);
        pool.join{value:0.1 ether}(id);
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidPhase.selector);
        pool.join{value:0.1 ether}(id);
        vm.stopPrank();
    }
    function testRosterImmutableBeforeSeed() public {
        uint256 id=joined(4,4,3,0);
        bytes32 beforeHash=pool.assignmentCommitment(id);
        vm.warp(pool.enrollmentDeadline(id)+1);
        pool.sealEnrollment(id);
        assertEq(beforeHash,pool.assignmentCommitment(id));
        vm.deal(actor(50),2 ether);
        vm.startPrank(actor(50));
        pool.register{value:1 ether}();
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidPhase.selector);
        pool.join{value:0.1 ether}(id);
        vm.stopPrank();
    }
    function testOnlyCoordinatorCanSupplyValidProof() public {
        uint256 id=joined(5,4,3,1);
        vm.warp(pool.enrollmentDeadline(id)+1);
        pool.sealEnrollment(id);
        vm.expectRevert(ScalableMonitorCommitteeV2.Unauthorized.selector);
        vm.prank(address(0xBAD));
        pool.supplyRandomness(id,SEED,abi.encode(bytes32(0)));
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidRandomness.selector);
        pool.supplyRandomness(id,SEED,abi.encode(bytes32(0)));
        pool.supplyRandomness(id,SEED,abi.encode(keccak256(abi.encode(pool.assignmentCommitment(id),SEED))));
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidPhase.selector);
        pool.supplyRandomness(id,SEED,abi.encode(bytes32(0)));
    }
    function testPartialSelectionDoesNotCreateCommittee() public {
        uint256 id=joined(20,4,3,2);
        seed(id);
        pool.processSelection(id,16);
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidPhase.selector);
        pool.finalizeSelection(id);
    }
    function testReadyRequiresEverySelectedConfirmation() public {
        uint256 id=ready(6,4,3,2);
        for(uint256 i;i<3;++i) {
            vm.prank(pool.seatAt(id,i));
            pool.confirm(id);
        }
        assertEq(pool.confirmedCount(id),3);
        assertEq(uint8(pool.status(id)),uint8(ScalableMonitorCommitteeV2.Status.Confirming));
        vm.prank(pool.seatAt(id,3));
        pool.confirm(id);
        assertEq(uint8(pool.status(id)),uint8(ScalableMonitorCommitteeV2.Status.Active));
    }
    function testOutsiderAndDuplicateConfirmationRejected() public {
        uint256 id=ready(6,4,3,2);
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidPhase.selector);
        vm.prank(address(0xDEAD));
        pool.confirm(id);
        address who=pool.seatAt(id,0);
        vm.prank(who);
        pool.confirm(id);
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidPhase.selector);
        vm.prank(who);
        pool.confirm(id);
    }
    function testNoShowCanBeReplacedAndObjectivelyPenalized() public {
        uint256 id=ready(6,4,3,2);
        address absent=pool.seatAt(id,3);
        address alternate=pool.rankedAt(id,4);
        for(uint256 i;i<3;++i) {
            vm.prank(pool.seatAt(id,i));
            pool.confirm(id);
        }
        vm.warp(pool.confirmationDeadline(id)+1);
        pool.replaceNoShows(id);
        assertEq(pool.seatAt(id,3),alternate);
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidPhase.selector);
        vm.prank(absent);
        pool.confirm(id);
        vm.prank(alternate);
        pool.confirm(id);
        assertEq(uint8(pool.status(id)),uint8(ScalableMonitorCommitteeV2.Status.Active));
        vm.prank(address(0xFACE));
        pool.settleTicket(id,absent);
        assertEq(pool.withdrawable(consumer),0.1 ether);
    }
    function testMultiRoundNoShowReplacementUsesNextStandby() public {
        uint256 id=ready(7,4,3,3);
        address absent=pool.seatAt(id,3);
        address reserve1=pool.rankedAt(id,4);
        address reserve2=pool.rankedAt(id,5);
        for(uint256 i;i<3;++i) {
            vm.prank(pool.seatAt(id,i));
            pool.confirm(id);
        }
        vm.warp(pool.confirmationDeadline(id)+1);
        pool.replaceNoShows(id);
        assertEq(pool.seatAt(id,3),reserve1);
        vm.warp(pool.confirmationDeadline(id)+1);
        pool.replaceNoShows(id);
        assertEq(pool.seatAt(id,3),reserve2);
        vm.prank(reserve2);
        pool.confirm(id);
        pool.settleTicket(id,absent);
        pool.settleTicket(id,reserve1);
        assertEq(pool.withdrawable(consumer),0.2 ether);
    }
    function testNoReserveAbortsWithoutConsumer() public {
        uint256 id=ready(4,4,3,0);
        for(uint256 i;i<3;++i) {
            vm.prank(pool.seatAt(id,i));
            pool.confirm(id);
        }
        address absent=pool.seatAt(id,3);
        vm.warp(pool.confirmationDeadline(id)+1);
        vm.prank(address(0xFACE));
        pool.replaceNoShows(id);
        assertEq(uint8(pool.status(id)),uint8(ScalableMonitorCommitteeV2.Status.Aborted));
        pool.settleTicket(id,absent);
        assertEq(pool.withdrawable(consumer),0.1 ether);
    }
    function testUnderfilledEnrollmentAbortsAndRefundsAllTickets() public {
        uint256 id=joined(2,4,3,0);
        vm.warp(pool.enrollmentDeadline(id)+1);
        pool.sealEnrollment(id);
        assertEq(uint8(pool.status(id)),uint8(ScalableMonitorCommitteeV2.Status.Aborted));
        pool.settleTicket(id,actor(0));
        pool.settleTicket(id,actor(1));
        assertEq(pool.withdrawable(actor(0)),0.1 ether);
    }
    function testOutsiderExpiryCannotAbortAdequatelyFilledEnrollment() public {
        uint256 id=joined(5,4,3,1);
        vm.warp(pool.enrollmentDeadline(id)+1);
        vm.prank(address(0xDEAD));
        pool.expire(id);
        assertEq(uint8(pool.status(id)),uint8(ScalableMonitorCommitteeV2.Status.WaitingSeed));
        pool.supplyRandomness(id,SEED,abi.encode(keccak256(abi.encode(pool.assignmentCommitment(id),SEED))));
        assertEq(uint8(pool.status(id)),uint8(ScalableMonitorCommitteeV2.Status.Selecting));
    }
    function testOutsiderExpiryAbortsOnlyUnderfilledEnrollment() public {
        uint256 id=joined(2,4,3,0);
        vm.warp(pool.enrollmentDeadline(id)+1);
        vm.prank(address(0xDEAD));
        pool.expire(id);
        assertEq(uint8(pool.status(id)),uint8(ScalableMonitorCommitteeV2.Status.Aborted));
        pool.settleTicket(id,actor(0));
        assertEq(pool.withdrawable(actor(0)),0.1 ether);
    }

    function testMissingRandomnessDoesNotLockCandidatesForever() public {
        uint256 id=joined(5,4,3,1);
        vm.warp(pool.enrollmentDeadline(id)+1);
        pool.sealEnrollment(id);
        vm.warp(pool.seedDeadline(id)+1);
        vm.prank(address(0xFACE));
        pool.expire(id);
        pool.settleTicket(id,actor(4));
        assertEq(pool.withdrawable(actor(4)),0.1 ether);
    }
    function testIncompleteSelectionCanExpireAndRefund() public {
        uint256 id=joined(20,4,3,2);
        seed(id);
        pool.processSelection(id,5);
        vm.warp(pool.selectionDeadline(id)+1);
        pool.expire(id);
        assertEq(uint8(pool.status(id)),uint8(ScalableMonitorCommitteeV2.Status.Aborted));
        pool.settleTicket(id,actor(19));
        assertEq(pool.withdrawable(actor(19)),0.1 ether);
    }
    function testSelectedTicketCannotBeReleasedDuringService() public {
        uint256 id=ready(6,4,3,2);
        confirmAll(id);
        address selectedMonitor=pool.seatAt(id,0);
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidPhase.selector);
        pool.settleTicket(id,selectedMonitor);
        vm.warp(pool.serviceDeadline(id));
        vm.prank(address(0xABCD));
        pool.expire(id);
        pool.settleTicket(id,selectedMonitor);
        assertEq(pool.withdrawable(selectedMonitor),0.1 ether);
    }
    function testConsumerAbsentCannotHoldBondsIndefinitely() public {
        uint256 id=ready(5,4,3,1);
        confirmAll(id);
        vm.warp(pool.serviceDeadline(id)+1);
        vm.prank(address(0xDEAD));
        pool.expire(id);
        for(uint256 i;i<5;++i) pool.settleTicket(id,actor(i));
        assertEq(uint8(pool.status(id)),uint8(ScalableMonitorCommitteeV2.Status.Released));
    }
    function testRegistryBondRequiresAllTicketsSettledAndExitDelay() public {
        uint256 id=joined(2,4,3,0);
        vm.prank(actor(0));
        pool.requestExit();
        vm.warp(block.timestamp+1 days+1);
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidPhase.selector);
        vm.prank(actor(0));
        pool.withdrawRegistryBond();
        pool.expire(id);
        pool.settleTicket(id,actor(0));
        vm.prank(actor(0));
        pool.withdrawRegistryBond();
        assertEq(pool.withdrawable(actor(0)),1.1 ether);
    }
    function testWithdrawAndTicketSettleCannotBeRepeated() public {
        uint256 id=joined(2,4,3,0);
        vm.warp(pool.enrollmentDeadline(id)+1);
        pool.sealEnrollment(id);
        pool.settleTicket(id,actor(0));
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidPhase.selector);
        pool.settleTicket(id,actor(0));
        uint256 beforeBalance=actor(0).balance;
        vm.prank(actor(0));
        pool.withdraw();
        assertEq(actor(0).balance,beforeBalance+0.1 ether);
        vm.expectRevert(ScalableMonitorCommitteeV2.NoCredit.selector);
        vm.prank(actor(0));
        pool.withdraw();
    }
    function testUnselectedReserveCanRefundBeforeCommitteeRelease() public {
        uint256 id=ready(7,4,3,2);
        confirmAll(id);
        address spare=pool.rankedAt(id,4);
        pool.settleTicket(id,spare);
        assertEq(pool.withdrawable(spare),0.1 ether);
        address stillSelected = pool.seatAt(id,0);
        vm.expectRevert(ScalableMonitorCommitteeV2.InvalidPhase.selector);
        pool.settleTicket(id,stillSelected);
    }
    function testMaxFinalistsDoesNotLimitEnrollment() public {
        uint256 id=joined(80,8,6,8);
        seed(id);
        for(uint256 i;i<5;++i) pool.processSelection(id,16);
        pool.finalizeSelection(id);
        assertEq(pool.rankingSize(id),16);
        assertEq(pool.selectedCount(id),8);
    }
}
