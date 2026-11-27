// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice SSE V4 candidate monitor registry: bonded, capacity-backed,
/// permissionless monitor entries and per-lease seat reservations.
/// @dev SOURCE-ONLY CANDIDATE (2026-11-27): not compiled, not tested, not deployed.
/// Holds monitor bonds in native TEST ETH. Only the bound market may sample
/// and reserve/release capacity. A bonded address is NOT proof of an
/// independent operator or fault domain; Sybil weight is one sampling
/// entry per address regardless of bond size.
///
/// Sampling model (see handoff/audits/SMART_CONTRACT_AUDIT.md §Sampling):
/// the roster is append-only; a lease freezes `populationCut` (roster length)
/// when it is awarded, before its entropy block exists. At draw time each
/// attempt hashes (seed, domain, attempt) to an index in [0, populationCut)
/// with rejection sampling (no modulo bias). Inactive entries, the lease's
/// consumer/provider, duplicates and entries without free capacity are
/// skipped. Conditional on a uniform seed/hash model and on eligibility at
/// draw time, the accepted sequence is a uniformly random ORDERED sample
/// without replacement from eligible entries. An adversary can only remove
/// its own entries after seeing the seed, which cannot increase its number
/// of drawn identities. The seed itself (future blockhash) is proposer-
/// influenceable; this is NOT a VRF.
contract SSEMonitorRegistryV4 {
    uint256 public constant MAX_CAPACITY = 64;
    uint256 public constant MAX_SAMPLE = 64;
    uint256 public constant ATTEMPTS_PER_SEAT = 8;
    uint256 public constant MAX_ATTEMPTS = 512;

    struct Entry {
        address monitor;
        bool active;
    }
    struct Position {
        uint256 bond;
        uint256 capacity;
        uint256 reserved;
        uint256 entryIndexPlusOne;
        bool exiting;
    }

    // Memory-only parameters keep the sampler's live stack bounded without
    // changing the public reservation interface or persistent storage layout.
    struct DrawInput {
        bytes32 seed;
        bytes32 domain;
        uint256 populationCut;
        uint256 count;
        address excludeA;
        address excludeB;
    }

    address public immutable market;
    uint256 public immutable perSeatBond;

    Entry[] private roster;
    mapping(address => Position) private positions;
    mapping(uint256 => address[]) private reservedByLease;
    mapping(uint256 => bool) public leaseReservationsReleased;
    mapping(address => uint256) public withdrawable;
    uint256 public activeEntries;
    uint256 public totalBonds;
    uint256 public totalWithdrawable;
    bool private withdrawing;

    error Unauthorized();
    error InvalidInput();
    error InvalidPhase();
    error CapacityExceeded();
    error NoWithdrawal();
    error TransferFailed();

    event MonitorRegistered(address indexed monitor, uint256 indexed entryIndex, uint256 bond, uint256 capacity);
    event MonitorBondUpdated(address indexed monitor, uint256 bond, uint256 capacity);
    event MonitorExitRequested(address indexed monitor, uint256 reservedRemaining);
    event MonitorBondReleased(address indexed monitor, uint256 bond);
    event SeatsReserved(uint256 indexed leaseId, address[] ordered, uint256 attempts);
    event SeatReleased(uint256 indexed leaseId, address indexed monitor);
    event Withdrawal(address indexed account, uint256 amount);

    constructor(address market_, uint256 perSeatBond_) {
        if (market_ == address(0) || perSeatBond_ == 0) revert InvalidInput();
        market = market_;
        perSeatBond = perSeatBond_;
    }

    modifier onlyMarket() {
        if (msg.sender != market) revert Unauthorized();
        _;
    }

    // ------------------------------------------------------------------
    // Permissionless monitor lifecycle
    // ------------------------------------------------------------------

    /// @notice Join with capacity c (concurrent seats). Requires bond >= c * perSeatBond.
    function register(uint256 capacity) external payable {
        Position storage p = positions[msg.sender];
        if (p.entryIndexPlusOne != 0 || p.bond != 0) revert InvalidPhase();
        if (capacity == 0 || capacity > MAX_CAPACITY || msg.value / perSeatBond < capacity)
            revert InvalidInput();
        roster.push(Entry(msg.sender, true));
        p.entryIndexPlusOne = roster.length;
        p.bond = msg.value;
        p.capacity = capacity;
        ++activeEntries;
        totalBonds += msg.value;
        emit MonitorRegistered(msg.sender, roster.length - 1, msg.value, capacity);
    }

    /// @notice Add bond and/or change declared capacity. Capacity may never
    /// drop below currently reserved seats or exceed bond coverage.
    function updateBond(uint256 newCapacity) external payable {
        Position storage p = positions[msg.sender];
        if (p.entryIndexPlusOne == 0 || p.exiting) revert InvalidPhase();
        if (newCapacity == 0 || newCapacity > MAX_CAPACITY) revert InvalidInput();
        uint256 bond = p.bond + msg.value;
        if (newCapacity < p.reserved || bond / perSeatBond < newCapacity) revert CapacityExceeded();
        p.bond = bond;
        p.capacity = newCapacity;
        totalBonds += msg.value;
        emit MonitorBondUpdated(msg.sender, bond, newCapacity);
    }

    /// @notice Stop being eligible for NEW draws immediately. Existing
    /// reservations remain bonded until their leases release them.
    function requestExit() external {
        Position storage p = positions[msg.sender];
        if (p.entryIndexPlusOne == 0 || p.exiting) revert InvalidPhase();
        p.exiting = true;
        roster[p.entryIndexPlusOne - 1].active = false;
        --activeEntries;
        emit MonitorExitRequested(msg.sender, p.reserved);
    }

    /// @notice Release the bond to pull-withdrawable credit once no seat is reserved.
    /// The address may register again later as a new roster entry.
    function completeExit() external {
        Position storage p = positions[msg.sender];
        if (!p.exiting || p.reserved != 0) revert InvalidPhase();
        uint256 bond = p.bond;
        delete positions[msg.sender];
        totalBonds -= bond;
        _credit(msg.sender, bond);
        emit MonitorBondReleased(msg.sender, bond);
    }

    function withdraw() external {
        if (withdrawing) revert InvalidPhase();
        uint256 amount = withdrawable[msg.sender];
        if (amount == 0) revert NoWithdrawal();
        withdrawing = true;
        withdrawable[msg.sender] = 0;
        totalWithdrawable -= amount;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        if (!ok) revert TransferFailed();
        withdrawing = false;
        emit Withdrawal(msg.sender, amount);
    }

    // ------------------------------------------------------------------
    // Market-only reservation interface
    // ------------------------------------------------------------------

    /// @notice Draw and reserve `count` ordered distinct eligible monitors.
    /// @return ok false (and no state change) if fewer than `count` eligible
    /// entries were found within the bounded attempt budget.
    function reserveSample(
        uint256 leaseId,
        bytes32 seed,
        bytes32 domain,
        uint256 populationCut,
        uint256 count,
        address excludeA,
        address excludeB
    ) external onlyMarket returns (bool ok, address[] memory ordered) {
        if (leaseId == 0 || count == 0 || count > MAX_SAMPLE ||
            reservedByLease[leaseId].length != 0 || leaseReservationsReleased[leaseId])
            revert InvalidInput();
        if (populationCut > roster.length) populationCut = roster.length;
        if (populationCut < count) return (false, new address[](0));
        DrawInput memory input = DrawInput(seed, domain, populationCut, count, excludeA, excludeB);
        uint256 attemptsUsed;
        (ordered, attemptsUsed) = _drawSample(input);
        if (ordered.length == 0) return (false, ordered);
        _reservePicked(leaseId, ordered, attemptsUsed);
        return (true, ordered);
    }

    /// @dev Read-only draw: no capacity is consumed unless the full sample exists.
    function _drawSample(DrawInput memory input) private view returns (address[] memory picked, uint256 a) {
        picked = new address[](input.count);
        uint256 found;
        uint256 attempts = input.count * ATTEMPTS_PER_SEAT;
        if (attempts > MAX_ATTEMPTS) attempts = MAX_ATTEMPTS;
        // 2^256 mod N: values below this threshold are rejected (no modulo bias).
        uint256 threshold = addmod(type(uint256).max, 1, input.populationCut);
        for (; a < attempts && found < input.count; ++a) {
            uint256 x = uint256(keccak256(abi.encode("SSE_V4_MONITOR_DRAW", input.seed, input.domain, a)));
            if (x < threshold) continue;
            Entry storage e = roster[x % input.populationCut];
            if (!e.active) continue;
            address m = e.monitor;
            if (m == input.excludeA || m == input.excludeB) continue;
            bool dup;
            for (uint256 j; j < found; ++j) if (picked[j] == m) { dup = true; break; }
            if (dup) continue;
            Position storage p = positions[m];
            if (p.reserved >= p.capacity || p.reserved >= p.bond / perSeatBond) continue;
            picked[found++] = m;
        }
        if (found < input.count) return (new address[](0), a);
    }

    /// @dev Commit the complete ordered sample atomically after selection.
    function _reservePicked(uint256 leaseId, address[] memory picked, uint256 attemptsUsed) private {
        address[] storage list = reservedByLease[leaseId];
        for (uint256 i; i < picked.length; ++i) {
            ++positions[picked[i]].reserved;
            list.push(picked[i]);
        }
        emit SeatsReserved(leaseId, picked, attemptsUsed);
    }

    /// @notice Release every reservation of `leaseId` except addresses in `keep`.
    /// Kept seats are released later by releaseAll. Idempotence: each address
    /// is released at most once because released entries are zeroed.
    function releaseExcept(uint256 leaseId, address[] calldata keep) external onlyMarket {
        address[] storage list = reservedByLease[leaseId];
        for (uint256 i; i < list.length; ++i) {
            address m = list[i];
            if (m == address(0)) continue;
            bool kept;
            for (uint256 j; j < keep.length; ++j) if (keep[j] == m) { kept = true; break; }
            if (kept) continue;
            list[i] = address(0);
            --positions[m].reserved;
            emit SeatReleased(leaseId, m);
        }
    }

    /// @notice Release all remaining reservations of a lease exactly once.
    function releaseAll(uint256 leaseId) external onlyMarket {
        if (leaseReservationsReleased[leaseId]) revert InvalidPhase();
        leaseReservationsReleased[leaseId] = true;
        address[] storage list = reservedByLease[leaseId];
        for (uint256 i; i < list.length; ++i) {
            address m = list[i];
            if (m == address(0)) continue;
            list[i] = address(0);
            --positions[m].reserved;
            emit SeatReleased(leaseId, m);
        }
    }

    // ------------------------------------------------------------------
    // Views (UI / agents). Paginated; never used on-chain in loops.
    // ------------------------------------------------------------------

    function rosterLength() external view returns (uint256) { return roster.length; }

    function entryAt(uint256 index) external view returns (address monitor, bool active) {
        Entry storage e = roster[index];
        return (e.monitor, e.active);
    }

    function position(address monitor) external view returns (
        uint256 bond, uint256 capacity, uint256 reserved, uint256 entryIndexPlusOne, bool exiting)
    {
        Position storage p = positions[monitor];
        return (p.bond, p.capacity, p.reserved, p.entryIndexPlusOne, p.exiting);
    }

    function available(address monitor) public view returns (uint256) {
        Position storage p = positions[monitor];
        if (p.entryIndexPlusOne == 0 || p.exiting) return 0;
        uint256 cap = p.capacity;
        uint256 covered = p.bond / perSeatBond;
        if (covered < cap) cap = covered;
        return cap > p.reserved ? cap - p.reserved : 0;
    }

    /// @notice Count eligible entries (free capacity, not excluded) in
    /// [offset, offset+limit). Off-chain feasibility check for the consumer UI;
    /// the on-chain draw re-checks eligibility and fails closed.
    function eligibleInRange(uint256 offset, uint256 limit, address excludeA, address excludeB)
        external view returns (uint256 eligible, uint256 scanned)
    {
        uint256 end = offset + limit;
        if (end > roster.length) end = roster.length;
        for (uint256 i = offset; i < end; ++i) {
            Entry storage e = roster[i];
            ++scanned;
            if (!e.active || e.monitor == excludeA || e.monitor == excludeB) continue;
            if (available(e.monitor) != 0) ++eligible;
        }
    }

    function reservedFor(uint256 leaseId) external view returns (address[] memory) {
        return reservedByLease[leaseId];
    }

    /// @notice Native TEST ETH coverage; forced ETH may create surplus.
    function bondAccounting() external view returns (uint256 balance, uint256 outstanding, bool covered) {
        balance = address(this).balance;
        outstanding = totalBonds + totalWithdrawable;
        covered = balance >= outstanding;
    }

    function _credit(address account, uint256 amount) private {
        if (amount == 0) return;
        withdrawable[account] += amount;
        totalWithdrawable += amount;
    }
}
