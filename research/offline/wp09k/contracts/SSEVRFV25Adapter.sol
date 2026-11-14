// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice VRF v2.5 request ABI compatibility (subscription method).
/// @dev Coordinator MUST independently verify the VRF cryptographic proof.
///      This consumer authenticates callback origin but cannot verify VRF alone.
library VRFV25Request {
    bytes4 internal constant EXTRA_ARGS_V1_TAG = bytes4(keccak256("VRF ExtraArgsV1"));

    struct RandomWordsRequest {
        bytes32 keyHash;
        uint256 subId;
        uint16 requestConfirmations;
        uint32 callbackGasLimit;
        uint32 numWords;
        bytes extraArgs;
    }

    function encodeExtraArgs(bool nativePayment) internal pure returns (bytes memory) {
        return abi.encodePacked(EXTRA_ARGS_V1_TAG, abi.encode(nativePayment));
    }
}

interface IVRFV25Coordinator {
    function requestRandomWords(VRFV25Request.RandomWordsRequest calldata req)
        external returns (uint256 requestId);
}

interface ISSEVRFPool {
    function randomnessSource() external view returns (address);
    function settlement() external view returns (address);
    function delayedBlockEntropyEnabled() external view returns (bool);
    function rsaEntropyVerifier() external view returns (address);
    function assignmentStatus(uint256 assignmentId) external view returns (uint8);
    function assignmentRequestedAt(uint256 assignmentId) external view returns (uint64);
    function randomnessTimeout() external view returns (uint64);
    function snapshotCommitment(uint256 assignmentId) external view returns (bytes32);
    function fulfillRandomness(uint256 assignmentId, uint256 seed) external;
}

interface ISSEVRFSettlement {
    function committeePool() external view returns (address);
    function isLeaseRandomnessOpen(uint256 leaseId, uint256 assignmentId)
        external view returns (bool);
}

