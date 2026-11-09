// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {OpenMonitorCommittee} from "../../contracts/OpenMonitorCommittee.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";

/**
 * @notice Research-prototype acceptance tests for Milestone 3.
 * @dev They test the CURRENT 3-of-4 adapter; they do not establish
 *      independent organizations, Sybil resistance or evidence truth.
 */
contract Milestone3ProtocolTest is Test {
    OpenMonitorCommittee internal committee;
    SSESettlement internal settlement;
    address internal consumer = address(0xA101);
    uint256 internal constant PROVIDER_KEY = 0xB101;
    address internal provider;
    address[5] internal monitors;

    bytes32 internal constant ACK_TYPEHASH =
        keccak256("ProviderAck(uint256 leaseId,uint256 epochId,bytes32 requestHash)");

    function setUp() public {
        vm.warp(10000);
        provider = vm.addr(PROVIDER_KEY);
        committee = new OpenMonitorCommittee(address(this), 1 ether, 7 days, 1 days);
        settlement = new SSESettlement(address(committee));
        committee.bindSettlement(address(settlement));
        vm.deal(consumer, 100 ether);
        vm.deal(provider, 100 ether);
        for (uint256 i; i < monitors.length; ++i) {
            address monitor = address(uint160(0xC100 + i));
            monitors[i] = monitor;
            vm.deal(monitor, 2 ether);
            vm.prank(monitor);
            committee.register{value: 1 ether}();
        }
    }

    function _lease(uint256 maxEpochs, uint256 exposureBudget) internal returns (uint256 id) {
        vm.prank(consumer);
        id = settlement.createLease{value: 25 * maxEpochs}(
            provider, keccak256("endpoint"), keccak256("profile"),
            25, 5, exposureBudget, maxEpochs, 100, 100, 100
        );
    }

    function _ready(uint256 maxEpochs, uint256 exposureBudget) internal returns (uint256 id) {
        id = _lease(maxEpochs, exposureBudget);
        vm.prank(provider);
        settlement.acceptLease(id);
        committee.fulfillRandomness(id, 1234);
        // Any address may apply a correctly assigned committee.
        vm.prank(address(0xDEAD));
        settlement.finalizeMonitorCommittee(id);
        address[4] memory selected = committee.getCommittee(id);
        for (uint256 i; i < selected.length; ++i) {
            vm.prank(selected[i]);
            settlement.confirmMonitorAssignment(id);
        }
    }

    function _admit(uint256 id) internal returns (SSESettlement.Epoch memory epoch) {
        vm.prank(consumer);
        settlement.admitEpoch(id, keccak256(abi.encodePacked("challenge", id)));
        epoch = settlement.getEpoch(id, 0);
    }

    function _failureVotes(uint256 id, uint256 count) internal {
        address[4] memory selected = committee.getCommittee(id);
        for (uint256 i; i < count; ++i) {
            vm.prank(selected[i]);
            settlement.submitMonitorVoteDirect(
                id, 0, SSESettlement.Outcome.Failure, keccak256(abi.encode(i + 1))
            );
        }
    }

    function testBondedRegistrationIsOpenButVoteAuthorityIsLeaseSpecific() public {
        uint256 id = _ready(1, 25);
        SSESettlement.Epoch memory epoch = _admit(id);
        vm.warp(uint256(epoch.responseDeadline) + 1);
        vm.prank(address(0xBEEF));
        vm.expectRevert(SSESettlement.Unauthorized.selector);
        settlement.submitMonitorVoteDirect(
            id, 0, SSESettlement.Outcome.Failure, keccak256("unselected")
        );
        assertEq(committee.candidateCount(), 5);
    }

    function testAnyoneCanApplyAuthorizedAssignment() public {
        uint256 id = _ready(1, 25);
        SSESettlement.Lease memory lease = settlement.getLease(id);
        assertEq(uint8(lease.state), uint8(SSESettlement.LeaseState.Ready));
        assertEq(lease.monitorConfirmations, 4);
    }

    function testTwoVotesAreNotAQuorum() public {
        uint256 id = _ready(1, 25);
        SSESettlement.Epoch memory epoch = _admit(id);
        vm.warp(uint256(epoch.responseDeadline) + 1);
        _failureVotes(id, 2);
        vm.warp(uint256(epoch.evidenceClose) + 1);
        settlement.closeEpochEvidence(id, 0);
        SSESettlement.Epoch memory afterEpoch = settlement.getEpoch(id, 0);
        assertEq(uint8(afterEpoch.outcome), uint8(SSESettlement.Outcome.None));
        assertEq(afterEpoch.unresolvedExposure, 25);
        assertEq(afterEpoch.providerCredited, 0);
        assertEq(afterEpoch.consumerCredited, 0);
    }

    function testThreeFailureVotesResultInConservativePartialRefund() public {
        uint256 id = _ready(1, 25);
        SSESettlement.Epoch memory epoch = _admit(id);
        vm.warp(uint256(epoch.responseDeadline) + 1);
        _failureVotes(id, 3);
        vm.warp(uint256(epoch.monitoringClose) + 1);
        settlement.sealMonitoring(id, 0);
        vm.prank(address(0xDEAD));
        settlement.settleEpoch(id, 0);
        SSESettlement.Epoch memory afterEpoch = settlement.getEpoch(id, 0);
        assertEq(uint8(afterEpoch.outcome), uint8(SSESettlement.Outcome.Failure));
        assertEq(afterEpoch.providerCredited, 0);
        assertEq(afterEpoch.consumerCredited, 20);
        assertEq(afterEpoch.unresolvedExposure, 5);
    }

    function testAuthenticatedLateAckRefinesFailureAndCreditsRemainingRefund() public {
        uint256 id = _ready(1, 25);
        SSESettlement.Epoch memory epoch = _admit(id);
        vm.warp(uint256(epoch.responseDeadline) + 1);
        _failureVotes(id, 3);
        vm.warp(uint256(epoch.monitoringClose) + 1);
        settlement.sealMonitoring(id, 0);
        settlement.settleEpoch(id, 0);
        bytes32 structHash = keccak256(abi.encode(
            ACK_TYPEHASH, id, uint256(0), epoch.requestHash
        ));
        bytes32 digest = keccak256(abi.encodePacked(
            "\x19\x01", settlement.domainSeparator(), structHash
        ));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(PROVIDER_KEY, digest);
        settlement.submitAcknowledgment(id, 0, abi.encodePacked(r, s, v));
        settlement.settleEpoch(id, 0);
        SSESettlement.Epoch memory afterEpoch = settlement.getEpoch(id, 0);
        assertEq(afterEpoch.consumerCredited, 25);
        assertEq(afterEpoch.providerCredited, 0);
        assertEq(afterEpoch.unresolvedExposure, 0);
        assertEq(settlement.withdrawable(consumer), 25);
    }

    function testEpochAdmissionRespectsExposureBudget() public {
        uint256 id = _ready(2, 25);
        _admit(id);
        vm.prank(consumer);
        vm.expectRevert(SSESettlement.ExposureExceeded.selector);
        settlement.admitEpoch(id, keccak256("second challenge"));
    }

    function testNonProviderCannotAcceptLease() public {
        uint256 id = _lease(1, 25);
        vm.prank(address(0xDEAD));
        vm.expectRevert(SSESettlement.Unauthorized.selector);
        settlement.acceptLease(id);
    }
}
