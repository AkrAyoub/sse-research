// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {AdaptiveMonitorQuorum} from "./AdaptiveMonitorQuorum.sol";

/// @notice Adaptive monitor vote ledger integrated with SSEAdaptiveMarketV2.
/// @dev The market freezes bonded candidates and registers committees, but
/// physical fault-domain independence and unbiased selection are NOT proven.
/// This ledger is not wired to the legacy V1 SSESettlement.
contract SSEAdaptiveVoteLedgerV4Candidate is EIP712 {
    enum Outcome { None, Success, Failure }

    bytes32 private constant VOTE_TYPEHASH = keccak256(
        "MonitorVote(uint256 leaseId,uint256 epochId,bytes32 requestHash,uint8 outcome,bytes32 responseHash,bytes32 evidenceHash)"
    );

    /// @dev One immutable per-lease policy record; struct argument avoids
    /// unsafe multi-argument ABI/stack pressure when k is dynamic.
    struct FreezeTerms {
        uint256 leaseId;
        address consumer;
        address provider;
        bytes32 snapshotRoot;
        uint256 eligibleCount;
        uint256 requiredFaultTolerance;
        uint256 gasBoundSeats;
        uint256 monitorBudget;
        uint256 payableEpochs;
        uint256 perMonitorEpochReward;
        // Frozen once at selection. A bounded pre-epoch confirmation period.
        uint64 confirmationTimeoutSeconds;
    }

    struct Committee {
        address consumer;
        address provider;
        bytes32 eligibilitySnapshotRoot;
        uint256 seats;
        uint256 quorum;
        uint256 requiredFaultTolerance;
        uint64 confirmationDeadline;
        bool initialized;
        bool ready;
        bool confirmationExpired;
        // Real, not merely declared, TEST ETH monitoring reward escrow.
        uint256 rewardPerReport;
        uint256 originalReportBudget;
        uint256 unspentReportBudget;
        uint256 maxPayableEpochs;
        uint256 openedEpochs;
        uint256 sealedEpochs;
        bool reportingClosed;
    }

    struct Epoch {
        bytes32 requestHash;
        bytes32 responseHash;
        uint64 responseDeadline;
        uint64 monitoringClose;
        uint256 successVotes;
        uint256 failureVotes;
        uint256 totalVotes;
        bool exists;
        bool responseAuthenticated;
        bool monitoringSealed;
        Outcome outcome;
    }

    address public immutable settlement;
    mapping(uint256 => Committee) private committees;
    mapping(uint256 => address[]) private seatsByLease;
    mapping(uint256 => mapping(address => bool)) public selectedMonitor;
    mapping(uint256 => mapping(address => bool)) public confirmedMonitor;
    mapping(uint256 => uint256) public confirmations;
    mapping(uint256 => mapping(uint256 => Epoch)) private epochs;
    mapping(uint256 => mapping(uint256 => mapping(address => bool))) public voted;
    mapping(uint256 => mapping(uint256 => mapping(address => bytes32))) public evidenceHashByMonitor;
    mapping(address => uint256) public withdrawable;
    // Conservation: total actual received report ETH still held =
    // totalUnspentReserves + totalWithdrawableCredits (unless external forced ETH).
    uint256 public totalUnspentReserves;
    uint256 public totalWithdrawableCredits;
    bool private withdrawing;

    error Unauthorized();
    error InvalidArgument();
    error InvalidPhase();
    error DuplicateMonitor();
    error NoSecureCommittee();
    error AlreadyVoted();
    error FundingMismatch();
    error PaymentFailed();
    error NoWithdrawal();

    event CommitteeFrozen(uint256 indexed leaseId, bytes32 indexed snapshotRoot, uint256 seats, uint256 quorum);
    event SeatConfirmed(uint256 indexed leaseId, address indexed monitor, uint256 totalConfirmed);
    event CommitteeReady(uint256 indexed leaseId);
    event CommitteeConfirmationExpired(uint256 indexed leaseId, uint256 missingConfirmations);
    event EpochOpened(uint256 indexed leaseId, uint256 indexed epochId, bytes32 requestHash);
    event ResponseAuthenticated(uint256 indexed leaseId, uint256 indexed epochId, bytes32 responseHash);
    event VoteRecorded(uint256 indexed leaseId, uint256 indexed epochId, address indexed monitor, Outcome outcome, bytes32 evidenceHash);
    event MonitoringSealed(uint256 indexed leaseId, uint256 indexed epochId, Outcome outcome);
    event ReportRewardEarned(uint256 indexed leaseId, uint256 indexed epochId, address indexed monitor, uint256 amount);
    event SeatSelected(uint256 indexed leaseId, address indexed monitor);
    event ReportingClosed(uint256 indexed leaseId, uint256 unspentRefunded);
    event Withdrawal(address indexed account, uint256 amount);

    constructor(address settlement_) EIP712("SSEAdaptiveCommitteeVotesV4", "1") {
        if (settlement_ == address(0)) revert InvalidArgument();
        settlement = settlement_;
    }

    modifier onlySettlement() {
        if (msg.sender != settlement) revert Unauthorized();
        _;
    }

    /// @dev Registers a real per-lease committee into on-chain state, not
    /// merely a pure math proposal. Caller must be a future audited settlement
    /// that already verified selection proof and independent candidate policy.
    /// Snapshot hash must be nonzero, frozen and immutable.
    function freezeCommittee(FreezeTerms calldata p, address[] calldata selectedSeats)
        external payable onlySettlement
    {
        _freeze(p, selectedSeats, false);
    }

    /// @dev Market MUST verify every seat confirmed in its standby state machine.
    function freezeConfirmedCommittee(FreezeTerms calldata p, address[] calldata selectedSeats)
        external payable onlySettlement
    {
        _freeze(p, selectedSeats, true);
    }

    function _freeze(FreezeTerms calldata p, address[] calldata selectedSeats, bool preconfirmed) private
    {
        if (p.leaseId == 0 || p.consumer == address(0) || p.provider == address(0) ||
            p.consumer == p.provider || p.snapshotRoot == bytes32(0) ||
            committees[p.leaseId].initialized ||
            p.confirmationTimeoutSeconds < 1 hours ||
            p.confirmationTimeoutSeconds > 7 days ||
            block.timestamp + p.confirmationTimeoutSeconds > type(uint64).max)
            revert InvalidArgument();

        if (msg.value != p.monitorBudget) revert FundingMismatch();
        AdaptiveMonitorQuorum.Decision memory plan = AdaptiveMonitorQuorum.decide(
            p.eligibleCount, p.requiredFaultTolerance, p.gasBoundSeats,
            p.monitorBudget, p.payableEpochs, p.perMonitorEpochReward
        );
        if (selectedSeats.length != plan.seats) revert NoSecureCommittee();
        // Prevent an unexpected monetary surplus from being trapped on deposit.
        // Every selected seat has exact guaranteed reward funding for every
        // committed report epoch; this is REAL native TEST ETH held here.
        if (p.monitorBudget != plan.seats * (p.payableEpochs * p.perMonitorEpochReward))
            revert FundingMismatch();

        Committee storage c = committees[p.leaseId];
        c.consumer = p.consumer;
        c.provider = p.provider;
        c.eligibilitySnapshotRoot = p.snapshotRoot;
        c.seats = plan.seats;
        c.quorum = plan.quorum;
        c.requiredFaultTolerance = p.requiredFaultTolerance;
        c.confirmationDeadline = uint64(block.timestamp + p.confirmationTimeoutSeconds);
        c.rewardPerReport = p.perMonitorEpochReward;
        c.originalReportBudget = msg.value;
        c.unspentReportBudget = msg.value;
        totalUnspentReserves += msg.value;
        c.maxPayableEpochs = p.payableEpochs;
        c.initialized = true;

        for (uint256 i; i < selectedSeats.length; ++i) {
            address monitor = selectedSeats[i];
            if (monitor == address(0) || monitor == p.consumer || monitor == p.provider)
                revert Unauthorized();
            if (selectedMonitor[p.leaseId][monitor]) revert DuplicateMonitor();
            selectedMonitor[p.leaseId][monitor] = true;
            seatsByLease[p.leaseId].push(monitor);
            emit SeatSelected(p.leaseId, monitor);
            if (preconfirmed) {
                confirmedMonitor[p.leaseId][monitor] = true;
                emit SeatConfirmed(p.leaseId, monitor, i + 1);
            }
        }
        emit CommitteeFrozen(p.leaseId, p.snapshotRoot, c.seats, c.quorum);
        if (preconfirmed) {
            confirmations[p.leaseId] = c.seats;
            c.ready = true;
            emit CommitteeReady(p.leaseId);
        }
    }

    function confirmSeat(uint256 leaseId) external {
        Committee storage c = committees[leaseId];
        if (!c.initialized || c.ready || c.confirmationExpired ||
            block.timestamp > c.confirmationDeadline ||
            !selectedMonitor[leaseId][msg.sender]) revert Unauthorized();
        if (confirmedMonitor[leaseId][msg.sender]) revert InvalidPhase();
        confirmedMonitor[leaseId][msg.sender] = true;
        uint256 count = ++confirmations[leaseId];
        emit SeatConfirmed(leaseId, msg.sender, count);
        if (count == c.seats) {
            c.ready = true;
            emit CommitteeReady(leaseId);
        }
    }

    /// @notice Anyone may expire an incomplete committee AFTER its frozen
    /// confirmation period; it cannot be reselected under the same lease ID.
    /// @dev No votes, funds, bonds, or consumer payouts are changed here.
    /// The future settlement must independently handle a safe lease refund.
    function expireUnconfirmed(uint256 leaseId) external {
        Committee storage c = committees[leaseId];
        if (!c.initialized || c.ready || c.confirmationExpired ||
            block.timestamp <= c.confirmationDeadline) revert InvalidPhase();
        c.confirmationExpired = true;
        c.reportingClosed = true;
        uint256 refund = c.unspentReportBudget;
        c.unspentReportBudget = 0;
        totalUnspentReserves -= refund;
        totalWithdrawableCredits += refund;
        withdrawable[c.consumer] += refund;
        emit CommitteeConfirmationExpired(leaseId, c.seats - confirmations[leaseId]);
        emit ReportingClosed(leaseId, refund);
    }

    function openEpoch(uint256 leaseId, uint256 epochId, bytes32 requestHash,
                       uint64 responseDeadline, uint64 monitoringClose)
        external onlySettlement
    {
        Committee storage c = committees[leaseId];
        if (!c.ready || c.reportingClosed || c.confirmationExpired ||
            requestHash == bytes32(0) || epochId != c.openedEpochs ||
            c.openedEpochs >= c.maxPayableEpochs ||
            monitoringClose <= responseDeadline || responseDeadline <= block.timestamp ||
            epochs[leaseId][epochId].exists) revert InvalidPhase();
        Epoch storage e = epochs[leaseId][epochId];
        e.requestHash = requestHash;
        e.responseDeadline = responseDeadline;
        e.monitoringClose = monitoringClose;
        e.exists = true;
        ++c.openedEpochs;
        emit EpochOpened(leaseId, epochId, requestHash);
    }

    /// @dev Only settlement may mark a response authenticated AFTER validating
    /// the real provider EIP-712 signature and lease/epoch context.
    function authenticateResponse(uint256 leaseId, uint256 epochId, bytes32 responseHash)
        external onlySettlement
    {
        Epoch storage e = epochs[leaseId][epochId];
        if (!e.exists || e.monitoringSealed || responseHash == bytes32(0) ||
            e.responseAuthenticated || block.timestamp > e.responseDeadline)
            revert InvalidPhase();
        e.responseHash = responseHash;
        e.responseAuthenticated = true;
        emit ResponseAuthenticated(leaseId, epochId, responseHash);
    }

    function submitSignedVote(
        uint256 leaseId, uint256 epochId, Outcome outcome,
        bytes32 evidenceHash, bytes calldata signature
    ) external {
        Epoch storage e = epochs[leaseId][epochId];
        if (!e.exists) revert InvalidPhase();
        bytes32 voteHash = keccak256(abi.encode(
            VOTE_TYPEHASH, leaseId, epochId, e.requestHash,
            uint8(outcome), outcome == Outcome.Success ? e.responseHash : bytes32(0),
            evidenceHash
        ));
        address signer = ECDSA.recover(_hashTypedDataV4(voteHash), signature);
        _recordVote(leaseId, epochId, outcome, evidenceHash, signer);
    }

    function submitVoteDirect(uint256 leaseId, uint256 epochId, Outcome outcome,
                              bytes32 evidenceHash) external {
        _recordVote(leaseId, epochId, outcome, evidenceHash, msg.sender);
    }

    function _recordVote(uint256 leaseId, uint256 epochId, Outcome outcome,
                         bytes32 evidenceHash, address signer) internal {
        Epoch storage e = epochs[leaseId][epochId];
        if (!e.exists || e.monitoringSealed || block.timestamp > e.monitoringClose) revert InvalidPhase();
        if (!confirmedMonitor[leaseId][signer]) revert Unauthorized();
        if (voted[leaseId][epochId][signer]) revert AlreadyVoted();
        if (evidenceHash == bytes32(0) || outcome == Outcome.None) revert InvalidArgument();
        if (outcome == Outcome.Failure && block.timestamp < e.responseDeadline) revert InvalidPhase();
        if (outcome == Outcome.Success && !e.responseAuthenticated) revert InvalidPhase();
        voted[leaseId][epochId][signer] = true;
        evidenceHashByMonitor[leaseId][epochId][signer] = evidenceHash;
        ++e.totalVotes;
        if (outcome == Outcome.Success) ++e.successVotes;
        else ++e.failureVotes;
        Committee storage c = committees[leaseId];
        // One paid report per selected signer and epoch (voted enforces this).
        // Reward eligibility does not mean that the signed report is true.
        uint256 reward = c.rewardPerReport;
        c.unspentReportBudget -= reward;
        totalUnspentReserves -= reward;
        totalWithdrawableCredits += reward;
        withdrawable[signer] += reward;
        emit VoteRecorded(leaseId, epochId, signer, outcome, evidenceHash);
        emit ReportRewardEarned(leaseId, epochId, signer, reward);
    }

    /// @notice Permissionless sealing does NOT assert physical truth of an SLA.
    /// Insufficient/conflicting evidence remains None, not a made-up payout.
    function seal(uint256 leaseId, uint256 epochId) external returns (Outcome result) {
        Epoch storage e = epochs[leaseId][epochId];
        if (!e.exists || e.monitoringSealed || block.timestamp <= e.monitoringClose) revert InvalidPhase();
        e.monitoringSealed = true;
        uint256 threshold = committees[leaseId].quorum;
        if (e.successVotes >= threshold) result = Outcome.Success;
        else if (e.failureVotes >= threshold) result = Outcome.Failure;
        else result = Outcome.None;
        e.outcome = result;
        ++committees[leaseId].sealedEpochs;
        emit MonitoringSealed(leaseId, epochId, result);
    }

    /// @notice Called only by the future audited settlement on lease close.
    /// Cannot return reserved rewards while ANY accepted epoch is unsealed.
    /// Refund goes to recorded consumer's owner account, not msg.sender.
    function closeReporting(uint256 leaseId) external onlySettlement {
        Committee storage c = committees[leaseId];
        if (!c.initialized || !c.ready || c.reportingClosed ||
            c.openedEpochs != c.sealedEpochs) revert InvalidPhase();
        c.reportingClosed = true;
        uint256 refund = c.unspentReportBudget;
        c.unspentReportBudget = 0;
        totalUnspentReserves -= refund;
        totalWithdrawableCredits += refund;
        withdrawable[c.consumer] += refund;
        emit ReportingClosed(leaseId, refund);
    }

    /// @notice Pull-payment; no report/timeout caller chooses a destination.
    function withdraw() external {
        if (withdrawing) revert InvalidPhase();
        uint256 amount = withdrawable[msg.sender];
        if (amount == 0) revert NoWithdrawal();
        withdrawing = true;
        withdrawable[msg.sender] = 0;
        totalWithdrawableCredits -= amount;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        if (!ok) revert PaymentFailed();
        withdrawing = false;
        emit Withdrawal(msg.sender, amount);
    }

    function committee(uint256 leaseId) external view returns (Committee memory) {
        return committees[leaseId];
    }

    function selected(uint256 leaseId) external view returns (address[] memory) {
        return seatsByLease[leaseId];
    }

    function epoch(uint256 leaseId, uint256 epochId) external view returns (Epoch memory) {
        return epochs[leaseId][epochId];
    }

    function domainSeparator() external view returns (bytes32) {
        return _domainSeparatorV4();
    }
}
