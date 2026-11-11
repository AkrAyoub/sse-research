// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice External proof-verifier interface, NOT itself a VRF implementation.
/// @dev Correctness/unbiasability of the installed verifier remains an explicit assumption.
interface IVerifiedMonitorRandomnessV2 {
    function verify(bytes32 assignmentCommitment, bytes32 seed, bytes calldata proof)
        external view returns (bool);
}

/// @notice Standalone research V2 monitor registry. NOT linked to SSESettlement V1.
/// @dev A valid monitor report is not a physical-service delivery certificate.
contract ScalableMonitorCommitteeV2 {
    uint8 public constant MAX_FINALISTS = 16;
    uint8 public constant MAX_PROCESS_STEPS = 16;
    uint64 public constant MAX_WINDOW = 30 days;
    uint64 public constant MAX_SERVICE_WINDOW = 365 days;

    enum Status { None, Enrollment, WaitingSeed, Selecting, Confirming, Active, Aborted, Released }
    struct Candidate {
        uint256 registryBond;
        uint256 lockedTickets;
        uint64 exitRequestedAt;
        bool active;
    }
    struct Terms {
        address consumer;
        address provider;
        uint8 size;
        uint8 quorum;
        uint8 reserves;
        uint64 enrollmentPeriod;
        uint64 randomnessPeriod;
        uint64 selectionPeriod;
        uint64 confirmationPeriod;
        uint64 servicePeriod;
    }
    struct Ticket {
        bool joined;
        bool paid;
        bool everSelected;
        bool confirmed;
        bool noShow;
    }
    struct Assignment {
        address consumer;
        address provider;
        uint8 size;
        uint8 quorum;
        uint8 reserves;
        uint64 enrollmentEnd;
        uint64 randomnessEnd;
        uint64 selectionEnd;
        uint64 confirmationEnd;
        uint64 serviceEnd;
        uint64 confirmationPeriod;
        Status status;
        bytes32 rosterHash;
        bytes32 seed;
        uint256 cursor;
        uint256 confirmedCount;
        uint256 nextReserve;
        address[] entrants;
        address[] ranked;
        uint256[] scores;
        address[] seats;
    }

    address public immutable bootstrapper;
    address public immutable randomnessSource;
    IVerifiedMonitorRandomnessV2 public immutable verifier;
    uint256 public immutable minimumRegistryBond;
    uint256 public immutable ticketBond;
    uint64 public immutable exitDelay;
    address public controller;
    uint256 public nextAssignmentId = 1;
    uint256 public registeredIdentities;
    bool private entered;
    mapping(address => Candidate) public candidates;
    mapping(uint256 => Assignment) private assignments;
    mapping(uint256 => mapping(address => Ticket)) public tickets;
    mapping(address => uint256) public withdrawable;

    error InvalidInput();
    error InvalidPhase();
    error Unauthorized();
    error InvalidRandomness();
    error NoCredit();
    error TransferFailed();

    event ControllerBound(address indexed controller);
    event Registered(address indexed candidate, uint256 registryBond);
    event RegistryExit(address indexed candidate);
    event AssignmentOpened(uint256 indexed id, address indexed consumer, address indexed provider,
                           uint8 size, uint8 quorum, uint8 reserves);
    event Enrolled(uint256 indexed id, address indexed candidate);
    event EnrollmentSealed(uint256 indexed id, uint256 entrants, bytes32 commitment);
    event RandomnessVerified(uint256 indexed id, bytes32 seed);
    event SelectionProgress(uint256 indexed id, uint256 cursor, uint256 total);
    event CommitteeSelected(uint256 indexed id, address[] seats);
    event Confirmed(uint256 indexed id, address indexed candidate);
    event Replacement(uint256 indexed id, address indexed absent, address indexed replacement);
    event AssignmentAborted(uint256 indexed id);
    event AssignmentReleased(uint256 indexed id);
    event TicketSettled(uint256 indexed id, address indexed candidate, address indexed beneficiary,
                        uint256 value, bool noShow);
    event Withdrawn(address indexed payee, uint256 amount);

    constructor(address randomnessAuthority, address randomnessVerifier,
                uint256 registryBond, uint256 joinBond, uint64 exitDelaySeconds) {
        if (randomnessAuthority == address(0) || randomnessVerifier.code.length == 0 ||
            registryBond == 0 || joinBond == 0 || exitDelaySeconds == 0) revert InvalidInput();
        bootstrapper = msg.sender;
        randomnessSource = randomnessAuthority;
        verifier = IVerifiedMonitorRandomnessV2(randomnessVerifier);
        minimumRegistryBond = registryBond;
        ticketBond = joinBond;
        exitDelay = exitDelaySeconds;
    }

    function bindController(address target) external {
        if (msg.sender != bootstrapper || controller != address(0)) revert Unauthorized();
        if (target.code.length == 0) revert InvalidInput();
        controller = target;
        emit ControllerBound(target);
    }
    modifier onlyController() {
        if (msg.sender != controller || controller == address(0)) revert Unauthorized();
        _;
    }

    function register() external payable {
        Candidate storage c = candidates[msg.sender];
        if (c.registryBond != 0 || msg.value < minimumRegistryBond) revert InvalidInput();
        c.registryBond = msg.value;
        c.exitRequestedAt = 0;
        c.active = true;
        ++registeredIdentities; // No lifetime cap or global candidate enumeration.
        emit Registered(msg.sender, msg.value);
    }
    function requestExit() external {
        Candidate storage c = candidates[msg.sender];
        if (!c.active) revert InvalidPhase();
        c.active = false;
        c.exitRequestedAt = uint64(block.timestamp);
        emit RegistryExit(msg.sender);
    }
    function withdrawRegistryBond() external {
        Candidate storage c = candidates[msg.sender];
        if (c.active || c.registryBond == 0 || c.exitRequestedAt == 0 ||
            c.lockedTickets != 0 || block.timestamp < uint256(c.exitRequestedAt) + exitDelay)
            revert InvalidPhase();
        uint256 value = c.registryBond;
        c.registryBond = 0;
        c.exitRequestedAt = 0;
        --registeredIdentities;
        withdrawable[msg.sender] += value;
    }

    function requestAssignment(Terms calldata t) external onlyController returns (uint256 id) {
        if (t.consumer == address(0) || t.provider == address(0) || t.consumer == t.provider ||
            t.size < 3 || t.size > MAX_FINALISTS || t.quorum <= t.size / 2 ||
            t.quorum > t.size || t.reserves > MAX_FINALISTS - t.size ||
            t.enrollmentPeriod == 0 || t.enrollmentPeriod > MAX_WINDOW ||
            t.randomnessPeriod == 0 || t.randomnessPeriod > MAX_WINDOW ||
            t.selectionPeriod == 0 || t.selectionPeriod > MAX_WINDOW ||
            t.confirmationPeriod == 0 || t.confirmationPeriod > MAX_WINDOW ||
            t.servicePeriod == 0 || t.servicePeriod > MAX_SERVICE_WINDOW) revert InvalidInput();
        uint256 end = block.timestamp + uint256(t.enrollmentPeriod) + t.randomnessPeriod +
            t.selectionPeriod + t.confirmationPeriod + t.servicePeriod;
        if (end > type(uint64).max) revert InvalidInput();
        id = nextAssignmentId++;
        Assignment storage r = assignments[id];
        r.consumer = t.consumer;
        r.provider = t.provider;
        r.size = t.size;
        r.quorum = t.quorum;
        r.reserves = t.reserves;
        r.enrollmentEnd = uint64(block.timestamp + t.enrollmentPeriod);
        r.randomnessEnd = r.enrollmentEnd + t.randomnessPeriod;
        r.selectionEnd = r.randomnessEnd + t.selectionPeriod;
        r.confirmationEnd = r.selectionEnd + t.confirmationPeriod;
        r.serviceEnd = r.confirmationEnd + t.servicePeriod;
        r.confirmationPeriod = t.confirmationPeriod;
        r.status = Status.Enrollment;
        emit AssignmentOpened(id, t.consumer, t.provider, t.size, t.quorum, t.reserves);
    }

    function join(uint256 id) external payable {
        Assignment storage r = assignments[id];
        Candidate storage c = candidates[msg.sender];
        Ticket storage ticket = tickets[id][msg.sender];
        if (r.status != Status.Enrollment || block.timestamp > r.enrollmentEnd ||
            !c.active || c.registryBond < minimumRegistryBond ||
            msg.sender == r.consumer || msg.sender == r.provider || ticket.joined ||
            msg.value != ticketBond) revert InvalidPhase();
        ticket.joined = true;
        ticket.paid = true;
        ++c.lockedTickets;
        r.entrants.push(msg.sender);
        r.rosterHash = keccak256(abi.encode(r.rosterHash, msg.sender));
        emit Enrolled(id, msg.sender);
    }
    function assignmentCommitment(uint256 id) public view returns (bytes32) {
        Assignment storage r = assignments[id];
        if (r.status == Status.None) revert InvalidInput();
        return keccak256(abi.encode(block.chainid, address(this), id, r.rosterHash,
            r.entrants.length, r.consumer, r.provider, r.size, r.quorum, r.reserves));
    }
    function sealEnrollment(uint256 id) external {
        Assignment storage r = assignments[id];
        if (r.status != Status.Enrollment || block.timestamp <= r.enrollmentEnd) revert InvalidPhase();
        if (r.entrants.length < r.size) {
            r.status = Status.Aborted;
            emit AssignmentAborted(id);
        } else {
            r.status = Status.WaitingSeed;
            emit EnrollmentSealed(id, r.entrants.length, assignmentCommitment(id));
        }
    }
    function supplyRandomness(uint256 id, bytes32 seed, bytes calldata proof) external {
        Assignment storage r = assignments[id];
        if (msg.sender != randomnessSource) revert Unauthorized();
        if (r.status != Status.WaitingSeed || block.timestamp > r.randomnessEnd) revert InvalidPhase();
        if (seed == bytes32(0) || !verifier.verify(assignmentCommitment(id), seed, proof))
            revert InvalidRandomness();
        r.seed = seed;
        r.status = Status.Selecting;
        emit RandomnessVerified(id, seed);
    }

    function _before(uint256 a, address addrA, uint256 b, address addrB)
        private pure returns (bool) {
        return a < b || (a == b && uint160(addrA) < uint160(addrB));
    }
    function _insert(Assignment storage r, address participant, uint256 score) private {
        uint256 n = r.ranked.length;
        uint256 limit = uint256(r.size) + r.reserves;
        uint256 pos;
        while (pos < n && !_before(score, participant, r.scores[pos], r.ranked[pos])) ++pos;
        if (pos >= limit) return;
        r.ranked.push(participant);
        r.scores.push(score);
        for (uint256 i = r.ranked.length - 1; i > pos; --i) {
            r.ranked[i] = r.ranked[i - 1];
            r.scores[i] = r.scores[i - 1];
        }
        r.ranked[pos] = participant;
        r.scores[pos] = score;
        if (r.ranked.length > limit) {
            r.ranked.pop();
            r.scores.pop();
        }
    }

    /// @notice Each transaction scans <=16 entrants and holds <=16 finalists.
    function processSelection(uint256 id, uint8 maxSteps) external {
        Assignment storage r = assignments[id];
        if (r.status != Status.Selecting || block.timestamp > r.selectionEnd ||
            maxSteps == 0 || maxSteps > MAX_PROCESS_STEPS) revert InvalidPhase();
        uint256 end = r.cursor + maxSteps;
        if (end > r.entrants.length) end = r.entrants.length;
        for (uint256 i = r.cursor; i < end; ++i) {
            address candidate = r.entrants[i];
            uint256 score = uint256(keccak256(abi.encode(r.seed, id, candidate)));
            _insert(r, candidate, score);
        }
        r.cursor = end;
        emit SelectionProgress(id, end, r.entrants.length);
    }
    function finalizeSelection(uint256 id) external {
        Assignment storage r = assignments[id];
        if (r.status != Status.Selecting || block.timestamp > r.selectionEnd ||
            r.cursor != r.entrants.length || r.ranked.length < r.size) revert InvalidPhase();
        for (uint256 i; i < r.size; ++i) {
            address candidate = r.ranked[i];
            r.seats.push(candidate);
            tickets[id][candidate].everSelected = true;
        }
        r.nextReserve = r.size;
        r.status = Status.Confirming;
        emit CommitteeSelected(id, r.seats);
    }
    function _isSeated(Assignment storage r, address candidate) private view returns (bool) {
        for (uint256 i; i < r.seats.length; ++i)
            if (r.seats[i] == candidate) return true;
        return false;
    }
    function confirm(uint256 id) external {
        Assignment storage r = assignments[id];
        Ticket storage t = tickets[id][msg.sender];
        if (r.status != Status.Confirming || block.timestamp > r.confirmationEnd ||
            !_isSeated(r, msg.sender) || t.confirmed || t.noShow) revert InvalidPhase();
        t.confirmed = true;
        ++r.confirmedCount;
        emit Confirmed(id, msg.sender);
        if (r.confirmedCount == r.size) r.status = Status.Active;
    }
    function _markUnconfirmedNoShows(uint256 id) private {
        Assignment storage r = assignments[id];
        for (uint256 i; i < r.seats.length; ++i) {
            Ticket storage t = tickets[id][r.seats[i]];
            if (!t.confirmed) t.noShow = true;
        }
    }
    /// @notice Only absence of ON-CHAIN confirmation is penalized, not off-chain SLA claims.
    function replaceNoShows(uint256 id) external {
        Assignment storage r = assignments[id];
        if (r.status != Status.Confirming || block.timestamp <= r.confirmationEnd ||
            block.timestamp >= r.serviceEnd) revert InvalidPhase();
        uint256 newEnd = block.timestamp + r.confirmationPeriod;
        if (newEnd >= r.serviceEnd) {
            _markUnconfirmedNoShows(id);
            r.status = Status.Aborted;
            emit AssignmentAborted(id);
            return;
        }
        for (uint256 i; i < r.seats.length; ++i) {
            address previous = r.seats[i];
            Ticket storage oldTicket = tickets[id][previous];
            if (oldTicket.confirmed) continue;
            oldTicket.noShow = true;
            if (r.nextReserve >= r.ranked.length) {
                r.status = Status.Aborted;
                emit AssignmentAborted(id);
                return;
            }
            address standby = r.ranked[r.nextReserve++];
            r.seats[i] = standby;
            tickets[id][standby].everSelected = true;
            emit Replacement(id, previous, standby);
        }
        r.confirmationEnd = uint64(newEnd);
    }
    function _abort(uint256 id) private {
        assignments[id].status = Status.Aborted;
        emit AssignmentAborted(id);
    }
    /// @notice Permissionless termination of stalled signup, seed, batch, confirmation, service.
    function expire(uint256 id) external {
        Assignment storage r = assignments[id];
        if (r.status == Status.Enrollment && block.timestamp > r.enrollmentEnd) {
            _abort(id);
        } else if (r.status == Status.WaitingSeed && block.timestamp > r.randomnessEnd) {
            _abort(id);
        } else if (r.status == Status.Selecting && block.timestamp > r.selectionEnd) {
            _abort(id);
        } else if (r.status == Status.Confirming && block.timestamp >= r.serviceEnd) {
            _markUnconfirmedNoShows(id);
            _abort(id);
        } else if (r.status == Status.Active && block.timestamp >= r.serviceEnd) {
            r.status = Status.Released;
            emit AssignmentReleased(id);
        } else revert InvalidPhase();
    }
    function releaseAssignment(uint256 id) external onlyController {
        Assignment storage r = assignments[id];
        if (r.status != Status.Active) revert InvalidPhase();
        r.status = Status.Released;
        emit AssignmentReleased(id);
    }
    /// @notice Anyone may settle missing participant ticket; selected Active seats remain bonded.
    function settleTicket(uint256 id, address participant) external {
        Assignment storage r = assignments[id];
        Ticket storage t = tickets[id][participant];
        if (!t.joined || !t.paid || r.status == Status.None) revert InvalidPhase();
        if (r.status != Status.Aborted && r.status != Status.Released &&
            !(r.status == Status.Active && !_isSeated(r, participant))) revert InvalidPhase();
        t.paid = false;
        --candidates[participant].lockedTickets;
        address beneficiary = t.noShow ? r.consumer : participant;
        withdrawable[beneficiary] += ticketBond;
        emit TicketSettled(id, participant, beneficiary, ticketBond, t.noShow);
    }
    function withdraw() external {
        if (entered) revert InvalidPhase();
        uint256 amount = withdrawable[msg.sender];
        if (amount == 0) revert NoCredit();
        entered = true;
        withdrawable[msg.sender] = 0;
        (bool success,) = payable(msg.sender).call{value: amount}("");
        if (!success) revert TransferFailed();
        entered = false;
        emit Withdrawn(msg.sender, amount);
    }

    function status(uint256 id) external view returns (Status) { return assignments[id].status; }
    function enrolledCount(uint256 id) external view returns (uint256) { return assignments[id].entrants.length; }
    function selectionCursor(uint256 id) external view returns (uint256) { return assignments[id].cursor; }
    function selectedCount(uint256 id) external view returns (uint256) { return assignments[id].seats.length; }
    function seatAt(uint256 id, uint256 index) external view returns (address) { return assignments[id].seats[index]; }
    function rankedAt(uint256 id, uint256 index) external view returns (address) { return assignments[id].ranked[index]; }
    function rankingSize(uint256 id) external view returns (uint256) { return assignments[id].ranked.length; }
    function confirmedCount(uint256 id) external view returns (uint256) { return assignments[id].confirmedCount; }
    function enrollmentDeadline(uint256 id) external view returns (uint256) { return assignments[id].enrollmentEnd; }
    function seedDeadline(uint256 id) external view returns (uint256) { return assignments[id].randomnessEnd; }
    function selectionDeadline(uint256 id) external view returns (uint256) { return assignments[id].selectionEnd; }
    function confirmationDeadline(uint256 id) external view returns (uint256) { return assignments[id].confirmationEnd; }
    function serviceDeadline(uint256 id) external view returns (uint256) { return assignments[id].serviceEnd; }
    function candidateAt(uint256 id, uint256 index) external view returns (address) { return assignments[id].entrants[index]; }
    function assignmentTerms(uint256 id) external view returns
        (uint8 size, uint8 quorum, uint8 reserves, address consumer, address provider) {
        Assignment storage r = assignments[id];
        return (r.size, r.quorum, r.reserves, r.consumer, r.provider);
    }
    function nextReserveAt(uint256 id) external view returns (uint256) { return assignments[id].nextReserve; }
    function rosterCommitment(uint256 id) external view returns (bytes32) { return assignments[id].rosterHash; }
}
