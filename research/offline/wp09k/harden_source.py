"""WP09K fail-closed Solidity hardening transformations, offline only."""
from __future__ import annotations


def one(content: str, before: str, after: str, label: str) -> str:
    count = content.count(before)
    if count != 1:
        raise ValueError(f'{label}: refusing ambiguous anchor ({count} matches): {before[:75]!r}')
    return content.replace(before, after, 1)


def harden_adapter(content: str) -> str:
    label = 'SSEVRFV25Adapter.sol'
    steps = [
        ('''interface ISSEVRFSettlement {
    function committeePool() external view returns (address);
}''',
         '''interface ISSEVRFSettlement {
    function committeePool() external view returns (address);
    function isLeaseRandomnessOpen(uint256 leaseId, uint256 assignmentId)
        external view returns (bool);
}'''),
        ('''    mapping(uint256 => bool) public assignmentEverRequested;''',
         '''    mapping(uint256 => bool) public assignmentEverRequested;
    mapping(uint256 => uint256) public leaseForAssignment;'''),
        ('''    function requestSeed(uint256 assignmentId) external returns (uint256 vrfId) {
        if (msg.sender != settlement || settlement == address(0)) revert Unauthorized();
        if (assignmentId == 0 || assignmentEverRequested[assignmentId] ||
            pool.assignmentStatus(assignmentId) != AWAITING_RANDOMNESS)
            revert BadState();''',
         '''    function requestSeed(uint256 leaseId, uint256 assignmentId)
        external returns (uint256 vrfId)
    {
        if (msg.sender != settlement || settlement == address(0)) revert Unauthorized();
        if (leaseId == 0 || assignmentId == 0 || assignmentEverRequested[assignmentId] ||
            !ISSEVRFSettlement(settlement).isLeaseRandomnessOpen(leaseId, assignmentId) ||
            pool.assignmentStatus(assignmentId) != AWAITING_RANDOMNESS)
            revert BadState();'''),
        ('''        vrfId = IVRFV25Coordinator(pinnedCoordinator).requestRandomWords(req);
        if (vrfId == 0 || byVrfId[vrfId].state != State.None) revert BadState();
        assignmentEverRequested[assignmentId] = true;
        requestForAssignment[assignmentId] = vrfId;''',
         '''        // EFFECTS BEFORE INTERACTION: disallow nested coordinator calls
        // from purchasing another request for the same assignment. Any
        // coordinator revert or invalid return rolls these writes back.
        assignmentEverRequested[assignmentId] = true;
        leaseForAssignment[assignmentId] = leaseId;
        vrfId = IVRFV25Coordinator(pinnedCoordinator).requestRandomWords(req);
        if (vrfId == 0 || byVrfId[vrfId].state != State.None) revert BadState();
        requestForAssignment[assignmentId] = vrfId;'''),
        ('''            pool.assignmentStatus(assignmentId) != AWAITING_RANDOMNESS ||
            pool.snapshotCommitment(assignmentId) != r.snapshotHash)''',
         '''            pool.assignmentStatus(assignmentId) != AWAITING_RANDOMNESS ||
            pool.snapshotCommitment(assignmentId) != r.snapshotHash ||
            // The consumer may have closed the lease while VRF was pending.
            // Do not create a new committee/bond lock for a closed lease.
            !ISSEVRFSettlement(settlement).isLeaseRandomnessOpen(
                leaseForAssignment[assignmentId], assignmentId))'''),
    ]
    for before, after in steps:
        content = one(content, before, after, label)
    return content


