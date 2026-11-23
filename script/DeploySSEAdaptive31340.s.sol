// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import {SSEAdaptiveMarketV2} from "../contracts/SSEAdaptiveMarketV2.sol";
import {SSEAdaptiveVoteLedger} from "../contracts/SSEAdaptiveVoteLedger.sol";

/// @notice Strict chain31340 research V2 deployment, NEVER Ethereum Mainnet.
/// @dev Not an approval to broadcast. R195 V1 fixed-4/3 is OBSOLETE for
/// the intended adaptive SSE. This is a single market contract which creates
/// one immutable dynamically funded vote ledger in its own constructor.
/// Operator must independently verify genesis, codehashes, wallet funding,
/// local Foundry tests, and authorize use of a separate TEST-ONLY EOA.
/// The contract models bonded EOA monitor candidates, NOT physical identity.
/// Delayed Ethereum blockhash selection is PROPOSER-BIASABLE, NOT VRF.
contract DeploySSEAdaptive31340 is Script {
    uint256 public constant REQUIRED_CHAIN = 31340;

    event MarketV2Deployed(address indexed market, address indexed voteLedger, uint256 minimumBond);

    function run() external returns (SSEAdaptiveMarketV2 market, SSEAdaptiveVoteLedger ledger) {
        require(block.chainid == REQUIRED_CHAIN, "SSE: unexpected chain ID");
        uint256 minimumBondWei = vm.envUint("SSE_V2_MIN_MONITOR_BOND_WEI");
        require(minimumBondWei > 0, "SSE: missing real bond");
        vm.startBroadcast();
        market = new SSEAdaptiveMarketV2(minimumBondWei);
        vm.stopBroadcast();
        ledger = market.votes();
        require(address(ledger) != address(0) && address(ledger).code.length > 0,
                "SSE: missing on-chain adaptive ledger");
        require(ledger.settlement() == address(market),
                "SSE: adaptive ledger incorrectly wired");
        emit MarketV2Deployed(address(market), address(ledger), minimumBondWei);
    }
}
