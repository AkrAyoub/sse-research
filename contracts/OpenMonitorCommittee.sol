// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;




contract OpenMonitorCommittee {
    uint256 public constant MAX_IDENTITIES = 32;
    uint256 public constant COMMITTEE_SIZE = 4;

    enum RequestStatus { None, AwaitingRandomness, Assigned, Expired, Released }
    struct Candidate {
        uint256 bond;
        uint64 exitRequestedAt;
        uint32 pendingSelections;
        uint32 activeAssignments;
        bool active;
        bool everRegistered;
    }
    struct Assignment {
        address consumer;
        address provider;
        uint64 requestedAt;
        RequestStatus status;
        address[4] committee;
    }

    address public immutable bootstrapper;
    address public immutable randomnessSource;
    uint256 public immutable minimumBond;
    uint64 public immutable exitDelay;
    uint64 public immutable randomnessTimeout;
    address public settlement;
    uint256 public nextAssignmentId = 1;
    bool private entered;

    address[] private allCandidates;
    mapping(address => Candidate) public candidates;
    mapping(uint256 => Assignment) private assignments;
    mapping(uint256 => address[]) private snapshots;
    // Full post-seed shuffle: never hand-pick a replacement or resample seed.
    mapping(uint256 => address[]) private standbyRosters;
    mapping(uint256 => uint256) private nextStandbyIndex;

    error InvalidInput();
    error InvalidPhase();
    error Unauthorized();
    error InsufficientCandidates();
    error TransferFailed();
    event CandidateRegistered(address indexed account, uint256 bond);
    event ExitRequested(address indexed account);
    event BondWithdrawn(address indexed account, uint256 amount);
    event SettlementBound(address indexed settlement);
    event AssignmentRequested(uint256 indexed requestId, address consumer, address provider, uint256 poolSize);
    event CommitteeSelected(uint256 indexed requestId, address[4] committee);
    event CommitteeMemberReplaced(uint256 indexed requestId, address indexed removed,
                                  address indexed replacement, uint256 remainingStandbys);
    event AssignmentExpired(uint256 indexed requestId);
    event AssignmentReleased(uint256 indexed requestId);

    constructor(address randomProvider, uint256 minBond, uint64 exitDelaySeconds, uint64 randomnessTimeoutSeconds) {
        if (randomProvider == address(0) || minBond == 0 ||
            randomnessTimeoutSeconds == 0 || exitDelaySeconds <= randomnessTimeoutSeconds)
            revert InvalidInput();
        bootstrapper = msg.sender;
        randomnessSource = randomProvider;
        minimumBond = minBond;
        exitDelay = exitDelaySeconds;
        randomnessTimeout = randomnessTimeoutSeconds;
    }

    //One time deployment wiring. After this, bootstrapper has no admin operations
    function bindSettlement(address target) external {
        if (msg.sender != bootstrapper || settlement != address(0)) revert Unauthorized();
        if (target == address(0) || target.code.length == 0) revert InvalidInput();
        settlement = target;
        emit SettlementBound(target);
    }

    modifier onlySettlement() {
        if (msg.sender != settlement || settlement == address(0)) revert Unauthorized();
        _;
    }

    function register() external payable {
        Candidate storage c = candidates[msg.sender];
        if (c.bond != 0 || msg.value < minimumBond) revert InvalidInput();
        if (!c.everRegistered) {
            if (allCandidates.length >= MAX_IDENTITIES) revert InvalidInput();
            allCandidates.push(msg.sender);
            c.everRegistered = true;
        }
        c.bond = msg.value;
        c.active = true;
        c.exitRequestedAt = 0;
        emit CandidateRegistered(msg.sender, msg.value);
    }

    function topUpBond() external payable {
        Candidate storage c = candidates[msg.sender];
        if (!c.active || msg.value == 0) revert InvalidPhase();
        c.bond += msg.value;
    }

    function requestExit() external {
        Candidate storage c = candidates[msg.sender];
        if (!c.active || c.pendingSelections != 0 || c.activeAssignments != 0) revert InvalidPhase();
        c.active = false;
        c.exitRequestedAt = uint64(block.timestamp);
        emit ExitRequested(msg.sender);
    }

    function withdrawBond() external {
        Candidate storage c = candidates[msg.sender];
        if (entered || c.active || c.bond == 0 || c.exitRequestedAt == 0 ||
            c.pendingSelections != 0 || c.activeAssignments != 0 ||
            block.timestamp < uint256(c.exitRequestedAt) + exitDelay) revert InvalidPhase();
        uint256 value = c.bond;
        c.bond = 0;
        c.exitRequestedAt = 0;
        entered = true;
        (bool ok,) = payable(msg.sender).call{value: value}("");
        if (!ok) revert TransferFailed();
        entered = false;
        emit BondWithdrawn(msg.sender, value);
    }

    function requestAssignment(address consumer, address provider) external onlySettlement returns (uint256 id) {
        if (consumer == address(0) || provider == address(0) || consumer == provider) revert InvalidInput();
        id = nextAssignmentId++;
        Assignment storage r = assignments[id];
        r.consumer = consumer;
        r.provider = provider;
        r.requestedAt = uint64(block.timestamp);
        r.status = RequestStatus.AwaitingRandomness;
        for (uint256 i; i < allCandidates.length; ++i) {
            address account = allCandidates[i];
            Candidate storage c = candidates[account];
            if (account != consumer && account != provider && c.active && c.bond >= minimumBond) {
                snapshots[id].push(account);
                ++c.pendingSelections;
            }
        }
        if (snapshots[id].length < COMMITTEE_SIZE) revert InsufficientCandidates();
        emit AssignmentRequested(id, consumer, provider, snapshots[id].length);
    }

    function fulfillRandomness(uint256 id, uint256 seed) external {
        if (msg.sender != randomnessSource) revert Unauthorized();
        Assignment storage r = assignments[id];
        if (r.status != RequestStatus.AwaitingRandomness ||
            block.timestamp > uint256(r.requestedAt) + randomnessTimeout) revert InvalidPhase();
        address[] memory roster = snapshots[id];
        uint256 length = roster.length;
        
        // Finish the seed-determined Fisher-Yates-style permutation; modulo
        // reduction may introduce negligible bias and the seed is V1 trusted.
        // Shuffle the full roster, not just the first four slots.
        // four selections, to establish an immutable standby order from the
        // SAME randomness draw. No consumer choice or second seed on recovery.
        for (uint256 i; i < length; ++i) {
            uint256 j = i + uint256(keccak256(abi.encode(seed, id, i))) % (length - i);
            (roster[i], roster[j]) = (roster[j], roster[i]);
            if (i < COMMITTEE_SIZE) r.committee[i] = roster[i];
            else standbyRosters[id].push(roster[i]);
        }
        _unlockSnapshot(id);
        for (uint256 i; i < COMMITTEE_SIZE; ++i) {
            ++candidates[r.committee[i]].activeAssignments;
        }
        r.status = RequestStatus.Assigned;
        emit CommitteeSelected(id, r.committee);
    }

    function expire(uint256 id) external {
        Assignment storage r = assignments[id];
        if (r.status != RequestStatus.AwaitingRandomness ||
            block.timestamp <= uint256(r.requestedAt) + randomnessTimeout) revert InvalidPhase();
        _unlockSnapshot(id);
        r.status = RequestStatus.Expired;
        emit AssignmentExpired(id);
    }

    /// @dev A standby may have exited after the original randomness reveal;
    /// skip it, never select an unbonded or currently inactive identity.
    /// Only the bound settlement may replace a confirmed *missing* seat.
    /// The settlement enforces the per-seat confirmation timeout and no epochs.
    function replaceUnconfirmed(uint256 id, address missing)
        external onlySettlement returns (address replacement)
    {
        Assignment storage r = assignments[id];
        if (r.status != RequestStatus.Assigned || missing == address(0)) revert InvalidPhase();
        bool member;
        for (uint256 i; i < COMMITTEE_SIZE; ++i) {
            if (r.committee[i] == missing) { member = true; break; }
        }
        if (!member) revert InvalidInput();

        address[] storage standby = standbyRosters[id];
        uint256 cursor = nextStandbyIndex[id];
        while (cursor < standby.length) {
            address candidate = standby[cursor++];
            Candidate storage c = candidates[candidate];
            if (!c.active || c.bond < minimumBond) continue;
            bool alreadyMember;
            for (uint256 j; j < COMMITTEE_SIZE; ++j) {
                if (r.committee[j] == candidate) { alreadyMember = true; break; }
            }
            if (alreadyMember) continue;
            replacement = candidate;
            break;
        }
        if (replacement == address(0)) revert InsufficientCandidates();
        nextStandbyIndex[id] = cursor;
        for (uint256 i; i < COMMITTEE_SIZE; ++i) {
            if (r.committee[i] == missing) {
                r.committee[i] = replacement;
                break;
            }
        }
        --candidates[missing].activeAssignments;
        ++candidates[replacement].activeAssignments;
        emit CommitteeMemberReplaced(id, missing, replacement, standby.length - cursor);
    }

    function standbyRemaining(uint256 id) external view returns (uint256) {
        return standbyRosters[id].length - nextStandbyIndex[id];
    }

    function releaseAssignment(uint256 id) external onlySettlement {
        Assignment storage r = assignments[id];
        if (r.status != RequestStatus.Assigned) revert InvalidPhase();
        for (uint256 i; i < COMMITTEE_SIZE; ++i) {
            --candidates[r.committee[i]].activeAssignments;
        }
        delete standbyRosters[id];
        delete nextStandbyIndex[id];
        r.status = RequestStatus.Released;
        emit AssignmentReleased(id);
    }

    function _unlockSnapshot(uint256 id) internal {
        address[] storage roster = snapshots[id];
        for (uint256 i; i < roster.length; ++i) --candidates[roster[i]].pendingSelections;
        delete snapshots[id];
    }

    function getCommittee(uint256 id) external view returns (address[4] memory) {
        Assignment storage r = assignments[id];
        if (r.status != RequestStatus.Assigned && r.status != RequestStatus.Released) revert InvalidPhase();
        return r.committee;
    }

    function assignmentStatus(uint256 id) external view returns (RequestStatus) { return assignments[id].status; }
    function candidateCount() external view returns (uint256) { return allCandidates.length; }
    function candidateAt(uint256 index) external view returns (address) { return allCandidates[index]; }
    function snapshotSize(uint256 id) external view returns (uint256) { return snapshots[id].length; }
}
