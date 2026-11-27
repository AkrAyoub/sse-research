// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice SSE V4 candidate public service-request and bid board. Holds no funds.
/// @dev SOURCE-ONLY CANDIDATE (2026-11-27): not compiled, not tested, not deployed.
/// Requests commit to off-chain content-addressed descriptors (profile = resource
/// and SLA manifest digest, policy = measurement/evidence policy digest,
/// artifactCommitment = Merkle/manifest root of uploaded inputs). Private
/// inputs are never placed on chain. Bids are free and unbounded in number;
/// nothing on chain iterates over bids. A bid NEVER authorizes execution:
/// only an awarded, accepted, funded and admitted epoch does (market).
contract SSEServiceBoardV4 {
    uint256 public constant MAX_EPOCHS = 64;
    uint256 public constant MAX_SEATS = 64;
    uint64 public constant MAX_WINDOW = 7 days;

    enum Status { None, Open, Awarded, Cancelled }

    struct RequestInput {
        bytes32 profileHash;
        bytes32 policyHash;
        bytes32 artifactCommitment;
        uint256 maxEpochFee;
        uint64 biddingClose;
        // 0 => providers propose epochs in [1, maxEpochs]; otherwise fixed.
        uint32 fixedEpochs;
        uint32 maxEpochs;
        // Consumer-selected monitoring committee: n primary seats, s ordered
        // standbys, fault bound b with n >= 3b+1 (quorum q = n - floor((n-1)/3)
        // satisfies 2q - n > b and q <= n - b).
        uint16 seats;
        uint16 standbys;
        uint16 faultTolerance;
        uint256 perReportReward;
    }

    struct Request {
        address consumer;
        Status status;
        uint32 fixedEpochs;
        uint32 maxEpochs;
        uint16 seats;
        uint16 standbys;
        uint16 faultTolerance;
        uint64 biddingClose;
        bytes32 profileHash;
        bytes32 policyHash;
        bytes32 artifactCommitment;
        uint256 maxEpochFee;
        uint256 perReportReward;
        uint256 awardedBid;
    }

    struct Bid {
        address provider;
        bool withdrawn;
        uint32 epochs;
        uint64 expiry;
        uint256 epochFee;
        // Commitment to the provider's public offer document: endpoint,
        // profile digest, resource reservation and immutable offer terms.
        bytes32 endpointHash;
        bytes32 offerHash;
    }

    address public immutable market;
    uint256 public nextRequestId = 1;
    mapping(uint256 => Request) private requests;
    mapping(uint256 => Bid[]) private bids;

    error Unauthorized();
    error InvalidInput();
    error InvalidPhase();

    event RequestCreated(uint256 indexed requestId, address indexed consumer, bytes32 profileHash,
        bytes32 policyHash, bytes32 artifactCommitment, uint256 maxEpochFee, uint64 biddingClose);
    event RequestMonitoring(uint256 indexed requestId, uint16 seats, uint16 standbys,
        uint16 faultTolerance, uint256 perReportReward, uint32 fixedEpochs, uint32 maxEpochs);
    event RequestCancelled(uint256 indexed requestId);
    event BidPlaced(uint256 indexed requestId, uint256 indexed index, address indexed provider,
        uint256 epochFee, uint32 epochs, uint64 expiry, bytes32 endpointHash, bytes32 offerHash);
    event BidWithdrawn(uint256 indexed requestId, uint256 indexed index);
    event BidAwarded(uint256 indexed requestId, uint256 indexed index, address indexed provider);

    constructor(address market_) {
        if (market_ == address(0)) revert InvalidInput();
        market = market_;
    }

    function createRequest(RequestInput calldata r) external returns (uint256 id) {
        if (r.profileHash == bytes32(0) || r.policyHash == bytes32(0) || r.maxEpochFee == 0 ||
            r.biddingClose <= block.timestamp || r.biddingClose > block.timestamp + MAX_WINDOW ||
            r.maxEpochs == 0 || r.maxEpochs > MAX_EPOCHS ||
            (r.fixedEpochs != 0 && r.fixedEpochs != r.maxEpochs) ||
            r.faultTolerance == 0 || r.seats < 4 ||
            uint256(r.seats) < 3 * uint256(r.faultTolerance) + 1 ||
            uint256(r.seats) + uint256(r.standbys) > MAX_SEATS ||
            r.perReportReward == 0) revert InvalidInput();
        id = nextRequestId++;
        Request storage q = requests[id];
        q.consumer = msg.sender;
        q.status = Status.Open;
        q.fixedEpochs = r.fixedEpochs;
        q.maxEpochs = r.maxEpochs;
        q.seats = r.seats;
        q.standbys = r.standbys;
        q.faultTolerance = r.faultTolerance;
        q.biddingClose = r.biddingClose;
        q.profileHash = r.profileHash;
        q.policyHash = r.policyHash;
        q.artifactCommitment = r.artifactCommitment;
        q.maxEpochFee = r.maxEpochFee;
        q.perReportReward = r.perReportReward;
        emit RequestCreated(id, msg.sender, r.profileHash, r.policyHash, r.artifactCommitment,
            r.maxEpochFee, r.biddingClose);
        emit RequestMonitoring(id, r.seats, r.standbys, r.faultTolerance, r.perReportReward,
            r.fixedEpochs, r.maxEpochs);
    }

    function cancelRequest(uint256 id) external {
        Request storage q = requests[id];
        if (q.consumer != msg.sender) revert Unauthorized();
        if (q.status != Status.Open) revert InvalidPhase();
        q.status = Status.Cancelled;
        emit RequestCancelled(id);
    }

    function placeBid(uint256 id, uint256 epochFee, uint32 epochs, uint64 expiry,
        bytes32 endpointHash, bytes32 offerHash) external returns (uint256 index)
    {
        Request storage q = requests[id];
        if (q.status != Status.Open || block.timestamp >= q.biddingClose) revert InvalidPhase();
        if (msg.sender == q.consumer || epochFee == 0 || epochFee > q.maxEpochFee ||
            epochs == 0 || epochs > q.maxEpochs ||
            (q.fixedEpochs != 0 && epochs != q.fixedEpochs) ||
            expiry <= block.timestamp || expiry > block.timestamp + MAX_WINDOW ||
            endpointHash == bytes32(0) || offerHash == bytes32(0)) revert InvalidInput();
        index = bids[id].length;
        bids[id].push(Bid(msg.sender, false, epochs, expiry, epochFee, endpointHash, offerHash));
        emit BidPlaced(id, index, msg.sender, epochFee, epochs, expiry, endpointHash, offerHash);
    }

    function withdrawBid(uint256 id, uint256 index) external {
        Bid storage b = bids[id][index];
        if (b.provider != msg.sender) revert Unauthorized();
        if (requests[id].status != Status.Open || b.withdrawn) revert InvalidPhase();
        b.withdrawn = true;
        emit BidWithdrawn(id, index);
    }

    /// @notice Market-only. The consumer may award ANY valid unexpired bid,
    /// including the only bid, before or after biddingClose (explicit early
    /// close). Awarding closes the request; there is no privileged selector.
    function award(uint256 id, uint256 index, address caller)
        external returns (Request memory q, Bid memory b)
    {
        if (msg.sender != market) revert Unauthorized();
        Request storage s = requests[id];
        if (s.consumer != caller) revert Unauthorized();
        if (s.status != Status.Open || index >= bids[id].length) revert InvalidPhase();
        Bid storage bs = bids[id][index];
        if (bs.withdrawn || block.timestamp > bs.expiry) revert InvalidPhase();
        s.status = Status.Awarded;
        s.awardedBid = index;
        emit BidAwarded(id, index, bs.provider);
        return (s, bs);
    }

    function request(uint256 id) external view returns (Request memory) { return requests[id]; }
    function bidCount(uint256 id) external view returns (uint256) { return bids[id].length; }
    function bidAt(uint256 id, uint256 index) external view returns (Bid memory) { return bids[id][index]; }

    /// @notice Paginated bid listing for dashboards.
    function bidsInRange(uint256 id, uint256 offset, uint256 limit) external view returns (Bid[] memory out) {
        Bid[] storage all = bids[id];
        uint256 end = offset + limit;
        if (end > all.length) end = all.length;
        if (offset >= end) return new Bid[](0);
        out = new Bid[](end - offset);
        for (uint256 i = offset; i < end; ++i) out[i - offset] = all[i];
    }
}
