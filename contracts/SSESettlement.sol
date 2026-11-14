// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {OpenMonitorCommittee} from "./OpenMonitorCommittee.sol";


contract SSESettlement is EIP712 {
    uint8 private constant COMMITTEE_SIZE = 4;
    uint8 private constant QUORUM = 3;
    uint256 private constant MAX_EPOCHS = 64;
    // Fixed pre-epoch confirmation window. Never shorten a replacement's
    // opportunity to confirm via repeated permissionless rotation calls.
    uint64 public constant MONITOR_CONFIRMATION_TIMEOUT = 1 hours;

    // Bits for N (no receipt), F (received but failed), S (fulfilled)
    uint8 private constant HISTORY_N = 1;
    uint8 private constant HISTORY_F = 2;
    uint8 private constant HISTORY_S = 4;

    bytes32 private constant RESPONSE_LABEL = keccak256("SSE_RESPONSE");

    bytes32 private constant ACK_TYPEHASH =
        keccak256("ProviderAck(uint256 leaseId,uint256 epochId,bytes32 requestHash)");
    bytes32 private constant RESPONSE_TYPEHASH =
        keccak256("ProviderResponse(uint256 leaseId,uint256 epochId,bytes32 requestHash,bytes32 responseHash)");
    bytes32 private constant VOTE_TYPEHASH =
        keccak256("MonitorVote(uint256 leaseId,uint256 epochId,bytes32 requestHash,uint8 outcome,bytes32 responseHash,bytes32 evidenceHash)");
    bytes32 private constant RESIDUAL_AGREEMENT_TYPEHASH =
        keccak256("ResidualAgreement(uint256 leaseId,uint256 epochId,uint256 unresolvedAmount,uint256 providerShare,uint256 consumerShare,uint256 nonce,uint256 expiry)");
    uint8 private constant REWARD_SEAL = 1;
    uint8 private constant REWARD_SETTLE = 2;
    uint8 private constant REWARD_CLOSE = 4;

    enum LeaseState { Offered, Accepted, Ready, Active, Closed }
    enum Outcome { None, Success, Failure }

    struct Lease {
        address consumer;
        address provider;
        address[4] monitors;
        uint256 assignmentId;
        bytes32 serviceEndpointHash;
        bytes32 resourceProfileHash;
        bytes32 slaPolicyHash;
        uint256 marketplaceRequestId;
        uint256 totalEscrow;
        uint256 uncommittedEscrow;
        uint256 refundedUnusedEscrow;
        uint256 epochFee;
        uint256 reservationFee;
        uint256 exposureBudget;
        uint256 currentExposure;
        uint256 nextEpochId;
        uint256 maxEpochs;
        uint64 responsePeriod;
        uint64 monitoringGrace;
        uint64 evidenceWindow;
        uint8 monitorConfirmations;
        LeaseState state;
    }

    struct LeaseTerms {
        address consumer;
        address provider;
        bytes32 serviceEndpointHash;
        bytes32 resourceProfileHash;
        bytes32 slaPolicyHash;
        uint256 marketplaceRequestId;
        uint256 epochFee;
        uint256 reservationFee;
        uint256 exposureBudget;
        uint256 maxEpochs;
        uint64 responsePeriod;
        uint64 monitoringGrace;
        uint64 evidenceWindow;
    }

    struct Epoch {
        bytes32 requestHash;
        bytes32 responseHash;
        uint256 fee;
        uint256 reservationFee;
        uint64 responseDeadline;
        uint64 monitoringClose;
        uint64 evidenceClose;
        uint256 providerCredited;
        uint256 consumerCredited;
        uint256 unresolvedExposure;
        uint8 successVotes;
        uint8 failureVotes;
        bool exists;
        bool acknowledged;
        bool responseAuthenticated;
        bool monitoringSealed;
        bool evidenceClosed;
        Outcome outcome;
    }

    struct ResidualAllocation {
        uint256 providerShare;
        uint256 consumerShare;
        uint256 nonce;
        uint256 expiry;
    }

    struct IncentiveBudget {
        uint256 monitorRewardPerReport;
        uint256 sealBounty;
        uint256 settlementBounty;
        uint256 evidenceCloseBounty;
        uint256 releaseBounty;
        uint256 monitorReserved;
        uint256 executorReserved;
        bool configured;
        bool refunded;
    }

    OpenMonitorCommittee public immutable committeePool;
    address public immutable bootstrapper;
    address public resourceBoard;
    uint256 public nextLeaseId = 1;
    bool private withdrawalEntered;

    mapping(uint256 => Lease) private leases;
    mapping(uint256 => mapping(uint256 => Epoch)) private epochs;
    mapping(uint256 => mapping(address => bool)) private confirmedMonitor;
    mapping(uint256 => uint64) public monitorConfirmationDeadline;
    mapping(uint256 => mapping(uint256 => mapping(address => bool))) private voted;
    mapping(uint256 => mapping(bytes32 => bool)) private usedRequestHash;
    mapping(address => uint256) public withdrawable;
    mapping(uint256 => IncentiveBudget) private incentiveBudgets;
    mapping(uint256 => mapping(uint256 => uint8)) private rewardedEpochTransitions;
    mapping(uint256 => bool) private rewardedCommitteeRelease;
    mapping(uint256 => mapping(uint256 => bool)) public residualResolved;
    // Commitment to the full off-chain evidence payload
    mapping(uint256 => mapping(uint256 => mapping(address => bytes32))) public monitorEvidenceHash;

    event ResourceBoardBound(address indexed board);
    event CommitteeAssignmentRequested(uint256 indexed leaseId, uint256 indexed assignmentId);
    event CommitteeAssigned(uint256 indexed leaseId, uint256 indexed assignmentId);
    event CommitteeBondsReleased(uint256 indexed leaseId);
    event CommitteeSeatRotated(uint256 indexed leaseId, address indexed missing,
                               address indexed replacement, uint64 nextDeadline);
    event LeaseCreated(uint256 indexed leaseId, address indexed consumer, address indexed provider, uint256 escrow);
    event ComputeProfileCommitted(uint256 indexed leaseId, bytes32 indexed profileHash);
    event LeaseAccepted(uint256 indexed leaseId);
    event CommitteeReady(uint256 indexed leaseId);
    event EpochAdmitted(uint256 indexed leaseId, uint256 indexed epochId, bytes32 requestHash);
    event ProviderAcknowledged(uint256 indexed leaseId, uint256 indexed epochId);
    event ProviderResponseAuthenticated(uint256 indexed leaseId, uint256 indexed epochId, bytes32 responseHash);
    event MonitorVoted(uint256 indexed leaseId, uint256 indexed epochId, address indexed monitor, Outcome outcome, bytes32 evidenceHash);
    event MonitoringSealed(uint256 indexed leaseId, uint256 indexed epochId, Outcome outcome);
    event SettlementUpdated(uint256 indexed leaseId, uint256 indexed epochId, uint256 lower, uint256 upper, uint256 exposure);
    event EpochEvidenceClosed(uint256 indexed leaseId, uint256 indexed epochId, uint256 retained);
    event LeaseClosed(uint256 indexed leaseId, uint256 uncommittedRefund);
    event Withdrawal(address indexed account, uint256 amount);
    event IncentivesFunded(uint256 indexed leaseId, uint256 monitorDeposit, uint256 executorDeposit);
    event MonitorRewardEarned(uint256 indexed leaseId, uint256 indexed epochId, address indexed monitor, uint256 amount);
    event ExecutorRewardEarned(uint256 indexed leaseId, uint256 indexed epochId, address indexed executor, uint8 action, uint256 amount);
    event UnusedIncentivesRefunded(uint256 indexed leaseId, address indexed consumer, uint256 amount);
    event ResidualAgreementExecuted(uint256 indexed leaseId, uint256 indexed epochId, uint256 indexed nonce, uint256 providerShare, uint256 consumerShare);

    error Unauthorized();
    error InvalidArgument();
    error InvalidState();
    error InvalidSignature();
    error InvalidEvidence();
    error OutsideWindow();
    error ExposureExceeded();
    error InsufficientFunding();
    error NoWithdrawal();
    error PaymentFailed();

    constructor(address pool) EIP712("SSESettlement", "1") {
        if (pool == address(0)) revert InvalidArgument();
        committeePool = OpenMonitorCommittee(pool);
        bootstrapper = msg.sender;
    }

    function bindResourceBoard(address board) external {
        if (msg.sender != bootstrapper || resourceBoard != address(0)) revert Unauthorized();
        if (board == address(0) || board.code.length == 0) revert InvalidArgument();
        resourceBoard = board;
        emit ResourceBoardBound(board);
    }

    modifier onlyConsumer(uint256 leaseId) {
        if (msg.sender != leases[leaseId].consumer) revert Unauthorized();
        _;
    }

    function createLease(
        address provider,
        bytes32 serviceEndpointHash,
        bytes32 resourceProfileHash,
        uint256 epochFee,
        uint256 reservationFee,
        uint256 exposureBudget,
        uint256 maxEpochs,
        uint64 responsePeriod,
        uint64 monitoringGrace,
        uint64 evidenceWindow
    ) external payable returns (uint256 leaseId) {
        LeaseTerms memory terms;
        terms.consumer = msg.sender;
        terms.provider = provider;
        terms.serviceEndpointHash = serviceEndpointHash;
        terms.resourceProfileHash = resourceProfileHash;
        terms.epochFee = epochFee;
        terms.reservationFee = reservationFee;
        terms.exposureBudget = exposureBudget;
        terms.maxEpochs = maxEpochs;
        terms.responsePeriod = responsePeriod;
        terms.monitoringGrace = monitoringGrace;
        terms.evidenceWindow = evidenceWindow;
        return _createLease(terms);
    }

    function createLeaseFromBoard(LeaseTerms calldata terms) external payable returns (uint256 leaseId) {
        if (resourceBoard == address(0) || msg.sender != resourceBoard) revert Unauthorized();
        if (terms.marketplaceRequestId == 0 || terms.slaPolicyHash == bytes32(0)) revert InvalidArgument();
        return _createLease(terms);
    }

    function _createLease(LeaseTerms memory terms) internal returns (uint256 leaseId) {
        if (terms.consumer == address(0) || terms.provider == address(0) ||
            terms.consumer == terms.provider) revert InvalidArgument();
        if (terms.serviceEndpointHash == bytes32(0) ||
            terms.resourceProfileHash == bytes32(0) || terms.epochFee == 0 ||
            terms.reservationFee > terms.epochFee ||
            terms.exposureBudget < terms.epochFee ||
            terms.maxEpochs == 0 || terms.maxEpochs > MAX_EPOCHS ||
            terms.responsePeriod == 0 || terms.monitoringGrace == 0 ||
            terms.evidenceWindow == 0) revert InvalidArgument();
        if (msg.value != terms.epochFee * terms.maxEpochs) revert InsufficientFunding();

        leaseId = nextLeaseId++;
        Lease storage lease = leases[leaseId];
        lease.consumer = terms.consumer;
        lease.provider = terms.provider;
        lease.serviceEndpointHash = terms.serviceEndpointHash;
        lease.resourceProfileHash = terms.resourceProfileHash;
        lease.slaPolicyHash = terms.slaPolicyHash;
        lease.marketplaceRequestId = terms.marketplaceRequestId;
        lease.totalEscrow = msg.value;
        lease.uncommittedEscrow = msg.value;
        lease.epochFee = terms.epochFee;
        lease.reservationFee = terms.reservationFee;
        lease.exposureBudget = terms.exposureBudget;
        lease.maxEpochs = terms.maxEpochs;
        lease.responsePeriod = terms.responsePeriod;
        lease.monitoringGrace = terms.monitoringGrace;
        lease.evidenceWindow = terms.evidenceWindow;
        lease.state = LeaseState.Offered;
        lease.assignmentId = committeePool.requestAssignment(terms.consumer, terms.provider);
        emit CommitteeAssignmentRequested(leaseId, lease.assignmentId);
        emit LeaseCreated(leaseId, terms.consumer, terms.provider, msg.value);
        emit ComputeProfileCommitted(leaseId, terms.resourceProfileHash);
    }
    function configureIncentives(
        uint256 leaseId,
        uint256 monitorRewardPerReport,
        uint256 sealBounty,
        uint256 settlementBounty,
        uint256 evidenceCloseBounty,
        uint256 releaseBounty
    ) external payable onlyConsumer(leaseId) {
        Lease storage lease = leases[leaseId];
        IncentiveBudget storage budget = incentiveBudgets[leaseId];
        if (lease.state != LeaseState.Offered || budget.configured) revert InvalidState();
        uint256 monitorDeposit = lease.maxEpochs * COMMITTEE_SIZE * monitorRewardPerReport;
        uint256 executorDeposit = lease.maxEpochs * (
            sealBounty + settlementBounty + evidenceCloseBounty
        ) + releaseBounty;
        if (monitorDeposit + executorDeposit == 0 || msg.value != monitorDeposit + executorDeposit)
            revert InsufficientFunding();
        budget.monitorRewardPerReport = monitorRewardPerReport;
        budget.sealBounty = sealBounty;
        budget.settlementBounty = settlementBounty;
        budget.evidenceCloseBounty = evidenceCloseBounty;
        budget.releaseBounty = releaseBounty;
        budget.monitorReserved = monitorDeposit;
        budget.executorReserved = executorDeposit;
        budget.configured = true;
        emit IncentivesFunded(leaseId, monitorDeposit, executorDeposit);
    }

    function getIncentiveBudget(uint256 leaseId) external view returns (IncentiveBudget memory) {
        return incentiveBudgets[leaseId];
    }

    function acceptLease(uint256 leaseId) external {
        Lease storage lease = leases[leaseId];
        if (msg.sender != lease.provider) revert Unauthorized();
        if (lease.state != LeaseState.Offered) revert InvalidState();
        lease.state = LeaseState.Accepted;
        emit LeaseAccepted(leaseId);
    }

    function finalizeMonitorCommittee(uint256 leaseId) external {
        Lease storage lease = leases[leaseId];
        if (lease.state != LeaseState.Accepted || lease.monitors[0] != address(0)) revert InvalidState();
        lease.monitors = committeePool.getCommittee(lease.assignmentId);
        _resetMonitorConfirmationDeadline(leaseId);
        emit CommitteeAssigned(leaseId, lease.assignmentId);
    }

    function confirmMonitorAssignment(uint256 leaseId) external {
        Lease storage lease = leases[leaseId];
        if (lease.state != LeaseState.Accepted || lease.monitors[0] == address(0)) revert InvalidState();
        bool found;
        for (uint256 i; i < COMMITTEE_SIZE; ++i) {
            if (lease.monitors[i] == msg.sender) { found = true; break; }
        }
        if (!found) revert Unauthorized();
        if (confirmedMonitor[leaseId][msg.sender]) revert InvalidState();
        confirmedMonitor[leaseId][msg.sender] = true;
        ++lease.monitorConfirmations;
        if (lease.monitorConfirmations == COMMITTEE_SIZE) {
            lease.state = LeaseState.Ready;
            emit CommitteeReady(leaseId);
        }
    }

    /// @notice Recover a pre-epoch lease if a selected monitor never confirms.
    /// @dev Permissionless after one full confirmation window; replaces only the
    /// first unconfirmed seat with the next eligible pre-shuffled standby.
    /// Existing confirmation signatures and lease funds are untouched. This
    /// cannot be invoked once the committee is Ready or an epoch has started.
    function replaceNoShowMonitor(uint256 leaseId) external {
        Lease storage lease = leases[leaseId];
        if (lease.state != LeaseState.Accepted || lease.monitors[0] == address(0) ||
            lease.nextEpochId != 0 || lease.monitorConfirmations >= COMMITTEE_SIZE)
            revert InvalidState();
        if (monitorConfirmationDeadline[leaseId] == 0 ||
            block.timestamp <= monitorConfirmationDeadline[leaseId]) revert OutsideWindow();

        for (uint256 i; i < COMMITTEE_SIZE; ++i) {
            address missing = lease.monitors[i];
            if (confirmedMonitor[leaseId][missing]) continue;
            // Pool requires its original seed-determined standby order and
            // enforces active-bond eligibility; never authorize arbitrary seats.
            address replacement = committeePool.replaceUnconfirmed(lease.assignmentId, missing);
            if (replacement == address(0) || confirmedMonitor[leaseId][replacement])
                revert InvalidState();
            lease.monitors[i] = replacement;
            _resetMonitorConfirmationDeadline(leaseId);
            emit CommitteeSeatRotated(leaseId, missing, replacement,
                                      monitorConfirmationDeadline[leaseId]);
            return;
        }
        revert InvalidState();
    }

    function _resetMonitorConfirmationDeadline(uint256 leaseId) internal {
        uint256 deadline = block.timestamp + MONITOR_CONFIRMATION_TIMEOUT;
        if (deadline > type(uint64).max) revert InvalidArgument();
        monitorConfirmationDeadline[leaseId] = uint64(deadline);
    }

    function admitEpoch(uint256 leaseId, bytes32 requestHash)
        external onlyConsumer(leaseId) returns (uint256 epochId)
    {
        Lease storage lease = leases[leaseId];
        if (lease.state != LeaseState.Ready && lease.state != LeaseState.Active) revert InvalidState();
        if (requestHash == bytes32(0) || usedRequestHash[leaseId][requestHash])
            revert InvalidArgument();
        if (lease.nextEpochId >= lease.maxEpochs) revert InvalidState();
        if (lease.uncommittedEscrow < lease.epochFee) revert InsufficientFunding();
        if (lease.currentExposure + lease.epochFee > lease.exposureBudget) revert ExposureExceeded();

        epochId = lease.nextEpochId++;
        usedRequestHash[leaseId][requestHash] = true;
        Epoch storage ep = epochs[leaseId][epochId];
        ep.exists = true;
        ep.requestHash = requestHash;
        // The expected response is derived from the agreed deterministic challenge protocol, not freely chosen by the consumer.
        ep.responseHash = keccak256(abi.encode(RESPONSE_LABEL, requestHash));
        ep.fee = lease.epochFee;
        ep.reservationFee = lease.reservationFee;
        uint256 responseTime = block.timestamp + lease.responsePeriod;
        uint256 monitoringTime = responseTime + lease.monitoringGrace;
        uint256 closureTime = monitoringTime + lease.evidenceWindow;
        if (closureTime > type(uint64).max) revert InvalidArgument();
        ep.responseDeadline = uint64(responseTime);
        ep.monitoringClose = uint64(monitoringTime);
        ep.evidenceClose = uint64(closureTime);
        ep.unresolvedExposure = ep.fee;
        lease.uncommittedEscrow -= ep.fee;
        lease.currentExposure += ep.fee;
        lease.state = LeaseState.Active;
        emit EpochAdmitted(leaseId, epochId, requestHash);
    }

    function submitAcknowledgment(uint256 leaseId, uint256 epochId, bytes calldata signature) external {
        Lease storage lease = leases[leaseId];
        Epoch storage ep = _epoch(leaseId, epochId);
        if (block.timestamp > ep.evidenceClose || ep.evidenceClosed) revert OutsideWindow();
        if (ep.acknowledged) revert InvalidState();
        bytes32 structHash = keccak256(abi.encode(ACK_TYPEHASH, leaseId, epochId, ep.requestHash));
        if (ECDSA.recover(_hashTypedDataV4(structHash), signature) != lease.provider)
            revert InvalidSignature();
        ep.acknowledged = true;
        emit ProviderAcknowledged(leaseId, epochId);
    }

    function submitProviderResponse(uint256 leaseId, uint256 epochId, bytes calldata signature) external {
        Lease storage lease = leases[leaseId];
        Epoch storage ep = _epoch(leaseId, epochId);
        if (block.timestamp > ep.monitoringClose || ep.monitoringSealed) revert OutsideWindow();
        if (ep.responseAuthenticated) revert InvalidState();
        bytes32 structHash = keccak256(abi.encode(
            RESPONSE_TYPEHASH, leaseId, epochId, ep.requestHash, ep.responseHash
        ));
        if (ECDSA.recover(_hashTypedDataV4(structHash), signature) != lease.provider)
            revert InvalidSignature();
        ep.responseAuthenticated = true;
        emit ProviderResponseAuthenticated(leaseId, epochId, ep.responseHash);
    }

    function submitMonitorVote(uint256 leaseId, uint256 epochId, Outcome outcome, bytes32 evidenceHash, bytes calldata signature)
        external
    {
        _recordMonitorVote(leaseId, epochId, outcome, evidenceHash, signature);
    }
    function submitMonitorVotesBatch(
        uint256 leaseId,
        uint256 epochId,
        Outcome[] calldata outcomes,
        bytes32[] calldata evidenceHashes,
        bytes[] calldata signatures
    ) external {
        uint256 count = outcomes.length;
        if (count == 0 || count > COMMITTEE_SIZE || count != signatures.length || count != evidenceHashes.length)
            revert InvalidArgument();
        for (uint256 i; i < count; ++i) {
            _recordMonitorVote(leaseId, epochId, outcomes[i], evidenceHashes[i], signatures[i]);
        }
    }

    function submitMonitorVoteDirect(uint256 leaseId, uint256 epochId, Outcome outcome, bytes32 evidenceHash) external {
        _recordAuthorizedVote(leaseId, epochId, outcome, evidenceHash, msg.sender);
    }

    function _recordMonitorVote(
        uint256 leaseId,
        uint256 epochId,
        Outcome outcome,
        bytes32 evidenceHash,
        bytes calldata signature
    ) internal {
        Epoch storage ep = _epoch(leaseId, epochId);
        bytes32 responseHash = outcome == Outcome.Success ? ep.responseHash : bytes32(0);
        bytes32 structHash = keccak256(abi.encode(
            VOTE_TYPEHASH, leaseId, epochId, ep.requestHash, uint8(outcome), responseHash, evidenceHash
        ));
        address monitor = ECDSA.recover(_hashTypedDataV4(structHash), signature);
        _recordAuthorizedVote(leaseId, epochId, outcome, evidenceHash, monitor);
    }

    function _recordAuthorizedVote(
        uint256 leaseId, uint256 epochId, Outcome outcome, bytes32 evidenceHash, address monitor
    ) internal {
        Lease storage lease = leases[leaseId];
        Epoch storage ep = _epoch(leaseId, epochId);
        if (block.timestamp > ep.monitoringClose || ep.monitoringSealed) revert OutsideWindow();
        if (outcome != Outcome.Success && outcome != Outcome.Failure || evidenceHash == bytes32(0)) revert InvalidArgument();
        if (outcome == Outcome.Failure && block.timestamp < ep.responseDeadline) revert OutsideWindow();
        if (outcome == Outcome.Success && !ep.responseAuthenticated) revert InvalidEvidence();
        bool member;
        for (uint256 i; i < COMMITTEE_SIZE; ++i) {
            if (lease.monitors[i] == monitor) { member = true; break; }
        }
        if (!member || !confirmedMonitor[leaseId][monitor]) revert Unauthorized();
        if (voted[leaseId][epochId][monitor]) revert InvalidState();
        voted[leaseId][epochId][monitor] = true;
        monitorEvidenceHash[leaseId][epochId][monitor] = evidenceHash;
        if (outcome == Outcome.Success) ++ep.successVotes;
        else ++ep.failureVotes;
        emit MonitorVoted(leaseId, epochId, monitor, outcome, evidenceHash);
        //pays eligible dissent as well as the majority
        IncentiveBudget storage budget = incentiveBudgets[leaseId];
        uint256 reward = budget.monitorRewardPerReport;
        if (reward != 0) {
            budget.monitorReserved -= reward;
            withdrawable[monitor] += reward;
            emit MonitorRewardEarned(leaseId, epochId, monitor, reward);
        }
    }

    function sealMonitoring(uint256 leaseId, uint256 epochId) public {
        Epoch storage ep = _epoch(leaseId, epochId);
        if (block.timestamp <= ep.monitoringClose) revert OutsideWindow();
        if (ep.monitoringSealed) revert InvalidState();
        ep.monitoringSealed = true;
        if (ep.successVotes >= QUORUM) ep.outcome = Outcome.Success;
        else if (ep.failureVotes >= QUORUM) ep.outcome = Outcome.Failure;
        // otherwise outcome none->> insufficient evidence, funds stay locked
        emit MonitoringSealed(leaseId, epochId, ep.outcome);
        _rewardEpochExecutor(leaseId, epochId, REWARD_SEAL);
    }


    function settleEpoch(uint256 leaseId, uint256 epochId) public {
        Lease storage lease = leases[leaseId];
        Epoch storage ep = _epoch(leaseId, epochId);
        if (!ep.monitoringSealed || residualResolved[leaseId][epochId]) revert InvalidState();

        uint8 mask = HISTORY_N | HISTORY_F | HISTORY_S;
        if (ep.acknowledged) mask &= HISTORY_F | HISTORY_S;
        if (ep.outcome == Outcome.Success) mask &= HISTORY_S;
        if (ep.outcome == Outcome.Failure) mask &= HISTORY_N | HISTORY_F;
        if (mask == 0) revert InvalidEvidence();

        uint256 lower = type(uint256).max;
        uint256 upper;
        if ((mask & HISTORY_N) != 0) {
            lower = ep.reservationFee;
            upper = ep.reservationFee;
        }
        if ((mask & HISTORY_F) != 0) {
            lower = 0;
        }
        if ((mask & HISTORY_S) != 0) {
            if (ep.fee < lower) lower = ep.fee;
            if (ep.fee > upper) upper = ep.fee;
        }
        uint256 targetProvider = lower;
        uint256 targetConsumer = ep.fee - upper;
        if (targetProvider < ep.providerCredited || targetConsumer < ep.consumerCredited)
            revert InvalidEvidence();
        uint256 deltaProvider = targetProvider - ep.providerCredited;
        uint256 deltaConsumer = targetConsumer - ep.consumerCredited;
        uint256 newExposure = upper - lower;
        if (newExposure > ep.unresolvedExposure) revert InvalidEvidence();
        lease.currentExposure -= ep.unresolvedExposure - newExposure;
        ep.unresolvedExposure = newExposure;
        ep.providerCredited = targetProvider;
        ep.consumerCredited = targetConsumer;
        withdrawable[lease.provider] += deltaProvider;
        withdrawable[lease.consumer] += deltaConsumer;
        emit SettlementUpdated(leaseId, epochId, lower, upper, newExposure);
        _rewardEpochExecutor(leaseId, epochId, REWARD_SETTLE);
    }

    function closeEpochEvidence(uint256 leaseId, uint256 epochId) external {
        Epoch storage ep = _epoch(leaseId, epochId);
        if (block.timestamp <= ep.evidenceClose) revert OutsideWindow();
        if (ep.evidenceClosed) revert InvalidState();
        if (!ep.monitoringSealed) sealMonitoring(leaseId, epochId);
        settleEpoch(leaseId, epochId);
        ep.evidenceClosed = true;
        emit EpochEvidenceClosed(leaseId, epochId, ep.unresolvedExposure);
        _rewardEpochExecutor(leaseId, epochId, REWARD_CLOSE);
    }

    function closeLease(uint256 leaseId) external onlyConsumer(leaseId) {
        Lease storage lease = leases[leaseId];
        if (lease.state == LeaseState.Closed) revert InvalidState();
        uint256 unused = lease.uncommittedEscrow;
        lease.uncommittedEscrow = 0;
        lease.refundedUnusedEscrow += unused;
        lease.state = LeaseState.Closed;
        withdrawable[lease.consumer] += unused;
        emit LeaseClosed(leaseId, unused);
    }

    function releaseCommitteeAfterEvidence(uint256 leaseId) external {
        Lease storage lease = leases[leaseId];
        if (lease.state != LeaseState.Closed || lease.assignmentId == 0) revert InvalidState();
        for (uint256 i; i < lease.nextEpochId; ++i) {
            Epoch storage ep = epochs[leaseId][i];
            if (!ep.evidenceClosed) revert InvalidState();
        }
        committeePool.releaseAssignment(lease.assignmentId);
        emit CommitteeBondsReleased(leaseId);
        if (!rewardedCommitteeRelease[leaseId]) {
            rewardedCommitteeRelease[leaseId] = true;
            IncentiveBudget storage budget = incentiveBudgets[leaseId];
            uint256 reward = budget.releaseBounty;
            if (reward != 0) {
                budget.executorReserved -= reward;
                withdrawable[msg.sender] += reward;
                emit ExecutorRewardEarned(leaseId, type(uint256).max, msg.sender, 8, reward);
            }
        }
    }

    function resolveResidualByAgreement(
        uint256 leaseId,
        uint256 epochId,
        ResidualAllocation calldata allocation,
        bytes calldata consumerSignature,
        bytes calldata providerSignature
    ) external {
        Lease storage lease = leases[leaseId];
        Epoch storage ep = _epoch(leaseId, epochId);
        uint256 residual = ep.unresolvedExposure;
        if (!ep.evidenceClosed || residual == 0 || residualResolved[leaseId][epochId])
            revert InvalidState();
        if (allocation.expiry < block.timestamp) revert OutsideWindow();
        if (allocation.providerShare > residual ||
            allocation.consumerShare != residual - allocation.providerShare)
            revert InvalidArgument();

        bytes32 structHash = keccak256(abi.encode(
            RESIDUAL_AGREEMENT_TYPEHASH,
            leaseId,
            epochId,
            residual,
            allocation.providerShare,
            allocation.consumerShare,
            allocation.nonce,
            allocation.expiry
        ));
        bytes32 digest = _hashTypedDataV4(structHash);
        if (ECDSA.recover(digest, consumerSignature) != lease.consumer ||
            ECDSA.recover(digest, providerSignature) != lease.provider)
            revert InvalidSignature();
        residualResolved[leaseId][epochId] = true;
        ep.unresolvedExposure = 0;
        lease.currentExposure -= residual;
        ep.providerCredited += allocation.providerShare;
        ep.consumerCredited += allocation.consumerShare;
        withdrawable[lease.provider] += allocation.providerShare;
        withdrawable[lease.consumer] += allocation.consumerShare;
        emit ResidualAgreementExecuted(leaseId, epochId, allocation.nonce, allocation.providerShare, allocation.consumerShare);
    }

    function refundUnusedIncentives(uint256 leaseId) external {
        Lease storage lease = leases[leaseId];
        IncentiveBudget storage budget = incentiveBudgets[leaseId];
        if (lease.state != LeaseState.Closed || !budget.configured || budget.refunded)
            revert InvalidState();
        OpenMonitorCommittee.RequestStatus assignmentStatus = committeePool.assignmentStatus(lease.assignmentId);
        if (assignmentStatus != OpenMonitorCommittee.RequestStatus.Released &&
            assignmentStatus != OpenMonitorCommittee.RequestStatus.Expired)
            revert InvalidState();
        for (uint256 i; i < lease.nextEpochId; ++i) {
            if (!epochs[leaseId][i].evidenceClosed) revert InvalidState();
        }
        uint256 refund = budget.monitorReserved + budget.executorReserved;
        budget.monitorReserved = 0;
        budget.executorReserved = 0;
        budget.refunded = true;
        withdrawable[lease.consumer] += refund;
        emit UnusedIncentivesRefunded(leaseId, lease.consumer, refund);
    }

    function _rewardEpochExecutor(uint256 leaseId, uint256 epochId, uint8 action) internal {
        uint8 previous = rewardedEpochTransitions[leaseId][epochId];
        if ((previous & action) != 0) return;
        rewardedEpochTransitions[leaseId][epochId] = previous | action;
        IncentiveBudget storage budget = incentiveBudgets[leaseId];
        uint256 amount;
        if (action == REWARD_SEAL) amount = budget.sealBounty;
        else if (action == REWARD_SETTLE) amount = budget.settlementBounty;
        else if (action == REWARD_CLOSE) amount = budget.evidenceCloseBounty;
        if (amount != 0) {
            budget.executorReserved -= amount;
            withdrawable[msg.sender] += amount;
            emit ExecutorRewardEarned(leaseId, epochId, msg.sender, action, amount);
        }
    }

    function withdraw() external {
        if (withdrawalEntered) revert InvalidState();
        uint256 amount = withdrawable[msg.sender];
        if (amount == 0) revert NoWithdrawal();
        withdrawalEntered = true;
        withdrawable[msg.sender] = 0;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        if (!ok) revert PaymentFailed();
        withdrawalEntered = false;
        emit Withdrawal(msg.sender, amount);
    }

    function getLease(uint256 leaseId) external view returns (Lease memory) { return leases[leaseId]; }
    function getEpoch(uint256 leaseId, uint256 epochId) external view returns (Epoch memory) {
        return epochs[leaseId][epochId];
    }
    function domainSeparator() external view returns (bytes32) { return _domainSeparatorV4(); }

    function _epoch(uint256 leaseId, uint256 epochId) internal view returns (Epoch storage ep) {
        ep = epochs[leaseId][epochId];
        if (!ep.exists) revert InvalidArgument();
    }
}
