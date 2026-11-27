// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import "forge-std/Test.sol";
import {SSEAdaptiveMarketV4 as M} from "../../contracts/SSEAdaptiveMarketV4.sol";
import {SSEServiceBoardV4 as Board} from "../../contracts/SSEServiceBoardV4.sol";
import {SSEMonitorRegistryV4 as Registry} from "../../contracts/SSEMonitorRegistryV4.sol";
import {SSEStandbyCommittee as Standby} from "../../contracts/SSEStandbyCommittee.sol";
import {SSEAdaptiveVoteLedgerV4Candidate as V} from "../../contracts/SSEAdaptiveVoteLedgerV4Candidate.sol";
import {SSEAuthenticatedEvidence as E} from "../../contracts/SSEAuthenticatedEvidence.sol";
import {SSEEntitlementBounds as B} from "../../contracts/SSEEntitlementBounds.sol";

/// @notice Isolated EVM lifecycle fixtures for the integrated V4 candidate.
/// TEST FIXTURES ONLY — not physical SLA evidence. Written 2026-11-27 in a
/// source-only session: NOT compiled, NOT executed. Owner runs:
///   forge test --match-contract SSEAdaptiveMarketV4Test -vvv
contract SSEAdaptiveMarketV4Test is Test {
    M private market;
    Board private board;
    Registry private registry;
    Standby private standby;
    V private votes;

    uint256 private constant P = 0x12345;
    uint256 private constant C = 0x67890;
    address private provider;
    address private consumer;
    uint256 private constant FEE = 100;
    uint32 private constant EPOCHS = 3;
    uint16 private constant SEATS = 4;
    uint16 private constant STANDBYS = 2;
    uint256 private constant REWARD = 10;
    uint256 private constant BOND = 1000;
    uint256 private constant SERVICE = FEE * EPOCHS;               // 300
    uint256 private constant MONITOR = uint256(SEATS) * EPOCHS * REWARD; // 120
    uint256 private constant TOTAL = SERVICE + MONITOR;            // 420
    uint256 private constant MONITORS = 8;
    bytes32 private constant REQUEST = keccak256("fixture request");
    bytes32 private constant RESPONSE_TYPEHASH = keccak256(
        "ProviderResponse(uint256 leaseId,uint256 epochId,bytes32 requestHash,bytes32 responseHash)");

    function setUp() public {
        vm.chainId(31340);
        vm.warp(1_000_000);
        vm.roll(1000);
        address predicted = vm.computeCreateAddress(address(this), uint256(vm.getNonce(address(this))) + 4);
        board = new Board(predicted);
        registry = new Registry(predicted, BOND);
        votes = new V(predicted);
        standby = new Standby(predicted);
        market = new M(board, registry, standby, votes);
        assertEq(address(market), predicted);
        provider = vm.addr(P);
        consumer = vm.addr(C);
        vm.deal(consumer, 10 ether);
        vm.deal(provider, 10 ether);
        for (uint256 i; i < MONITORS; ++i) {
            address m = mon(i);
            vm.deal(m, 10 ether);
            vm.prank(m);
            registry.register{value: 3 * BOND}(3);
        }
    }

    // ---------------------------------------------------------------- helpers
    function mon(uint256 i) private pure returns (address) { return address(uint160(0xA000 + i)); }

    function terms(bool conditional, bool responseReceipt) private pure returns (M.Terms memory) {
        return M.Terms({acceptSeconds: 1 days, confirmationRoundSeconds: 600, responseSeconds: 100,
            monitoringSeconds: 100, evidenceSeconds: 1000, idleSeconds: 1 days, reservationFee: 20,
            exposureBudget: 150, conditionalQuorumPolicy: conditional, responseAdmitsReceipt: responseReceipt});
    }

    function request(uint16 seats, uint16 standbys) private returns (uint256 id) {
        id = requestB(seats, standbys, 1);
    }

    function requestB(uint16 seats, uint16 standbys, uint16 b) private returns (uint256 id) {
        Board.RequestInput memory r = Board.RequestInput({
            profileHash: keccak256("profile"), policyHash: keccak256("policy"),
            artifactCommitment: keccak256("artifacts"), maxEpochFee: FEE,
            biddingClose: uint64(block.timestamp + 1 hours), fixedEpochs: EPOCHS, maxEpochs: EPOCHS,
            seats: seats, standbys: standbys, faultTolerance: b, perReportReward: REWARD});
        vm.prank(consumer);
        id = board.createRequest(r);
        vm.prank(provider);
        board.placeBid(id, FEE, EPOCHS, uint64(block.timestamp + 1 days), keccak256("endpoint"), keccak256("offer"));
    }

    function fund(bool conditional, bool responseReceipt) private returns (uint256 id) {
        uint256 rid = request(SEATS, STANDBYS);
        uint256 value = SERVICE + uint256(SEATS) * EPOCHS * REWARD;
        vm.prank(consumer);
        id = market.awardAndFund{value: value}(rid, 0, terms(conditional, responseReceipt));
    }

    function draw(uint256 id) private {
        uint256 eb = market.lease(id).entropyBlock;
        vm.roll(eb + 1);
        vm.setBlockhash(eb, keccak256(abi.encode("fixture entropy", id)));
        market.drawCommittee(id);
    }

    function confirmAll(uint256 id) private {
        address[] memory p = standby.assignment(id).primary;
        for (uint256 i; i < p.length; ++i) { vm.prank(p[i]); standby.confirm(id); }
    }

    function open(bool conditional, bool responseReceipt) private returns (uint256 id) {
        id = fund(conditional, responseReceipt);
        draw(id);
        confirmAll(id);
        market.activateCommittee(id);
        bytes32 h = market.lease(id).termsHash;
        vm.prank(provider);
        market.acceptLease(id, h);
    }

    function sign(uint256 key, bytes32 digest) private pure returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(key, digest);
        return abi.encodePacked(r, s, v);
    }

    function respond(uint256 id, uint256 ep, bytes32 req) private {
        bytes32 resp = keccak256(abi.encode("response", id, ep));
        bytes32 d = keccak256(abi.encodePacked("\x19\x01", market.domainSeparator(),
            keccak256(abi.encode(RESPONSE_TYPEHASH, id, ep, req, resp))));
        market.authenticateProviderResponse(id, ep, resp, sign(P, d));
    }

    function vote(uint256 id, uint256 ep, V.Outcome o, uint256 n) private {
        address[] memory s = votes.selected(id);
        if (o == V.Outcome.Failure) vm.warp(uint256(votes.epoch(id, ep).responseDeadline) + 1);
        for (uint256 i; i < n; ++i) {
            vm.prank(s[i]);
            votes.submitVoteDirect(id, ep, o, keccak256(abi.encode(i, ep)));
        }
    }

    function conclude(uint256 id, uint256 ep) private {
        vm.warp(uint256(votes.epoch(id, ep).monitoringClose) + 1);
        market.finalizeEpoch(id, ep);
    }

    function covered() private view {
        (uint256 bal, uint256 out, bool ok) = market.escrowAccounting();
        assertTrue(ok);
        assertEq(bal, out);
        assertEq(address(votes).balance, votes.totalUnspentReserves() + votes.totalWithdrawableCredits());
        (uint256 rb, uint256 ro, bool rok) = registry.bondAccounting();
        assertTrue(rok);
        assertEq(rb, ro);
    }

    function totalReserved() private view returns (uint256 sum) {
        for (uint256 i; i < MONITORS; ++i) { (,, uint256 r,,) = registry.position(mon(i)); sum += r; }
    }

    // ------------------------------------------------------------------ tests

    function testHappyPathEndToEndConservation() public {
        uint256 id = open(true, false);
        assertEq(totalReserved(), SEATS); // standbys released at activation
        for (uint256 ep; ep < EPOCHS; ++ep) {
            bytes32 req = keccak256(abi.encode(REQUEST, ep));
            vm.prank(consumer);
            assertEq(market.startEpoch(id, req), ep);
            respond(id, ep, req);
            vote(id, ep, V.Outcome.Success, 3);
            conclude(id, ep);
            assertEq(market.scientificEpoch(id, ep).unresolved, 0);
            covered();
        }
        assertEq(market.withdrawable(provider), SERVICE);
        vm.prank(consumer);
        market.closeLease(id);
        assertEq(totalReserved(), 0);
        assertEq(market.totalServiceEscrow(), 0);
        assertEq(votes.withdrawable(consumer), MONITOR - 9 * REWARD);
        (,,,,,, bool conserved) = market.scientificAccounting(id);
        assertTrue(conserved);
        uint256 before = provider.balance;
        vm.prank(provider);
        market.withdraw();
        assertEq(provider.balance - before, SERVICE);
        covered();
    }

    function testBidAwardAndFundingAloneNeverAuthorizeExecution() public {
        uint256 id = fund(true, false);
        vm.prank(consumer);
        vm.expectRevert(M.InvalidPhase.selector);
        market.startEpoch(id, REQUEST);         // PendingDraw
        draw(id);
        confirmAll(id);
        vm.prank(consumer);
        vm.expectRevert(M.InvalidPhase.selector);
        market.startEpoch(id, REQUEST);         // Forming, not activated
        market.activateCommittee(id);
        vm.prank(consumer);
        vm.expectRevert(M.InvalidPhase.selector);
        market.startEpoch(id, REQUEST);         // Active but provider not accepted
    }

    function testWrongTermsHashCannotAccept() public {
        uint256 id = fund(true, false);
        vm.prank(provider);
        vm.expectRevert(M.InvalidPhase.selector);
        market.acceptLease(id, keccak256("other terms"));
        bytes32 committed = market.lease(id).termsHash;
        vm.prank(consumer);
        vm.expectRevert(M.Unauthorized.selector);
        market.acceptLease(id, committed);
    }

    function testEarlyAwardOfSingleBidClosesRequest() public {
        uint256 rid = request(SEATS, STANDBYS);
        assertLt(block.timestamp, board.request(rid).biddingClose);
        vm.prank(consumer);
        market.awardAndFund{value: TOTAL}(rid, 0, terms(true, false));
        vm.prank(address(0xBEEF));
        vm.expectRevert(Board.InvalidPhase.selector);
        board.placeBid(rid, FEE, EPOCHS, uint64(block.timestamp + 1 days), keccak256("e"), keccak256("o"));
        vm.prank(consumer);
        vm.expectRevert(Board.InvalidPhase.selector);
        market.awardAndFund{value: TOTAL}(rid, 0, terms(true, false));
    }

    function testOnlyConsumerAwardsAndExactFunding() public {
        uint256 rid = request(SEATS, STANDBYS);
        vm.prank(provider);
        vm.expectRevert(Board.Unauthorized.selector);
        market.awardAndFund{value: TOTAL}(rid, 0, terms(true, false));
        vm.prank(consumer);
        vm.expectRevert(M.InsufficientFunding.selector);
        market.awardAndFund{value: TOTAL - 1}(rid, 0, terms(true, false));
    }

    function testStandbyPromotionFreezesFinalCommitteeAndReleasesOthers() public {
        uint256 id = fund(true, false);
        draw(id);
        Standby.Assignment memory a = standby.assignment(id);
        address p1 = a.primary[1];
        address p3 = a.primary[3];
        vm.prank(a.primary[0]); standby.confirm(id);
        vm.prank(a.primary[2]); standby.confirm(id);
        vm.warp(uint256(a.deadline) + 1);
        standby.advance(id);
        vm.prank(a.standby[0]); standby.confirm(id);
        vm.prank(a.standby[1]); standby.confirm(id);
        market.activateCommittee(id);
        address[] memory seats = votes.selected(id);
        assertEq(seats.length, SEATS);
        assertEq(seats[1], a.standby[0]);
        assertEq(seats[3], a.standby[1]);
        (,, uint256 r1,,) = registry.position(p1);
        (,, uint256 r3,,) = registry.position(p3);
        assertEq(r1, 0);
        assertEq(r3, 0);
        assertEq(totalReserved(), SEATS);
        assertEq(votes.committee(id).quorum, 3);
        bytes32 committed = market.lease(id).termsHash;
        vm.prank(provider);
        market.acceptLease(id, committed);
        vm.prank(consumer);
        market.startEpoch(id, REQUEST);
        respond(id, 0, REQUEST);
        vm.prank(p1); // replaced primary cannot vote
        vm.expectRevert(V.Unauthorized.selector);
        votes.submitVoteDirect(id, 0, V.Outcome.Success, keccak256("x"));
    }

    function testUnformedCommitteeRefundsEverything() public {
        uint256 id = fund(true, false);
        draw(id);
        vm.warp(uint256(standby.assignment(id).deadline) + 1);
        standby.advance(id); // 4 missing > 2 standbys => Expired
        assertEq(uint8(standby.assignment(id).phase), uint8(Standby.Phase.Expired));
        market.cancelUnformed(id);
        assertEq(market.withdrawable(consumer), TOTAL);
        assertEq(totalReserved(), 0);
        assertEq(market.totalPendingMonitorFunding(), 0);
        covered();
    }

    function testInsufficientEligibleMonitorsCancelsWithoutWeakening() public {
        uint256 rid = request(SEATS, 5); // 9 > 8 registered monitors
        vm.prank(consumer);
        uint256 id = market.awardAndFund{value: TOTAL}(rid, 0, terms(true, false));
        draw(id);
        assertEq(uint8(market.lease(id).phase), uint8(M.Phase.Cancelled));
        assertEq(market.withdrawable(consumer), TOTAL);
        assertEq(totalReserved(), 0);
        covered();
    }

    function testExpiredDrawRefund() public {
        uint256 id = fund(true, false);
        vm.roll(market.lease(id).entropyBlock + 257);
        vm.expectRevert(M.InvalidPhase.selector);
        market.drawCommittee(id);
        market.cancelExpiredDraw(id);
        assertEq(market.withdrawable(consumer), TOTAL);
        covered();
    }

    function testUnacceptedCancellationRules() public {
        uint256 id = fund(true, false);
        draw(id);
        confirmAll(id);
        market.activateCommittee(id);
        vm.prank(address(0xBEEF));
        vm.expectRevert(M.Unauthorized.selector);
        market.cancelUnaccepted(id);           // stranger before deadline
        vm.warp(uint256(market.lease(id).acceptDeadline) + 1);
        bytes32 committed = market.lease(id).termsHash;
        vm.prank(provider);
        vm.expectRevert(M.InvalidPhase.selector);
        market.acceptLease(id, committed); // too late
        vm.prank(address(0xBEEF));
        market.cancelUnaccepted(id);
        assertEq(market.withdrawable(consumer), SERVICE);
        assertEq(votes.withdrawable(consumer), MONITOR); // ledger refunds report budget
        assertEq(totalReserved(), 0);
        covered();
    }

    function testConsumerMayWithdrawBeforeAcceptanceDuringForming() public {
        uint256 id = fund(true, false);
        draw(id);
        vm.prank(consumer);
        market.cancelUnaccepted(id);
        assertEq(market.withdrawable(consumer), TOTAL);
        assertEq(uint8(standby.assignment(id).phase), uint8(Standby.Phase.Expired));
        address[] memory p = standby.assignment(id).primary;
        vm.prank(p[0]);
        vm.expectRevert(Standby.InvalidPhase.selector);
        standby.confirm(id);
        assertEq(totalReserved(), 0);
    }

    function testReadyButNotActivatedCancellationClearsSeats() public {
        uint256 id = fund(true, false);
        draw(id);
        confirmAll(id);
        assertEq(uint8(standby.assignment(id).phase), uint8(Standby.Phase.Ready));
        vm.prank(consumer);
        market.cancelUnaccepted(id);
        assertEq(uint8(market.lease(id).phase), uint8(M.Phase.Cancelled));
        assertEq(uint8(standby.assignment(id).phase), uint8(Standby.Phase.Expired));
        assertEq(market.withdrawable(consumer), TOTAL);
        assertEq(totalReserved(), 0);
        covered();
    }

    function testCounterpartiesNeverDrawn() public {
        vm.prank(provider); registry.register{value: 2 * BOND}(2);
        vm.prank(consumer); registry.register{value: 2 * BOND}(2);
        uint256 id = fund(true, false);
        draw(id);
        address[] memory r = registry.reservedFor(id);
        for (uint256 i; i < r.length; ++i) {
            assertTrue(r[i] != provider && r[i] != consumer);
            for (uint256 j; j < i; ++j) assertTrue(r[i] != r[j]);
        }
    }

    function testLateRegistrantsExcludedFromDraw() public {
        uint256 id = fund(true, false);
        address late = address(0xCAFE);
        vm.deal(late, 1 ether);
        vm.prank(late); registry.register{value: BOND}(1);
        draw(id);
        address[] memory r = registry.reservedFor(id);
        for (uint256 i; i < r.length; ++i) assertTrue(r[i] != late);
    }

    function testExitBlockedWhileReservedThenReleased() public {
        uint256 id = open(true, false);
        address m = votes.selected(id)[0];
        vm.prank(m); registry.requestExit();
        vm.prank(m);
        vm.expectRevert(Registry.InvalidPhase.selector);
        registry.completeExit();
        vm.prank(consumer); market.closeLease(id);
        vm.prank(m); registry.completeExit();
        assertEq(registry.withdrawable(m), 3 * BOND);
        covered();
    }

    function testConcurrentLeasesRespectCapacity() public {
        // 8 monitors x capacity 3 = 24 seats; each lease reserves 6 then keeps 4.
        uint256 a = open(true, false);
        uint256 b = open(true, false);
        uint256 c = fund(true, false);
        draw(c);
        assertEq(totalReserved(), 2 * SEATS + SEATS + STANDBYS);
        for (uint256 i; i < MONITORS; ++i) {
            (,, uint256 r,,) = registry.position(mon(i));
            assertLe(r, 3);
        }
        vm.prank(consumer); market.closeLease(a);
        vm.prank(consumer); market.closeLease(b);
        vm.prank(consumer); market.cancelUnaccepted(c);
        assertEq(totalReserved(), 0);
        covered();
    }

    function testResponseAsReceiptOnlyUnderExplicitTerm() public {
        // With the term: signed response excludes N; failure quorum => full refund.
        uint256 id = open(true, true);
        vm.prank(consumer); market.startEpoch(id, REQUEST);
        respond(id, 0, REQUEST);
        assertTrue(market.epoch(id, 0).acknowledged);
        vote(id, 0, V.Outcome.Failure, 3);
        conclude(id, 0);
        assertEq(market.withdrawable(consumer), FEE);
        assertEq(market.scientificEpoch(id, 0).unresolved, 0);
        // Without the term (V3 semantics): reservation fee stays unresolved.
        uint256 id2 = open(true, false);
        vm.prank(consumer); market.startEpoch(id2, REQUEST);
        respond(id2, 0, REQUEST);
        assertFalse(market.epoch(id2, 0).acknowledged);
        vote(id2, 0, V.Outcome.Failure, 3);
        conclude(id2, 0);
        assertEq(market.scientificEpoch(id2, 0).unresolved, 20);
        covered();
    }

    function testConservativeModeNeverInfersVerdictFromVotes() public {
        uint256 id = open(false, false);
        vm.prank(consumer); market.startEpoch(id, REQUEST);
        vote(id, 0, V.Outcome.Failure, 4);
        conclude(id, 0);
        assertEq(market.withdrawable(consumer), 0);
        assertEq(market.withdrawable(provider), 0);
        assertEq(market.scientificEpoch(id, 0).unresolved, FEE);
        vm.prank(consumer);
        vm.expectRevert(B.ExposureExceeded.selector);
        market.startEpoch(id, keccak256("second"));
    }

    function testMissingResponseIsNotProofOfViolation() public {
        // No response, no failure quorum: all histories remain admissible.
        uint256 id = open(true, false);
        vm.prank(consumer); market.startEpoch(id, REQUEST);
        vote(id, 0, V.Outcome.Failure, 2); // below quorum 3
        conclude(id, 0);
        assertEq(uint8(votes.epoch(id, 0).outcome), uint8(V.Outcome.None));
        assertEq(market.scientificEpoch(id, 0).mask, 7);
        assertEq(market.scientificEpoch(id, 0).unresolved, FEE);
    }

    function testResidualConsentAfterEvidenceClosureAndReplay() public {
        uint256 id = open(true, false);
        vm.prank(consumer); market.startEpoch(id, REQUEST);
        vote(id, 0, V.Outcome.Failure, 3);
        conclude(id, 0);
        assertEq(market.scientificEpoch(id, 0).unresolved, 20);
        vm.prank(consumer); market.closeLease(id);
        vm.warp(uint256(market.epoch(id, 0).evidenceClose) + 1);
        market.closeEpochEvidence(id, 0);
        E.Allocation memory al = E.Allocation(20, 7, 13, 0, block.timestamp + 100);
        bytes32 d = E.allocationDigest(market.domainSeparator(), E.Context(id, 0, REQUEST), al);
        bytes memory ps = sign(P, d);
        bytes memory cs = sign(C, d);
        vm.expectRevert(E.InvalidSignature.selector);
        market.resolveResidual(id, 0, al, ps, ps);
        market.resolveResidual(id, 0, al, cs, ps);
        assertEq(market.withdrawable(provider), 7);
        assertEq(market.totalServiceEscrow(), 0);
        vm.expectRevert(M.InvalidPhase.selector);
        market.resolveResidual(id, 0, al, cs, ps);
        covered();
    }

    function testNoDoubleFinalizeOrAcknowledge() public {
        uint256 id = open(true, false);
        vm.prank(consumer); market.startEpoch(id, REQUEST);
        bytes32 d = E.acknowledgmentDigest(market.domainSeparator(), E.Context(id, 0, REQUEST));
        market.submitAcknowledgment(id, 0, sign(P, d));
        vm.expectRevert(M.InvalidPhase.selector);
        market.submitAcknowledgment(id, 0, sign(P, d));
        conclude(id, 0);
        vm.expectRevert(M.InvalidPhase.selector);
        market.finalizeEpoch(id, 0);
    }

    function testIdleForceCloseIsPermissionless() public {
        uint256 id = open(true, false);
        vm.expectRevert(M.InvalidPhase.selector);
        market.forceCloseIdle(id);
        vm.warp(block.timestamp + 1 days + 1);
        vm.prank(address(0xBEEF));
        market.forceCloseIdle(id);
        assertEq(market.withdrawable(consumer), SERVICE);
        assertEq(totalReserved(), 0);
        covered();
    }

    /// @dev Agents recompute termsHash from public board views (DRV-V4-PARITY anchor);
    /// the logged value is compared with tools/sse_v4_terms.py by the owner.
    function testTermsHashRecomputableFromPublicViews() public {
        uint256 id = fund(true, false);
        M.Lease memory l = market.lease(id);
        bytes32 h = keccak256(abi.encode(block.chainid, address(market), id, l.bidIndex,
            board.request(l.requestId), board.bidAt(l.requestId, l.bidIndex), terms(true, false)));
        assertEq(h, l.termsHash);
        emit log_named_bytes32("termsHash", h);
    }

    /// @dev Larger committee n=7, b=2, s=4 (gas report anchor for DRV-V4-GAS).
    function testSevenSeatCommitteeQuorumFive() public {
        for (uint256 i = MONITORS; i < 20; ++i) {
            address m = mon(i);
            vm.deal(m, 10 ether);
            vm.prank(m);
            registry.register{value: BOND}(1);
        }
        uint256 rid = requestB(7, 4, 2);
        vm.prank(consumer);
        uint256 id = market.awardAndFund{value: SERVICE + 7 * uint256(EPOCHS) * REWARD}(rid, 0, terms(true, false));
        draw(id);
        assertEq(uint8(market.lease(id).phase), uint8(M.Phase.Forming));
        confirmAll(id);
        market.activateCommittee(id);
        assertEq(votes.committee(id).seats, 7);
        assertEq(votes.committee(id).quorum, 5);
        assertEq(votes.selected(id).length, 7);
        covered();
    }

    // ------------------------------------------------- gas-parametrized formation
    /// @dev Records formation gas for larger committees (owner reads `forge test -vv` logs and
    /// `--gas-report`). Asserts only structural facts and a generous per-call ceiling so the
    /// test fails loudly if a configuration would not fit a 30M block. Written, NOT executed.
    function formationGas(uint16 n, uint16 s, uint16 b) private {
        for (uint256 i = MONITORS; i < 40; ++i) { // 40 entries: draw failure odds negligible for n+s ≤ 14
            address m = mon(i);
            vm.deal(m, 10 ether);
            vm.prank(m);
            registry.register{value: BOND}(1);
        }
        uint256 rid = requestB(n, s, b);
        vm.prank(consumer);
        uint256 id = market.awardAndFund{value: SERVICE + uint256(n) * EPOCHS * REWARD}(rid, 0, terms(true, false));
        uint256 eb = market.lease(id).entropyBlock;
        vm.roll(eb + 1);
        vm.setBlockhash(eb, keccak256(abi.encode("fixture entropy", id)));
        uint256 g = gasleft();
        market.drawCommittee(id);
        uint256 drawGas = g - gasleft();
        assertEq(uint8(market.lease(id).phase), uint8(M.Phase.Forming));
        confirmAll(id);
        g = gasleft();
        market.activateCommittee(id);
        uint256 activateGas = g - gasleft();
        emit log_named_uint("seats", n);
        emit log_named_uint("standbys", s);
        emit log_named_uint("drawCommittee gas", drawGas);
        emit log_named_uint("activateCommittee gas", activateGas);
        assertLt(drawGas, 15_000_000);
        assertLt(activateGas, 15_000_000);
        assertEq(votes.committee(id).seats, n);
        assertEq(votes.committee(id).quorum, uint256(n) - (uint256(n) - 1) / 3);
        uint256 reservedSum;
        for (uint256 i; i < 40; ++i) { (,, uint256 r,,) = registry.position(mon(i)); reservedSum += r; }
        assertEq(reservedSum, n); // standbys released at activation
        covered();
    }

    function testFormationGas7Seats2Standbys() public { formationGas(7, 2, 2); }
    function testFormationGas7Seats4Standbys() public { formationGas(7, 4, 2); }
    function testFormationGas10Seats2Standbys() public { formationGas(10, 2, 3); }
    function testFormationGas10Seats4Standbys() public { formationGas(10, 4, 3); }

    /// @dev Fuzz: arbitrary per-epoch evidence combinations conserve funds.
    function testFuzzConservation(uint8 pattern) public {
        uint256 id = open(true, true);
        for (uint256 ep; ep < EPOCHS; ++ep) {
            uint8 k = uint8((pattern >> (2 * ep)) & 3);
            bytes32 req = keccak256(abi.encode(REQUEST, ep));
            vm.prank(consumer);
            try market.startEpoch(id, req) returns (uint256) {} catch { break; }
            if (k == 1 || k == 2) respond(id, ep, req);
            if (k == 1) vote(id, ep, V.Outcome.Success, 3);
            if (k == 2 || k == 3) vote(id, ep, V.Outcome.Failure, 3);
            conclude(id, ep);
            (,,,,,, bool conserved) = market.scientificAccounting(id);
            assertTrue(conserved);
            covered();
        }
        vm.prank(consumer);
        market.closeLease(id);
        covered();
    }
}
