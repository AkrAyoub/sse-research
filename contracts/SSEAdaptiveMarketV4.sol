// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {SSEExposureAccounting as Accounting} from "./SSEExposureAccounting.sol";
import {SSEHistoryPolicy as History} from "./SSEHistoryPolicy.sol";
import {SSEAuthenticatedEvidence as Evidence} from "./SSEAuthenticatedEvidence.sol";
import {SSEAdaptiveVoteLedgerV4Candidate as Ledger} from "./SSEAdaptiveVoteLedgerV4Candidate.sol";
import {SSEStandbyCommittee as Standby} from "./SSEStandbyCommittee.sol";
import {SSEMonitorRegistryV4 as Registry} from "./SSEMonitorRegistryV4.sol";
import {SSEServiceBoardV4 as Board} from "./SSEServiceBoardV4.sol";

/// @notice SSE V4 integrated candidate market (escrow + lifecycle orchestration).
/// @dev SOURCE-ONLY CANDIDATE (2026-11-27): NOT compiled, NOT tested, NOT deployed.
/// A distinct new version; it never replaces V3 at its address. Modules:
///   Board    — public requests/bids, no funds;
///   Registry — monitor bonds, capacity, ordered sampling and reservations;
///   Standby  — pre-service confirmation with fixed ordered standby promotion;
///   Ledger   — frozen confirmed committee, votes, report rewards;
///   this     — service escrow, monitor-budget pending reserve, SSE accounting.
/// Lifecycle: award(+fund) -> PendingDraw -> draw -> Forming -> activate ->
/// Active (provider must also accept) -> epochs -> Closed; every pre-service
/// failure path is a refund (Cancelled). Execution is authorized only by an
/// admitted epoch (EpochStarted) of an accepted lease with a frozen committee.
/// Scientific semantics follow V3: N/F/S masks, monotone refinement,
/// exposure-bounded admission, evidence closure, bilateral residual consent.
/// Randomness: future blockhash (proposer-influenceable, NOT a VRF).
contract SSEAdaptiveMarketV4 is EIP712 {
    using Accounting for Accounting.Lease;

    uint256 public constant DRAW_DELAY_BLOCKS = 2;
    uint64 public constant MAX_WINDOW = 7 days;
    bytes32 private constant RESPONSE_TYPEHASH = keccak256(
        "ProviderResponse(uint256 leaseId,uint256 epochId,bytes32 requestHash,bytes32 responseHash)"
    );

    enum Phase { None, PendingDraw, Forming, Active, Closed, Cancelled }

    /// @notice Consumer-chosen operational terms supplied at award time.
    struct Terms {
        uint64 acceptSeconds;          // provider acceptance window after award
        uint64 confirmationRoundSeconds; // standby round (60s..1 day)
        uint64 responseSeconds;
        uint64 monitoringSeconds;
        uint64 evidenceSeconds;
        uint64 idleSeconds;            // max gap between progress steps
        uint256 reservationFee;        // N-history payment (<= epoch fee)
        uint256 exposureBudget;        // max concurrent unresolved exposure
        // Explicit, bilateral evidence assumptions (never implied):
        bool conditionalQuorumPolicy;  // quorum votes qualify S / not-S
        bool responseAdmitsReceipt;    // signed response = binding receipt (excludes N)
    }

    struct Lease {
        address consumer;
        address provider;
        Phase phase;
        bool providerAccepted;
        bool conditionalQuorumPolicy;
        bool responseAdmitsReceipt;
        uint16 seats;
        uint16 standbys;
        uint16 faultTolerance;
        uint64 acceptDeadline;
        uint64 confirmationRoundSeconds;
        uint64 responseSeconds;
        uint64 monitoringSeconds;
        uint64 evidenceSeconds;
        uint64 idleSeconds;
        uint64 lastProgressAt;
        uint256 requestId;
        uint256 bidIndex;
        uint256 epochFee;
        uint256 maxEpochs;
        uint256 nextEpoch;
        uint256 closedEpochs;
        uint256 serviceRemaining;
        uint256 monitorBudget;          // held here until committee activation
        bool monitorBudgetTransferred;
        uint256 perReportReward;
        uint256 entropyBlock;
        uint256 populationCut;
        bytes32 profileHash;
        bytes32 policyHash;
        bytes32 artifactCommitment;
        bytes32 endpointHash;
        bytes32 offerHash;
        bytes32 termsHash;
    }

    struct Epoch {
        bytes32 requestHash;
        bytes32 responseHash;
        uint256 fee;
        uint256 nonce;
        bool exists;
        bool resolved;
        bool acknowledged;
        bool accounted;
        uint64 evidenceClose;
    }

    Board public immutable board;
    Registry public immutable registry;
    Standby public immutable standby;
    Ledger public immutable votes;

    uint256 public nextLeaseId = 1;
    uint256 public totalServiceEscrow;
    uint256 public totalPendingMonitorFunding;
    uint256 public totalWithdrawable;
    mapping(uint256 => Lease) private leases;
    mapping(uint256 => mapping(uint256 => Epoch)) private epochs;
    mapping(uint256 => Accounting.Lease) private accounts;
    mapping(address => uint256) public withdrawable;
    bool private entered;

    error Unauthorized();
    error InvalidInput();
    error InvalidPhase();
    error InsufficientFunding();
    error NoWithdrawal();
    error TransferFailed();
    error InvalidSignature();
    error Reentrancy();

    event LeaseFunded(uint256 indexed leaseId, uint256 indexed requestId, address indexed provider,
        uint256 bidIndex, bytes32 termsHash);
    event DrawCommitted(uint256 indexed leaseId, uint256 entropyBlock, uint256 populationCut);
    event CommitteeDrawn(uint256 indexed leaseId, bytes32 indexed entropy, uint256 seats, uint256 standbys);
    event CommitteeActivated(uint256 indexed leaseId, uint256 seats, uint256 quorum);
    event ProviderAccepted(uint256 indexed leaseId);
    event LeaseCancelled(uint256 indexed leaseId, uint8 reason, uint256 refundedWei);
    event EpochStarted(uint256 indexed leaseId, uint256 indexed epochId, bytes32 requestHash,
        uint64 responseDeadline, uint64 monitoringClose, uint64 evidenceClose);
    event ProviderResponseVerified(uint256 indexed leaseId, uint256 indexed epochId, bytes32 responseHash);
    event ReceiptAccepted(uint256 indexed leaseId, uint256 indexed epochId, bool fromResponse);
    event EntitlementsUpdated(uint256 indexed leaseId, uint256 indexed epochId, uint8 histories,
        uint256 providerDelta, uint256 consumerDelta, uint256 unresolved);
    event EpochConcluded(uint256 indexed leaseId, uint256 indexed epochId, Ledger.Outcome outcome);
    event EvidenceClosed(uint256 indexed leaseId, uint256 indexed epochId);
    event InconclusiveAllocated(uint256 indexed leaseId, uint256 indexed epochId,
        uint256 consumerShare, uint256 providerShare);
    event LeaseClosed(uint256 indexed leaseId, uint256 returnedServiceWei, bool idleExpiry);
    event Withdrawal(address indexed account, uint256 amount);

    // Cancellation reasons (LeaseCancelled.reason)
    uint8 private constant CANCEL_DRAW_EXPIRED = 1;
    uint8 private constant CANCEL_INSUFFICIENT_MONITORS = 2;
    uint8 private constant CANCEL_COMMITTEE_UNFORMED = 3;
    uint8 private constant CANCEL_UNACCEPTED = 4;

    /// @dev Every module is constructed with this market's (precomputed CREATE)
    /// address; the constructor verifies the mutual wiring so no admin
    /// binding step or privileged owner exists after deployment.
    constructor(Board board_, Registry registry_, Standby standby_, Ledger votes_)
        EIP712("SSEAdaptiveMarketV4", "1")
    {
        if (block.chainid != 31340) revert InvalidInput();
        if (board_.market() != address(this) || registry_.market() != address(this) ||
            standby_.market() != address(this) || votes_.settlement() != address(this))
            revert InvalidInput();
        board = board_;
        registry = registry_;
        standby = standby_;
        votes = votes_;
    }

    modifier nonReentrant() {
        if (entered) revert Reentrancy();
        entered = true;
        _;
        entered = false;
    }

    // ------------------------------------------------------------------
    // Award and funding
    // ------------------------------------------------------------------

    /// @notice Consumer awards any valid bid (no minimum bid count, early
    /// close allowed) and funds service escrow + exact monitor report budget.
    function awardAndFund(uint256 requestId, uint256 bidIndex, Terms calldata t)
        external payable nonReentrant returns (uint256 leaseId)
    {
        (Board.Request memory q, Board.Bid memory b) = board.award(requestId, bidIndex, msg.sender);
        if (t.acceptSeconds < 10 minutes || t.acceptSeconds > MAX_WINDOW ||
            t.confirmationRoundSeconds < 60 || t.confirmationRoundSeconds > 1 days ||
            t.responseSeconds == 0 || t.responseSeconds > MAX_WINDOW ||
            t.monitoringSeconds == 0 || t.monitoringSeconds > MAX_WINDOW ||
            t.evidenceSeconds == 0 || t.evidenceSeconds > MAX_WINDOW ||
            t.idleSeconds < 10 minutes || t.idleSeconds > MAX_WINDOW ||
            t.reservationFee > b.epochFee || t.exposureBudget < b.epochFee) revert InvalidInput();
        if (msg.value != b.epochFee * b.epochs + uint256(q.seats) * b.epochs * q.perReportReward)
            revert InsufficientFunding();
        leaseId = nextLeaseId++;
        _recordLease(leaseId, requestId, bidIndex, q, b, t);
    }

    /// @dev Split from awardAndFund to bound stack depth (static review; compile unverified).
    function _recordLease(uint256 leaseId, uint256 requestId, uint256 bidIndex,
        Board.Request memory q, Board.Bid memory b, Terms calldata t) private
    {
        uint256 service = b.epochFee * b.epochs;
        uint256 monitorBudget = uint256(q.seats) * b.epochs * q.perReportReward;
        Lease storage l = leases[leaseId];
        l.consumer = q.consumer;
        l.provider = b.provider;
        l.phase = Phase.PendingDraw;
        l.conditionalQuorumPolicy = t.conditionalQuorumPolicy;
        l.responseAdmitsReceipt = t.responseAdmitsReceipt;
        l.seats = q.seats;
        l.standbys = q.standbys;
        l.faultTolerance = q.faultTolerance;
        l.acceptDeadline = uint64(block.timestamp + t.acceptSeconds);
        l.confirmationRoundSeconds = t.confirmationRoundSeconds;
        l.responseSeconds = t.responseSeconds;
        l.monitoringSeconds = t.monitoringSeconds;
        l.evidenceSeconds = t.evidenceSeconds;
        l.idleSeconds = t.idleSeconds;
        l.requestId = requestId;
        l.bidIndex = bidIndex;
        l.epochFee = b.epochFee;
        l.maxEpochs = b.epochs;
        l.serviceRemaining = service;
        l.monitorBudget = monitorBudget;
        l.perReportReward = q.perReportReward;
        l.entropyBlock = block.number + DRAW_DELAY_BLOCKS;
        // Entries registered after award are excluded from this lease's draw.
        l.populationCut = registry.rosterLength();
        l.profileHash = q.profileHash;
        l.policyHash = q.policyHash;
        l.artifactCommitment = q.artifactCommitment;
        l.endpointHash = b.endpointHash;
        l.offerHash = b.offerHash;
        // Canonical terms commitment the provider must accept verbatim. q is the
        // board record AFTER award (status Awarded, awardedBid = bidIndex).
        l.termsHash = keccak256(abi.encode(block.chainid, address(this), leaseId, bidIndex, q, b, t));
        accounts[leaseId].initialize(b.epochFee, t.reservationFee, t.exposureBudget, b.epochs, service);
        totalServiceEscrow += service;
        totalPendingMonitorFunding += monitorBudget;
        emit LeaseFunded(leaseId, requestId, b.provider, bidIndex, l.termsHash);
        emit DrawCommitted(leaseId, l.entropyBlock, l.populationCut);
    }

    // ------------------------------------------------------------------
    // Committee formation (permissionless, deterministic)
    // ------------------------------------------------------------------

    /// @notice Anyone may draw once the committed entropy block exists.
    /// Insufficient eligible monitors cancels and refunds; never weakens n/b.
    function drawCommittee(uint256 leaseId) external nonReentrant {
        Lease storage l = leases[leaseId];
        if (l.phase != Phase.PendingDraw || block.number <= l.entropyBlock ||
            block.number > l.entropyBlock + 256) revert InvalidPhase();
        bytes32 entropy = blockhash(l.entropyBlock);
        if (entropy == bytes32(0)) revert InvalidPhase();
        bytes32 domain = keccak256(abi.encode("SSE_V4_LEASE_DRAW", block.chainid, address(this), leaseId, l.termsHash));
        uint256 count = uint256(l.seats) + uint256(l.standbys);
        (bool ok, address[] memory ordered) = registry.reserveSample(
            leaseId, entropy, domain, l.populationCut, count, l.consumer, l.provider);
        if (!ok) {
            _cancel(leaseId, CANCEL_INSUFFICIENT_MONITORS);
            return;
        }
        l.phase = Phase.Forming;
        standby.initialize(leaseId, l.consumer, l.provider, ordered, l.seats, l.confirmationRoundSeconds);
        emit CommitteeDrawn(leaseId, entropy, l.seats, l.standbys);
    }

    /// @notice After the standby state machine reports Ready, freeze exactly the
    /// confirmed committee in the vote ledger, transfer the exact report budget
    /// once, and release every unused standby / replaced reservation.
    function activateCommittee(uint256 leaseId) external nonReentrant {
        Lease storage l = leases[leaseId];
        if (l.phase != Phase.Forming || l.monitorBudgetTransferred) revert InvalidPhase();
        (address[] memory members, uint256 quorum) = standby.readyMembers(leaseId);
        if (members.length != l.seats) revert InvalidPhase();
        l.phase = Phase.Active;
        l.monitorBudgetTransferred = true;
        totalPendingMonitorFunding -= l.monitorBudget;
        if (l.providerAccepted) l.lastProgressAt = uint64(block.timestamp);
        Ledger.FreezeTerms memory p = Ledger.FreezeTerms({
            leaseId: leaseId, consumer: l.consumer, provider: l.provider,
            snapshotRoot: l.termsHash, eligibleCount: l.seats,
            requiredFaultTolerance: l.faultTolerance, gasBoundSeats: l.seats,
            monitorBudget: l.monitorBudget, payableEpochs: l.maxEpochs,
            perMonitorEpochReward: l.perReportReward,
            confirmationTimeoutSeconds: 1 hours
        });
        votes.freezeConfirmedCommittee{value: l.monitorBudget}(p, members);
        registry.releaseExcept(leaseId, members);
        emit CommitteeActivated(leaseId, members.length, quorum);
    }

    /// @notice Provider accepts the exact committed terms within the window.
    function acceptLease(uint256 leaseId, bytes32 expectedTermsHash) external {
        Lease storage l = leases[leaseId];
        if (msg.sender != l.provider) revert Unauthorized();
        if (l.providerAccepted || expectedTermsHash != l.termsHash ||
            (l.phase != Phase.PendingDraw && l.phase != Phase.Forming && l.phase != Phase.Active) ||
            block.timestamp > l.acceptDeadline) revert InvalidPhase();
        l.providerAccepted = true;
        if (l.phase == Phase.Active) l.lastProgressAt = uint64(block.timestamp);
        emit ProviderAccepted(leaseId);
    }

    // ------------------------------------------------------------------
    // Pre-service cancellation paths (all refund the consumer in full)
    // ------------------------------------------------------------------

    /// @notice Committed blockhash expired: nobody can choose a replacement seed.
    function cancelExpiredDraw(uint256 leaseId) external nonReentrant {
        Lease storage l = leases[leaseId];
        if (l.phase != Phase.PendingDraw || block.number <= l.entropyBlock + 256) revert InvalidPhase();
        _cancel(leaseId, CANCEL_DRAW_EXPIRED);
    }

    /// @notice Standby reserves exhausted (assignment Expired): refund.
    function cancelUnformed(uint256 leaseId) external nonReentrant {
        Lease storage l = leases[leaseId];
        if (l.phase != Phase.Forming) revert InvalidPhase();
        if (standby.assignment(leaseId).phase != Standby.Phase.Expired) revert InvalidPhase();
        _cancel(leaseId, CANCEL_COMMITTEE_UNFORMED);
    }

    /// @notice Before provider acceptance the consumer may withdraw at any
    /// time; anyone may cancel after the acceptance deadline.
    function cancelUnaccepted(uint256 leaseId) external nonReentrant {
        Lease storage l = leases[leaseId];
        if (l.providerAccepted ||
            (l.phase != Phase.PendingDraw && l.phase != Phase.Forming && l.phase != Phase.Active))
            revert InvalidPhase();
        if (msg.sender != l.consumer && block.timestamp <= l.acceptDeadline) revert Unauthorized();
        _cancel(leaseId, CANCEL_UNACCEPTED);
    }

    /// @dev No epoch was ever admitted on any path reaching here.
    function _cancel(uint256 leaseId, uint8 reason) private {
        Lease storage l = leases[leaseId];
        Phase prior = l.phase;
        l.phase = Phase.Cancelled;
        if (prior == Phase.Forming) {
            if (standby.assignment(leaseId).phase == Standby.Phase.Confirming) standby.cancel(leaseId);
        } else if (prior == Phase.Active) {
            // Committee frozen but unused: ledger refunds its report budget to consumer.
            votes.closeReporting(leaseId);
        }
        if (prior != Phase.PendingDraw) registry.releaseAll(leaseId);
        uint256 refund = l.serviceRemaining;
        if (!l.monitorBudgetTransferred) {
            totalPendingMonitorFunding -= l.monitorBudget;
            refund += l.monitorBudget;
            l.monitorBudgetTransferred = true; // budget leaves the market exactly once
        }
        totalServiceEscrow -= l.serviceRemaining;
        l.serviceRemaining = 0;
        accounts[leaseId].close();
        _credit(l.consumer, refund);
        emit LeaseCancelled(leaseId, reason, refund);
    }

    // ------------------------------------------------------------------
    // Epochs and SSE evidence accounting (V3 semantics preserved)
    // ------------------------------------------------------------------

    /// @notice The ONLY execution authorization: provider agents start work for
    /// (leaseId, epochId, requestHash) only after this event is canonical/final.
    function startEpoch(uint256 leaseId, bytes32 requestHash) external returns (uint256 epochId) {
        Lease storage l = leases[leaseId];
        if (msg.sender != l.consumer) revert Unauthorized();
        if (l.phase != Phase.Active || !l.providerAccepted || requestHash == bytes32(0) ||
            l.nextEpoch >= l.maxEpochs || l.nextEpoch != l.closedEpochs ||
            block.timestamp > uint256(l.lastProgressAt) + l.idleSeconds) revert InvalidPhase();
        uint256 responseDeadline = block.timestamp + l.responseSeconds;
        uint256 monitoringClose = responseDeadline + l.monitoringSeconds;
        uint256 evidenceClose = monitoringClose + l.evidenceSeconds;
        epochId = accounts[leaseId].admit(requestHash);
        ++l.nextEpoch;
        Epoch storage e = epochs[leaseId][epochId];
        e.requestHash = requestHash;
        e.fee = l.epochFee;
        e.exists = true;
        e.evidenceClose = uint64(evidenceClose);
        l.lastProgressAt = uint64(block.timestamp);
        votes.openEpoch(leaseId, epochId, requestHash, uint64(responseDeadline), uint64(monitoringClose));
        emit EpochStarted(leaseId, epochId, requestHash, uint64(responseDeadline),
            uint64(monitoringClose), uint64(evidenceClose));
    }

    /// @notice Authenticates the provider's signed response hash (relayable).
    /// Authenticates origin and context only — NOT SLA correctness. Under the
    /// explicit responseAdmitsReceipt term it is also a binding receipt (excludes N).
    function authenticateProviderResponse(uint256 leaseId, uint256 epochId,
        bytes32 responseHash, bytes calldata signature) external
    {
        Lease storage l = leases[leaseId];
        Epoch storage e = epochs[leaseId][epochId];
        if (!e.exists || e.resolved || responseHash == bytes32(0)) revert InvalidPhase();
        bytes32 digest = _hashTypedDataV4(keccak256(abi.encode(
            RESPONSE_TYPEHASH, leaseId, epochId, e.requestHash, responseHash)));
        if (ECDSA.recover(digest, signature) != l.provider) revert InvalidSignature();
        e.responseHash = responseHash;
        votes.authenticateResponse(leaseId, epochId, responseHash);
        emit ProviderResponseVerified(leaseId, epochId, responseHash);
        if (l.responseAdmitsReceipt && !e.acknowledged) {
            e.acknowledged = true;
            emit ReceiptAccepted(leaseId, epochId, true);
            if (e.accounted) _refine(leaseId, epochId, votes.epoch(leaseId, epochId).outcome);
        }
    }

    /// @notice Binding provider receipt, relayable within the evidence window.
    function submitAcknowledgment(uint256 leaseId, uint256 epochId, bytes calldata signature) external {
        Lease storage l = leases[leaseId];
        Epoch storage e = epochs[leaseId][epochId];
        if (!e.exists || e.acknowledged || accounts[leaseId].epochs[epochId].evidenceClosed)
            revert InvalidPhase();
        Evidence.verifyAcknowledgment(_domainSeparatorV4(),
            Evidence.Context(leaseId, epochId, e.requestHash), l.provider, e.evidenceClose, signature);
        e.acknowledged = true;
        emit ReceiptAccepted(leaseId, epochId, false);
        if (e.accounted) _refine(leaseId, epochId, votes.epoch(leaseId, epochId).outcome);
    }

    function _refine(uint256 leaseId, uint256 epochId, Ledger.Outcome outcome) private {
        Lease storage l = leases[leaseId];
        Epoch storage e = epochs[leaseId][epochId];
        Accounting.Lease storage a = accounts[leaseId];
        if (a.epochs[epochId].residualAllocated || a.epochs[epochId].evidenceClosed) return;
        uint8 mask = History.admissible(e.acknowledged,
            l.conditionalQuorumPolicy && outcome == Ledger.Outcome.Success,
            l.conditionalQuorumPolicy && outcome == Ledger.Outcome.Failure);
        mask = History.narrow(a.epochs[epochId].mask, mask);
        (uint256 dp, uint256 dc) = a.refine(epochId, mask);
        l.serviceRemaining -= dp + dc;
        totalServiceEscrow -= dp + dc;
        _credit(l.provider, dp);
        _credit(l.consumer, dc);
        e.resolved = a.epochs[epochId].unresolved == 0;
        emit EntitlementsUpdated(leaseId, epochId, mask, dp, dc, a.epochs[epochId].unresolved);
    }

    /// @notice Permissionless; epochs are finalized strictly in order.
    function finalizeEpoch(uint256 leaseId, uint256 epochId) public returns (Ledger.Outcome outcome) {
        Lease storage l = leases[leaseId];
        Epoch storage e = epochs[leaseId][epochId];
        if (!e.exists || e.accounted || epochId != l.closedEpochs) revert InvalidPhase();
        Ledger.Epoch memory v = votes.epoch(leaseId, epochId);
        outcome = v.monitoringSealed ? v.outcome : votes.seal(leaseId, epochId);
        e.accounted = true;
        ++l.closedEpochs;
        if (l.phase == Phase.Active) l.lastProgressAt = uint64(block.timestamp);
        _refine(leaseId, epochId, outcome);
        emit EpochConcluded(leaseId, epochId, outcome);
    }

    function closeEpochEvidence(uint256 leaseId, uint256 epochId) external {
        Epoch storage e = epochs[leaseId][epochId];
        if (!e.exists || block.timestamp <= e.evidenceClose) revert InvalidPhase();
        if (!e.accounted) finalizeEpoch(leaseId, epochId);
        accounts[leaseId].closeEvidence(epochId);
        emit EvidenceClosed(leaseId, epochId);
    }

    /// @notice Bilateral consent allocation of a closed epoch's residual.
    /// Consent is not evidence; the history mask is preserved.
    function resolveResidual(uint256 leaseId, uint256 epochId, Evidence.Allocation calldata a,
        bytes calldata consumerSig, bytes calldata providerSig) external
    {
        Lease storage l = leases[leaseId];
        Epoch storage e = epochs[leaseId][epochId];
        if (!e.exists || e.resolved || !accounts[leaseId].epochs[epochId].evidenceClosed) revert InvalidPhase();
        _verifyResidual(leaseId, epochId, a, consumerSig, providerSig);
        ++e.nonce;
        accounts[leaseId].allocateResidual(epochId, a.providerShare, a.consumerShare);
        e.resolved = true;
        l.serviceRemaining -= a.unresolvedAmount;
        totalServiceEscrow -= a.unresolvedAmount;
        _credit(l.consumer, a.consumerShare);
        _credit(l.provider, a.providerShare);
        emit InconclusiveAllocated(leaseId, epochId, a.consumerShare, a.providerShare);
    }

    /// @dev Preserve the exact library validation and typed digest, but
    /// split the multi-argument call to reduce legacy compiler stack pressure.
    function _verifyResidual(uint256 leaseId, uint256 epochId, Evidence.Allocation calldata a,
        bytes calldata consumerSig, bytes calldata providerSig) private view
    {
        if (block.timestamp > a.expiry) revert Evidence.Expired();
        Lease storage l = leases[leaseId];
        if (l.provider == address(0) || l.consumer == address(0) || l.provider == l.consumer ||
            a.unresolvedAmount != accounts[leaseId].epochs[epochId].unresolved ||
            a.nonce != epochs[leaseId][epochId].nonce) revert Evidence.InvalidEvidence();
        bytes32 digest = Evidence.allocationDigest(_domainSeparatorV4(),
            Evidence.Context(leaseId, epochId, epochs[leaseId][epochId].requestHash), a);
        if (ECDSA.recover(digest, providerSig) != l.provider ||
            ECDSA.recover(digest, consumerSig) != l.consumer) revert Evidence.InvalidSignature();
    }

    // ------------------------------------------------------------------
    // Closure
    // ------------------------------------------------------------------

    /// @notice Consumer early close between epochs.
    function closeLease(uint256 leaseId) external nonReentrant {
        Lease storage l = leases[leaseId];
        if (msg.sender != l.consumer) revert Unauthorized();
        if (l.phase != Phase.Active || !l.providerAccepted || l.nextEpoch != l.closedEpochs) revert InvalidPhase();
        _closeService(leaseId, false);
    }

    /// @notice Anyone may close a lease idle beyond the negotiated idle window
    /// (also covers completion of all epochs) so bonds and escrow are not stranded.
    function forceCloseIdle(uint256 leaseId) external nonReentrant {
        Lease storage l = leases[leaseId];
        if (l.phase != Phase.Active || !l.providerAccepted || l.nextEpoch != l.closedEpochs ||
            (l.nextEpoch < l.maxEpochs && block.timestamp <= uint256(l.lastProgressAt) + l.idleSeconds))
            revert InvalidPhase();
        _closeService(leaseId, true);
    }

    function _closeService(uint256 leaseId, bool idle) private {
        Lease storage l = leases[leaseId];
        l.phase = Phase.Closed;
        votes.closeReporting(leaseId);
        registry.releaseAll(leaseId);
        uint256 refund = accounts[leaseId].close();
        l.serviceRemaining -= refund;
        totalServiceEscrow -= refund;
        _credit(l.consumer, refund);
        emit LeaseClosed(leaseId, refund, idle);
    }

    // ------------------------------------------------------------------
    // Pull payments and views
    // ------------------------------------------------------------------

    function withdraw() external nonReentrant {
        uint256 amount = withdrawable[msg.sender];
        if (amount == 0) revert NoWithdrawal();
        withdrawable[msg.sender] = 0;
        totalWithdrawable -= amount;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        if (!ok) revert TransferFailed();
        emit Withdrawal(msg.sender, amount);
    }

    function _credit(address account, uint256 amount) private {
        if (amount == 0) return;
        withdrawable[account] += amount;
        totalWithdrawable += amount;
    }

    function lease(uint256 leaseId) external view returns (Lease memory) { return leases[leaseId]; }
    function epoch(uint256 leaseId, uint256 epochId) external view returns (Epoch memory) {
        return epochs[leaseId][epochId];
    }

    function scientificAccounting(uint256 leaseId) external view returns (
        uint256 funded, uint256 available, uint256 exposure, uint256 budget,
        uint256 providerCredit, uint256 consumerCredit, bool conserved)
    {
        Accounting.Lease storage a = accounts[leaseId];
        return (a.funded, a.available, a.exposure, a.budget, a.providerCredit, a.consumerCredit, a.conserved());
    }

    function scientificEpoch(uint256 leaseId, uint256 epochId) external view returns (Accounting.Epoch memory) {
        return accounts[leaseId].epochs[epochId];
    }

    /// @notice Market-side native TEST ETH coverage (forced ETH may add surplus).
    function escrowAccounting() external view returns (uint256 marketBalance, uint256 outstanding, bool fullyCovered) {
        marketBalance = address(this).balance;
        outstanding = totalServiceEscrow + totalPendingMonitorFunding + totalWithdrawable;
        fullyCovered = marketBalance >= outstanding;
    }

    function domainSeparator() external view returns (bytes32) { return _domainSeparatorV4(); }
}
