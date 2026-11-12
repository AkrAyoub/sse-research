// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ScalableMonitorCommitteeV2, IVerifiedMonitorRandomnessV2}
    from "./ScalableMonitorCommitteeV2.sol";

/// @dev Minimal ABI compatible with the Chainlink VRF v2.5 subscription coordinator.
/// No mock VRF proof is accepted here: the deployed coordinator is responsible
/// for verifying its VRF proof *before* calling rawFulfillRandomWords.
interface IVRFV25CoordinatorSSE {
    struct RandomWordsRequest {
        bytes32 keyHash;
        uint256 subId;
        uint16 requestConfirmations;
        uint32 callbackGasLimit;
        uint32 numWords;
        bytes extraArgs;
    }
    function requestRandomWords(RandomWordsRequest calldata req) external returns (uint256 requestId);
}

/// @notice SSE V2 adapter for Chainlink VRF v2.5 verified coordinator callbacks.
/// @dev Research integration. It MUST be deployed against an independently
/// verified Chainlink VRF coordinator, funded subscription and supported network.
/// This adapter itself DOES NOT cryptographically verify a VRF proof, attest
/// monitor independence or qualify the physical delivery of any service.
contract SSEVRFV25Adapter is IVerifiedMonitorRandomnessV2 {
    // From Chainlink VRFV2PlusClient.EXTRA_ARGS_V1_TAG.
    bytes4 public constant EXTRA_ARGS_V1_TAG = bytes4(keccak256("VRF ExtraArgsV1"));
    uint32 public constant NUM_WORDS = 1;

    struct Request {
        uint256 assignmentId;
        bytes32 assignmentCommitment;
        bytes32 seed;
        uint256 randomWord;
        bool fulfilled;
        bool delivered;
    }

    address public immutable bootstrapper;
    address public immutable requestOperator;
    IVRFV25CoordinatorSSE public immutable coordinator;
    bytes32 public immutable keyHash;
    uint256 public immutable subscriptionId;
    uint16 public immutable confirmations;
    uint32 public immutable callbackGasLimit;
    bool public immutable nativePayment;
    ScalableMonitorCommitteeV2 public pool;

    mapping(uint256 => uint256) public requestForAssignment;
    // Set BEFORE calling the coordinator. Prevents a malicious or misconfigured
    // requestOperator/coordinator pair from reentering and buying extra draws.
    mapping(uint256 => bool) public requestStarted;
    mapping(uint256 => Request) public requests;

    error InvalidInput();
    error Unauthorized();
    error InvalidState();
    error UnknownRequest();
    error InvalidCoordinatorFulfillment();

    event PoolBound(address indexed pool);
    event RandomnessRequested(uint256 indexed assignmentId, uint256 indexed requestId, bytes32 commitment);
    event RandomnessFulfilled(uint256 indexed assignmentId, uint256 indexed requestId, bytes32 derivedSeed);
    event RandomnessApplied(uint256 indexed assignmentId, uint256 indexed requestId, bytes32 derivedSeed);

    constructor(address coordinator_, address requester_, bytes32 keyHash_,
                uint256 subscription_, uint16 confirmations_, uint32 callbackGasLimit_,
                bool nativePayment_) {
        if (coordinator_.code.length == 0 || requester_ == address(0) ||
            keyHash_ == bytes32(0) || subscription_ == 0 ||
            confirmations_ < 3 || confirmations_ > 200 ||
            callbackGasLimit_ < 100_000 || callbackGasLimit_ > 2_000_000)
            revert InvalidInput();
        bootstrapper = msg.sender;
        requestOperator = requester_;
        coordinator = IVRFV25CoordinatorSSE(coordinator_);
        keyHash = keyHash_;
        subscriptionId = subscription_;
        confirmations = confirmations_;
        callbackGasLimit = callbackGasLimit_;
        nativePayment = nativePayment_;
    }

    /// @notice Bind after deploying the pool with randomnessSource AND verifier
    /// both set to the adapter address. One-time bootstrapper-only wiring.
    function bindPool(address pool_) external {
        if (msg.sender != bootstrapper || address(pool) != address(0)) revert Unauthorized();
        if (pool_.code.length == 0) revert InvalidInput();
        ScalableMonitorCommitteeV2 target = ScalableMonitorCommitteeV2(pool_);
        if (target.randomnessSource() != address(this) || address(target.verifier()) != address(this))
            revert InvalidInput();
        pool = target;
        emit PoolBound(pool_);
    }

    /// @notice Subscription spending requires an accountable trusted operator.
    /// A permissionless caller could otherwise drain a shared subscription by
    /// opening arbitrarily many funded assignments.
    /// Once requested, the assignment NEVER re-requests randomness: allowing
    /// retries after inspecting results would enable selective/grinding attacks.
    function requestRandomness(uint256 assignmentId) external returns (uint256 requestId) {
        if (msg.sender != requestOperator) revert Unauthorized();
        ScalableMonitorCommitteeV2 target = pool;
        if (address(target) == address(0) ||
            target.status(assignmentId) != ScalableMonitorCommitteeV2.Status.WaitingSeed ||
            block.timestamp > target.seedDeadline(assignmentId) ||
            requestStarted[assignmentId]) revert InvalidState();

        bytes32 commitment = target.assignmentCommitment(assignmentId);
        requestStarted[assignmentId] = true; // rolls back if the coordinator call fails
        bytes memory extra = abi.encodeWithSelector(EXTRA_ARGS_V1_TAG, nativePayment);
        requestId = coordinator.requestRandomWords(IVRFV25CoordinatorSSE.RandomWordsRequest({
            keyHash: keyHash,
            subId: subscriptionId,
            requestConfirmations: confirmations,
            callbackGasLimit: callbackGasLimit,
            numWords: NUM_WORDS,
            extraArgs: extra
        }));
        if (requestId == 0 || requests[requestId].assignmentId != 0) revert InvalidCoordinatorFulfillment();
        requestForAssignment[assignmentId] = requestId;
        Request storage r = requests[requestId];
        r.assignmentId = assignmentId;
        r.assignmentCommitment = commitment;
        emit RandomnessRequested(assignmentId, requestId, commitment);
    }

    /// @notice Called *only* by the configured VRF v2.5 coordinator, after that
    /// coordinator has verified the VRF cryptographic proof.
    /// Store only: a callback NEVER immediately attempts a pool state transition.
    /// A separate permissionless finalize avoids losing a coordinator callback
    /// solely because pool supplyRandomness is temporarily unavailable.
    function rawFulfillRandomWords(uint256 requestId, uint256[] calldata randomWords) external {
        if (msg.sender != address(coordinator)) revert Unauthorized();
        Request storage r = requests[requestId];
        if (r.assignmentId == 0) revert UnknownRequest();
        if (r.fulfilled || randomWords.length != 1) revert InvalidCoordinatorFulfillment();
        r.randomWord = randomWords[0];
        r.seed = keccak256(abi.encode(
            randomWords[0], r.assignmentCommitment, r.assignmentId, block.chainid, address(this)
        ));
        r.fulfilled = true;
        emit RandomnessFulfilled(r.assignmentId, requestId, r.seed);
    }

    /// @notice Permissionless after coordinator fulfillment, before the V2 pool
    /// seed deadline. No second request is made if a callback arrives too late.
    function finalizeRandomness(uint256 assignmentId) external {
        uint256 requestId = requestForAssignment[assignmentId];
        Request storage r = requests[requestId];
        ScalableMonitorCommitteeV2 target = pool;
        if (requestId == 0 || !r.fulfilled || r.delivered ||
            r.assignmentId != assignmentId ||
            target.status(assignmentId) != ScalableMonitorCommitteeV2.Status.WaitingSeed ||
            block.timestamp > target.seedDeadline(assignmentId) ||
            target.assignmentCommitment(assignmentId) != r.assignmentCommitment) revert InvalidState();
        r.delivered = true; // reentrancy-safe; external failure rolls back this flag
        target.supplyRandomness(assignmentId, r.seed, abi.encode(requestId));
        emit RandomnessApplied(assignmentId, requestId, r.seed);
    }

    /// @notice This adapter is also the pool's configured verification interface.
    /// Checks only a coordinator-attested, locally recorded seed and its exact
    /// pre-seed roster commitment. An arbitrary EOA cannot call it as the pool.
    function verify(bytes32 commitment, bytes32 seed, bytes calldata proof)
        external view override returns (bool)
    {
        if (msg.sender != address(pool) || proof.length != 32) return false;
        uint256 requestId = abi.decode(proof, (uint256));
        Request storage r = requests[requestId];
        return r.assignmentId != 0 && r.fulfilled && r.delivered &&
            r.assignmentCommitment == commitment && r.seed == seed &&
            requestForAssignment[r.assignmentId] == requestId;
    }
}
