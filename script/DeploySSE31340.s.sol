// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import {OpenMonitorCommittee} from "../contracts/OpenMonitorCommittee.sol";
import {SSESettlement} from "../contracts/SSESettlement.sol";
import {OpenResourceBoard} from "../contracts/OpenResourceBoard.sol";

/// @title SSE live original chain31340 marketplace deployment
/// @notice Deploys on the empirically verified original live chain31340 using TEST ETH only.
/// @dev One-time atomic-in-order setup is performed by the funded deployer
/// across broadcast transactions; do NOT consider deployment successful
/// until all binding transactions are mined and independently verified.
/// There is no administrator permission to register as consumer/provider/monitor
/// once the one-time wiring is complete. Ethereum's consensus-layer staking,
/// not SSE, controls validator activation and slot proposals.
contract DeploySSE31340 is Script {
    uint256 public constant OWN_SSE_POS_CHAIN = 31340;
    address public constant DISABLED_LEGACY_RANDOMNESS_SOURCE =
        address(0x000000000000000000000000000000000000dEaD);

    event SSEOwnPosContractsDeployed(
        uint256 indexed chainId,
        address indexed committee,
        address indexed settlement,
        address board,
        bool globalMerkle,
        bool delayedBlockEntropy
    );

    function run()
        external
        returns (
            OpenMonitorCommittee committee,
            SSESettlement settlement,
            OpenResourceBoard board
        )
    {
        require(block.chainid == OWN_SSE_POS_CHAIN, "SSE: wrong chain");
        uint256 minimumBond = vm.envOr("SSE_MIN_MONITOR_BOND_WEI", uint256(1e15));
        uint64 exitDelay = uint64(vm.envOr("SSE_EXIT_DELAY_SECONDS", uint256(604800)));
        uint64 randomnessTimeout = uint64(
            vm.envOr("SSE_RANDOMNESS_TIMEOUT_SECONDS", uint256(86400))
        );
        bool useGlobalMerkle = vm.envOr("SSE_USE_GLOBAL_MERKLE", false);
        require(minimumBond > 0, "SSE: no free Sybil registrations");
        require(
            exitDelay > randomnessTimeout && randomnessTimeout >= 300,
            "SSE: invalid deadlines"
        );

        // No private key is included in this script or GitHub. Use an
        // interactive local Foundry keystore and pin --sender to the EOA.
        vm.startBroadcast();
        committee = new OpenMonitorCommittee(
            DISABLED_LEGACY_RANDOMNESS_SOURCE,
            minimumBond,
            exitDelay,
            randomnessTimeout
        );

        // Bootstrap MUST happen before bindSettlement(). The pool
        // rejects both entropy-mode changes and global-election opt-in
        // after settlement is wired, by design. The former R15 script
        // bound settlement first and reverted Unauthorized() during
        // both simulation and --broadcast preflight.
        //
        // Delayed future-block entropy avoids a privileged seed writer,
        // but remains proposer-biasable. It is a research baseline
        // rather than an unbiased production VRF.
        committee.enableDelayedBlockEntropy();
        if (useGlobalMerkle) {
            committee.enableGlobalMerkleElection();
            committee.enableGlobalBatchedRecovery();
        }

        settlement = new SSESettlement(address(committee));
        board = new OpenResourceBoard();
        committee.bindSettlement(address(settlement));
        settlement.bindResourceBoard(address(board));
        board.bindSettlement(address(settlement));
        vm.stopBroadcast();

        require(committee.settlement() == address(settlement), "SSE: pool not bound");
        require(settlement.resourceBoard() == address(board), "SSE: board not linked");
        require(board.approvedSettlement() == address(settlement), "SSE: board not bound");
        require(committee.delayedBlockEntropyEnabled(), "SSE: unsafe entropy mode");
        require(committee.globalMerkleElectionEnabled() == useGlobalMerkle,
                "SSE: wrong election mode");
        require(committee.globalBatchedRecoveryEnabled() == useGlobalMerkle,
                "SSE: wrong batched recovery mode");

        emit SSEOwnPosContractsDeployed(
            block.chainid,
            address(committee), address(settlement), address(board),
            useGlobalMerkle, true
        );
    }
}
