// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {ScalableMonitorCommitteeV2} from "./ScalableMonitorCommitteeV2.sol";

/// @notice Isolated V2 RESEARCH funded lease/committee adapter.
/// @dev There is deliberately NO monitor-vote-funded payout. Bilateral EIP-712
///      allocation is the only way to allocate an admitted epoch. Incomplete
///      evidence retains the full unresolved amount; indefinite disagreement
///      remains unresolved pending a separately justified dispute policy.
///      Not compatible with production SSESettlement V1; not a full SLA oracle.
contract SSELeaseControllerV2 is EIP712 {
    uint256 public constant MAX_EPOCHS = 64;
    bytes32 public constant ALLOCATION_TYPEHASH = keccak256(
        "EpochAllocation(uint256 leaseId,uint256 epochId,bytes32 requestHash,uint256 providerShare,uint256 consumerShare,uint256 nonce,uint256 expiry)"
    );

    enum State { Offered, Accepted, Live, Ended, Closed, Cancelled }
    struct Terms {
        address provider;
        bytes32 endpointHash;
        bytes32 profileHash;
        bytes32 slaPolicyHash;
        uint256 epochFee;
        uint256 maxEpochs;
        uint256 exposureBudget;
        uint64 epochWindow;
        uint64 acceptanceWindow;
    }
    struct Lease {
        address consumer;
        address provider;
        bytes32 endpointHash;
        bytes32 profileHash;
        bytes32 slaPolicyHash;
        uint256 assignmentId;
        uint256 escrow;
        uint256 fee;
        uint256 maxEpochs;
        uint256 exposureBudget;
        uint256 nextEpochId;
        uint256 pending;
        uint256 uncommitted;
        uint256 consumerCredited;
        uint256 providerCredited;
        uint256 unusedRefunded;
        uint64 epochWindow;
        uint64 acceptanceDeadline;
        State state;
    }
    struct Epoch {
        bytes32 requestHash;
        uint256 fee;
        uint64 deadline;
        uint256 providerShare;
        uint256 consumerShare;
        uint256 nonce;
        bool admitted;
        bool allocated;
    }
    struct Allocation {
        uint256 leaseId;
        uint256 epochId;
        bytes32 requestHash;
        uint256 providerShare;
        uint256 consumerShare;
        uint256 nonce;
        uint256 expiry;
    }

    ScalableMonitorCommitteeV2 public immutable pool;
    uint256 public nextLeaseId = 1;
    bool private withdrawalEntered;
    mapping(uint256 => Lease) private leases;
    mapping(uint256 => mapping(uint256 => Epoch)) private epochs;
    mapping(uint256 => mapping(bytes32 => bool)) private usedRequests;
    mapping(address => uint256) public withdrawable;

    error InvalidArgument();
    error Unauthorized();
    error InvalidState();
    error InsufficientFunding();
    error ExposureExceeded();
    error InvalidSignatures();
    error NoWithdrawal();
    error TransferFailed();

    event FundedLeaseCreated(uint256 indexed leaseId, uint256 indexed assignmentId, address consumer, address provider, uint256 escrow);
    event ProviderAccepted(uint256 indexed leaseId);
    event LeaseActivated(uint256 indexed leaseId, uint256 indexed assignmentId);
    event LeaseSetupCancelled(uint256 indexed leaseId, uint256 refunded);
    event EpochAdmitted(uint256 indexed leaseId, uint256 indexed epochId, bytes32 requestHash, uint256 amount);
    event EpochAllocated(uint256 indexed leaseId, uint256 indexed epochId, uint256 providerShare, uint256 consumerShare);
    event AdmissionsEnded(uint256 indexed leaseId, uint256 unusedRefund);
    event LeaseClosed(uint256 indexed leaseId);
    event Withdrawal(address indexed to, uint256 amount);

    constructor(address pool_) EIP712("SSELeaseControllerV2", "2") {
        if (pool_.code.length == 0) revert InvalidArgument();
        pool = ScalableMonitorCommitteeV2(pool_);
    }

    function createLease(Terms calldata t, ScalableMonitorCommitteeV2.Terms calldata committee)
        external payable returns (uint256 leaseId)
    {
        if (pool.controller() != address(this) || t.provider == address(0) ||
            t.provider == msg.sender || committee.consumer != msg.sender ||
            committee.provider != t.provider ||
            t.endpointHash == bytes32(0) || t.profileHash == bytes32(0) ||
            t.slaPolicyHash == bytes32(0) || t.epochFee == 0 ||
            t.maxEpochs == 0 || t.maxEpochs > MAX_EPOCHS ||
            t.exposureBudget < t.epochFee || t.exposureBudget > t.epochFee * t.maxEpochs ||
            t.epochWindow == 0 || t.acceptanceWindow == 0 ||
            t.acceptanceWindow > committee.enrollmentPeriod) revert InvalidArgument();
        uint256 requiredEscrow = t.epochFee * t.maxEpochs;
        if (msg.value != requiredEscrow) revert InsufficientFunding();

        leaseId = nextLeaseId++;
        uint256 assignmentId = pool.requestAssignment(committee);
        Lease storage lease = leases[leaseId];
        lease.consumer = msg.sender;
        lease.provider = t.provider;
        lease.endpointHash = t.endpointHash;
        lease.profileHash = t.profileHash;
        lease.slaPolicyHash = t.slaPolicyHash;
        lease.assignmentId = assignmentId;
        lease.escrow = requiredEscrow;
        lease.fee = t.epochFee;
        lease.maxEpochs = t.maxEpochs;
        lease.exposureBudget = t.exposureBudget;
        lease.uncommitted = requiredEscrow;
        lease.epochWindow = t.epochWindow;
        lease.acceptanceDeadline = uint64(block.timestamp + t.acceptanceWindow);
        lease.state = State.Offered;
        emit FundedLeaseCreated(leaseId, assignmentId, msg.sender, t.provider, requiredEscrow);
    }

    function acceptLease(uint256 leaseId) external {
        Lease storage lease = _lease(leaseId);
        if (msg.sender != lease.provider) revert Unauthorized();
        if (lease.state != State.Offered || block.timestamp > lease.acceptanceDeadline ||
            pool.status(lease.assignmentId) != ScalableMonitorCommitteeV2.Status.Enrollment)
            revert InvalidState();
        lease.state = State.Accepted;
        emit ProviderAccepted(leaseId);
    }

    function activateLease(uint256 leaseId) external {
        Lease storage lease = _lease(leaseId);
        if (lease.state != State.Accepted ||
            pool.status(lease.assignmentId) != ScalableMonitorCommitteeV2.Status.Active ||
            block.timestamp >= pool.serviceDeadline(lease.assignmentId)) revert InvalidState();
        lease.state = State.Live;
        emit LeaseActivated(leaseId, lease.assignmentId);
    }

    /// @notice No admitted service obligations exist before Live; full refund is safe
    /// under the experimental terms. Anyone may execute the timeout recovery.
    function cancelFailedSetup(uint256 leaseId) external {
        Lease storage lease = _lease(leaseId);
        if (lease.state != State.Offered && lease.state != State.Accepted) revert InvalidState();
        ScalableMonitorCommitteeV2.Status s = pool.status(lease.assignmentId);
        bool setupTimedOut = (lease.state == State.Offered &&
                              block.timestamp > lease.acceptanceDeadline);
        if (!setupTimedOut && s != ScalableMonitorCommitteeV2.Status.Aborted &&
            s != ScalableMonitorCommitteeV2.Status.Released &&
            block.timestamp < pool.serviceDeadline(lease.assignmentId)) revert InvalidState();
        uint256 refund = lease.uncommitted;
        lease.uncommitted = 0;
        lease.unusedRefunded += refund;
        lease.state = State.Cancelled;
        withdrawable[lease.consumer] += refund;
        emit LeaseSetupCancelled(leaseId, refund);
    }

    /// @notice Does not treat selected committee signatures as proof of delivery.
    function admitEpoch(uint256 leaseId, bytes32 requestHash) external returns (uint256 epochId) {
        Lease storage lease = _lease(leaseId);
        if (msg.sender != lease.consumer) revert Unauthorized();
        if (lease.state != State.Live ||
            pool.status(lease.assignmentId) != ScalableMonitorCommitteeV2.Status.Active ||
            requestHash == bytes32(0) || usedRequests[leaseId][requestHash] ||
            lease.nextEpochId >= lease.maxEpochs || lease.uncommitted < lease.fee)
            revert InvalidState();
        if (block.timestamp + lease.epochWindow > pool.serviceDeadline(lease.assignmentId))
            revert InvalidState();
        if (lease.pending + lease.fee > lease.exposureBudget) revert ExposureExceeded();

        epochId = lease.nextEpochId++;
        usedRequests[leaseId][requestHash] = true;
        Epoch storage ep = epochs[leaseId][epochId];
        ep.requestHash = requestHash;
        ep.fee = lease.fee;
        ep.deadline = uint64(block.timestamp + lease.epochWindow);
        ep.admitted = true;
        lease.uncommitted -= lease.fee;
        lease.pending += lease.fee;
        emit EpochAdmitted(leaseId, epochId, requestHash, lease.fee);
    }

    /// @notice Strict bilateral allocation, independent of raw monitor votes.
    /// Any relayer can submit the signatures; both parties agree to an exact
    /// provider/consumer split for this epoch. No adjudication is claimed.
    function allocateEpoch(Allocation calldata a, bytes calldata consumerSignature,
                           bytes calldata providerSignature) external {
        Lease storage lease = _lease(a.leaseId);
        if (lease.state != State.Live && lease.state != State.Ended) revert InvalidState();
        Epoch storage ep = epochs[a.leaseId][a.epochId];
        if (!ep.admitted || ep.allocated || ep.requestHash != a.requestHash ||
            a.providerShare > ep.fee || a.consumerShare != ep.fee - a.providerShare ||
            a.nonce != ep.nonce || a.expiry < block.timestamp) revert InvalidArgument();

        bytes32 structHash = keccak256(abi.encode(
            ALLOCATION_TYPEHASH, a.leaseId, a.epochId, a.requestHash,
            a.providerShare, a.consumerShare, a.nonce, a.expiry
        ));
        bytes32 digest = _hashTypedDataV4(structHash);
        if (ECDSA.recover(digest, consumerSignature) != lease.consumer ||
            ECDSA.recover(digest, providerSignature) != lease.provider) revert InvalidSignatures();

        ep.allocated = true;
        ++ep.nonce;
        ep.providerShare = a.providerShare;
        ep.consumerShare = a.consumerShare;
        lease.pending -= ep.fee;
        lease.providerCredited += a.providerShare;
        lease.consumerCredited += a.consumerShare;
        withdrawable[lease.provider] += a.providerShare;
        withdrawable[lease.consumer] += a.consumerShare;
        emit EpochAllocated(a.leaseId, a.epochId, a.providerShare, a.consumerShare);
    }

    /// @notice Neither party can withdraw *uncommitted* advance funding early
    /// unilaterally. At the publicly fixed service end, anyone can stop admission.
    /// Previously admitted unallocated epochs remain held and unresolved.
    function endAdmissions(uint256 leaseId) external {
        Lease storage lease = _lease(leaseId);
        if (lease.state != State.Live || block.timestamp < pool.serviceDeadline(lease.assignmentId))
            revert InvalidState();
        lease.state = State.Ended;
        uint256 refund = lease.uncommitted;
        lease.uncommitted = 0;
        lease.unusedRefunded += refund;
        withdrawable[lease.consumer] += refund;
        emit AdmissionsEnded(leaseId, refund);
    }

    function finishLease(uint256 leaseId) external {
        Lease storage lease = _lease(leaseId);
        if (lease.state != State.Ended || lease.pending != 0) revert InvalidState();
        lease.state = State.Closed;
        if (pool.status(lease.assignmentId) == ScalableMonitorCommitteeV2.Status.Active)
            pool.releaseAssignment(lease.assignmentId);
        emit LeaseClosed(leaseId);
    }

    function withdraw() external {
        if (withdrawalEntered) revert InvalidState();
        uint256 amount = withdrawable[msg.sender];
        if (amount == 0) revert NoWithdrawal();
        withdrawalEntered = true;
        withdrawable[msg.sender] = 0;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        if (!ok) revert TransferFailed();
        withdrawalEntered = false;
        emit Withdrawal(msg.sender, amount);
    }

    function getLease(uint256 leaseId) external view returns (Lease memory) { return _lease(leaseId); }
    function getEpoch(uint256 leaseId, uint256 epochId) external view returns (Epoch memory) {
        _lease(leaseId);
        if (!epochs[leaseId][epochId].admitted) revert InvalidArgument();
        return epochs[leaseId][epochId];
    }
    function domainSeparator() external view returns (bytes32) { return _domainSeparatorV4(); }
    function _lease(uint256 leaseId) internal view returns (Lease storage l) {
        l = leases[leaseId];
        if (l.consumer == address(0)) revert InvalidArgument();
    }
}
