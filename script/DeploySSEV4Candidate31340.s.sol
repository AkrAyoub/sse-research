// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import {SSEAdaptiveMarketV4} from "../contracts/SSEAdaptiveMarketV4.sol";
import {SSEServiceBoardV4} from "../contracts/SSEServiceBoardV4.sol";
import {SSEMonitorRegistryV4} from "../contracts/SSEMonitorRegistryV4.sol";
import {SSEStandbyCommittee} from "../contracts/SSEStandbyCommittee.sol";
import {SSEAdaptiveVoteLedgerV4Candidate} from "../contracts/SSEAdaptiveVoteLedgerV4Candidate.sol";

/// @notice OWNER-RUN ONLY. Deploys the integrated V4 candidate as a NEW version.
/// @dev SOURCE-ONLY (2026-11-27): never compiled or executed by the coding agent.
/// Not an approval to broadcast. Run first with --fork-url against an isolated
/// chain or simulation; broadcast to chain31340 only after owner review of
/// bytecode sizes, tests and the migration plan (handoff/planning/DEFERRED_RUNTIME_VALIDATION.md).
/// Five CREATEs from one EOA in a fixed nonce order; every module receives the
/// precomputed market address and the market constructor verifies the wiring.
/// If ANY transaction in the sequence fails or another tx from the deployer
/// interleaves, the wiring check reverts the market CREATE; restart with a
/// fresh plan, never re-send blindly.
contract DeploySSEV4Candidate31340 is Script {
    uint256 public constant REQUIRED_CHAIN = 31340;

    function run() external returns (SSEAdaptiveMarketV4 market) {
        require(block.chainid == REQUIRED_CHAIN, "SSE: unexpected chain ID");
        address deployer = vm.envAddress("SSE_V4_DEPLOYER");
        uint256 perSeatBond = vm.envUint("SSE_V4_PER_SEAT_BOND_WEI");
        require(perSeatBond > 0, "SSE: missing bond");
        uint64 nonce = vm.getNonce(deployer);
        address predicted = vm.computeCreateAddress(deployer, uint256(nonce) + 4);

        vm.startBroadcast(deployer);
        SSEServiceBoardV4 board = new SSEServiceBoardV4(predicted);
        SSEMonitorRegistryV4 registry = new SSEMonitorRegistryV4(predicted, perSeatBond);
        SSEAdaptiveVoteLedgerV4Candidate ledger = new SSEAdaptiveVoteLedgerV4Candidate(predicted);
        SSEStandbyCommittee standby = new SSEStandbyCommittee(predicted);
        market = new SSEAdaptiveMarketV4(board, registry, standby, ledger);
        vm.stopBroadcast();

        require(address(market) == predicted, "SSE: nonce drift");
        require(address(market.board()) == address(board) && address(market.registry()) == address(registry) &&
            address(market.standby()) == address(standby) && address(market.votes()) == address(ledger),
            "SSE: wiring");
        console2.log("board", address(board));
        console2.log("registry", address(registry));
        console2.log("ledger", address(ledger));
        console2.log("standby", address(standby));
        console2.log("market", address(market));
        console2.log("runtime bytes market", address(market).code.length);
    }
}
