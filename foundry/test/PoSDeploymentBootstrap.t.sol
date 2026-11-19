// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {OpenMonitorCommittee} from "../../contracts/OpenMonitorCommittee.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";
import {OpenResourceBoard} from "../../contracts/OpenResourceBoard.sol";

/// @dev Regress the live VM4705 R15 Unauthorized() deployment failure.
/// These tests exercise the same pool/settlement/board order as the
/// real chain31339 script, for both R15 legacy and global Merkle modes.
/// The chain's validator admission is entirely outside these contracts.
contract PoSDeploymentBootstrapTest is Test {
    uint256 internal constant BOND = 1e15;

    function _deploy(bool globalMerkle)
        internal
        returns (
            OpenMonitorCommittee pool,
            SSESettlement settlement,
            OpenResourceBoard board
        )
    {
        pool = new OpenMonitorCommittee(
            address(0x000000000000000000000000000000000000dEaD),
            BOND,
            7 days,
            1 days
        );

        // THE CRITICAL ORDER: all irreversible feature opt-ins must
        // happen BEFORE the one-time binding of settlement.
        pool.enableDelayedBlockEntropy();
        if (globalMerkle) {
            pool.enableGlobalMerkleElection();
            pool.enableGlobalBatchedRecovery();
        }

        settlement = new SSESettlement(address(pool));
        board = new OpenResourceBoard();
        pool.bindSettlement(address(settlement));
        settlement.bindResourceBoard(address(board));
        board.bindSettlement(address(settlement));
    }

    function _assertWiring(
        OpenMonitorCommittee pool,
        SSESettlement settlement,
        OpenResourceBoard board,
        bool globalMerkle
    ) internal view {
        assertEq(pool.settlement(), address(settlement));
        assertEq(address(settlement.committeePool()), address(pool));
        assertEq(settlement.resourceBoard(), address(board));
        assertEq(board.approvedSettlement(), address(settlement));
        assertEq(pool.minimumBond(), BOND);
        assertTrue(pool.delayedBlockEntropyEnabled());
        assertEq(pool.globalMerkleElectionEnabled(), globalMerkle);
        assertEq(pool.globalBatchedRecoveryEnabled(), globalMerkle);
    }

    function testLegacyModeBootstrapsBeforeWiring() public {
        (OpenMonitorCommittee pool, SSESettlement settlement, OpenResourceBoard board)
            = _deploy(false);
        _assertWiring(pool, settlement, board, false);
    }

    function testGlobalMerkleBatchedModeBootstrapsBeforeWiring() public {
        (OpenMonitorCommittee pool, SSESettlement settlement, OpenResourceBoard board)
            = _deploy(true);
        _assertWiring(pool, settlement, board, true);
    }

    function testPostBindingLateFeatureChangesRefused() public {
        (OpenMonitorCommittee pool,,) = _deploy(false);
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        pool.enableDelayedBlockEntropy();
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        pool.enableGlobalMerkleElection();
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        pool.enableGlobalBatchedRecovery();
    }
}
