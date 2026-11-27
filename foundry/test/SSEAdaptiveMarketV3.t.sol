// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import "forge-std/Test.sol";
import {SSEAdaptiveMarketV3 as M} from "../../contracts/SSEAdaptiveMarketV3.sol";
import {SSEAdaptiveVoteLedger as V} from "../../contracts/SSEAdaptiveVoteLedger.sol";
import {SSEExposureAccounting as A} from "../../contracts/SSEExposureAccounting.sol";
import {SSEAuthenticatedEvidence as E} from "../../contracts/SSEAuthenticatedEvidence.sol";
import {SSEEntitlementBounds as B} from "../../contracts/SSEEntitlementBounds.sol";

/// @notice Isolated EVM lifecycle fixtures, not physical SLA evidence.
contract SSEAdaptiveMarketV3Test is Test {
    M private market;
    V private votes;
    uint256 private constant P=0x12345;
    uint256 private constant C=0x67890;
    address private provider;
    address private consumer;
    uint256 private constant FEE=100;
    uint256 private constant BOND=1000;
    uint256 private constant REWARD=10;
    bytes32 private constant REQUEST=keccak256("fixture request");
    function setUp() public {
        vm.chainId(31340);
        vm.warp(1000000);
        vm.roll(1000);
        market=new M(BOND);
        votes=market.votes();
        provider=vm.addr(P);
        consumer=vm.addr(C);
        vm.deal(consumer,1 ether);
        for(uint256 i=0;i<4;++i) {
            address m=address(uint160(0xA000+i));
            vm.deal(m,1 ether);
            vm.prank(m);
            market.registerMonitor{value:BOND}();
        }
    }
    function fund(bool conditional) private returns(uint256 id) {
        uint64 end=uint64(vm.getBlockTimestamp()+20);
        vm.prank(consumer);
        uint256 requestId=market.requestResource(keccak256("profile"),keccak256("policy"),FEE,end);
        vm.prank(provider);
        market.placeBid(requestId,FEE);
        vm.warp(uint256(end)+1);
        M.Terms memory t=M.Terms({
            endpointHash:keccak256("endpoint"),epochs:3,monitorBudget:120,
            perMonitorEpochReward:REWARD,requiredFaultTolerance:1,gasBoundSeats:4,
            confirmationSeconds:3600,responseSeconds:100,monitoringSeconds:100,
            evidenceSeconds:1000,reservationFee:20,exposureBudget:150,
            conditionalQuorumPolicy:conditional
        });
        vm.prank(consumer);
        id=market.chooseBidAndFund{value:420}(requestId,0,t);
    }
    function open(bool conditional) private returns(uint256 id) {
        id=fund(conditional);
        M.Lease memory l=market.lease(id);
        vm.roll(l.entropyBlock+1);
        market.drawCommittee(id);
        address[] memory selected=votes.selected(id);
        for(uint256 i=0;i<selected.length;++i){
            vm.prank(selected[i]);
            votes.confirmSeat(id);
        }
        vm.prank(provider);
        market.acceptLease(id,l.termsHash);
        vm.prank(consumer);
        market.startEpoch(id,REQUEST);
    }
    function negative(uint256 id,uint256 epoch) private {
        V.Epoch memory v=votes.epoch(id,epoch);
        vm.warp(uint256(v.responseDeadline)+1);
        address[] memory selected=votes.selected(id);
        for(uint256 i=0;i<3;++i){
            vm.prank(selected[i]);
            votes.submitVoteDirect(id,epoch,V.Outcome.Failure,keccak256(abi.encode(i,epoch)));
        }
        vm.warp(uint256(v.monitoringClose)+1);
        market.finalizeEpoch(id,epoch);
    }
    function sign(uint256 key,bytes32 digest) private pure returns(bytes memory) {
        (uint8 v,bytes32 r,bytes32 s)=vm.sign(key,digest);
        return abi.encodePacked(r,s,v);
    }
    function receipt(uint256 id,uint256 epoch,bytes32 request) private {
        bytes32 d=E.acknowledgmentDigest(market.domainSeparator(),E.Context(id,epoch,request));
        market.submitAcknowledgment(id,epoch,sign(P,d));
    }
    function covered() private view {
        (uint256 balance,uint256 outstanding,bool ok)=market.escrowAccounting();
        assertTrue(ok);
        assertEq(balance,outstanding);
        assertEq(address(votes).balance,votes.totalUnspentReserves()+votes.totalWithdrawableCredits());
    }
    function testPartialRefundAndLateReceipt() public {
        uint256 id=open(true);
        negative(id,0);
        assertEq(market.withdrawable(consumer),80);
        assertEq(market.totalServiceEscrow(),220);
        assertEq(market.scientificEpoch(id,0).unresolved,20);
        receipt(id,0,REQUEST);
        assertEq(market.withdrawable(consumer),100);
        assertEq(market.scientificEpoch(id,0).unresolved,0);
        vm.prank(consumer);
        market.closeLease(id);
        assertEq(market.withdrawable(consumer),300);
        assertEq(market.totalServiceEscrow(),0);
        assertEq(votes.withdrawable(consumer),90);
        covered();
        uint256 before=consumer.balance;
        vm.prank(consumer);
        market.withdraw();
        assertEq(consumer.balance-before,300);
        covered();
    }
    function testExposureContinuationAndRefusal() public {
        uint256 id=open(true);
        negative(id,0);
        vm.prank(consumer);
        market.startEpoch(id,keccak256("second"));
        vm.warp(uint256(votes.epoch(id,1).monitoringClose)+1);
        market.finalizeEpoch(id,1);
        vm.prank(consumer);
        vm.expectRevert(B.ExposureExceeded.selector);
        market.startEpoch(id,keccak256("third"));
        assertEq(market.lease(id).nextEpoch,2);
        covered();
    }
    function testConservativeQuorumRetainsEscrow() public {
        uint256 id=open(false);
        negative(id,0);
        assertEq(market.withdrawable(consumer),0);
        assertEq(market.withdrawable(provider),0);
        assertEq(market.scientificEpoch(id,0).unresolved,100);
        vm.prank(consumer);
        vm.expectRevert(B.ExposureExceeded.selector);
        market.startEpoch(id,keccak256("second"));
        covered();
    }
    function testResidualAfterClosureAndReplayRefusal() public {
        uint256 id=open(true);
        negative(id,0);
        vm.prank(consumer);
        market.closeLease(id);
        assertEq(market.totalServiceEscrow(),20);
        vm.warp(uint256(market.epoch(id,0).evidenceClose)+1);
        market.closeEpochEvidence(id,0);
        E.Allocation memory a=E.Allocation(20,7,13,0,block.timestamp+100);
        bytes32 d=E.allocationDigest(market.domainSeparator(),E.Context(id,0,REQUEST),a);
        bytes memory p=sign(P,d);
        bytes memory c=sign(C,d);
        vm.expectRevert(M.InvalidSignature.selector);
        market.resolveResidual(id,0,a,p,p);
        market.resolveResidual(id,0,a,c,p);
        assertEq(market.withdrawable(provider),7);
        assertEq(market.withdrawable(consumer),293);
        assertEq(market.totalServiceEscrow(),0);
        vm.expectRevert(M.InvalidPhase.selector);
        market.resolveResidual(id,0,a,c,p);
        covered();
    }
    function testExpiredDrawRefundAndUnlock() public {
        uint256 id=fund(true);
        vm.roll(market.lease(id).entropyBlock+257);
        market.cancelExpiredDraw(id);
        assertEq(market.withdrawable(consumer),420);
        assertEq(market.totalServiceEscrow(),0);
        assertEq(market.totalPendingMonitorFunding(),0);
        for(uint256 i=0;i<4;++i){
            (,uint256 locked,)=market.monitors(address(uint160(0xA000+i)));
            assertEq(locked,0);
        }
        covered();
    }
}
