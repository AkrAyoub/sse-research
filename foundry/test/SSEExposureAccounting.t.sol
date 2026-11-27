// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {SSEExposureAccounting as A} from "../../contracts/SSEExposureAccounting.sol";
import {SSEEntitlementBounds as B} from "../../contracts/SSEEntitlementBounds.sol";

contract SSEExposureAccountingTest is Test {
    using A for A.Lease;
    A.Lease private l;

    function setUp() public {
        l.initialize(100,20,150,4,400);
    }

    function admit(uint256 n) public returns (uint256) {
        return l.admit(bytes32(n));
    }

    function refine(uint256 id,uint8 mask) external {
        l.refine(id,mask);
    }

    function allocate(uint256 id,uint256 p,uint256 c) external {
        l.allocateResidual(id,p,c);
    }

    function closeEvidence(uint256 id) external {
        l.closeEvidence(id);
    }

    function testContinuationWithUnresolvedEpoch() public {
        uint256 first=admit(1);
        (uint256 dp,uint256 dc)=l.refine(first,3);
        assertEq(dp,0);
        assertEq(dc,80);
        assertEq(l.exposure,20);
        uint256 second=admit(2);
        assertEq(second,1);
        assertEq(l.exposure,120);
        vm.expectRevert(B.ExposureExceeded.selector);
        this.admit(3);
        assertEq(l.nextEpoch,2);
        assertEq(l.available,200);
        l.refine(second,4);
        assertEq(l.exposure,20);
        assertEq(admit(3),2);
        assertTrue(l.conserved());
    }

    function testMonotonicCreditsAndIdempotence() public {
        uint256 id=admit(1);
        l.refine(id,3);
        (uint256 p,uint256 c)=l.refine(id,3);
        assertEq(p,0);
        assertEq(c,0);
        l.refine(id,2);
        assertEq(l.consumerCredit,100);
        assertEq(l.exposure,0);
        vm.expectRevert(B.InvalidHistory.selector);
        this.refine(id,7);
        assertTrue(l.conserved());
    }

    function testClosePreservesResidualAndAllowsRefinement() public {
        uint256 id=admit(1);
        l.refine(id,3);
        assertEq(l.close(),300);
        assertEq(l.consumerCredit,380);
        assertEq(l.exposure,20);
        vm.expectRevert(A.InvalidState.selector);
        this.admit(2);
        l.refine(id,1);
        assertEq(l.providerCredit,20);
        assertEq(l.exposure,0);
        assertTrue(l.conserved());
    }

    function testResidualRequiresEvidenceClosureAndExactShares() public {
        uint256 id=admit(1);
        l.refine(id,3);
        vm.expectRevert(A.InvalidState.selector);
        this.allocate(id,10,10);
        l.closeEvidence(id);
        vm.expectRevert(A.InvalidAllocation.selector);
        this.allocate(id,21,0);
        vm.expectRevert(A.InvalidAllocation.selector);
        this.allocate(id,10,9);
        l.allocateResidual(id,10,10);
        assertEq(l.providerCredit,10);
        assertEq(l.consumerCredit,90);
        assertEq(l.exposure,0);
        assertEq(l.epochs[id].mask,3);
        vm.expectRevert(A.InvalidState.selector);
        this.allocate(id,10,10);
        vm.expectRevert(A.InvalidState.selector);
        this.refine(id,2);
        assertTrue(l.conserved());
    }

    function testRejectReplayAndZeroRequest() public {
        admit(1);
        vm.expectRevert(A.InvalidRequest.selector);
        this.admit(1);
        vm.expectRevert(A.InvalidRequest.selector);
        this.admit(0);
        assertEq(l.nextEpoch,1);
        assertTrue(l.conserved());
    }

    function testRejectUnknownEpoch() public {
        vm.expectRevert(A.InvalidState.selector);
        this.refine(99,4);
        vm.expectRevert(A.InvalidState.selector);
        this.closeEvidence(99);
    }

    function testEpochLimitAndFullSettlement() public {
        for(uint256 i=0;i<4;++i) {
            uint256 id=admit(i+1);
            l.refine(id,4);
            l.closeEvidence(id);
            assertTrue(l.conserved());
        }
        assertEq(l.providerCredit,400);
        assertEq(l.available,0);
        vm.expectRevert(A.InvalidState.selector);
        this.admit(5);
        assertEq(l.close(),0);
        assertTrue(l.conserved());
    }

    function testFuzzRefinementAndClosure(uint8 rawMask,uint8 rawNext) public {
        uint8 mask=uint8(bound(rawMask,1,7));
        uint8 next=uint8(bound(rawNext,1,7)) & mask;
        if(next==0) next=mask;
        uint256 id=admit(1);
        l.refine(id,mask);
        l.refine(id,next);
        assertTrue(l.conserved());
        l.closeEvidence(id);
        uint256 x=l.exposure;
        if(x!=0) l.allocateResidual(id,x/2,x-x/2);
        l.close();
        assertEq(l.exposure,0);
        assertEq(l.available,0);
        assertTrue(l.conserved());
    }
}