/// @title SSE-VRF-v2.5 adapter, WP-09J experimental integration
/// @notice Thin ABI-compatible consumer and no-reroll lifecycle for a pinned
/// Chainlink v2.5 subscription coordinator, OR a local test mock.
/// @dev NOT an on-chain VRF prover/verifier; only a real, correctly configured
/// coordinator verifies VRF proofs. The test mock DOES NOT verify any proof.
contract SSEVRFV25Adapter {
    bytes32 public constant DOMAIN = keccak256("SSE-WP09J-COORDINATOR-BOUND-VRF-V1");
    uint8 private constant AWAITING_RANDOMNESS = 1;

    enum State { None, Requested, Ready, Applied, Expired }

    struct Request {
        uint256 assignmentId;
        bytes32 snapshotHash;
        uint256 deadline;
        State state;
        uint256 output;
    }

    address public immutable bootstrapper;
    address public immutable pinnedCoordinator;
    bytes32 public immutable keyHash;
    uint256 public immutable subscriptionId;
    uint16 public immutable confirmations;
    uint32 public immutable callbackGasLimit;
    bool public immutable nativePayment;
    ISSEVRFPool public pool;
    address public settlement;

    mapping(uint256 => Request) public byVrfId;
    mapping(uint256 => uint256) public requestForAssignment;
    mapping(uint256 => bool) public assignmentEverRequested;
    mapping(uint256 => uint256) public leaseForAssignment;

    error Unauthorized();
    error BadState();
    error BadConfiguration();

    event PoolAndSettlementBound(address indexed pool, address indexed settlement);
    event Requested(uint256 indexed assignmentId, uint256 indexed vrfId,
                    bytes32 snapshotHash, uint256 deadline);
    event RandomnessStored(uint256 indexed assignmentId, uint256 indexed vrfId);
    event CallbackIgnored(uint256 indexed vrfId, State previousState);
    event Applied(uint256 indexed assignmentId, uint256 indexed vrfId, bytes32 seedHash);
    event Expired(uint256 indexed assignmentId, uint256 indexed vrfId);

    constructor(address coordinator_, bytes32 keyHash_, uint256 subscriptionId_,
                uint16 confirmations_, uint32 callbackGasLimit_, bool nativePayment_) {
        if (coordinator_ == address(0) || coordinator_.code.length == 0 ||
            keyHash_ == bytes32(0) || subscriptionId_ == 0 ||
            confirmations_ < 3 || callbackGasLimit_ < 100_000) revert BadConfiguration();
        bootstrapper = msg.sender;
        pinnedCoordinator = coordinator_;
        keyHash = keyHash_;
        subscriptionId = subscriptionId_;
        confirmations = confirmations_;
        callbackGasLimit = callbackGasLimit_;
        nativePayment = nativePayment_;
    }

    /// @notice One-way binding avoids cyclic constructor addresses:
    /// coordinator -> adapter -> pool -> settlement, followed by binding.
    function bindPoolAndSettlement(address pool_, address settlement_) external {
        if (msg.sender != bootstrapper || settlement != address(0) ||
            pool_ == address(0) || settlement_ == address(0) ||
            pool_.code.length == 0 || settlement_.code.length == 0) revert Unauthorized();
        ISSEVRFPool target = ISSEVRFPool(pool_);
        if (target.randomnessSource() != address(this) ||
            target.settlement() != settlement_ ||
            target.delayedBlockEntropyEnabled() ||
            target.rsaEntropyVerifier() != address(0) ||
            ISSEVRFSettlement(settlement_).committeePool() != pool_) revert BadConfiguration();
        pool = target;
        settlement = settlement_;
        emit PoolAndSettlementBound(pool_, settlement_);
    }

    /// @notice Only settlement requests randomness, once per assignment.
    /// @dev Deadline is derived from the pool's ORIGINAL request timestamp;
    /// settlement/requester cannot move it or force a new draw after timeout.
    function requestSeed(uint256 leaseId, uint256 assignmentId)
        external returns (uint256 vrfId)
    {
        if (msg.sender != settlement || settlement == address(0)) revert Unauthorized();
        if (leaseId == 0 || assignmentId == 0 || assignmentEverRequested[assignmentId] ||
            !ISSEVRFSettlement(settlement).isLeaseRandomnessOpen(leaseId, assignmentId) ||
            pool.assignmentStatus(assignmentId) != AWAITING_RANDOMNESS)
            revert BadState();
        bytes32 snapshotHash = pool.snapshotCommitment(assignmentId);
        uint64 requestedAt = pool.assignmentRequestedAt(assignmentId);
        uint256 deadline = uint256(requestedAt) + uint256(pool.randomnessTimeout());
        if (snapshotHash == bytes32(0) || requestedAt == 0 ||
            deadline <= block.timestamp) revert BadState();

        VRFV25Request.RandomWordsRequest memory req = VRFV25Request.RandomWordsRequest({
            keyHash: keyHash,
            subId: subscriptionId,
            requestConfirmations: confirmations,
            callbackGasLimit: callbackGasLimit,
            numWords: 1,
            extraArgs: VRFV25Request.encodeExtraArgs(nativePayment)
        });
        // External request should NOT reenter this adapter. All attempts to
        // call requestSeed need the settlement address. In production the
        // coordinator verifies proofs before calling back asynchronously.
        // EFFECTS BEFORE INTERACTION: disallow nested coordinator calls
        // from purchasing another request for the same assignment. Any
        // coordinator revert or invalid return rolls these writes back.
        assignmentEverRequested[assignmentId] = true;
        leaseForAssignment[assignmentId] = leaseId;
        vrfId = IVRFV25Coordinator(pinnedCoordinator).requestRandomWords(req);
        if (vrfId == 0 || byVrfId[vrfId].state != State.None) revert BadState();
        requestForAssignment[assignmentId] = vrfId;
        byVrfId[vrfId] = Request(assignmentId, snapshotHash, deadline, State.Requested, 0);
        emit Requested(assignmentId, vrfId, snapshotHash, deadline);
    }

    /// @notice Coordinator-only callback, compatible with Chainlink v2.5.
    /// @dev Unknown, late, duplicate, malformed callbacks are ignored so the
    /// coordinator's transaction does not revert. NO pool call in callback.
    function rawFulfillRandomWords(uint256 vrfId, uint256[] calldata randomWords) external {
        if (msg.sender != pinnedCoordinator) revert Unauthorized();
        Request storage r = byVrfId[vrfId];
        if (r.state != State.Requested || randomWords.length != 1 ||
            block.timestamp > r.deadline) {
            emit CallbackIgnored(vrfId, r.state);
            return;
        }
        r.output = randomWords[0];
        r.state = State.Ready;
        emit RandomnessStored(r.assignmentId, vrfId);
    }

    /// @notice Separate permissionless application; no repeat or reroll.
    function apply(uint256 assignmentId) external {
        uint256 vrfId = requestForAssignment[assignmentId];
        Request storage r = byVrfId[vrfId];
        if (vrfId == 0 || r.assignmentId != assignmentId || r.state != State.Ready ||
            block.timestamp > r.deadline ||
            pool.assignmentStatus(assignmentId) != AWAITING_RANDOMNESS ||
            pool.snapshotCommitment(assignmentId) != r.snapshotHash ||
            // The consumer may have closed the lease while VRF was pending.
            // Do not create a new committee/bond lock for a closed lease.
            !ISSEVRFSettlement(settlement).isLeaseRandomnessOpen(
                leaseForAssignment[assignmentId], assignmentId))
            revert BadState();
        uint256 seed = uint256(keccak256(abi.encode(
            DOMAIN, block.chainid, address(pool), assignmentId,
            vrfId, r.snapshotHash, r.output
        )));
        r.state = State.Applied;
        // If the pool reverts, EVM rolls state back to Ready atomically.
        pool.fulfillRandomness(assignmentId, seed);
        emit Applied(assignmentId, vrfId, keccak256(abi.encode(seed)));
    }

    /// @notice Fail closed on withholding; pool must also expire its request.
    function expire(uint256 assignmentId) external {
        uint256 vrfId = requestForAssignment[assignmentId];
        Request storage r = byVrfId[vrfId];
        if (vrfId == 0 || r.assignmentId != assignmentId ||
            (r.state != State.Requested && r.state != State.Ready) ||
            block.timestamp <= r.deadline) revert BadState();
        r.state = State.Expired;
        delete r.output;
        emit Expired(assignmentId, vrfId);
    }
}
