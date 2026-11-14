// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// UNCOMPILED INTEGRATION DRAFT. Requires a pinned compatible @chainlink/contracts
// version, a supported network coordinator, funded subscription, and matching
// SSESettlement deployment changes. No real VRF is called by offline tests.
import {VRFConsumerBaseV2Plus} from
    "@chainlink/contracts/src/v0.8/vrf/dev/VRFConsumerBaseV2Plus.sol";
import {VRFV2PlusClient} from
    "@chainlink/contracts/src/v0.8/vrf/dev/libraries/VRFV2PlusClient.sol";

interface IWP09IPool {
    function assignmentStatus(uint256 assignmentId) external view returns (uint8);
    function snapshotCommitment(uint256 assignmentId) external view returns (bytes32);
    function fulfillRandomness(uint256 assignmentId, uint256 seed) external;
}

/// @notice Research proposal using standard VRF v2.5 COORDINATOR verification.
/// @dev The COORDINATOR, not this contract, checks cryptographic VRF proofs;
/// VRFConsumerBaseV2Plus authenticates the callback source. NOT a threshold VRF.
/// The pool must be constructed with randomnessSource = address(this) in LEGACY
/// entropy mode, then bindPool() must occur before settlement is bound. An
/// explicit settlement hook to call requestSeed() must also be implemented.
contract WP09IVRFV25AdapterDraft is VRFConsumerBaseV2Plus {
    bytes32 public constant DOMAIN = keccak256("SSE-WP09I-COORDINATOR-BOUND-ENTROPY-V1");
    uint8 private constant AWAITING_RANDOMNESS = 1;

    enum State { None, Requested, Ready, Applied, Expired }

    struct Request {
        uint256 assignmentId;
        bytes32 snapshotHash;
        uint64 deadline;
        State state;
        uint256 output;
    }

    address public immutable bootstrapper;
    // Base v2.5 exposes setCoordinator() for migrations. Its mutable pointer
    // is NOT sufficient authentication for a strict pinned coordinator.
    // Preserve an independent immutable pin and fail closed if migrated.
    address public immutable pinnedCoordinator;
    address public immutable expectedSettlement;
    bytes32 public immutable keyHash;
    uint256 public immutable subscriptionId;
    uint16 public immutable confirmations;
    uint32 public immutable callbackGasLimit;
    bool public immutable nativePayment;
    IWP09IPool public pool;

    mapping(uint256 => Request) public byVrfId;
    mapping(uint256 => uint256) public requestForAssignment;
    mapping(uint256 => bool) public assignmentEverRequested;

    error Unauthorized();
    error BadState();
    error BadConfiguration();

    event PoolBound(address pool);
    event Requested(uint256 indexed assignmentId, uint256 indexed vrfId,
                    bytes32 snapshotCommitment, uint256 deadline);
    event RandomnessStored(uint256 indexed assignmentId, uint256 indexed vrfId);
    event CallbackIgnored(uint256 indexed vrfId, State state);
    event Applied(uint256 indexed assignmentId, uint256 indexed vrfId, bytes32 seedCommitment);
    event Expired(uint256 indexed assignmentId, uint256 indexed vrfId);

    constructor(
        address coordinator, address settlement,
        bytes32 keyHash_, uint256 subscriptionId_, uint16 confirmations_,
        uint32 callbackGasLimit_, bool nativePayment_
    ) VRFConsumerBaseV2Plus(coordinator) {
        if (coordinator == address(0) || settlement == address(0) ||
            keyHash_ == bytes32(0) || subscriptionId_ == 0 ||
            confirmations_ == 0 || callbackGasLimit_ < 10000)
            revert BadConfiguration();
        bootstrapper = msg.sender;
        pinnedCoordinator = coordinator;
        expectedSettlement = settlement;
        keyHash = keyHash_;
        subscriptionId = subscriptionId_;
        confirmations = confirmations_;
        callbackGasLimit = callbackGasLimit_;
        nativePayment = nativePayment_;
    }

    /// @dev Exactly one pool, before any requests. The pool must authorize
    /// this adapter as its immutable randomnessSource.
    function bindPool(address target) external {
        if (msg.sender != bootstrapper || address(pool) != address(0) ||
            target == address(0) || target.code.length == 0)
            revert Unauthorized();
        pool = IWP09IPool(target);
        emit PoolBound(target);
    }

    /// @notice Must be called by an integrated SSESettlement hook only,
    /// after the eligibility snapshot is committed. One request PER LEASE.
    function requestSeed(uint256 assignmentId, uint64 deadline)
        external returns (uint256 vrfId)
    {
        if (msg.sender != expectedSettlement) revert Unauthorized();
        if (assignmentId == 0 || address(pool) == address(0) ||
            assignmentEverRequested[assignmentId] ||
            deadline <= block.timestamp ||
            address(s_vrfCoordinator) != pinnedCoordinator ||
            pool.assignmentStatus(assignmentId) != AWAITING_RANDOMNESS)
            revert BadState();
        bytes32 commitment = pool.snapshotCommitment(assignmentId);
        if (commitment == bytes32(0)) revert BadState();
        // Do not add arbitrary user-selected keyHash, coordinator or retry.
        // The fulfillment transaction verifies proof IN the trusted coordinator.
        vrfId = s_vrfCoordinator.requestRandomWords(
            VRFV2PlusClient.RandomWordsRequest({
                keyHash: keyHash,
                subId: subscriptionId,
                requestConfirmations: confirmations,
                callbackGasLimit: callbackGasLimit,
                numWords: 1,
                extraArgs: VRFV2PlusClient._argsToBytes(
                    VRFV2PlusClient.ExtraArgsV1({nativePayment: nativePayment})
                )
            })
        );
        // Coordinator requestIDs are expected to be unique within this
        // coordinator; do not reuse a consumed ID.
        if (vrfId == 0 || byVrfId[vrfId].state != State.None) revert BadState();
        assignmentEverRequested[assignmentId] = true;
        requestForAssignment[assignmentId] = vrfId;
        byVrfId[vrfId] = Request(assignmentId, commitment, deadline,
                                State.Requested, 0);
        emit Requested(assignmentId, vrfId, commitment, deadline);
    }

    /// @dev Only the authenticated VRF base is permitted to invoke this.
    /// IMPORTANT: no external pool calls, and no reverting on duplicate,
    /// unexpected, or late callbacks. Fulfillment is not automatically retried.
    function fulfillRandomWords(uint256 vrfId, uint256[] calldata words)
        internal override
    {
        Request storage r = byVrfId[vrfId];
        // Even if inherited setCoordinator() changes the base pointer,
        // accept no output from a new coordinator for this pinned adapter.
        if (msg.sender != pinnedCoordinator ||
            r.state != State.Requested || words.length != 1 ||
            block.timestamp > r.deadline) {
            emit CallbackIgnored(vrfId, r.state);
            return;
        }
        r.output = words[0];
        r.state = State.Ready;
        emit RandomnessStored(r.assignmentId, vrfId);
    }

    /// @notice Permissionless separate apply. A pool failure cannot poison
    /// the VRF service's one-time callback transaction.
    function apply(uint256 assignmentId) external {
        uint256 vrfId = requestForAssignment[assignmentId];
        Request storage r = byVrfId[vrfId];
        if (r.state != State.Ready || r.assignmentId != assignmentId ||
            block.timestamp > r.deadline ||
            pool.assignmentStatus(assignmentId) != AWAITING_RANDOMNESS ||
            pool.snapshotCommitment(assignmentId) != r.snapshotHash)
            revert BadState();
        uint256 seed = uint256(keccak256(abi.encode(
            DOMAIN, block.chainid, address(pool), assignmentId,
            vrfId, r.snapshotHash, r.output
        )));
        r.state = State.Applied;
        // This call must succeed atomically or r.state reverts to Ready.
        // The pool is constructed with randomnessSource = address(this).
        pool.fulfillRandomness(assignmentId, seed);
        emit Applied(assignmentId, vrfId, keccak256(abi.encode(seed)));
    }

    /// @notice Fail closed after timeout. No second draw or blockhash fallback.
    /// The pool and settlement must ALSO follow their existing permissionless
    /// expire/close/refund path. VRF subscription fees are not refunded here.
    function expire(uint256 assignmentId) external {
        uint256 vrfId = requestForAssignment[assignmentId];
        Request storage r = byVrfId[vrfId];
        if (r.assignmentId != assignmentId ||
            (r.state != State.Requested && r.state != State.Ready) ||
            block.timestamp <= r.deadline) revert BadState();
        r.state = State.Expired;
        delete r.output;
        emit Expired(assignmentId, vrfId);
    }
}
