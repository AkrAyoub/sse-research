// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "forge-std/console2.sol";
import {OpenMonitorCommittee} from "../../contracts/OpenMonitorCommittee.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";
import {SSEVRFV25Adapter} from "../../contracts/SSEVRFV25Adapter.sol";
import {MockVRFV25Coordinator} from "../mocks/MockVRFV25Coordinator.sol";
import {GlobalRosterMerkle} from "../../contracts/GlobalRosterMerkle.sol";

/// @notice WP09N successful-call microbenchmarks. Never deploy to a network.
/// @dev Each gasleft() difference measures the caller frame and the nested call,
///      excluding the intrinsic 21k transaction gas and live-chain overhead.
///      All setup is OUTSIDE the measured region. Mock VRF proves no entropy.
contract WP09NGasBench is Test {
    uint256 private constant BOND = 1 ether;
    uint256 private constant FEE = 0.001 ether;
    uint256 private constant CAPACITY = 1 << 20;
    address private constant CONSUMER = address(0xA100);
    address private constant PROVIDER = address(0xB100);
    address private constant REQUESTER = address(0xDADA);

    // Historical Merkle tree is only used by tests that run a GLOBAL election.
    mapping(uint256 => bytes32) private historicalTree;
    address[] private historicalRoster;

    function setUp() public {
        vm.roll(100);
        vm.warp(100_000);
        vm.deal(CONSUMER, 10 ether);
        vm.deal(PROVIDER, 10 ether);
        vm.deal(REQUESTER, 1 ether);
    }

    function _register(OpenMonitorCommittee pool, uint256 n, bool globalMode)
        internal
    {
        for (uint256 i; i < n; ++i) {
            address member = address(uint160(0xC100 + i));
            vm.deal(member, 2 ether);
            vm.prank(member);
            pool.register{value: BOND}();
            if (globalMode) {
                historicalRoster.push(member);
                GlobalRosterMerkle.write(historicalTree, i, member);
            }
        }
    }

    function _poolAndSettlement(bool globalMode, bool vrfMode)
        internal returns (OpenMonitorCommittee pool, SSESettlement settlement,
                          SSEVRFV25Adapter adapter, MockVRFV25Coordinator coordinator)
    {
        address source = address(0xD1CE);
        if (vrfMode) {
            coordinator = new MockVRFV25Coordinator();
            adapter = new SSEVRFV25Adapter(
                address(coordinator), keccak256("WP09N-test-only-key"),
                42, 3, 220_000, false
            );
            source = address(adapter);
        }
        pool = new OpenMonitorCommittee(source, BOND, 7 days, 1 days);
        if (globalMode) pool.enableGlobalMerkleElection();
        settlement = new SSESettlement(address(pool));
        pool.bindSettlement(address(settlement));
        if (vrfMode) {
            adapter.bindPoolAndSettlement(address(pool), address(settlement));
            settlement.configureVrfFeePolicy(FEE, 100);
            settlement.bindRandomnessAdapter(address(adapter));
        }
    }

    function _lease(SSESettlement settlement) internal returns (uint256 leaseId) {
        vm.prank(CONSUMER);
        leaseId = settlement.createLease{value: 25}(
            PROVIDER, keccak256("wp09n-endpoint"), keccak256("wp09n-profile"),
            25, 5, 25, 1, 100, 100, 100
        );
    }

    function _acceptedFundedLease(SSESettlement settlement)
        internal returns (uint256 leaseId)
    {
        leaseId = _lease(settlement);
        vm.prank(PROVIDER);
        settlement.acceptLease(leaseId);
        vm.prank(CONSUMER);
        settlement.fundVrfRequestFee{value: FEE}(leaseId);
    }

    function _registerBench(uint256 n, bool globalMode) internal {
        (OpenMonitorCommittee pool,,,) = _poolAndSettlement(globalMode, false);
        // This measures only the LAST successful registration, with n members
        // already active. Historical Merkle test bookkeeping is not measured.
        _register(pool, n, globalMode);
        address newcomer = address(0xE000);
        vm.deal(newcomer, 2 ether);
        vm.prank(newcomer);
        uint256 beforeGas = gasleft();
        pool.register{value: BOND}();
        uint256 used = beforeGas - gasleft();
        assertEq(pool.candidateCount(), n + 1);
        console2.log("WP09N|register|n_active", n);
        console2.log("WP09N|register|global_mode", globalMode ? 1 : 0);
        console2.log("WP09N|register|gas", used);
    }

    function testBenchRegisterLegacy4() public { _registerBench(4, false); }
    function testBenchRegisterLegacy16() public { _registerBench(16, false); }
    function testBenchRegisterLegacy64() public { _registerBench(64, false); }
    function testBenchRegisterLegacy160() public { _registerBench(160, false); }
    function testBenchRegisterGlobal16() public { _registerBench(16, true); }
    function testBenchRegisterGlobal160() public { _registerBench(160, true); }

    function _leaseBench(uint256 n, bool globalMode) internal {
        (OpenMonitorCommittee pool, SSESettlement settlement,,) =
            _poolAndSettlement(globalMode, false);
        _register(pool, n, globalMode);
        vm.prank(CONSUMER);
        uint256 beforeGas = gasleft();
        uint256 leaseId = settlement.createLease{value: 25}(
            PROVIDER, keccak256("wp09n-endpoint"), keccak256("wp09n-profile"),
            25, 5, 25, 1, 100, 100, 100
        );
        uint256 used = beforeGas - gasleft();
        assertEq(leaseId, 1);
        assertEq(uint8(pool.assignmentStatus(leaseId)),
                 uint8(OpenMonitorCommittee.RequestStatus.AwaitingRandomness));
        console2.log("WP09N|create_lease|n_active", n);
        console2.log("WP09N|create_lease|global_mode", globalMode ? 1 : 0);
        console2.log("WP09N|create_lease|gas", used);
    }

    function testBenchCreateLeaseLegacy4() public { _leaseBench(4, false); }
    function testBenchCreateLeaseLegacy16() public { _leaseBench(16, false); }
    function testBenchCreateLeaseLegacy64() public { _leaseBench(64, false); }
    function testBenchCreateLeaseLegacy160() public { _leaseBench(160, false); }
    function testBenchCreateLeaseGlobal16() public { _leaseBench(16, true); }
    function testBenchCreateLeaseGlobal160() public { _leaseBench(160, true); }

    function testBenchVRFRequestAndApplyLegacy16() public {
        (OpenMonitorCommittee pool, SSESettlement settlement,
         SSEVRFV25Adapter adapter, MockVRFV25Coordinator coordinator) =
            _poolAndSettlement(false, true);
        _register(pool, 16, false);
        uint256 leaseId = _acceptedFundedLease(settlement);
        vm.startPrank(REQUESTER);
        uint256 beforeRequest = gasleft();
        uint256 vrfId = settlement.requestLeaseRandomness(leaseId);
        uint256 requestGas = beforeRequest - gasleft();
        vm.stopPrank();
        assertEq(vrfId, 1);
        uint256[] memory words = new uint256[](1);
        words[0] = 0xBEEF;
        coordinator.deliver(vrfId, words);
        vm.startPrank(REQUESTER);
        uint256 beforeApply = gasleft();
        adapter.applyRandomness(leaseId); // assignmentId==leaseId only in this isolated fixture
        uint256 applyGas = beforeApply - gasleft();
        vm.stopPrank();
        assertEq(uint8(pool.assignmentStatus(leaseId)),
                 uint8(OpenMonitorCommittee.RequestStatus.Assigned));
        console2.log("WP09N|vrf_purchase|n_active", uint256(16));
        console2.log("WP09N|vrf_purchase|gas", requestGas);
        console2.log("WP09N|vrf_apply|gas", applyGas);
    }

    function _proofsForCurrentSnapshot(OpenMonitorCommittee pool, uint256 leaseId)
        internal view returns (address[] memory accounts, bytes32[][] memory paths)
    {
        uint256[] memory indexes = pool.globalDrawIndexes(leaseId);
        accounts = new address[](indexes.length);
        paths = new bytes32[][](indexes.length);
        for (uint256 i; i < indexes.length; ++i) {
            uint256 index = indexes[i];
            accounts[i] = historicalRoster[index];
            paths[i] = new bytes32[](20);
            uint256 node = CAPACITY + index;
            for (uint256 j; j < 20; ++j) {
                paths[i][j] = historicalTree[node ^ 1];
                node >>= 1;
            }
        }
    }

    function _globalFinalizeBench(uint256 n) internal {
        (OpenMonitorCommittee pool, SSESettlement settlement,
         SSEVRFV25Adapter adapter, MockVRFV25Coordinator coordinator) =
            _poolAndSettlement(true, true);
        _register(pool, n, true);
        uint256 leaseId = _acceptedFundedLease(settlement);
        uint256 vrfId = settlement.requestLeaseRandomness(leaseId);
        uint256[] memory words = new uint256[](1);
        words[0] = 0xCAFE;
        coordinator.deliver(vrfId, words);
        adapter.applyRandomness(leaseId);
        (address[] memory accounts, bytes32[][] memory paths) =
            _proofsForCurrentSnapshot(pool, leaseId);
        vm.startPrank(REQUESTER);
        uint256 beforeGas = gasleft();
        pool.finalizeGlobalCommittee(leaseId, accounts, paths);
        uint256 used = beforeGas - gasleft();
        vm.stopPrank();
        assertEq(uint8(pool.assignmentStatus(leaseId)),
                 uint8(OpenMonitorCommittee.RequestStatus.Assigned));
        assertEq(pool.standbyRemaining(leaseId), 6);
        console2.log("WP09N|global_finalize|n_active", n);
        console2.log("WP09N|global_finalize|n_proofs", accounts.length);
        console2.log("WP09N|global_finalize|gas", used);
    }

    function testBenchGlobalFinalize16() public { _globalFinalizeBench(16); }
    function testBenchGlobalFinalize160() public { _globalFinalizeBench(160); }
}