def harden_settlement_patch(content: str) -> str:
    label = 'SSESettlement.sol'
    steps = [
        ('''    function requestSeed(uint256 assignmentId) external returns (uint256);''',
         '''    function requestSeed(uint256 leaseId, uint256 assignmentId)
        external returns (uint256);'''),
        ('''    /// @notice Permissionless request after lease creation; exactly ONE VRF
    /// request for the lease's frozen assignment, with no alternative seed.''',
         '''    /// @notice TEMPORARY subscription-spend gate: only the bootstrapper
    /// can dispatch a paid VRF request, and only after provider acceptance.
    /// This is a deliberately CENTRALIZED cost control, not final protocol.
    /// A fee-backed permissionless dispatch policy needs separate review.'''),
        ('''    function requestLeaseRandomness(uint256 leaseId) external returns (uint256 vrfId) {
        Lease storage lease = leases[leaseId];
        if (address(randomnessAdapter) == address(0) ||
            lease.consumer == address(0) ||
            (lease.state != LeaseState.Offered && lease.state != LeaseState.Accepted) ||
            lease.monitors[0] != address(0) ||
            committeePool.assignmentStatus(lease.assignmentId) !=
                OpenMonitorCommittee.RequestStatus.AwaitingRandomness)
            revert InvalidState();
        vrfId = randomnessAdapter.requestSeed(lease.assignmentId);
        emit LeaseRandomnessRequested(leaseId, lease.assignmentId, vrfId);
    }''',
         '''    function requestLeaseRandomness(uint256 leaseId) external returns (uint256 vrfId) {
        if (msg.sender != bootstrapper) revert Unauthorized();
        Lease storage lease = leases[leaseId];
        if (address(randomnessAdapter) == address(0) ||
            !isLeaseRandomnessOpen(leaseId, lease.assignmentId)) revert InvalidState();
        vrfId = randomnessAdapter.requestSeed(leaseId, lease.assignmentId);
        emit LeaseRandomnessRequested(leaseId, lease.assignmentId, vrfId);
    }

    /// @notice Adapter safety check both before PURCHASE and before APPLY.
    /// @dev Does not rely only on pool assignment status: closing a lease
    /// must prevent subsequent randomness from locking monitor bonds.
    function isLeaseRandomnessOpen(uint256 leaseId, uint256 assignmentId)
        public view returns (bool)
    {
        Lease storage lease = leases[leaseId];
        return assignmentId != 0 && lease.consumer != address(0) &&
            lease.assignmentId == assignmentId &&
            lease.state == LeaseState.Accepted &&
            lease.monitors[0] == address(0) &&
            committeePool.assignmentStatus(assignmentId) ==
                OpenMonitorCommittee.RequestStatus.AwaitingRandomness;
    }'''),
    ]
    for before, after in steps:
        content = one(content, before, after, label)
    return content


def harden_foundry_test(content: str) -> str:
    label = 'VRFAdapterIntegration.t.sol'
    steps = [
        ('''    function _createLease() internal returns (uint256 leaseId) {
        vm.prank(consumer);
        leaseId = settlement.createLease{value: 25}(
            provider, keccak256("endpoint"), keccak256("profile"),
            25, 5, 25, 1, 100, 100, 100
        );
    }''',
         '''    function _createOfferedLease() internal returns (uint256 leaseId) {
        vm.prank(consumer);
        leaseId = settlement.createLease{value: 25}(
            provider, keccak256("endpoint"), keccak256("profile"),
            25, 5, 25, 1, 100, 100, 100
        );
    }

    function _createLease() internal returns (uint256 leaseId) {
        leaseId = _createOfferedLease();
        vm.prank(provider);
        settlement.acceptLease(leaseId);
    }'''),
        ('''    function _request(uint256 leaseId) internal returns (uint256 vrfId) {
        vm.prank(outsider);
        vrfId = settlement.requestLeaseRandomness(leaseId);
    }''',
         '''    function _request(uint256 leaseId) internal returns (uint256 vrfId) {
        // Test contract is deployer/bootstrapper and has the temporary
        // authorization needed to spend the subscription.
        vrfId = settlement.requestLeaseRandomness(leaseId);
    }'''),
        ('''        vm.prank(provider);
        settlement.acceptLease(leaseId);
        settlement.finalizeMonitorCommittee(leaseId);''',
         '''        settlement.finalizeMonitorCommittee(leaseId);'''),
        ('''        vm.prank(address(0xA100));
        uint256 leaseId = settlement.createLease{value: 25}(
            address(0xB100), keccak256("endpoint"), keccak256("profile"),
            25, 5, 25, 1, 100, 100, 100
        );
        uint256 vrfId = settlement.requestLeaseRandomness(leaseId);''',
         '''        vm.prank(address(0xA100));
        uint256 leaseId = settlement.createLease{value: 25}(
            address(0xB100), keccak256("endpoint"), keccak256("profile"),
            25, 5, 25, 1, 100, 100, 100
        );
        vm.prank(address(0xB100));
        settlement.acceptLease(leaseId);
        uint256 vrfId = settlement.requestLeaseRandomness(leaseId);'''),
    ]
    for before, after in steps:
        content = one(content, before, after, label)
    return content


