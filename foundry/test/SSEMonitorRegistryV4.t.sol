// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import "forge-std/Test.sol";
import {SSEMonitorRegistryV4 as Registry} from "../../contracts/SSEMonitorRegistryV4.sol";
import {SSEServiceBoardV4 as Board} from "../../contracts/SSEServiceBoardV4.sol";
import {SSEAdaptiveMarketV4 as M} from "../../contracts/SSEAdaptiveMarketV4.sol";
import {SSEStandbyCommittee as Standby} from "../../contracts/SSEStandbyCommittee.sol";
import {SSEAdaptiveVoteLedgerV4Candidate as V} from "../../contracts/SSEAdaptiveVoteLedgerV4Candidate.sol";

/// @notice Registry/board unit fixtures + EIP-170/EIP-3860 size gates.
/// Written 2026-11-27 (source-only): NOT compiled, NOT executed.
contract SSEMonitorRegistryV4Test is Test {
    Registry private r;
    uint256 private constant BOND = 1000;

    function setUp() public {
        r = new Registry(address(this), BOND); // this test acts as the market
    }

    function join(uint256 i, uint256 cap) private returns (address m) {
        m = address(uint160(0xB000 + i));
        vm.deal(m, 100 ether);
        vm.prank(m);
        r.register{value: cap * BOND}(cap);
    }

    function testRegisterRequiresBondPerCapacity() public {
        address m = address(0xB0B);
        vm.deal(m, 1 ether);
        vm.prank(m);
        vm.expectRevert(Registry.InvalidInput.selector);
        r.register{value: 2 * BOND - 1}(2);
        vm.prank(m);
        vm.expectRevert(Registry.InvalidInput.selector);
        r.register{value: 65 * BOND}(65);
        vm.prank(m);
        r.register{value: 2 * BOND}(2);
        vm.prank(m);
        vm.expectRevert(Registry.InvalidPhase.selector);
        r.register{value: 2 * BOND}(2);
        assertEq(r.available(m), 2);
    }

    function testSampleDistinctOrderedAndExcludes() public {
        for (uint256 i; i < 10; ++i) join(i, 1);
        address ex = address(uint160(0xB000));
        (bool ok, address[] memory o) = r.reserveSample(1, keccak256("s"), keccak256("d"), 10, 6, ex, address(0));
        assertTrue(ok);
        assertEq(o.length, 6);
        for (uint256 i; i < 6; ++i) {
            assertTrue(o[i] != ex);
            for (uint256 j; j < i; ++j) assertTrue(o[i] != o[j]);
            assertEq(r.available(o[i]), 0);
        }
    }

    function testInsufficientReturnsFalseWithoutStateChange() public {
        for (uint256 i; i < 5; ++i) join(i, 1);
        (bool ok, address[] memory o) = r.reserveSample(1, keccak256("s"), keccak256("d"), 5, 6, address(0), address(0));
        assertFalse(ok);
        assertEq(o.length, 0);
        for (uint256 i; i < 5; ++i) assertEq(r.available(address(uint160(0xB000 + i))), 1);
    }

    function testFullCapacityAndExitedEntriesSkipped() public {
        for (uint256 i; i < 6; ++i) join(i, 1);
        vm.prank(address(uint160(0xB000))); r.requestExit();
        (bool ok,) = r.reserveSample(1, keccak256("s"), keccak256("d"), 6, 5, address(0), address(0));
        assertTrue(ok);
        (bool ok2,) = r.reserveSample(2, keccak256("s2"), keccak256("d"), 6, 1, address(0), address(0));
        assertFalse(ok2); // everyone eligible is now full
    }

    function testReleaseExceptThenReleaseAllExactlyOnce() public {
        for (uint256 i; i < 6; ++i) join(i, 1);
        (, address[] memory o) = r.reserveSample(1, keccak256("s"), keccak256("d"), 6, 6, address(0), address(0));
        address[] memory keep = new address[](4);
        for (uint256 i; i < 4; ++i) keep[i] = o[i];
        r.releaseExcept(1, keep);
        assertEq(r.available(o[4]), 1);
        assertEq(r.available(o[5]), 1);
        assertEq(r.available(o[0]), 0);
        r.releaseExcept(1, keep); // idempotent
        assertEq(r.available(o[4]), 1);
        r.releaseAll(1);
        for (uint256 i; i < 6; ++i) assertEq(r.available(o[i]), 1);
        vm.expectRevert(Registry.InvalidPhase.selector);
        r.releaseAll(1);
        vm.expectRevert(Registry.InvalidInput.selector);
        r.reserveSample(1, keccak256("s"), keccak256("d"), 6, 1, address(0), address(0));
    }

    function testOnlyMarketReserves() public {
        join(0, 1);
        vm.prank(address(0xBAD));
        vm.expectRevert(Registry.Unauthorized.selector);
        r.reserveSample(1, keccak256("s"), keccak256("d"), 1, 1, address(0), address(0));
    }

    function testCapacityCannotDropBelowReserved() public {
        address m = join(0, 2);
        (bool ok,) = r.reserveSample(1, keccak256("s"), keccak256("d"), 1, 1, address(0), address(0));
        (bool ok2,) = r.reserveSample(2, keccak256("s"), keccak256("d"), 1, 1, address(0), address(0));
        assertTrue(ok && ok2);
        vm.prank(m);
        vm.expectRevert(Registry.CapacityExceeded.selector);
        r.updateBond(1);
        vm.prank(m);
        r.updateBond{value: BOND}(3); // top-up raises capacity
    }

    function testExitLifecycleAndReregister() public {
        address m = join(0, 1);
        vm.prank(m); r.requestExit();
        assertEq(r.activeEntries(), 0);
        vm.prank(m); r.completeExit();
        assertEq(r.withdrawable(m), BOND);
        uint256 before = m.balance;
        vm.prank(m); r.withdraw();
        assertEq(m.balance - before, BOND);
        vm.prank(m); r.register{value: BOND}(1);
        assertEq(r.rosterLength(), 2); // new append-only entry
        (address old, bool active) = r.entryAt(0);
        assertEq(old, m);
        assertFalse(active);
    }

    /// @dev Statistical smoke check (fixture): over 200 seeds each of 10 entries
    /// is drawn into a 3-seat sample at least once and no more than 2x its mean.
    /// Not a proof of uniformity; see SMART_CONTRACT_AUDIT.md for the argument.
    function testSamplingRoughUniformity() public {
        for (uint256 i; i < 10; ++i) join(i, 64);
        uint256[10] memory hits;
        for (uint256 s; s < 200; ++s) {
            (bool ok, address[] memory o) = r.reserveSample(s + 1, keccak256(abi.encode(s)), keccak256("d"), 10, 3, address(0), address(0));
            assertTrue(ok);
            for (uint256 i; i < 3; ++i) hits[uint160(o[i]) - 0xB000]++;
            r.releaseAll(s + 1);
        }
        for (uint256 i; i < 10; ++i) {
            assertGt(hits[i], 0);
            assertLt(hits[i], 120); // mean 60
        }
    }

    function testFuzzReservationAccounting(uint8 n, uint8 k, bytes32 seed) public {
        uint256 pop = bound(uint256(n), 1, 30);
        uint256 cnt = bound(uint256(k), 1, 30);
        for (uint256 i; i < pop; ++i) join(i, 1);
        (bool ok, address[] memory o) = r.reserveSample(7, seed, keccak256("d"), pop, cnt, address(0), address(0));
        uint256 reserved;
        for (uint256 i; i < pop; ++i) {
            (,, uint256 res,,) = r.position(address(uint160(0xB000 + i)));
            reserved += res;
        }
        assertEq(reserved, ok ? cnt : 0);
        if (ok) assertEq(o.length, cnt);
        (uint256 bal, uint256 out, bool cov) = r.bondAccounting();
        assertTrue(cov);
        assertEq(bal, out);
    }

    /// @dev EIP-170 runtime (24576) and EIP-3860 initcode (49152) gates.
    function testBytecodeSizeLimits() public {
        vm.chainId(31340);
        address predicted = vm.computeCreateAddress(address(this), uint256(vm.getNonce(address(this))) + 4);
        Board b = new Board(predicted);
        Registry g = new Registry(predicted, BOND);
        V v = new V(predicted);
        Standby s = new Standby(predicted);
        M m = new M(b, g, s, v);
        assertLe(address(m).code.length, 24576, "market runtime > EIP-170");
        assertLe(address(b).code.length, 24576);
        assertLe(address(g).code.length, 24576);
        assertLe(address(v).code.length, 24576);
        assertLe(address(s).code.length, 24576);
        assertLe(type(M).creationCode.length, 49152, "market initcode > EIP-3860");
        emit log_named_uint("market runtime bytes", address(m).code.length);
    }
}
