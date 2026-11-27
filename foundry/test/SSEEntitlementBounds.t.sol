// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import "forge-std/Test.sol";
import {SSEEntitlementBounds as SSE} from "../../contracts/SSEEntitlementBounds.sol";

contract SSEEntitlementBoundsTest is Test {
    function testAllSevenMasks() public pure {
        uint256[7] memory p = [uint256(20),0,0,100,20,0,0];
        uint256[7] memory c = [uint256(80),100,80,0,0,0,0];
        for (uint8 m=1; m<=7; ++m) {
            SSE.Bounds memory b = SSE.calculate(100,20,m);
            assertEq(b.provider,p[m-1]);
            assertEq(b.consumer,c[m-1]);
            assertEq(b.unresolved,100-p[m-1]-c[m-1]);
        }
    }
    function testFuzzRefinement(uint128 rawFee, uint128 rawReservation) public pure {
        uint256 fee = uint256(rawFee)+1;
        uint256 reservationFee = uint256(rawReservation) % (fee+1);
        for (uint8 prior=1; prior<=7; ++prior) {
            SSE.Bounds memory old = SSE.calculate(fee,reservationFee,prior);
            assertEq(old.provider+old.consumer+old.unresolved,fee);
            for (uint8 next=1; next<=7; ++next) {
                if ((prior & next)!=next) continue;
                (SSE.Bounds memory b,uint256 dp,uint256 dc,uint256 dx) =
                    SSE.refine(fee,reservationFee,prior,next);
                assertEq(old.provider+dp,b.provider);
                assertEq(old.consumer+dc,b.consumer);
                assertEq(old.unresolved-dx,b.unresolved);
                assertEq(dp+dc,dx);
                assertEq(b.provider+b.consumer+b.unresolved,fee);
            }
        }
    }
    function testRefuseHistoryExpansion() public {
        vm.expectRevert(SSE.InvalidHistory.selector);
        this.refinement(3,7);
    }
    function testRefuseEmptyMask() public {
        vm.expectRevert(SSE.InvalidHistory.selector);
        this.calculation(100,20,0);
    }
    function testRefuseUnknownBit() public {
        vm.expectRevert(SSE.InvalidHistory.selector);
        this.calculation(100,20,8);
    }
    function testRefuseInvalidReservation() public {
        vm.expectRevert(SSE.InvalidTerms.selector);
        this.calculation(100,101,7);
    }
    function testExposureContinuationAndRefusal() public {
        assertEq(SSE.reserve(20,100,120),120);
        vm.expectRevert(SSE.ExposureExceeded.selector);
        this.reservation(20,100,119);
    }
    function testExposureOverflowRefused() public {
        vm.expectRevert(SSE.ExposureExceeded.selector);
        this.reservation(type(uint256).max,1,type(uint256).max);
    }
    function calculation(uint256 fee,uint256 r,uint8 mask) external pure {
        SSE.calculate(fee,r,mask);
    }
    function refinement(uint8 prior,uint8 next) external pure {
        SSE.refine(100,20,prior,next);
    }
    function reservation(uint256 x,uint256 fee,uint256 budget) external pure {
        SSE.reserve(x,fee,budget);
    }
}
