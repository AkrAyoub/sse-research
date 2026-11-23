// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {SSEAdaptiveMarketV2} from "../../contracts/SSEAdaptiveMarketV2.sol";
import {SSEAdaptiveVoteLedger} from "../../contracts/SSEAdaptiveVoteLedger.sol";

/// @notice Isolated Foundry EVM regression tests, NOT real external SLAs.
/// Tests ensure frozen selection, dynamic k/q, signed provider responses,
/// escrow/refund conservation and no payment on inconclusive reports.
contract SSEAdaptiveMarketV2Test is Test {
    SSEAdaptiveMarketV2 internal market;
    SSEAdaptiveVoteLedger internal votes;
    address internal consumer = address(0xC0A1);
    uint256 internal providerKey = 0xBEEF123;
    address internal provider;
    uint256 internal constant BOND = 1e15;
    uint256 internal constant FEE = 3e15;
    uint256 internal constant REWARD = 1e12;
    bytes32 internal constant PROFILE = keccak256("actual-cpu-reservation-v2");
    bytes32 internal constant POLICY = keccak256("real-sla-v2");
    bytes32 internal constant ENDPOINT = keccak256("real-provider-url-v2");

    function setUp() public {
        vm.chainId(31340);
        vm.warp(1_000_000);
        vm.roll(1000);
        provider = vm.addr(providerKey);
        market = new SSEAdaptiveMarketV2(BOND);
        votes = market.votes();
        vm.deal(consumer, 10 ether);
        vm.deal(provider, 10 ether);
        for (uint256 i; i < 9; ++i) {
            address monitor = address(uint160(0xA000 + i));
            vm.deal(monitor, 2 ether);
            vm.prank(monitor);
            market.registerMonitor{value: BOND}();
        }
    }

    function _terms(uint256 seats) internal pure returns (SSEAdaptiveMarketV2.Terms memory) {
        return SSEAdaptiveMarketV2.Terms({
            endpointHash: ENDPOINT,
            epochs: 1,
            monitorBudget: seats * REWARD,
            perMonitorEpochReward: REWARD,
            requiredFaultTolerance: 1,
            gasBoundSeats: seats,
            confirmationSeconds: 1 hours,
            responseSeconds: 100,
            monitoringSeconds: 100
        });
    }

    function _fund(uint256 seats) internal returns (uint256 leaseId) {
        vm.prank(consumer);
        uint256 id = market.requestResource(PROFILE, POLICY, FEE, uint64(block.timestamp + 20));
        vm.prank(provider);
        market.placeBid(id, FEE);
        vm.warp(block.timestamp + 21);
        vm.prank(consumer);
        leaseId = market.chooseBidAndFund{value: FEE + seats * REWARD}(
            id, 0, _terms(seats)
        );
    }

    function _draw(uint256 leaseId) internal {
        SSEAdaptiveMarketV2.Lease memory l = market.lease(leaseId);
        vm.roll(l.entropyBlock + 1);
        market.drawCommittee(leaseId);
    }

    function _confirm(uint256 leaseId) internal {
        address[] memory selected = votes.selected(leaseId);
        for (uint256 i; i < selected.length; ++i) {
            vm.prank(selected[i]);
            votes.confirmSeat(leaseId);
        }
    }

    function _open(uint256 seats) internal returns (uint256 leaseId) {
        leaseId = _fund(seats);
        _draw(leaseId);
        _confirm(leaseId);
        vm.prank(provider);
        market.acceptLease(leaseId);
        vm.prank(consumer);
        market.startEpoch(leaseId, keccak256("real-request-content"));
    }

    function testCommitteeSizeAndThresholdAdaptToFundedBoundedPolicy() public {
        uint256 leaseId = _fund(7);
        _draw(leaseId);
        SSEAdaptiveVoteLedger.Committee memory c = votes.committee(leaseId);
        assertEq(c.seats, 7);
        assertEq(c.quorum, 5);
        assertEq(c.originalReportBudget, 7 * REWARD);
        assertEq(votes.selected(leaseId).length, 7);
        assertEq(market.totalServiceEscrow(), FEE);
        assertEq(address(votes).balance, 7 * REWARD);
        assertEq(address(market).balance, FEE + 9 * BOND);
    }

    function testRealVoteFailureRefundsConsumerAndPaysActualMonitorReportCredits() public {
        uint256 leaseId = _open(4);
        SSEAdaptiveVoteLedger.Epoch memory ep = votes.epoch(leaseId, 0);
        vm.warp(uint256(ep.responseDeadline) + 1);
        address[] memory selected = votes.selected(leaseId);
        for (uint256 i; i < 3; ++i) {
            vm.prank(selected[i]);
            votes.submitVoteDirect(leaseId, 0, SSEAdaptiveVoteLedger.Outcome.Failure,
                                   keccak256(abi.encode("actual-evidence-digest", i)));
        }
        vm.warp(uint256(ep.monitoringClose) + 1);
        assertEq(uint8(market.finalizeEpoch(leaseId, 0)), uint8(SSEAdaptiveVoteLedger.Outcome.Failure));
        assertEq(market.withdrawable(consumer), FEE);
        assertEq(market.withdrawable(provider), 0);
        assertEq(votes.withdrawable(selected[0]), REWARD);
        vm.prank(consumer);
        market.closeLease(leaseId);
        assertEq(votes.withdrawable(consumer), REWARD);
        assertEq(market.totalServiceEscrow(), 0);
        assertEq(market.totalWithdrawable(), FEE);
    }

    function testNoQuorumCannotFabricateSlaPayment() public {
        uint256 leaseId = _open(4);
        SSEAdaptiveVoteLedger.Epoch memory ep = votes.epoch(leaseId, 0);
        vm.warp(uint256(ep.responseDeadline) + 1);
        address[] memory selected = votes.selected(leaseId);
        vm.prank(selected[0]);
        votes.submitVoteDirect(leaseId, 0, SSEAdaptiveVoteLedger.Outcome.Failure, keccak256("proof"));
        vm.warp(uint256(ep.monitoringClose) + 1);
        assertEq(uint8(market.finalizeEpoch(leaseId, 0)), uint8(SSEAdaptiveVoteLedger.Outcome.None));
        assertEq(market.withdrawable(consumer), 0);
        assertEq(market.withdrawable(provider), 0);
        assertEq(market.totalServiceEscrow(), FEE);
        vm.prank(consumer);
        vm.expectRevert(SSEAdaptiveMarketV2.InvalidPhase.selector);
        market.closeLease(leaseId);
    }

    function testAuthenticatedProviderResponseAllowsSuccessQuorum() public {
        uint256 leaseId = _open(4);
        bytes32 requestHash = keccak256("real-request-content");
        bytes32 responseHash = keccak256("actual-measured-response");
        bytes32 typeHash = keccak256(
            "ProviderResponse(uint256 leaseId,uint256 epochId,bytes32 requestHash,bytes32 responseHash)"
        );
        bytes32 digest = keccak256(abi.encodePacked(
            "\x19\x01", market.domainSeparator(),
            keccak256(abi.encode(typeHash, leaseId, uint256(0), requestHash, responseHash))
        ));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(providerKey, digest);
        market.authenticateProviderResponse(leaseId, 0, responseHash, abi.encodePacked(r, s, v));
        address[] memory selected = votes.selected(leaseId);
        for (uint256 i; i < 3; ++i) {
            vm.prank(selected[i]);
            votes.submitVoteDirect(leaseId, 0, SSEAdaptiveVoteLedger.Outcome.Success,
                                   keccak256(abi.encode("monitor-measurement", i)));
        }
        SSEAdaptiveVoteLedger.Epoch memory ep = votes.epoch(leaseId, 0);
        vm.warp(uint256(ep.monitoringClose) + 1);
        assertEq(uint8(market.finalizeEpoch(leaseId, 0)), uint8(SSEAdaptiveVoteLedger.Outcome.Success));
        assertEq(market.withdrawable(provider), FEE);
        assertEq(market.withdrawable(consumer), 0);
    }

    function testTimeoutDoesNotLetConsumerRerollRandomness() public {
        uint256 leaseId = _fund(4);
        SSEAdaptiveMarketV2.Lease memory l = market.lease(leaseId);
        vm.roll(l.entropyBlock + 257);
        vm.expectRevert(SSEAdaptiveMarketV2.InvalidPhase.selector);
        market.drawCommittee(leaseId);
        market.cancelExpiredDraw(leaseId);
        assertEq(market.withdrawable(consumer), FEE + 4 * REWARD);
        assertEq(market.totalServiceEscrow(), 0);
    }

    function testDecliningProviderCannotLockConsumerEscrowForever() public {
        uint256 leaseId = _fund(4);
        _draw(leaseId);
        SSEAdaptiveVoteLedger.Committee memory c = votes.committee(leaseId);
        vm.warp(uint256(c.confirmationDeadline) + 1);
        market.cancelUnaccepted(leaseId);
        assertEq(market.withdrawable(consumer), FEE);
        assertEq(votes.withdrawable(consumer), 4 * REWARD);
        assertEq(market.totalServiceEscrow(), 0);
    }

    function testUnconfirmedCommitteeCanBeExpiredDirectlyAndThenRefunded() public {
        uint256 leaseId = _fund(4);
        _draw(leaseId);
        SSEAdaptiveVoteLedger.Committee memory c = votes.committee(leaseId);
        vm.warp(uint256(c.confirmationDeadline) + 1);
        votes.expireUnconfirmed(leaseId); // outsider wins the ledger expiry race
        market.cancelUnconfirmed(leaseId);
        assertEq(market.withdrawable(consumer), FEE);
        assertEq(votes.withdrawable(consumer), 4 * REWARD);
    }

    function testInconclusiveRequiresBothBilateralSignatures() public {
        uint256 consumerKey = 0xC0A10001;
        address consumerSigner = vm.addr(consumerKey);
        vm.deal(consumerSigner, 10 ether);
        // Consumer signer cannot retroactively take the previous consumer's
        // lease. Create an independent real lease with this test's signer.
        vm.prank(consumerSigner);
        uint256 requestId = market.requestResource(PROFILE, POLICY, FEE, uint64(block.timestamp + 20));
        vm.prank(provider);
        market.placeBid(requestId, FEE);
        vm.warp(block.timestamp + 21);
        vm.prank(consumerSigner);
        uint256 leaseId = market.chooseBidAndFund{value: FEE + 4 * REWARD}(
            requestId, 0, _terms(4)
        );
        _draw(leaseId);
        _confirm(leaseId);
        vm.prank(provider);
        market.acceptLease(leaseId);
        vm.prank(consumerSigner);
        market.startEpoch(leaseId, keccak256("unsigned-real-request"));
        SSEAdaptiveVoteLedger.Epoch memory ep = votes.epoch(leaseId, 0);
        vm.warp(uint256(ep.monitoringClose) + 1);
        assertEq(uint8(market.finalizeEpoch(leaseId, 0)), uint8(SSEAdaptiveVoteLedger.Outcome.None));

        uint256 consumerShare = 2e15;
        uint256 providerShare = 1e15;
        uint256 nonce = 0;
        uint256 expiry = block.timestamp + 1000;
        bytes32 typeHash = keccak256(
            "ResidualAllocation(uint256 leaseId,uint256 epochId,uint256 consumerShare,uint256 providerShare,uint256 nonce,uint256 expiry)"
        );
        bytes32 digest = keccak256(abi.encodePacked(
            "\x19\x01", market.domainSeparator(),
            keccak256(abi.encode(typeHash, leaseId, uint256(0),
                                 consumerShare, providerShare, nonce, expiry))
        ));
        (uint8 cv, bytes32 cr, bytes32 cs) = vm.sign(consumerKey, digest);
        (uint8 pv, bytes32 pr, bytes32 ps) = vm.sign(providerKey, digest);
        bytes memory consumerSig = abi.encodePacked(cr, cs, cv);
        bytes memory providerSig = abi.encodePacked(pr, ps, pv);
        vm.expectRevert(SSEAdaptiveMarketV2.InvalidSignature.selector);
        market.resolveInconclusive(leaseId, 0, consumerShare, providerShare,
                                   nonce, expiry, providerSig, providerSig);
        market.resolveInconclusive(leaseId, 0, consumerShare, providerShare,
                                   nonce, expiry, consumerSig, providerSig);
        assertEq(market.withdrawable(consumerSigner), consumerShare);
        assertEq(market.withdrawable(provider), providerShare);
        assertEq(market.totalServiceEscrow(), 0);
        vm.expectRevert(SSEAdaptiveMarketV2.InvalidPhase.selector);
        market.resolveInconclusive(leaseId, 0, consumerShare, providerShare,
                                   nonce, expiry, consumerSig, providerSig);
    }

    function testConsumerCannotForceProviderResponseWithoutSignature() public {
        uint256 leaseId = _open(4);
        vm.prank(consumer);
        vm.expectRevert();
        market.authenticateProviderResponse(leaseId, 0, keccak256("claim"),
                                             new bytes(65));
        assertEq(votes.epoch(leaseId, 0).responseAuthenticated, false);
    }

    function testSnapshotLocksBondUntilCommitteeDrawAndReleasesUnselected() public {
        uint256 leaseId = _fund(4);
        address frozen = market.eligibleAt(leaseId, 0);
        (uint256 bond, uint256 locked, bool active) = market.monitors(frozen);
        assertEq(bond, BOND);
        assertEq(locked, 1);
        assertTrue(active);
        vm.prank(frozen);
        vm.expectRevert(SSEAdaptiveMarketV2.InvalidPhase.selector);
        market.exitMonitor();
        _draw(leaseId);
        address[] memory selected = votes.selected(leaseId);
        bool inCommittee;
        for (uint256 i; i < selected.length; ++i)
            if (selected[i] == frozen) inCommittee = true;
        (, locked,) = market.monitors(frozen);
        assertEq(locked, inCommittee ? 1 : 0);
    }

    function testExpiredEntropyReleasesEveryFrozenBond() public {
        uint256 leaseId = _fund(4);
        address frozen = market.eligibleAt(leaseId, 0);
        (, uint256 beforeLock,) = market.monitors(frozen);
        assertEq(beforeLock, 1);
        SSEAdaptiveMarketV2.Lease memory l = market.lease(leaseId);
        vm.roll(l.entropyBlock + 257);
        market.cancelExpiredDraw(leaseId);
        (, uint256 afterLock,) = market.monitors(frozen);
        assertEq(afterLock, 0);
        vm.prank(frozen);
        market.exitMonitor();
    }

    function testLateProviderSignatureCannotTurnMissedDeadlineIntoSuccess() public {
        uint256 leaseId = _open(4);
        bytes32 responseHash = keccak256("late-provider-response");
        bytes32 typeHash = keccak256(
            "ProviderResponse(uint256 leaseId,uint256 epochId,bytes32 requestHash,bytes32 responseHash)"
        );
        bytes32 digest = keccak256(abi.encodePacked(
            "\\x19\\x01", market.domainSeparator(),
            keccak256(abi.encode(typeHash, leaseId, uint256(0),
                                 keccak256("real-request-content"), responseHash))
        ));
        (uint8 v, bytes32 r, bytes32 sigS) = vm.sign(providerKey, digest);
        SSEAdaptiveVoteLedger.Epoch memory ep = votes.epoch(leaseId, 0);
        vm.warp(uint256(ep.responseDeadline) + 1);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        market.authenticateProviderResponse(leaseId, 0, responseHash,
                                            abi.encodePacked(r, sigS, v));
        assertFalse(votes.epoch(leaseId, 0).responseAuthenticated);
        address[] memory selected = votes.selected(leaseId);
        vm.prank(selected[0]);
        vm.expectRevert(SSEAdaptiveVoteLedger.InvalidPhase.selector);
        votes.submitVoteDirect(leaseId, 0, SSEAdaptiveVoteLedger.Outcome.Success,
                               keccak256("late-success-claim"));
    }

    function testProviderCannotAcceptAfterFrozenDeadline() public {
        uint256 leaseId = _fund(4);
        _draw(leaseId);
        SSEAdaptiveVoteLedger.Committee memory c = votes.committee(leaseId);
        vm.warp(uint256(c.confirmationDeadline) + 1);
        vm.prank(provider);
        vm.expectRevert(SSEAdaptiveMarketV2.InvalidPhase.selector);
        market.acceptLease(leaseId);
        market.cancelUnaccepted(leaseId);
        assertEq(market.withdrawable(consumer), FEE);
        assertEq(votes.withdrawable(consumer), 4 * REWARD);
    }

    function testConstructorRefusesMainnetOrAnotherResearchChain() public {
        vm.chainId(1);
        vm.expectRevert(SSEAdaptiveMarketV2.InvalidInput.selector);
        new SSEAdaptiveMarketV2(BOND);
        vm.chainId(31339);
        vm.expectRevert(SSEAdaptiveMarketV2.InvalidInput.selector);
        new SSEAdaptiveMarketV2(BOND);
        vm.chainId(31340);
        SSEAdaptiveMarketV2 good = new SSEAdaptiveMarketV2(BOND);
        assertEq(good.minimumBond(), BOND);
    }

    function testMarketBalanceCoversBondServiceAndPendingMonitorLiabilities() public {
        uint256 leaseId = _fund(4);
        (uint256 held, uint256 owed, bool covered) = market.escrowAccounting();
        assertTrue(covered);
        assertEq(held, owed);
        assertEq(market.totalPendingMonitorFunding(), 4 * REWARD);
        assertEq(market.totalServiceEscrow(), FEE);
        assertEq(market.totalMonitorBonds(), 9 * BOND);
        _draw(leaseId);
        (held, owed, covered) = market.escrowAccounting();
        assertTrue(covered);
        assertEq(held, owed);
        assertEq(market.totalPendingMonitorFunding(), 0);
        assertEq(address(votes).balance, 4 * REWARD);
    }

    function testRegistrationNotLimitedTo64LifetimeOrActiveEOAs() public {
        for (uint256 i; i < 70; ++i) {
            address addr = address(uint160(0xD000 + i));
            vm.deal(addr, 1 ether);
            vm.prank(addr);
            market.registerMonitor{value: BOND}();
        }
        assertEq(market.activeMonitorCount(), 79);
        // Each lease still scans at most 64 candidates for gas boundedness.
        uint256 leaseId = _fund(4);
        assertEq(market.lease(leaseId).eligibleCount, 64);
    }
}