def harden_pool_patch(content: str) -> str:
    """Append a settlement-only cancellation hook to the WP09J-patched pool.

    Cancellation is invoked *only* by the SSESettlement closeLease hook when
    the settlement has not yet finalized the committee; no VRF reroll.
    """
    label = 'OpenMonitorCommittee.sol'
    content = one(content,
        '    event AssignmentExpired(uint256 indexed requestId);',
        '''    event AssignmentExpired(uint256 indexed requestId);
    event AssignmentCancelled(uint256 indexed requestId, RequestStatus previousStatus);''', label)
    content = one(content, '''    function expire(uint256 id) external {''',
        '''    /// @notice Settlement may atomically cancel an assignment when a
    /// lease is CLOSED before the committee is copied into settlement.
    /// The consumer is NOT granted direct permission on this pool method.
    /// This also prevents already-staged global seeds from assigning after
    /// lease close, and frees selected bonds if not yet finalized.
    function cancelUnassigned(uint256 id) external onlySettlement {
        Assignment storage r = assignments[id];
        RequestStatus previous = r.status;
        if (previous == RequestStatus.AwaitingRandomness) {
            if (!globalMerkleElectionEnabled) _unlockSnapshot(id);
            delete pendingGlobalSeedReady[id];
            delete pendingGlobalSeed[id];
            r.status = RequestStatus.Expired;
        } else if (previous == RequestStatus.Assigned) {
            // Settlement hasn't copied the committee yet; no epoch exists.
            for (uint256 i; i < COMMITTEE_SIZE; ++i) {
                --candidates[r.committee[i]].activeAssignments;
            }
            delete standbyRosters[id];
            delete nextStandbyIndex[id];
            r.status = RequestStatus.Released;
            emit AssignmentReleased(id);
        } else if (previous != RequestStatus.Expired) {
            revert InvalidPhase();
        }
        emit AssignmentCancelled(id, previous);
    }

    function expire(uint256 id) external {''', label)
    return content


def harden_close_lease(content: str) -> str:
    label = 'SSESettlement.sol'
    return one(content, '''    function closeLease(uint256 leaseId) external onlyConsumer(leaseId) {
        Lease storage lease = leases[leaseId];
        if (lease.state == LeaseState.Closed) revert InvalidState();
        uint256 unused = lease.uncommittedEscrow;''',
        '''    function closeLease(uint256 leaseId) external onlyConsumer(leaseId) {
        Lease storage lease = leases[leaseId];
        if (lease.state == LeaseState.Closed) revert InvalidState();
        if (address(randomnessAdapter) != address(0) &&
            lease.monitors[0] == address(0)) {
            // No committee has been handed to settlement. Release any
            // pending snapshots or pre-finalization selected bond locks.
            // Pool call is atomic with this closure and refund accounting.
            committeePool.cancelUnassigned(lease.assignmentId);
        }
        uint256 unused = lease.uncommittedEscrow;''', label)
