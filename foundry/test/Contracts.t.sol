// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {OpenMonitorBondPool} from "../../contracts/OpenMonitorBondPool.sol";
import {OpenResourceBoard} from "../../contracts/OpenResourceBoard.sol";
import {SSEBoundsHarness} from "../../contracts/SSEBoundsPure.sol";

contract ContractsTest is Test {
    OpenMonitorBondPool pool;
    OpenResourceBoard board;
    SSEBoundsHarness bounds;
    address user1 = address(0xB0B);
    address user2 = address(0xA11CE);

    function setUp() public {
        pool = new OpenMonitorBondPool(1 ether, 7 days);
        board = new OpenResourceBoard();
        bounds = new SSEBoundsHarness();
        vm.deal(user1, 10 ether);
        vm.deal(user2, 10 ether);
    }

    function testSSEAmbiguousFailure() public view {
        (uint256 p, uint256 c, uint256 x) = bounds.calculate(3, 25, 5);
        assertEq(p, 0);
        assertEq(c, 20);
        assertEq(x, 5);
    }

    function testBoundedConservationFuzz(uint8 mask, uint96 rawFee, uint96 rawReservation) public view {
        mask = uint8(bound(mask, 1, 7));
        uint256 fee = bound(rawFee, 1, 1e18);
        uint256 reservation = bound(rawReservation, 0, fee);
        (uint256 p, uint256 c, uint256 x) = bounds.calculate(mask, fee, reservation);
        assertEq(p + c + x, fee);
    }

    function testPermissionlessMonitorEntryAndCooldown() public {
        vm.prank(user1);
        pool.register{value: 1 ether}();
        assertTrue(pool.isEligible(user1));
        vm.prank(user1);
        pool.requestExit();
        assertFalse(pool.isEligible(user1));
        vm.prank(user1);
        vm.expectRevert(OpenMonitorBondPool.InvalidState.selector);
        pool.withdrawBond();
        vm.warp(block.timestamp + 7 days + 1);
        uint256 beforeBalance = user1.balance;
        vm.prank(user1);
        pool.withdrawBond();
        assertEq(user1.balance, beforeBalance + 1 ether);
    }

    function testPermissionlessRequestBidAndSelection() public {
        bytes32 profile = keccak256("cpu-profile");
        bytes32 policy = keccak256("sla-policy");
        vm.prank(user1);
        uint256 id = board.requestResource(profile, policy, 50, uint64(block.timestamp + 1 days));
        vm.prank(user2);
        board.placeBid(id, 30);
        vm.warp(block.timestamp + 1 days);
        vm.prank(user1);
        (address provider, uint256 price) = board.chooseBid(id, 0);
        assertEq(provider, user2);
        assertEq(price, 30);
    }
}
