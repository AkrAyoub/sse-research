// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import "forge-std/Test.sol";
import {SSEHistoryPolicy as H} from "../../contracts/SSEHistoryPolicy.sol";
import {SSEExposureAccounting as A} from "../../contracts/SSEExposureAccounting.sol";

contract SSEHistoryPolicyTest is Test {
    using A for A.Lease;
    A.Lease private l;

    function testAllConsistentPredicates() public pure {
        assertEq(H.admissible(false,false,false),7);
        assertEq(H.admissible(true,false,false),6);
        assertEq(H.admissible(false,false,true),3);
        assertEq(H.admissible(true,false,true),2);
        assertEq(H.admissible(false,true,false),4);
        assertEq(H.admissible(true,true,false),4);
    }

    function predicates(bool receipt,bool success,bool negative) external pure returns(uint8) {
        return H.admissible(receipt,success,negative);
    }

    function narrow(uint8 prior,uint8 additional) external pure returns(uint8) {
        return H.narrow(prior,additional);
    }

    function testRejectConflictingPredicates() public {
        vm.expectRevert(H.ConflictingEvidence.selector);
        this.predicates(false,true,true);
        vm.expectRevert(H.ConflictingEvidence.selector);
        this.predicates(true,true,true);
    }

    function testRejectDisjointHistories() public {
        vm.expectRevert(H.ConflictingEvidence.selector);
        this.narrow(3,4);
    }

    function testRejectInvalidMasks() public {
        vm.expectRevert(H.InvalidHistory.selector);
        this.narrow(0,7);
        vm.expectRevert(H.InvalidHistory.selector);
        this.narrow(7,8);
    }

    function testFuzzNonemptyIntersections(uint8 a,uint8 b) public {
        a=uint8(bound(a,1,7));
        b=uint8(bound(b,1,7));
        uint8 intersection=a&b;
        if(intersection==0) {
            vm.expectRevert(H.ConflictingEvidence.selector);
            this.narrow(a,b);
        } else {
            assertEq(H.narrow(a,b),intersection);
            assertEq(H.narrow(b,a),intersection);
            assertEq(H.narrow(intersection,a),intersection);
        }
    }

    // Unit-test predicates are fixtures, not observations of physical SLA.
    function testNegativeWithoutReceiptRetainsReservationExposure() public {
        l.initialize(100,20,150,2,200);
        uint256 id=l.admit(bytes32(uint256(1)));
        l.refine(id,H.admissible(false,false,true));
        assertEq(l.consumerCredit,80);
        assertEq(l.providerCredit,0);
        assertEq(l.exposure,20);
        l.refine(id,H.narrow(l.epochs[id].mask,H.admissible(true,false,false)));
        assertEq(l.consumerCredit,100);
        assertEq(l.exposure,0);
        assertTrue(l.conserved());
    }

    function testUnqualifiedObservationsCannotReleaseEscrow() public {
        l.initialize(100,20,150,2,200);
        uint256 id=l.admit(bytes32(uint256(1)));
        l.refine(id,H.admissible(false,false,false));
        assertEq(l.consumerCredit,0);
        assertEq(l.providerCredit,0);
        assertEq(l.exposure,100);
        assertTrue(l.conserved());
    }
}
