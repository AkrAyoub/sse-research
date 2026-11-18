// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {OpenMonitorCommittee} from "../../contracts/OpenMonitorCommittee.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";

/// @notice A consumer contract that tries to withdraw twice from its fallback.
/// @dev The attempted recursive call MUST revert while the first withdrawal succeeds.
contract WP09NReenteringConsumer {
    SSESettlement public immutable settlement;
    bool public attempted;
    bool public reentryBlocked;

    constructor(SSESettlement settlement_) { settlement = settlement_; }

    function createAndClose(address provider) external {
        uint256 leaseId = settlement.createLease{value: 25}(
            provider, keccak256("wp09n-http"), keccak256("wp09n-cpu"),
            25, 5, 25, 1, 100, 100, 100
        );
        settlement.closeLease(leaseId);
    }

    function withdraw() external { settlement.withdraw(); }

    receive() external payable {
        if (attempted) return;
        attempted = true;
        try settlement.withdraw() {
            reentryBlocked = false;
        } catch {
            reentryBlocked = true;
        }
    }
}

contract WP09NWithdrawalReentrancyTest is Test {
    function testConsumerRefundReentryRejectedAndOriginalTransferSucceeds() public {
        vm.warp(100_000);
        OpenMonitorCommittee pool = new OpenMonitorCommittee(
            address(0xD1CE), 1 ether, 7 days, 1 days
        );
        SSESettlement settlement = new SSESettlement(address(pool));
        pool.bindSettlement(address(settlement));
        for (uint256 i; i < 4; ++i) {
            address member = address(uint160(0xC100 + i));
            vm.deal(member, 2 ether);
            vm.prank(member);
            pool.register{value: 1 ether}();
        }
        WP09NReenteringConsumer consumer = new WP09NReenteringConsumer(settlement);
        vm.deal(address(consumer), 25);
        consumer.createAndClose(address(0xB100));
        assertEq(settlement.withdrawable(address(consumer)), 25);
        consumer.withdraw();
        assertTrue(consumer.attempted());
        assertTrue(consumer.reentryBlocked());
        assertEq(settlement.withdrawable(address(consumer)), 0);
        assertEq(address(consumer).balance, 25);
        assertEq(address(settlement).balance, 0);
    }
}
