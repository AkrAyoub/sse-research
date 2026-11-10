// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {OpenMonitorCommittee} from "../../contracts/OpenMonitorCommittee.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";

/**
 * @title WorldSoundnessAdversarialTest
 * @notice WP-06: REAL EVM calls/real EIP-712 signatures for conditional
 *         world-soundness counterexamples found in WP-05.
 *
 * IMPORTANT LIMIT:
 *   Foundry proves contract transitions under the submitted signed messages;
 *   it cannot establish that any off-chain service actually fulfilled its SLA.
 *   Labels like "physical S" or "physical F" are stipulated counterfactual
 *   test scenarios, NOT oracle readings, real network observations or formal
 *   proofs of reachable faults in an independently operated cloud network.
 *
 * No production contract source is modified by this test file.
 */
contract WorldSoundnessAdversarialTest is Test {
    uint256 internal constant PROVIDER_KEY = 0xB3101;
    uint256 internal constant OUTSIDER_KEY = 0xBADF00;
    bytes32 internal constant ACK_TYPEHASH = keccak256(
        "ProviderAck(uint256 leaseId,uint256 epochId,bytes32 requestHash)"
    );
    bytes32 internal constant RESPONSE_TYPEHASH = keccak256(
        "ProviderResponse(uint256 leaseId,uint256 epochId,bytes32 requestHash,bytes32 responseHash)"
    );
    bytes32 internal constant VOTE_TYPEHASH = keccak256(
        "MonitorVote(uint256 leaseId,uint256 epochId,bytes32 requestHash,uint8 outcome,bytes32 responseHash,bytes32 evidenceHash)"
    );

    OpenMonitorCommittee internal pool;
    SSESettlement internal settlement;
    address internal consumer;
    address internal provider;
    uint256[5] internal monitorKeys;
    address[4] internal selected;
    uint256 internal leaseId;
    SSESettlement.Epoch internal initialEpoch;

    function setUp() public {
        vm.warp(10_000);
        consumer = vm.addr(0xA3101);
        provider = vm.addr(PROVIDER_KEY);
        vm.deal(consumer, 1 ether);
        pool = new OpenMonitorCommittee(address(this), 1 ether, 7 days, 1 days);
        settlement = new SSESettlement(address(pool));
        pool.bindSettlement(address(settlement));

        // Bonded identities. Randomness is TEST-CONTROLLED; the test does not
        // claim unbiased production committee selection or Sybil resistance.
        for (uint256 i; i < monitorKeys.length; ++i) {
            monitorKeys[i] = 0xC3101 + i;
            address m = vm.addr(monitorKeys[i]);
            vm.deal(m, 2 ether);
            vm.prank(m);
            pool.register{value: 1 ether}();
        }

        // Real contract lifecycle: create -> provider accept -> oracle assigns
        // -> selected monitors confirm -> consumer admits one funded epoch.
        vm.prank(consumer);
        leaseId = settlement.createLease{value: 25}(
            provider, keccak256("wp06-endpoint"), keccak256("wp06-profile"),
            25, 5, 25, 1, 10, 5, 8
        );
        vm.prank(provider);
        settlement.acceptLease(leaseId);
        pool.fulfillRandomness(leaseId, 0xC0FFEE);
        settlement.finalizeMonitorCommittee(leaseId);
        selected = pool.getCommittee(leaseId);
        for (uint256 i; i < selected.length; ++i) {
            vm.prank(selected[i]);
            settlement.confirmMonitorAssignment(leaseId);
        }
        vm.prank(consumer);
        settlement.admitEpoch(leaseId, keccak256("wp06-request"));
        initialEpoch = settlement.getEpoch(leaseId, 0);
    }

    function _keyFor(address monitor) internal returns (uint256) {
        for (uint256 i; i < monitorKeys.length; ++i) {
            if (vm.addr(monitorKeys[i]) == monitor) return monitorKeys[i];
        }
        revert("selected monitor absent from bonded test keys");
    }

    function _sign(uint256 key, bytes32 structHash) internal returns (bytes memory) {
        bytes32 typedDigest = keccak256(abi.encodePacked(
            hex"1901", settlement.domainSeparator(), structHash
        ));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(key, typedDigest);
        return abi.encodePacked(r, s, v);
    }

    function _ack() internal {
        bytes32 h = keccak256(abi.encode(
            ACK_TYPEHASH, leaseId, uint256(0), initialEpoch.requestHash
        ));
        settlement.submitAcknowledgment(leaseId, 0, _sign(PROVIDER_KEY, h));
    }

    function _responseWithKey(uint256 key) internal {
        bytes32 h = keccak256(abi.encode(
            RESPONSE_TYPEHASH, leaseId, uint256(0), initialEpoch.requestHash,
            initialEpoch.responseHash
        ));
        settlement.submitProviderResponse(leaseId, 0, _sign(key, h));
    }

    function _voteSignature(
        uint256 key, SSESettlement.Outcome outcome, bytes32 evidenceHash
    ) internal returns (bytes memory) {
        bytes32 responseHash = outcome == SSESettlement.Outcome.Success
            ? initialEpoch.responseHash : bytes32(0);
        bytes32 h = keccak256(abi.encode(
            VOTE_TYPEHASH, leaseId, uint256(0), initialEpoch.requestHash,
            uint8(outcome), responseHash, evidenceHash
        ));
        return _sign(key, h);
    }

    function _vote(uint256 selectedIndex, SSESettlement.Outcome outcome) internal {
        bytes32 evidence = keccak256(abi.encode("wp06-report", selectedIndex, uint8(outcome)));
        settlement.submitMonitorVote(
            leaseId, 0, outcome, evidence,
            _voteSignature(_keyFor(selected[selectedIndex]), outcome, evidence)
        );
        assertEq(settlement.monitorEvidenceHash(leaseId, 0, selected[selectedIndex]), evidence);
    }

    function _sealAndSettle() internal returns (SSESettlement.Epoch memory e) {
        vm.warp(uint256(initialEpoch.monitoringClose) + 1);
        settlement.sealMonitoring(leaseId, 0);
        settlement.settleEpoch(leaseId, 0);
        e = settlement.getEpoch(leaseId, 0);
        assertEq(e.providerCredited + e.consumerCredited + e.unresolvedExposure, 25);
        SSESettlement.Lease memory l = settlement.getLease(leaseId);
        assertEq(l.currentExposure, e.unresolvedExposure);
        assertEq(settlement.withdrawable(provider), e.providerCredited);
        assertEq(settlement.withdrawable(consumer), e.consumerCredited);
    }

    // CE-01: stipulate physically fulfilled consumer-delivery SLA, but three
    // selected monitors truthfully report LOCAL probe timeouts due to delay.
    // Neither the EVM nor this test proves physical fulfillment; it shows the
    // exact financial consequence if that physical scenario occurs.
    function testCE01_ThreeAuthenticatedFailureVotesOverrefundStipulatedSuccess() public {
        vm.warp(uint256(initialEpoch.responseDeadline)); // exact equality is allowed
        for (uint256 i; i < 3; ++i) _vote(i, SSESettlement.Outcome.Failure);
        SSESettlement.Epoch memory e = _sealAndSettle();
        assertEq(uint8(e.outcome), uint8(SSESettlement.Outcome.Failure));
        assertEq(e.failureVotes, 3);
        assertEq(e.providerCredited, 0);
        assertEq(e.consumerCredited, 20); // true S would entitle consumer to 0
        assertEq(e.unresolvedExposure, 5);
    }

    // CE-02: a real signed provider ACK narrows the contract's selected
    // history to F when three failure reports are accepted. A true S would
    // make the 25 wei consumer credit physically inconsistent.
    function testCE02_SignedAckPlusThreeFailuresCreditsFullConsumer() public {
        _ack();
        vm.warp(uint256(initialEpoch.responseDeadline) + 1);
        for (uint256 i; i < 3; ++i) _vote(i, SSESettlement.Outcome.Failure);
        SSESettlement.Epoch memory e = _sealAndSettle();
        assertTrue(e.acknowledged);
        assertEq(e.consumerCredited, 25);
        assertEq(e.providerCredited, 0);
        assertEq(e.unresolvedExposure, 0);
    }

    // CE-03: correct EIP-712 signed RESPONSE and three selected signed
    // Success votes do NOT prove the consumer received a result on time.
    // Stipulate actual F caused by undelivered response, and check the payout.
    function testCE03_AuthenticatedSuccessCanCreditProviderWithoutDeliveryProof() public {
        _responseWithKey(PROVIDER_KEY);
        for (uint256 i; i < 3; ++i) _vote(i, SSESettlement.Outcome.Success);
        SSESettlement.Epoch memory e = _sealAndSettle();
        assertTrue(e.responseAuthenticated);
        assertEq(uint8(e.outcome), uint8(SSESettlement.Outcome.Success));
        assertEq(e.providerCredited, 25); // true F would entitle provider to 0
        assertEq(e.consumerCredited, 0);
        assertEq(e.unresolvedExposure, 0);
    }

    // CE-04: response signature can first be INCLUDED on-chain during the
    // monitoring grace, strictly later than responseDeadline. Whether physical
    // completion was also late is unknowable from chain inclusion alone.
    function testCE04_GracePeriodResponseAndSuccessVotesStillSettleSuccess() public {
        vm.warp(uint256(initialEpoch.responseDeadline) + 1);
        _responseWithKey(PROVIDER_KEY);
        for (uint256 i; i < 3; ++i) _vote(i, SSESettlement.Outcome.Success);
        SSESettlement.Epoch memory e = _sealAndSettle();
        assertEq(e.providerCredited, 25);
        assertEq(e.unresolvedExposure, 0);
    }

    function test_RevertFailureVoteRejectedOneSecondBeforeDeadlineAcceptedAtBoundary() public {
        vm.warp(uint256(initialEpoch.responseDeadline) - 1);
        bytes32 evidence = keccak256("before-deadline");
        bytes memory sig = _voteSignature(
            _keyFor(selected[0]), SSESettlement.Outcome.Failure, evidence
        );
        vm.expectRevert(SSESettlement.OutsideWindow.selector);
        settlement.submitMonitorVote(leaseId, 0, SSESettlement.Outcome.Failure, evidence, sig);
        vm.warp(uint256(initialEpoch.responseDeadline));
        _vote(0, SSESettlement.Outcome.Failure);
        SSESettlement.Epoch memory e = settlement.getEpoch(leaseId, 0);
        assertEq(e.failureVotes, 1);
    }

    function testUnsignedSuccessWithoutProviderResponseIsRejected() public {
        bytes32 evidence = keccak256("success-without-provider-response");
        bytes memory sig = _voteSignature(
            _keyFor(selected[0]), SSESettlement.Outcome.Success, evidence
        );
        vm.expectRevert(SSESettlement.InvalidEvidence.selector);
        settlement.submitMonitorVote(leaseId, 0, SSESettlement.Outcome.Success, evidence, sig);
    }

    function testOutsiderSignatureCannotCastMonitorVote() public {
        vm.warp(uint256(initialEpoch.responseDeadline));
        bytes32 evidence = keccak256("outsider");
        bytes memory signature = _voteSignature(
            OUTSIDER_KEY, SSESettlement.Outcome.Failure, evidence
        );
        vm.expectRevert(SSESettlement.Unauthorized.selector);
        settlement.submitMonitorVote(leaseId, 0, SSESettlement.Outcome.Failure, evidence, signature);
    }

    function testTamperedSignedEvidenceCannotPassMonitorMembershipCheck() public {
        vm.warp(uint256(initialEpoch.responseDeadline));
        bytes32 evidence = keccak256("original-evidence");
        bytes memory signature = _voteSignature(
            _keyFor(selected[0]), SSESettlement.Outcome.Failure, evidence
        );
        // Changing the evidence changes the EIP-712 digest, so the recovered
        // signer is not the authorized monitor (except negligible collision).
        vm.expectRevert(SSESettlement.Unauthorized.selector);
        settlement.submitMonitorVote(
            leaseId, 0, SSESettlement.Outcome.Failure, keccak256("tampered"), signature
        );
    }

    function testDuplicateSignedVoteRejected() public {
        vm.warp(uint256(initialEpoch.responseDeadline));
        _vote(0, SSESettlement.Outcome.Failure);
        bytes32 evidence = keccak256("duplicate-report");
        bytes memory sig = _voteSignature(
            _keyFor(selected[0]), SSESettlement.Outcome.Failure, evidence
        );
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.submitMonitorVote(leaseId, 0, SSESettlement.Outcome.Failure, evidence, sig);
    }

    function testTwoFailureVotesDoNotProduceDefinitiveOutcome() public {
        vm.warp(uint256(initialEpoch.responseDeadline));
        _vote(0, SSESettlement.Outcome.Failure);
        _vote(1, SSESettlement.Outcome.Failure);
        SSESettlement.Epoch memory e = _sealAndSettle();
        assertEq(uint8(e.outcome), uint8(SSESettlement.Outcome.None));
        assertEq(e.providerCredited, 0);
        assertEq(e.consumerCredited, 0);
        assertEq(e.unresolvedExposure, 25);
    }

    function testOnlyOneOutcomeCanHaveThreeVotesAmongFourIdentities() public {
        _responseWithKey(PROVIDER_KEY);
        vm.warp(uint256(initialEpoch.responseDeadline));
        for (uint256 i; i < 3; ++i) _vote(i, SSESettlement.Outcome.Failure);
        _vote(3, SSESettlement.Outcome.Success);
        SSESettlement.Epoch memory e = _sealAndSettle();
        assertEq(e.failureVotes, 3);
        assertEq(e.successVotes, 1);
        assertEq(uint8(e.outcome), uint8(SSESettlement.Outcome.Failure));
        assertEq(e.consumerCredited, 20);
    }

    function testResponseSubmittedAfterMonitoringCloseRejected() public {
        vm.warp(uint256(initialEpoch.monitoringClose) + 1);
        bytes32 h = keccak256(abi.encode(
            RESPONSE_TYPEHASH, leaseId, uint256(0), initialEpoch.requestHash,
            initialEpoch.responseHash
        ));
        bytes memory sig = _sign(PROVIDER_KEY, h);
        vm.expectRevert(SSESettlement.OutsideWindow.selector);
        settlement.submitProviderResponse(leaseId, 0, sig);
    }

    function test_RevertFailureVoteAfterMonitoringCloseRejected() public {
        vm.warp(uint256(initialEpoch.monitoringClose) + 1);
        bytes32 evidence = keccak256("late-failure-report");
        bytes memory sig = _voteSignature(
            _keyFor(selected[0]), SSESettlement.Outcome.Failure, evidence
        );
        vm.expectRevert(SSESettlement.OutsideWindow.selector);
        settlement.submitMonitorVote(leaseId, 0, SSESettlement.Outcome.Failure, evidence, sig);
    }

    function testLateAckAcceptedThroughEvidenceCloseAndIncrementalRefund() public {
        vm.warp(uint256(initialEpoch.responseDeadline));
        for (uint256 i; i < 3; ++i) _vote(i, SSESettlement.Outcome.Failure);
        _sealAndSettle();
        assertEq(settlement.withdrawable(consumer), 20);
        vm.warp(uint256(initialEpoch.evidenceClose));
        _ack();
        settlement.settleEpoch(leaseId, 0);
        SSESettlement.Epoch memory e = settlement.getEpoch(leaseId, 0);
        assertEq(e.consumerCredited, 25);
        assertEq(e.unresolvedExposure, 0);
        assertEq(settlement.withdrawable(consumer), 25); // additional 5, not 20 again
    }

    function testAckAfterEvidenceWindowRejected() public {
        vm.warp(uint256(initialEpoch.evidenceClose) + 1);
        bytes32 h = keccak256(abi.encode(
            ACK_TYPEHASH, leaseId, uint256(0), initialEpoch.requestHash
        ));
        bytes memory sig = _sign(PROVIDER_KEY, h);
        vm.expectRevert(SSESettlement.OutsideWindow.selector);
        settlement.submitAcknowledgment(leaseId, 0, sig);
    }

    function testWrongProviderResponseSignatureRejected() public {
        bytes32 h = keccak256(abi.encode(
            RESPONSE_TYPEHASH, leaseId, uint256(0), initialEpoch.requestHash,
            initialEpoch.responseHash
        ));
        bytes memory sig = _sign(OUTSIDER_KEY, h);
        vm.expectRevert(SSESettlement.InvalidSignature.selector);
        settlement.submitProviderResponse(leaseId, 0, sig);
    }

    function testRepeatedSettlementDoesNotDoubleCredit() public {
        vm.warp(uint256(initialEpoch.responseDeadline));
        for (uint256 i; i < 3; ++i) _vote(i, SSESettlement.Outcome.Failure);
        _sealAndSettle();
        uint256 amount = settlement.withdrawable(consumer);
        settlement.settleEpoch(leaseId, 0);
        assertEq(settlement.withdrawable(consumer), amount);
        SSESettlement.Epoch memory e = settlement.getEpoch(leaseId, 0);
        assertEq(e.unresolvedExposure, 5);
    }
}
