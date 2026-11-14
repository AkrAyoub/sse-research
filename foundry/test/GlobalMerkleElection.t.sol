// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {OpenMonitorCommittee} from "../../contracts/OpenMonitorCommittee.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";
import {GlobalRosterMerkle} from "../../contracts/GlobalRosterMerkle.sol";
import {GlobalRosterSampler} from "../../contracts/GlobalRosterSampler.sol";

/// @notice WP09E: global frozen indexed selection, adversarial proof and
/// membership churn; no claim about VRF entropy or independent operators.
contract GlobalMerkleElectionTest is Test {
    OpenMonitorCommittee pool;
    SSESettlement settlement;
    address consumer = address(0xA101);
    address provider = address(0xB101);
    address outsider = address(0xDADA);
    uint256 constant BOND = 1 ether;
    uint256 constant DEPTH = 20;
    uint256 constant CAPACITY = 1 << DEPTH;

    mapping(uint256 => bytes32) private historicalTree;
    address[] private historicalRoster;

    function setUp() public {
        vm.roll(100);
        vm.warp(100_000);
        pool = new OpenMonitorCommittee(address(this), BOND, 7 days, 1 days);
        pool.enableGlobalMerkleElection();
        settlement = new SSESettlement(address(pool));
        pool.bindSettlement(address(settlement));
        vm.deal(consumer, 10 ether);
        vm.deal(provider, 10 ether);
    }

    function _register(address who) internal {
        vm.deal(who, 2 ether);
        vm.prank(who);
        pool.register{value: BOND}();
        historicalRoster.push(who);
        GlobalRosterMerkle.write(historicalTree, historicalRoster.length - 1, who);
        assertEq(pool.globalRosterRoot(), historicalTree[1]);
    }

    function _registerMany(uint256 number) internal {
        for (uint256 i; i < number; ++i) {
            _register(address(uint160(0xC100 + i)));
        }
    }

    function _lease() internal returns (uint256 id) {
        vm.prank(consumer);
        id = settlement.createLease{value: 25}(
            provider, keccak256("global-merkle-endpoint"), keccak256("global-merkle-profile"),
            25, 5, 25, 1, 100, 100, 100
        );
    }

    function _prove(uint256 id)
        internal view returns (address[] memory accounts, bytes32[][] memory paths)
    {
        uint256[] memory indexes = pool.globalDrawIndexes(id);
        accounts = new address[](indexes.length);
        paths = new bytes32[][](indexes.length);
        for (uint256 i; i < indexes.length; ++i) {
            uint256 index = indexes[i];
            accounts[i] = historicalRoster[index];
            paths[i] = new bytes32[](DEPTH);
            uint256 node = CAPACITY + index;
            for (uint256 j; j < DEPTH; ++j) {
                paths[i][j] = historicalTree[node ^ 1];
                node >>= 1;
            }
        }
    }

    function testGlobalRootCovers80ActivesAndSamplesBeyondFormer64Window() public {
        _registerMany(80);
        assertEq(pool.candidateCount(), 80);
        assertEq(pool.globalRosterRoot(), historicalTree[1]);
        uint256 id = _lease();
        assertEq(id, 1);
        assertEq(pool.globalSnapshotRoot(id), historicalTree[1]);
        assertEq(pool.globalSnapshotCount(id), 80);
        assertEq(pool.snapshotSize(id), 0); // no 64-entry pending lock scan
        for (uint256 i; i < 80; ++i) {
            (,,uint32 pending,,,) = pool.candidates(historicalRoster[i]);
            assertEq(pending, 0);
        }

        uint256 chosenSeed;
        for (uint256 seed = 1; seed < 64; ++seed) {
            uint256[] memory sample = GlobalRosterSampler.draw(seed, id, 80, 10);
            for (uint256 i; i < sample.length; ++i) {
                if (sample[i] >= 64) { chosenSeed = seed; break; }
            }
            if (chosenSeed != 0) break;
        }
        assertTrue(chosenSeed != 0);
        pool.fulfillRandomness(id, chosenSeed); // legacy-mode lab-only seed
        uint256[] memory indexes = pool.globalDrawIndexes(id);
        assertEq(indexes.length, 10);
        bool sampleBeyond64;
        for (uint256 i; i < indexes.length; ++i) {
            if (indexes[i] >= 64) sampleBeyond64 = true;
            for (uint256 j; j < i; ++j) assertTrue(indexes[i] != indexes[j]);
        }
        assertTrue(sampleBeyond64);
        (address[] memory accounts, bytes32[][] memory paths) = _prove(id);
        vm.prank(outsider);
        pool.finalizeGlobalCommittee(id, accounts, paths);
        assertEq(uint8(pool.assignmentStatus(id)),
                 uint8(OpenMonitorCommittee.RequestStatus.Assigned));
        assertEq(pool.standbyRemaining(id), 6);
        address[4] memory selected = pool.getCommittee(id);
        for (uint256 i; i < 4; ++i) assertEq(selected[i], accounts[i]);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.globalDrawIndexes(id);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.finalizeGlobalCommittee(id, accounts, paths);
    }

    function testMalformedOrCallerChosenGlobalProofFailsClosed() public {
        _registerMany(7);
        uint256 id = _lease();
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.globalDrawIndexes(id);
        pool.fulfillRandomness(id, 17);
        (address[] memory accounts, bytes32[][] memory paths) = _prove(id);
        address original = accounts[0];
        accounts[0] = outsider;
        vm.expectRevert(OpenMonitorCommittee.InvalidGlobalProof.selector);
        pool.finalizeGlobalCommittee(id, accounts, paths);
        accounts[0] = original;

        bytes32 originalSibling = paths[0][0];
        paths[0][0] = bytes32(uint256(1));
        vm.expectRevert(OpenMonitorCommittee.InvalidGlobalProof.selector);
        pool.finalizeGlobalCommittee(id, accounts, paths);
        paths[0][0] = originalSibling;

        (accounts[0], accounts[1]) = (accounts[1], accounts[0]);
        vm.expectRevert(OpenMonitorCommittee.InvalidGlobalProof.selector);
        pool.finalizeGlobalCommittee(id, accounts, paths);
        (accounts[0], accounts[1]) = (accounts[1], accounts[0]);

        vm.prank(outsider);
        pool.finalizeGlobalCommittee(id, accounts, paths);
        assertEq(pool.standbyRemaining(id), 3);
    }

    function testRosterSwapPopAndHistoricalSnapshotCannotBeRewritten() public {
        _registerMany(8);
        uint256 id = _lease();
        bytes32 previousRoot = pool.globalSnapshotRoot(id);
        pool.fulfillRandomness(id, 17);
        uint256[] memory indexes = pool.globalDrawIndexes(id);
        address removed = historicalRoster[indexes[0]];
        address moved = historicalRoster[historicalRoster.length - 1];
        vm.prank(removed);
        pool.requestExit();
        assertEq(pool.candidateCount(), 7);
        assertEq(pool.globalSnapshotRoot(id), previousRoot);
        assertTrue(pool.globalRosterRoot() != previousRoot);
        assertEq(pool.activeSlot(removed), 0);
        if (removed != moved) {
            assertEq(pool.candidateAt(indexes[0]), moved);
        }
        // These are PRE-EXIT proofs, reconstructed from historical state.
        (address[] memory accounts, bytes32[][] memory paths) = _prove(id);
        assertEq(accounts[0], removed);
        pool.finalizeGlobalCommittee(id, accounts, paths);
        address[4] memory selected = pool.getCommittee(id);
        for (uint256 i; i < 4; ++i) assertTrue(selected[i] != removed);
        assertEq(pool.standbyRemaining(id), 3);
        (,,,uint32 locked,,) = pool.candidates(removed);
        assertEq(locked, 0);
        for (uint256 i; i < 4; ++i) {
            vm.prank(selected[i]);
            vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
            pool.requestExit();
        }
    }

    function testGlobalPartiesExcludedAndActualNoShowRecoveryWorks() public {
        _registerMany(5);
        _register(consumer);
        _register(provider);
        uint256 id = _lease();
        vm.prank(provider);
        settlement.acceptLease(id);
        pool.fulfillRandomness(id, 19);
        (address[] memory accounts, bytes32[][] memory paths) = _prove(id);
        pool.finalizeGlobalCommittee(id, accounts, paths);
        settlement.finalizeMonitorCommittee(id);
        address[4] memory selected = pool.getCommittee(id);
        for (uint256 i; i < 4; ++i)
            assertTrue(selected[i] != consumer && selected[i] != provider);
        assertEq(pool.standbyRemaining(id), 1);
        for (uint256 i; i < 3; ++i) {
            vm.prank(selected[i]);
            settlement.confirmMonitorAssignment(id);
        }
        vm.prank(consumer);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.admitEpoch(id, keccak256("not-confirmed"));
        vm.warp(settlement.monitorConfirmationDeadline(id) + 1);
        vm.prank(outsider);
        settlement.replaceNoShowMonitor(id);
        address[4] memory replacement = pool.getCommittee(id);
        assertTrue(replacement[3] != selected[3]);
        vm.prank(replacement[3]);
        settlement.confirmMonitorAssignment(id);
        assertEq(uint8(settlement.getLease(id).state),
                 uint8(SSESettlement.LeaseState.Ready));
        vm.prank(consumer);
        settlement.admitEpoch(id, keccak256("ready-now"));
        assertEq(settlement.getLease(id).nextEpochId, 1);
    }

    function testGlobalInsufficientExcludingPartiesRevertsAtomically() public {
        _registerMany(3);
        _register(consumer);
        _register(provider);
        vm.prank(consumer);
        vm.expectRevert(OpenMonitorCommittee.InsufficientCandidates.selector);
        settlement.createLease{value: 25}(
            provider, keccak256("too-few"), keccak256("profile"),
            25, 5, 25, 1, 100, 100, 100
        );
        assertEq(pool.nextAssignmentId(), 1);
        assertEq(pool.globalRosterRoot(), historicalTree[1]);
        assertEq(address(settlement).balance, 0);
    }

    function testUnrevealedOrUnprovenEntropyCanExpireAndRefundWithoutBondLocks() public {
        _registerMany(6);
        uint256 id = _lease();
        pool.fulfillRandomness(id, 42);
        assertTrue(pool.pendingGlobalSeedReady(id));
        vm.warp(block.timestamp + pool.randomnessTimeout() + 1);
        (address[] memory accounts, bytes32[][] memory paths) = _proveExpiredSnapshot(id);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.finalizeGlobalCommittee(id, accounts, paths);
        pool.expire(id);
        assertFalse(pool.pendingGlobalSeedReady(id));
        assertEq(uint8(pool.assignmentStatus(id)),
                 uint8(OpenMonitorCommittee.RequestStatus.Expired));
        vm.prank(consumer);
        settlement.closeLease(id);
        assertEq(settlement.withdrawable(consumer), 25);
        for (uint256 i; i < 6; ++i) {
            (,,uint32 pending,uint32 locked,,) = pool.candidates(historicalRoster[i]);
            assertEq(pending, 0);
            assertEq(locked, 0);
        }
    }

    function _proveExpiredSnapshot(uint256 id)
        internal view returns (address[] memory accounts, bytes32[][] memory paths)
    {
        return _prove(id);
    }

    function testGlobalOptInMustPrecedeRegistrationAndSettlementBinding() public {
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        pool.enableGlobalMerkleElection();
        OpenMonitorCommittee another =
            new OpenMonitorCommittee(address(this), BOND, 7 days, 1 days);
        vm.deal(outsider, 2 ether);
        vm.prank(outsider);
        another.register{value: BOND}();
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        another.enableGlobalMerkleElection();
        vm.prank(outsider);
        another.requestExit();
        vm.warp(block.timestamp + another.exitDelay() + 1);
        vm.prank(outsider);
        another.withdrawBond();
        assertEq(another.candidateCount(), 0);
        // Even after every candidate withdraws, enrollment history means
        // the global tree has not tracked the complete prior mutation log.
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        another.enableGlobalMerkleElection();
    }
}
