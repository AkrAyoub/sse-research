// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {Test} from "forge-std/Test.sol";
import {SSEStandbyCommittee} from "../../contracts/SSEStandbyCommittee.sol";

contract SSEStandbyCommitteeTest is Test {
    SSEStandbyCommittee private c;
    function setUp() public {
        c=new SSEStandbyCommittee(address(this));
    }
    function roster(uint256 n) private pure returns(address[] memory a){
        a=new address[](n);
        for(uint256 i=0;i<n;++i) a[i]=address(uint160(100+i));
    }
    function init(uint256 n) private {
        c.initialize(1,address(1),address(2),roster(n),4,60);
    }
    function confirm(uint256 i) private {
        vm.prank(address(uint160(100+i)));
        c.confirm(1);
    }
    function advanceTime() private {
        SSEStandbyCommittee.Assignment memory a=c.assignment(1);
        vm.warp(uint256(a.deadline)+1);
    }
    function testReadyWithoutReplacement() public {
        init(6);
        for(uint256 i=0;i<4;++i) confirm(i);
        (address[] memory members,uint256 q)=c.readyMembers(1);
        assertEq(members.length,4);
        assertEq(q,3);
        assertEq(c.assignment(1).nextStandby,0);
        advanceTime();
        vm.expectRevert(SSEStandbyCommittee.InvalidPhase.selector);
        c.advance(1);
    }
    function testOrderedReplacementAndImmutableQuorum() public {
        init(6);
        confirm(0);
        confirm(2);
        advanceTime();
        vm.prank(address(999));
        c.advance(1);
        SSEStandbyCommittee.Assignment memory a=c.assignment(1);
        assertEq(a.primary[0],address(100));
        assertEq(a.primary[1],address(104));
        assertEq(a.primary[2],address(102));
        assertEq(a.primary[3],address(105));
        assertEq(a.nextStandby,2);
        assertEq(a.confirmedCount,2);
        assertEq(a.quorum,3);
        assertFalse(c.activeSeat(1,address(101)));
        vm.expectRevert(SSEStandbyCommittee.Unauthorized.selector);
        confirm(1);
        confirm(4);
        confirm(5);
        (,uint256 q)=c.readyMembers(1);
        assertEq(q,3);
    }
    function testRepeatedReplacementAndExhaustion() public {
        init(6);
        confirm(0);
        confirm(1);
        confirm(2);
        advanceTime();
        c.advance(1);
        assertEq(c.assignment(1).primary[3],address(104));
        advanceTime();
        c.advance(1);
        assertEq(c.assignment(1).primary[3],address(105));
        advanceTime();
        c.advance(1);
        SSEStandbyCommittee.Assignment memory a=c.assignment(1);
        assertEq(uint256(a.phase),uint256(SSEStandbyCommittee.Phase.Expired));
        assertEq(a.confirmedCount,0);
        for(uint256 i=0;i<6;++i){
            assertFalse(c.activeSeat(1,address(uint160(100+i))));
            assertFalse(c.confirmed(1,address(uint160(100+i))));
        }
        vm.expectRevert(SSEStandbyCommittee.InvalidPhase.selector);
        c.readyMembers(1);
    }
    function testInsufficientReservesExpiresWithoutPartialPromotion() public {
        init(5);
        confirm(0);
        confirm(1);
        advanceTime();
        c.advance(1);
        assertEq(c.assignment(1).nextStandby,0);
        assertEq(uint256(c.assignment(1).phase),uint256(SSEStandbyCommittee.Phase.Expired));
    }
    function testDeadlineAndUnauthorizedConfirmation() public {
        init(6);
        vm.expectRevert(SSEStandbyCommittee.Unauthorized.selector);
        confirm(4);
        confirm(0);
        vm.expectRevert(SSEStandbyCommittee.InvalidPhase.selector);
        confirm(0);
        vm.warp(c.assignment(1).deadline);
        vm.expectRevert(SSEStandbyCommittee.InvalidPhase.selector);
        c.advance(1);
        confirm(1);
        advanceTime();
        vm.expectRevert(SSEStandbyCommittee.InvalidPhase.selector);
        confirm(2);
    }
    function testInitializationGuards() public {
        address[] memory a=roster(6);
        vm.prank(address(999));
        vm.expectRevert(SSEStandbyCommittee.Unauthorized.selector);
        c.initialize(1,address(1),address(2),a,4,60);
        a[5]=a[0];
        vm.expectRevert(SSEStandbyCommittee.InvalidPolicy.selector);
        c.initialize(1,address(1),address(2),a,4,60);
        a[5]=address(2);
        vm.expectRevert(SSEStandbyCommittee.InvalidPolicy.selector);
        c.initialize(1,address(1),address(2),a,4,60);
        init(6);
        vm.expectRevert(SSEStandbyCommittee.InvalidPolicy.selector);
        init(6);
    }
    function testLeaseIsolation() public {
        init(6);
        c.initialize(2,address(1),address(2),roster(6),4,60);
        confirm(0);
        assertFalse(c.confirmed(2,address(100)));
        assertEq(c.assignment(2).confirmedCount,0);
    }
}
