// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {OpenMonitorCommittee} from "../../contracts/OpenMonitorCommittee.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";

/**
 * @notice Research extension tests for separately prefunded protocol rewards
 *         and the two-party residual escrow agreement.
 * @dev These test contract-side safety rules, not truthful off-chain monitoring.
 */
contract ProtocolEconomicsTest is Test {
    uint256 internal constant CONSUMER_KEY = 0xA1001;
    uint256 internal constant PROVIDER_KEY = 0xB1001;
    uint256 internal constant ATTACKER_KEY = 0xBAD01;
    bytes32 internal constant RESIDUAL_TYPEHASH = keccak256(
        "ResidualAgreement(uint256 leaseId,uint256 epochId,uint256 unresolvedAmount,uint256 providerShare,uint256 consumerShare,uint256 nonce,uint256 expiry)"
    );
    bytes32 internal constant RESPONSE_TYPEHASH = keccak256(
        "ProviderResponse(uint256 leaseId,uint256 epochId,bytes32 requestHash,bytes32 responseHash)"
    );

    OpenMonitorCommittee internal committee;
    SSESettlement internal settlement;
    address internal consumer;
    address internal provider;
    address internal executor = address(0xEEE0);
    address internal anotherExecutor = address(0xEEE1);
    address[5] internal candidates;

    function setUp() public {
        vm.warp(10_000);
        consumer = vm.addr(CONSUMER_KEY);
        provider = vm.addr(PROVIDER_KEY);
        committee = new OpenMonitorCommittee(address(this), 1 ether, 7 days, 1 days);
        settlement = new SSESettlement(address(committee));
        committee.bindSettlement(address(settlement));
        vm.deal(consumer, 100 ether);
        vm.deal(provider, 100 ether);
        for (uint256 i; i < candidates.length; ++i) {
            candidates[i] = address(uint160(0xD001 + i));
            vm.deal(candidates[i], 2 ether);
            vm.prank(candidates[i]);
            committee.register{value: 1 ether}();
        }
    }

    function _create(uint256 maxEpochs, bool funded) internal returns (uint256 id) {
        vm.prank(consumer);
        id = settlement.createLease{value: maxEpochs * 25}(
            provider, keccak256("service-endpoint"), keccak256("resource-profile"),
            25, 5, 25 * maxEpochs, maxEpochs, 100, 100, 100
        );
        if (funded) {
            // 4 monitor reports per epoch at 2 each, 3 executor actions
            // per epoch at 3+5+7, one release at 11.
            uint256 monitorDeposit = maxEpochs * 4 * 2;
            uint256 executorDeposit = maxEpochs * (3 + 5 + 7) + 11;
            vm.prank(consumer);
            settlement.configureIncentives{value: monitorDeposit + executorDeposit}(
                id, 2, 3, 5, 7, 11
            );
        }
    }

    function _ready(uint256 maxEpochs, bool funded) internal returns (uint256 id) {
        id = _create(maxEpochs, funded);
        vm.prank(provider);
        settlement.acceptLease(id);
        // Test-only trusted randomnessSource, not production verifiable randomness.
        committee.fulfillRandomness(id, 0xC0FFEE);
        settlement.finalizeMonitorCommittee(id);
        address[4] memory selected = committee.getCommittee(id);
        for (uint256 i; i < selected.length; ++i) {
            vm.prank(selected[i]);
            settlement.confirmMonitorAssignment(id);
        }
    }

    function _admit(uint256 leaseId) internal returns (SSESettlement.Epoch memory ep) {
        vm.prank(consumer);
        settlement.admitEpoch(leaseId, keccak256(abi.encode("research-challenge", leaseId)));
        ep = settlement.getEpoch(leaseId, 0);
    }

    function _closeAsAmbiguousFailure(uint256 leaseId) internal {
        SSESettlement.Epoch memory ep = _admit(leaseId);
        vm.warp(uint256(ep.responseDeadline) + 1);
        address[4] memory selected = committee.getCommittee(leaseId);
        for (uint256 i; i < 3; ++i) {
            vm.prank(selected[i]);
            settlement.submitMonitorVoteDirect(
                leaseId, 0, SSESettlement.Outcome.Failure,
                keccak256(abi.encode("negative-evidence", i))
            );
        }
        vm.warp(uint256(ep.evidenceClose) + 1);
        vm.prank(executor);
        settlement.closeEpochEvidence(leaseId, 0);
    }

    function _sign(uint256 key, bytes32 digest) internal returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(key, digest);
        return abi.encodePacked(r, s, v);
    }

    function _residualSignatures(
        uint256 leaseId,
        SSESettlement.ResidualAllocation memory a,
        uint256 consumerKey
    ) internal returns (bytes memory consumerSig, bytes memory providerSig) {
        SSESettlement.Epoch memory ep = settlement.getEpoch(leaseId, 0);
        bytes32 h = keccak256(abi.encode(
            RESIDUAL_TYPEHASH, leaseId, uint256(0), ep.unresolvedExposure,
            a.providerShare, a.consumerShare, a.nonce, a.expiry
        ));
        bytes32 digest = keccak256(abi.encodePacked(
            "\x19\x01", settlement.domainSeparator(), h
        ));
        return (_sign(consumerKey, digest), _sign(PROVIDER_KEY, digest));
    }

    function testResidualAgreementRequiresBothCorrectSignatures() public {
        uint256 id = _ready(1, false);
        _closeAsAmbiguousFailure(id);
        SSESettlement.ResidualAllocation memory a = SSESettlement.ResidualAllocation({
            providerShare: 2, consumerShare: 3, nonce: 1, expiry: block.timestamp + 100
        });
        (bytes memory wrong, bytes memory providerSig) = _residualSignatures(id, a, ATTACKER_KEY);
        vm.expectRevert(SSESettlement.InvalidSignature.selector);
        vm.prank(anotherExecutor);
        settlement.resolveResidualByAgreement(id, 0, a, wrong, providerSig);
        SSESettlement.Epoch memory unchanged = settlement.getEpoch(id, 0);
        assertEq(unchanged.unresolvedExposure, 5);
    }

    function testResidualAgreementRequiresClosedEvidenceAndExactShares() public {
        uint256 id = _ready(1, false);
        SSESettlement.Epoch memory ep = _admit(id);
        SSESettlement.ResidualAllocation memory a = SSESettlement.ResidualAllocation({
            providerShare: 2, consumerShare: 3, nonce: 7, expiry: block.timestamp + 1000
        });
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.resolveResidualByAgreement(id, 0, a, hex"11", hex"22");
        // Even correct dual signatures cannot allocate more than the 5 wei residual.
        vm.warp(uint256(ep.responseDeadline) + 1);
        address[4] memory selected = committee.getCommittee(id);
        for (uint256 i; i < 3; ++i) {
            vm.prank(selected[i]);
            settlement.submitMonitorVoteDirect(id, 0, SSESettlement.Outcome.Failure, keccak256(abi.encode(i + 1)));
        }
        vm.warp(uint256(ep.evidenceClose) + 1);
        settlement.closeEpochEvidence(id, 0);
        a.consumerShare = 4; // Sum=6; invalid independent of signatures.
        vm.expectRevert(SSESettlement.InvalidArgument.selector);
        settlement.resolveResidualByAgreement(id, 0, a, hex"11", hex"22");
    }

    function testJointResidualAgreementConservesFundsAndPreventsReplay() public {
        uint256 id = _ready(1, false);
        _closeAsAmbiguousFailure(id);
        SSESettlement.Epoch memory before = settlement.getEpoch(id, 0);
        assertEq(before.providerCredited, 0);
        assertEq(before.consumerCredited, 20);
        assertEq(before.unresolvedExposure, 5);
        SSESettlement.ResidualAllocation memory a = SSESettlement.ResidualAllocation({
            providerShare: 2, consumerShare: 3, nonce: 7, expiry: block.timestamp + 100
        });
        (bytes memory cSig, bytes memory pSig) = _residualSignatures(id, a, CONSUMER_KEY);
        vm.prank(anotherExecutor);
        settlement.resolveResidualByAgreement(id, 0, a, cSig, pSig);

        SSESettlement.Epoch memory afterEp = settlement.getEpoch(id, 0);
        assertEq(afterEp.providerCredited, 2);
        assertEq(afterEp.consumerCredited, 23);
        assertEq(afterEp.unresolvedExposure, 0);
        SSESettlement.Lease memory lease = settlement.getLease(id);
        assertEq(lease.currentExposure, 0);
        assertEq(settlement.withdrawable(provider), 2);
        assertEq(settlement.withdrawable(consumer), 23);
        assertTrue(settlement.residualResolved(id, 0));
        assertEq(afterEp.providerCredited + afterEp.consumerCredited + afterEp.unresolvedExposure, 25);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.resolveResidualByAgreement(id, 0, a, cSig, pSig);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.settleEpoch(id, 0);
    }

    function testTamperingWithAuthorizedSplitInvalidatesSignatures() public {
        uint256 id = _ready(1, false);
        _closeAsAmbiguousFailure(id);
        SSESettlement.ResidualAllocation memory a = SSESettlement.ResidualAllocation({
            providerShare: 2, consumerShare: 3, nonce: 11, expiry: block.timestamp + 100
        });
        (bytes memory cSig, bytes memory pSig) = _residualSignatures(id, a, CONSUMER_KEY);
        a.providerShare = 1;
        a.consumerShare = 4; // Valid sum, but different from the signed split.
        vm.expectRevert(SSESettlement.InvalidSignature.selector);
        settlement.resolveResidualByAgreement(id, 0, a, cSig, pSig);
    }

    function testFuzzBilateralAgreementConservesEveryPossibleSplit(uint8 rawShare) public {
        uint256 id = _ready(1, false);
        _closeAsAmbiguousFailure(id);
        uint256 providerShare = bound(uint256(rawShare), 0, 5);
        SSESettlement.ResidualAllocation memory a = SSESettlement.ResidualAllocation({
            providerShare: providerShare, consumerShare: 5 - providerShare,
            nonce: 13, expiry: block.timestamp + 100
        });
        (bytes memory cSig, bytes memory pSig) = _residualSignatures(id, a, CONSUMER_KEY);
        settlement.resolveResidualByAgreement(id, 0, a, cSig, pSig);
        SSESettlement.Epoch memory ep = settlement.getEpoch(id, 0);
        assertEq(ep.providerCredited, providerShare);
        assertEq(ep.consumerCredited, 25 - providerShare);
        assertEq(ep.providerCredited + ep.consumerCredited, 25);
        assertEq(ep.unresolvedExposure, 0);
    }

    function testWithdrawAfterJointAgreementTransfersExactlyAllServiceFunds() public {
        uint256 id = _ready(1, false);
        _closeAsAmbiguousFailure(id);
        SSESettlement.ResidualAllocation memory a = SSESettlement.ResidualAllocation({
            providerShare: 2, consumerShare: 3, nonce: 19, expiry: block.timestamp + 100
        });
        (bytes memory cSig, bytes memory pSig) = _residualSignatures(id, a, CONSUMER_KEY);
        settlement.resolveResidualByAgreement(id, 0, a, cSig, pSig);
        assertEq(address(settlement).balance, 25);
        uint256 initialConsumerBalance = consumer.balance;
        uint256 initialProviderBalance = provider.balance;
        vm.prank(consumer);
        settlement.withdraw();
        vm.prank(provider);
        settlement.withdraw();
        assertEq(consumer.balance, initialConsumerBalance + 23);
        assertEq(provider.balance, initialProviderBalance + 2);
        assertEq(address(settlement).balance, 0);
        assertEq(settlement.withdrawable(consumer), 0);
        assertEq(settlement.withdrawable(provider), 0);
    }

    function testExpiredAgreementCannotBeExecuted() public {
        uint256 id = _ready(1, false);
        _closeAsAmbiguousFailure(id);
        SSESettlement.ResidualAllocation memory a = SSESettlement.ResidualAllocation({
            providerShare: 2, consumerShare: 3, nonce: 9, expiry: block.timestamp - 1
        });
        (bytes memory cSig, bytes memory pSig) = _residualSignatures(id, a, CONSUMER_KEY);
        vm.expectRevert(SSESettlement.OutsideWindow.selector);
        settlement.resolveResidualByAgreement(id, 0, a, cSig, pSig);
    }

    function testIncentivesRequireExactPrefundingAndConsumerAuthorization() public {
        uint256 id = _create(1, false);
        vm.prank(provider);
        vm.expectRevert(SSESettlement.Unauthorized.selector);
        settlement.configureIncentives{value: 34}(id, 2, 3, 5, 7, 11);
        vm.prank(consumer);
        vm.expectRevert(SSESettlement.InsufficientFunding.selector);
        settlement.configureIncentives{value: 33}(id, 2, 3, 5, 7, 11);
        // Correct funding for 1 epoch: 8 monitor + (3+5+7+11) executor = 34.
        vm.prank(consumer);
        settlement.configureIncentives{value: 34}(id, 2, 3, 5, 7, 11);
        SSESettlement.IncentiveBudget memory budget = settlement.getIncentiveBudget(id);
        assertEq(budget.monitorReserved, 8);
        assertEq(budget.executorReserved, 26);
        vm.prank(consumer);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.configureIncentives{value: 34}(id, 2, 3, 5, 7, 11);
    }

    function testEveryAcceptedReportEarnsRewardAndExecutorRewardIsOnce() public {
        uint256 id = _ready(2, true);
        SSESettlement.Epoch memory ep = _admit(id);
        bytes32 h = keccak256(abi.encode(
            RESPONSE_TYPEHASH, id, uint256(0), ep.requestHash, ep.responseHash
        ));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", settlement.domainSeparator(), h));
        settlement.submitProviderResponse(id, 0, _sign(PROVIDER_KEY, digest));

        address[4] memory selected = committee.getCommittee(id);
        vm.prank(selected[3]);
        settlement.submitMonitorVoteDirect(id, 0, SSESettlement.Outcome.Success, keccak256("positive"));
        vm.warp(uint256(ep.responseDeadline) + 1);
        for (uint256 i; i < 3; ++i) {
            vm.prank(selected[i]);
            settlement.submitMonitorVoteDirect(id, 0, SSESettlement.Outcome.Failure, keccak256(abi.encode("negative", i)));
        }
        // The dissenting monitor is paid equally; no majority-alignment incentive.
        for (uint256 i; i < 4; ++i) assertEq(settlement.withdrawable(selected[i]), 2);

        vm.warp(uint256(ep.evidenceClose) + 1);
        vm.prank(executor);
        settlement.closeEpochEvidence(id, 0); // seal + settle + close in one call
        assertEq(settlement.withdrawable(executor), 3 + 5 + 7);
        vm.prank(anotherExecutor);
        settlement.settleEpoch(id, 0); // repeat: no new execution bounty
        assertEq(settlement.withdrawable(anotherExecutor), 0);

        vm.prank(consumer);
        settlement.closeLease(id); // return unused service escrow for epoch 2
        vm.prank(anotherExecutor);
        settlement.releaseCommitteeAfterEvidence(id);
        assertEq(settlement.withdrawable(anotherExecutor), 11);
        settlement.refundUnusedIncentives(id);
        // 2 epochs: service 50, monitor budget 16, executor budget 41.
        // Four reports paid 8; actions paid 15+11=26. Unused = 8+15=23.
        assertEq(settlement.withdrawable(consumer), 20 + 25 + 23);
        SSESettlement.IncentiveBudget memory budget = settlement.getIncentiveBudget(id);
        assertEq(budget.monitorReserved, 0);
        assertEq(budget.executorReserved, 0);
        assertTrue(budget.refunded);
        uint256 totalCredits = settlement.withdrawable(consumer) + settlement.withdrawable(provider)
            + settlement.withdrawable(executor) + settlement.withdrawable(anotherExecutor);
        for (uint256 i; i < 4; ++i) totalCredits += settlement.withdrawable(selected[i]);
        // Service escrow ambiguity 5 remains in the contract, undisturbed.
        SSESettlement.Epoch memory afterEp = settlement.getEpoch(id, 0);
        assertEq(totalCredits + afterEp.unresolvedExposure, 50 + 57);
        assertEq(address(settlement).balance, 50 + 57);
    }

    function testAbandonedLeaseRefundsIncentivesAfterAssignmentExpiry() public {
        uint256 id = _create(1, true);
        // Provider never accepts and randomness is never supplied.
        vm.prank(consumer);
        settlement.closeLease(id);
        vm.warp(block.timestamp + 1 days + 1);
        committee.expire(id);
        settlement.refundUnusedIncentives(id);
        assertEq(settlement.withdrawable(consumer), 25 + 34);
        SSESettlement.IncentiveBudget memory unused = settlement.getIncentiveBudget(id);
        assertEq(unused.monitorReserved, 0);
        assertEq(unused.executorReserved, 0);
    }

    function testUnusedIncentivesCannotBeRefundedBeforeReleaseOrTwice() public {
        uint256 id = _ready(1, true);
        _closeAsAmbiguousFailure(id);
        vm.prank(consumer);
        settlement.closeLease(id);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.refundUnusedIncentives(id);
        settlement.releaseCommitteeAfterEvidence(id);
        settlement.refundUnusedIncentives(id);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.refundUnusedIncentives(id);
    }
}
