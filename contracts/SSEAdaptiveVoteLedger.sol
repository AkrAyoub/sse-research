// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {AdaptiveMonitorQuorum} from "./AdaptiveMonitorQuorum.sol";

/// @notice R22 REAL on-chain variable-size monitor vote ledger for future SSE V2.
/// @dev NOT integrated with V1 SSESettlement or an independently verified
/// election mechanism yet. Only a future immutable settlement contract can
/// register committees and authenticate actual provider responses. The chosen
/// monitors, eligible pool, fault-domain assumptions, and snapshot root MUST
/// be validated by that external settlement before registration.
contract SSEAdaptiveVoteLedger is EIP712 {
    enum Outcome { None, Success, Failure }

    bytes32 private constant VOTE_TYPEHASH = keccak256(
        "MonitorVote(uint256 leaseId,uint256 epochId,bytes32 requestHash,uint8 outcome,bytes32 responseHash,bytes32 evidenceHash)"
    );

    struct Committee {
        address consumer;
        address provider;
        bytes32 eligibilitySnapshotRoot;
        uint256 seats;
        uint256 quorum;
        uint256 requiredFaultTolerance;
        bool initialized;
        bool ready;
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
        bool sealed;
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

    error Unauthorized();
    error InvalidArgument();
    error InvalidPhase();
    error DuplicateMonitor();
    error NoSecureCommittee();
    error AlreadyVoted();

    event CommitteeFrozen(uint256 indexed leaseId, bytes32 indexed snapshotRoot, uint256 seats, uint256 quorum);
    event SeatConfirmed(uint256 indexed leaseId, address indexed monitor, uint256 totalConfirmed);
    event CommitteeReady(uint256 indexed leaseId);
    event EpochOpened(uint256 indexed leaseId, uint256 indexed epochId, bytes32 requestHash);
    event ResponseAuthenticated(uint256 indexed leaseId, uint256 indexed epochId, bytes32 responseHash);
    event VoteRecorded(uint256 indexed leaseId, uint256 indexed epochId, address indexed monitor, Outcome outcome, bytes32 evidenceHash);
    event MonitoringSealed(uint256 indexed leaseId, uint256 indexed epochId, Outcome outcome);

    constructor(address settlement_) EIP712("SSEAdaptiveCommitteeVotes", "1") {
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
    function freezeCommittee(
        uint256 leaseId,
        address consumer,
        address provider,
        bytes32 snapshotRoot,
        address[] calldata selected,
        uint256 eligibleCount,
        uint256 requiredFaultTolerance,
        uint256 gasBoundSeats,
        uint256 monitorBudget,
        uint256 payableEpochs,
        uint256 perMonitorEpochReward
    ) external onlySettlement {
        if (leaseId == 0 || consumer == address(0) || provider == address(0) ||
            consumer == provider || snapshotRoot == bytes32(0) ||
            committees[leaseId].initialized) revert InvalidArgument();

        AdaptiveMonitorQuorum.Decision memory plan = AdaptiveMonitorQuorum.decide(
            eligibleCount, requiredFaultTolerance, gasBoundSeats, monitorBudget,
            payableEpochs, perMonitorEpochReward
        );
        if (selected.length != plan.seats) revert NoSecureCommittee();

        Committee storage c = committees[leaseId];
        c.consumer = consumer;
        c.provider = provider;
        c.eligibilitySnapshotRoot = snapshotRoot;
        c.seats = plan.seats;
        c.quorum = plan.quorum;
        c.requiredFaultTolerance = requiredFaultTolerance;
        c.initialized = true;

        for (uint256 i; i < selected.length; ++i) {
            address monitor = selected[i];
            if (monitor == address(0) || monitor == consumer || monitor == provider)
                revert Unauthorized();
            if (selectedMonitor[leaseId][monitor]) revert DuplicateMonitor();
            selectedMonitor[leaseId][monitor] = true;
            seatsByLease[leaseId].push(monitor);
        }
        emit CommitteeFrozen(leaseId, snapshotRoot, c.seats, c.quorum);
    }

    function confirmSeat(uint256 leaseId) external {
        Committee storage c = committees[leaseId];
        if (!c.initialized || c.ready || !selectedMonitor[leaseId][msg.sender]) revert Unauthorized();
        if (confirmedMonitor[leaseId][msg.sender]) revert InvalidPhase();
        confirmedMonitor[leaseId][msg.sender] = true;
        uint256 count = ++confirmations[leaseId];
        emit SeatConfirmed(leaseId, msg.sender, count);
        if (count == c.seats) {
            c.ready = true;
            emit CommitteeReady(leaseId);
        }
    }

    function openEpoch(uint256 leaseId, uint256 epochId, bytes32 requestHash,
                       uint64 responseDeadline, uint64 monitoringClose)
        external onlySettlement
    {
        if (!committees[leaseId].ready || requestHash == bytes32(0) ||
            monitoringClose <= responseDeadline || responseDeadline <= block.timestamp ||
            epochs[leaseId][epochId].exists) revert InvalidPhase();
        Epoch storage e = epochs[leaseId][epochId];
        e.requestHash = requestHash;
        e.responseDeadline = responseDeadline;
        e.monitoringClose = monitoringClose;
        e.exists = true;
        emit EpochOpened(leaseId, epochId, requestHash);
    }

    /// @dev Only settlement may mark a response authenticated AFTER validating
    /// the real provider EIP-712 signature and lease/epoch context.
    function authenticateResponse(uint256 leaseId, uint256 epochId, bytes32 responseHash)
        external onlySettlement
    {
        Epoch storage e = epochs[leaseId][epochId];
        if (!e.exists || e.sealed || responseHash == bytes32(0) ||
            e.responseAuthenticated || block.timestamp > e.monitoringClose)
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
        if (!e.exists || e.sealed || block.timestamp > e.monitoringClose) revert InvalidPhase();
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
        emit VoteRecorded(leaseId, epochId, signer, outcome, evidenceHash);
    }

    /// @notice Permissionless sealing does NOT assert physical truth of an SLA.
    /// Insufficient/conflicting evidence remains None, not a made-up payout.
    function seal(uint256 leaseId, uint256 epochId) external returns (Outcome result) {
        Epoch storage e = epochs[leaseId][epochId];
        if (!e.exists || e.sealed || block.timestamp <= e.monitoringClose) revert InvalidPhase();
        e.sealed = true;
        uint256 threshold = committees[leaseId].quorum;
        if (e.successVotes >= threshold) result = Outcome.Success;
        else if (e.failureVotes >= threshold) result = Outcome.Failure;
        else result = Outcome.None;
        e.outcome = result;
        emit MonitoringSealed(leaseId, epochId, result);
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
