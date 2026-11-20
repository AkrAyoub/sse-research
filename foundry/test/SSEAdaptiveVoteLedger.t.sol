// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {SSEAdaptiveVoteLedger} from "../../contracts/SSEAdaptiveVoteLedger.sol";
import {AdaptiveMonitorQuorum} from "../../contracts/AdaptiveMonitorQuorum.sol";

/// @notice These are EVM adversarial UNIT tests using synthetic addresses
/// ONLY as fixtures; no real monitor measurements or outside operators.
contract SSEAdaptiveVoteLedgerTest is Test {
    SSEAdaptiveVoteLedger internal ledger;
    address internal constant SETTLEMENT = address(0xBEEF);
    address internal constant CONSUMER = address(0xC001);
    address internal constant PROVIDER = address(0xD002);
    bytes32 internal constant SNAPSHOT = keccak256("fixture-root-only");
    bytes32 internal constant REQUEST = keccak256("fixture-request");
    bytes32 internal constant RESPONSE = keccak256("fixture-provider-response");
    bytes32 internal constant EVIDENCE = keccak256("fixture-offchain-evidence");
    bytes32 internal constant VOTE_TYPEHASH = keccak256(
        "MonitorVote(uint256 leaseId,uint256 epochId,bytes32 requestHash,uint8 outcome,bytes32 responseHash,bytes32 evidenceHash)"
    );
    uint256 internal constant SIGNER_KEY = 0x11ABCD;

    function setUp() public {
        vm.warp(100_000);
        ledger = new SSEAdaptiveVoteLedger(SETTLEMENT);
        vm.deal(SETTLEMENT, 1_000 ether);
    }

    function _monitors(uint256 seats) internal pure returns (address[] memory people) {
        people = new address[](seats);
        for (uint256 i; i < seats; ++i) {
            people[i] = address(uint160(0x10000 + i));
        }
    }

    function _terms(uint256 leaseId, uint256 k, uint256 f,
                    uint256 gasSeats, uint256 budget)
        internal pure returns (SSEAdaptiveVoteLedger.FreezeTerms memory)
    {
        return SSEAdaptiveVoteLedger.FreezeTerms({
            leaseId: leaseId,
            consumer: CONSUMER,
            provider: PROVIDER,
            snapshotRoot: SNAPSHOT,
            eligibleCount: k,
            requiredFaultTolerance: f,
            gasBoundSeats: gasSeats,
            monitorBudget: budget,
            payableEpochs: 2,
            perMonitorEpochReward: 5,
            confirmationTimeoutSeconds: 1 hours
        });
    }

    function _freeze(uint256 leaseId, uint256 k, uint256 f)
        internal returns (address[] memory people)
    {
        people = _monitors(k);
        vm.prank(SETTLEMENT);
        ledger.freezeCommittee{value: k * 2 * 5}(_terms(leaseId, k, f, k, k * 2 * 5), people);
    }

    function _confirm(uint256 leaseId, address[] memory people) internal {
        for (uint256 i; i < people.length; ++i) {
            vm.prank(people[i]);
            ledger.confirmSeat(leaseId);
        }
    }

    function _open(uint256 leaseId, uint256 epochId) internal {
        vm.prank(SETTLEMENT);
        ledger.openEpoch(
            leaseId, epochId, REQUEST,
            uint64(block.timestamp + 20), uint64(block.timestamp + 40)
        );
    }

    function testFourFiveSevenTenSeatsAndThresholdsAreRealStorage() public {
        uint256[4] memory counts = [uint256(4), 5, 7, 10];
        uint256[4] memory quorum = [uint256(3), 4, 5, 7];
        for (uint256 i; i < counts.length; ++i) {
            address[] memory people = _freeze(1 + i, counts[i], 1);
            SSEAdaptiveVoteLedger.Committee memory c = ledger.committee(1 + i);
            assertEq(c.seats, counts[i]);
            assertEq(c.quorum, quorum[i]);
            assertEq(ledger.selected(1 + i).length, counts[i]);
            assertFalse(c.ready);
            _confirm(1 + i, people);
            assertTrue(ledger.committee(1 + i).ready);
        }
    }

    function testNoFixedMonitorNetworkMembershipLimitAndLargeLocalSeatCount() public {
        address[] memory people = _freeze(1, 24, 4);
        _confirm(1, people);
        SSEAdaptiveVoteLedger.Committee memory c = ledger.committee(1);
        assertEq(c.seats, 24);
        assertEq(c.quorum, 17);
        assertEq(c.requiredFaultTolerance, 4);
    }

    function testCannotInitializeFromUntrustedAccountOrOverwriteLease() public {
        address[] memory people = _monitors(4);
        vm.expectRevert(SSEAdaptiveVoteLedger.Unauthorized.selector);
        ledger.freezeCommittee{value: 40}(_terms(1, 4, 1, 4, 40), people);
        _freeze(1, 4, 1);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidArgument.selector);
        vm.prank(SETTLEMENT);
        ledger.freezeCommittee{value: 40}(_terms(1, 4, 1, 4, 40), people);
    }

    function testDuplicateOrPartyAsMonitorCannotBeSelected() public {
        address[] memory people = _monitors(4);
        people[3] = people[0];
        vm.expectRevert(SSEAdaptiveVoteLedger.DuplicateMonitor.selector);
        vm.prank(SETTLEMENT);
        ledger.freezeCommittee{value: 40}(_terms(1, 4, 1, 4, 40), people);
        people[3] = PROVIDER;
        vm.expectRevert(SSEAdaptiveVoteLedger.Unauthorized.selector);
        vm.prank(SETTLEMENT);
        ledger.freezeCommittee{value: 40}(_terms(1, 4, 1, 4, 40), people);
    }

    function testUnderfundedSnapshotIsRejectedNotDownscaled() public {
        address[] memory people = _monitors(4);
        vm.expectRevert(AdaptiveMonitorQuorum.InsufficientMonitorRewardBudget.selector);
        vm.prank(SETTLEMENT);
        ledger.freezeCommittee{value: 39}(_terms(1, 4, 1, 4, 39), people);
    }

    function testInsufficientEligiblePoolIsRejected() public {
        address[] memory people = _monitors(3);
        vm.expectRevert(AdaptiveMonitorQuorum.InsufficientIndependentEligibleMonitors.selector);
        vm.prank(SETTLEMENT);
        ledger.freezeCommittee{value: 30}(_terms(1, 3, 1, 3, 30), people);
    }

    function testInvalidOrDuplicateSeatConfirmationRejected() public {
        address[] memory people = _freeze(1, 4, 1);
        vm.expectRevert(SSEAdaptiveVoteLedger.Unauthorized.selector);
        vm.prank(address(0xBAD));
        ledger.confirmSeat(1);
        vm.prank(people[0]);
        ledger.confirmSeat(1);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        vm.prank(people[0]);
        ledger.confirmSeat(1);
        _confirmRemaining(1, people);
        assertEq(ledger.confirmations(1), 4);
    }

    function _confirmRemaining(uint256 leaseId, address[] memory people) internal {
        for (uint256 i = 1; i < people.length; ++i) {
            vm.prank(people[i]);
            ledger.confirmSeat(leaseId);
        }
    }

    function testEpochNeedsConfirmedCommitteeAndAuthenticatedResponse() public {
        address[] memory people = _freeze(1, 4, 1);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        vm.prank(SETTLEMENT);
        ledger.openEpoch(1, 0, REQUEST, uint64(block.timestamp + 20), uint64(block.timestamp + 40));
        _confirm(1, people);
        _open(1, 0);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        vm.prank(people[0]);
        ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE);
        vm.expectRevert(SSEAdaptiveVoteLedger.Unauthorized.selector);
        vm.prank(address(0xBAD));
        ledger.authenticateResponse(1, 0, RESPONSE);
        vm.prank(SETTLEMENT);
        ledger.authenticateResponse(1, 0, RESPONSE);
        vm.prank(people[0]);
        ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE);
        assertEq(ledger.epoch(1, 0).successVotes, 1);
    }

    function testOneIdentityCannotVoteTwiceOrVoteAnotherLease() public {
        address[] memory people = _freeze(1, 4, 1);
        _confirm(1, people);
        _open(1, 0);
        vm.prank(SETTLEMENT);
        ledger.authenticateResponse(1, 0, RESPONSE);
        vm.prank(people[0]);
        ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE);
        vm.expectRevert(SSEAdaptiveVoteLedger.AlreadyVoted.selector);
        vm.prank(people[0]);
        ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE);
        vm.expectRevert(SSEAdaptiveVoteLedger.Unauthorized.selector);
        vm.prank(address(0xE000));
        ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        vm.prank(people[0]);
        ledger.submitVoteDirect(2, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE);
    }

    function testThreeOfFiveIsNotOutcomeAndFourOfFiveIsOutcome() public {
        address[] memory people = _freeze(1, 5, 1);
        _confirm(1, people);
        _open(1, 0);
        vm.prank(SETTLEMENT);
        ledger.authenticateResponse(1, 0, RESPONSE);
        for (uint256 i; i < 3; ++i) {
            vm.prank(people[i]);
            ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE);
        }
        vm.warp(block.timestamp + 41);
        assertEq(uint8(ledger.seal(1, 0)), uint8(SSEAdaptiveVoteLedger.Outcome.None));

        _open(1, 1);
        vm.prank(SETTLEMENT);
        ledger.authenticateResponse(1, 1, RESPONSE);
        for (uint256 i; i < 4; ++i) {
            vm.prank(people[i]);
            ledger.submitVoteDirect(1, 1, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE);
        }
        vm.warp(block.timestamp + 41);
        assertEq(uint8(ledger.seal(1, 1)), uint8(SSEAdaptiveVoteLedger.Outcome.Success));
    }

    function test_RevertFailureVotesBeforeResponseDeadline() public {
        address[] memory people = _freeze(1, 4, 1);
        _confirm(1, people);
        _open(1, 0);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        vm.prank(people[0]);
        ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Failure, EVIDENCE);
        vm.warp(block.timestamp + 21);
        for (uint256 i; i < 3; ++i) {
            vm.prank(people[i]);
            ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Failure, EVIDENCE);
        }
        vm.warp(block.timestamp + 20);
        assertEq(uint8(ledger.seal(1, 0)), uint8(SSEAdaptiveVoteLedger.Outcome.Failure));
    }

    function testConflictingOrMissingVotesAreInconclusive() public {
        address[] memory people = _freeze(1, 7, 2);
        _confirm(1, people);
        _open(1, 0);
        vm.prank(SETTLEMENT);
        ledger.authenticateResponse(1, 0, RESPONSE);
        for (uint256 i; i < 3; ++i) {
            vm.prank(people[i]);
            ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE);
        }
        vm.warp(block.timestamp + 21);
        for (uint256 i = 3; i < 6; ++i) {
            vm.prank(people[i]);
            ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Failure, EVIDENCE);
        }
        vm.warp(block.timestamp + 20);
        assertEq(uint8(ledger.seal(1, 0)), uint8(SSEAdaptiveVoteLedger.Outcome.None));
        SSEAdaptiveVoteLedger.Epoch memory e = ledger.epoch(1, 0);
        assertEq(e.successVotes, 3);
        assertEq(e.failureVotes, 3);
        assertEq(e.totalVotes, 6);
    }

    function testWrongSignerOrInvalidEvidenceCannotChangeOutcome() public {
        address[] memory people = _freeze(1, 4, 1);
        _confirm(1, people);
        _open(1, 0);
        vm.prank(SETTLEMENT);
        ledger.authenticateResponse(1, 0, RESPONSE);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidArgument.selector);
        vm.prank(people[0]);
        ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, bytes32(0));
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidArgument.selector);
        vm.prank(people[0]);
        ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.None, EVIDENCE);
    }

    function testActualEIP712SignatureRecordedWithLeaseEpochAndChainBinding() public {
        address signer = vm.addr(SIGNER_KEY);
        address[] memory people = _monitors(4);
        people[0] = signer;
        vm.prank(SETTLEMENT);
        ledger.freezeCommittee{value: 40}(_terms(1, 4, 1, 4, 40), people);
        _confirm(1, people);
        _open(1, 0);
        vm.prank(SETTLEMENT);
        ledger.authenticateResponse(1, 0, RESPONSE);
        bytes32 structHash = keccak256(abi.encode(
            VOTE_TYPEHASH, uint256(1), uint256(0), REQUEST,
            uint8(SSEAdaptiveVoteLedger.Outcome.Success), RESPONSE, EVIDENCE
        ));
        bytes32 digest = keccak256(abi.encodePacked(
            "\x19\x01", ledger.domainSeparator(), structHash
        ));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(SIGNER_KEY, digest);
        bytes memory sig = abi.encodePacked(r, s, v);
        vm.prank(address(0x9999));
        ledger.submitSignedVote(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE, sig);
        assertTrue(ledger.voted(1, 0, signer));
        assertEq(ledger.epoch(1, 0).successVotes, 1);
        vm.expectRevert(SSEAdaptiveVoteLedger.AlreadyVoted.selector);
        vm.prank(address(0x9999));
        ledger.submitSignedVote(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE, sig);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        vm.prank(address(0x9999));
        ledger.submitSignedVote(1, 99, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE, sig);
    }

    function testCannotSealEarlyResealOrVoteAfterSeal() public {
        address[] memory people = _freeze(1, 4, 1);
        _confirm(1, people);
        _open(1, 0);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        ledger.seal(1, 0);
        vm.warp(block.timestamp + 41);
        ledger.seal(1, 0);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        ledger.seal(1, 0);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        vm.prank(people[0]);
        ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Failure, EVIDENCE);
    }

    function testAnyoneCanExpireNoShowCommitteeOnlyAfterFrozenDeadline() public {
        address[] memory people = _freeze(7, 5, 1);
        SSEAdaptiveVoteLedger.Committee memory before_ = ledger.committee(7);
        assertEq(before_.confirmationDeadline, block.timestamp + 1 hours);
        for (uint256 i; i < 4; ++i) {
            vm.prank(people[i]);
            ledger.confirmSeat(7);
        }
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        ledger.expireUnconfirmed(7);
        vm.warp(uint256(before_.confirmationDeadline) + 1);
        vm.prank(address(0xDEAD));
        ledger.expireUnconfirmed(7);
        SSEAdaptiveVoteLedger.Committee memory after_ = ledger.committee(7);
        assertTrue(after_.confirmationExpired);
        assertFalse(after_.ready);
        assertEq(ledger.confirmations(7), 4);
        vm.expectRevert(SSEAdaptiveVoteLedger.Unauthorized.selector);
        vm.prank(people[4]);
        ledger.confirmSeat(7);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        vm.prank(address(0xDEAD));
        ledger.expireUnconfirmed(7);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidArgument.selector);
        vm.prank(SETTLEMENT);
        ledger.freezeCommittee{value: 50}(_terms(7, 5, 1, 5, 50), people);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        vm.prank(SETTLEMENT);
        ledger.openEpoch(7, 0, REQUEST, uint64(block.timestamp + 20), uint64(block.timestamp + 40));
    }

    function testReadyCommitteeCannotBeCancelledEvenAfterDeadline() public {
        address[] memory people = _freeze(1, 4, 1);
        _confirm(1, people);
        vm.warp(block.timestamp + 2 hours);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        ledger.expireUnconfirmed(1);
        assertTrue(ledger.committee(1).ready);
    }

    function testFreezeRejectsZeroShortOrExcessiveConfirmationPeriod() public {
        address[] memory people = _monitors(4);
        uint64[3] memory invalid = [uint64(0), uint64(59 minutes), uint64(8 days)];
        for (uint256 i; i < invalid.length; ++i) {
            SSEAdaptiveVoteLedger.FreezeTerms memory p = _terms(1, 4, 1, 4, 40);
            p.confirmationTimeoutSeconds = invalid[i];
            vm.expectRevert(SSEAdaptiveVoteLedger.InvalidArgument.selector);
            vm.prank(SETTLEMENT);
            ledger.freezeCommittee{value: p.monitorBudget}(p, people);
        }
    }

    function testCannotConfirmAfterDeadlineWithoutExplicitExpirationCall() public {
        address[] memory people = _freeze(5, 4, 1);
        uint256 frozenDeadline = ledger.committee(5).confirmationDeadline;
        vm.prank(people[0]);
        ledger.confirmSeat(5);
        assertEq(ledger.committee(5).confirmationDeadline, frozenDeadline);
        vm.warp(frozenDeadline + 1);
        vm.expectRevert(SSEAdaptiveVoteLedger.Unauthorized.selector);
        vm.prank(people[1]);
        ledger.confirmSeat(5);
        assertEq(ledger.confirmations(5), 1);
        assertFalse(ledger.committee(5).ready);
        ledger.expireUnconfirmed(5);
        assertTrue(ledger.committee(5).confirmationExpired);
    }

    function testSignedVoteIsNotReplayableAcrossChainIds() public {
        address signer = vm.addr(SIGNER_KEY);
        address[] memory people = _monitors(4);
        people[0] = signer;
        vm.prank(SETTLEMENT);
        ledger.freezeCommittee{value: 40}(_terms(1, 4, 1, 4, 40), people);
        _confirm(1, people);
        _open(1, 0);
        vm.prank(SETTLEMENT);
        ledger.authenticateResponse(1, 0, RESPONSE);
        bytes32 structHash = keccak256(abi.encode(
            VOTE_TYPEHASH, uint256(1), uint256(0), REQUEST,
            uint8(SSEAdaptiveVoteLedger.Outcome.Success), RESPONSE, EVIDENCE
        ));
        bytes32 digest = keccak256(abi.encodePacked(
            "\x19\x01", ledger.domainSeparator(), structHash
        ));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(SIGNER_KEY, digest);
        bytes memory sig = abi.encodePacked(r, s, v);
        vm.chainId(block.chainid + 1);
        vm.expectRevert(SSEAdaptiveVoteLedger.Unauthorized.selector);
        ledger.submitSignedVote(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE, sig);
        assertEq(ledger.epoch(1, 0).totalVotes, 0);
    }


    function testNativeReportRewardBudgetMustActuallyBeDeposited() public {
        address[] memory people = _monitors(4);
        vm.expectRevert(SSEAdaptiveVoteLedger.FundingMismatch.selector);
        vm.prank(SETTLEMENT);
        ledger.freezeCommittee(_terms(1, 4, 1, 4, 40), people);
        assertEq(address(ledger).balance, 0);
        vm.prank(SETTLEMENT);
        ledger.freezeCommittee{value: 40}(_terms(1, 4, 1, 4, 40), people);
        assertEq(address(ledger).balance, 40);
        assertEq(ledger.committee(1).unspentReportBudget, 40);
        assertEq(ledger.committee(1).originalReportBudget, 40);
    }

    function testExcessDeclaredBudgetFailsWithoutTrappingFunds() public {
        address[] memory people = _monitors(4);
        vm.expectRevert(SSEAdaptiveVoteLedger.FundingMismatch.selector);
        vm.prank(SETTLEMENT);
        ledger.freezeCommittee{value: 60}(_terms(1, 4, 1, 4, 60), people);
        assertEq(address(ledger).balance, 0);
    }

    function testDissentingReportEarnsTheSameFundedReward() public {
        address[] memory people = _freeze(1, 5, 1);
        _confirm(1, people);
        _open(1, 0);
        vm.prank(SETTLEMENT);
        ledger.authenticateResponse(1, 0, RESPONSE);
        for (uint256 i; i < 3; ++i) {
            vm.prank(people[i]);
            ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE);
        }
        vm.warp(block.timestamp + 21);
        for (uint256 i = 3; i < 5; ++i) {
            vm.prank(people[i]);
            ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Failure, EVIDENCE);
        }
        for (uint256 i; i < people.length; ++i) {
            assertEq(ledger.withdrawable(people[i]), 5);
        }
        assertEq(ledger.committee(1).unspentReportBudget, 25);
        assertEq(address(ledger).balance, 50);
        vm.warp(block.timestamp + 20);
        assertEq(uint8(ledger.seal(1, 0)), uint8(SSEAdaptiveVoteLedger.Outcome.None));
        assertEq(ledger.epoch(1, 0).totalVotes, 5);
    }

    function testNoShowExpiresAndRefundsOnlyRealConsumerOnce() public {
        address[] memory people = _freeze(7, 5, 1);
        vm.deal(CONSUMER, 100);
        vm.prank(people[0]);
        ledger.confirmSeat(7);
        uint256 deadline = ledger.committee(7).confirmationDeadline;
        vm.warp(deadline + 1);
        vm.prank(address(0xBAD));
        ledger.expireUnconfirmed(7);
        assertEq(ledger.withdrawable(CONSUMER), 50);
        assertEq(ledger.committee(7).unspentReportBudget, 0);
        assertEq(ledger.withdrawable(PROVIDER), 0);
        vm.expectRevert(SSEAdaptiveVoteLedger.NoWithdrawal.selector);
        vm.prank(PROVIDER);
        ledger.withdraw();
        uint256 before_ = CONSUMER.balance;
        vm.prank(CONSUMER);
        ledger.withdraw();
        assertEq(CONSUMER.balance, before_ + 50);
        assertEq(ledger.withdrawable(CONSUMER), 0);
        assertEq(address(ledger).balance, 0);
        vm.expectRevert(SSEAdaptiveVoteLedger.NoWithdrawal.selector);
        vm.prank(CONSUMER);
        ledger.withdraw();
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        ledger.expireUnconfirmed(7);
    }

    function testCloseReportingRefundsUnspentAfterSealedEpoch() public {
        address[] memory people = _freeze(1, 4, 1);
        _confirm(1, people);
        _open(1, 0);
        vm.prank(SETTLEMENT);
        ledger.authenticateResponse(1, 0, RESPONSE);
        vm.prank(people[0]);
        ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE);
        assertEq(ledger.withdrawable(people[0]), 5);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        vm.prank(SETTLEMENT);
        ledger.closeReporting(1);
        vm.warp(block.timestamp + 41);
        ledger.seal(1, 0);
        vm.expectRevert(SSEAdaptiveVoteLedger.Unauthorized.selector);
        vm.prank(address(0xBAD));
        ledger.closeReporting(1);
        vm.prank(SETTLEMENT);
        ledger.closeReporting(1);
        assertEq(ledger.withdrawable(CONSUMER), 35);
        assertEq(ledger.committee(1).unspentReportBudget, 0);
        assertTrue(ledger.committee(1).reportingClosed);
        assertEq(ledger.withdrawable(people[0]), 5);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        vm.prank(SETTLEMENT);
        ledger.closeReporting(1);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        vm.prank(SETTLEMENT);
        ledger.openEpoch(1, 1, REQUEST, uint64(block.timestamp + 20), uint64(block.timestamp + 40));
    }

    function testCannotOpenMoreEpochsThanNativeRewardsFund() public {
        address[] memory people = _freeze(1, 4, 1);
        _confirm(1, people);
        _open(1, 0);
        _open(1, 1);
        assertEq(ledger.committee(1).openedEpochs, 2);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        vm.prank(SETTLEMENT);
        ledger.openEpoch(1, 2, REQUEST, uint64(block.timestamp + 20), uint64(block.timestamp + 40));
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        vm.prank(SETTLEMENT);
        ledger.openEpoch(1, 0, REQUEST, uint64(block.timestamp + 20), uint64(block.timestamp + 40));
    }

    function testNativeRewardWithdrawCannotStealOtherMonitorCredit() public {
        address[] memory people = _freeze(1, 4, 1);
        _confirm(1, people);
        _open(1, 0);
        vm.prank(SETTLEMENT);
        ledger.authenticateResponse(1, 0, RESPONSE);
        vm.prank(people[0]);
        ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE);
        vm.expectRevert(SSEAdaptiveVoteLedger.NoWithdrawal.selector);
        vm.prank(people[1]);
        ledger.withdraw();
        uint256 before_ = people[0].balance;
        vm.prank(people[0]);
        ledger.withdraw();
        assertEq(people[0].balance, before_ + 5);
        assertEq(ledger.withdrawable(people[0]), 0);
        vm.expectRevert(SSEAdaptiveVoteLedger.NoWithdrawal.selector);
        vm.prank(people[0]);
        ledger.withdraw();
        assertEq(address(ledger).balance, 35);
    }


    function testNativeReportFundsConservedAcrossTwoRealOnchainLeaseBudgets() public {
        address[] memory first = _freeze(1, 4, 1);
        address[] memory second = _freeze(2, 5, 1);
        assertEq(address(ledger).balance, 90);
        assertEq(ledger.totalUnspentReserves(), 90);
        assertEq(ledger.totalWithdrawableCredits(), 0);
        _confirm(1, first);
        _open(1, 0);
        vm.prank(SETTLEMENT);
        ledger.authenticateResponse(1, 0, RESPONSE);
        vm.prank(first[0]);
        ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE);
        vm.prank(first[1]);
        ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE);
        assertEq(ledger.totalUnspentReserves(), 80);
        assertEq(ledger.totalWithdrawableCredits(), 10);
        assertEq(address(ledger).balance, 90);
        vm.warp(block.timestamp + 41);
        ledger.seal(1, 0);
        vm.prank(SETTLEMENT);
        ledger.closeReporting(1);
        assertEq(ledger.withdrawable(CONSUMER), 30);
        assertEq(ledger.totalUnspentReserves(), 50);
        assertEq(ledger.totalWithdrawableCredits(), 40);
        uint256 pre = first[0].balance;
        vm.prank(first[0]);
        ledger.withdraw();
        assertEq(first[0].balance, pre + 5);
        assertEq(ledger.totalUnspentReserves(), 50);
        assertEq(ledger.totalWithdrawableCredits(), 35);
        assertEq(address(ledger).balance, 85);
        uint256 deadline = ledger.committee(2).confirmationDeadline;
        vm.warp(deadline + 1);
        ledger.expireUnconfirmed(2);
        assertEq(ledger.withdrawable(CONSUMER), 80);
        assertEq(ledger.totalUnspentReserves(), 0);
        assertEq(ledger.totalWithdrawableCredits(), 85);
        assertEq(address(ledger).balance, 85);
        // Second lease committee remains an independent, never-ready state.
        assertTrue(ledger.committee(2).confirmationExpired);
        assertFalse(ledger.committee(2).ready);
        assertEq(second.length, 5);
    }

    function testNoSelectedMonitorMayWithdrawWithoutRealSignedOrDirectReport() public {
        address[] memory people = _freeze(1, 4, 1);
        _confirm(1, people);
        assertEq(ledger.withdrawable(people[0]), 0);
        vm.expectRevert(SSEAdaptiveVoteLedger.NoWithdrawal.selector);
        vm.prank(people[0]);
        ledger.withdraw();
        _open(1, 0);
        vm.prank(people[0]);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        ledger.submitVoteDirect(1, 0, SSEAdaptiveVoteLedger.Outcome.Success, EVIDENCE);
        assertEq(ledger.totalUnspentReserves(), 40);
        assertEq(ledger.totalWithdrawableCredits(), 0);
        assertEq(address(ledger).balance, 40);
    }

    function testFuzzCommitteeQuorumAlwaysStrictForDynamicSeats(uint8 extra) public {
        uint256 k = 4 + uint256(extra % 30);
        address[] memory people = _freeze(1, k, 1);
        assertEq(people.length, k);
        SSEAdaptiveVoteLedger.Committee memory c = ledger.committee(1);
        assertGt(c.quorum, (2 * k) / 3);
        assertLe(c.quorum, k);
    }
}
