// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {VRFV25Request} from "./SSEVRFV25Adapter.sol";

interface IRawVRFV25Receiver {
    function rawFulfillRandomWords(uint256 requestId, uint256[] calldata words) external;
}

/// @notice ONLY a deterministic test double; it verifies NO cryptographic VRF.
/// @dev NEVER deploy as a production randomness coordinator.
contract MockVRFV25Coordinator {
    uint256 public nextRequestId = 1;
    address public immutable operator;

    struct RequestRecord {
        address consumer;
        bytes32 keyHash;
        uint256 subId;
        uint16 confirmations;
        uint32 callbackGasLimit;
        bytes extraArgs;
    }

    mapping(uint256 => RequestRecord) private requests;

    error Unauthorized();
    error UnknownRequest();
    event MockRequested(uint256 indexed requestId, address indexed consumer);

    constructor() { operator = msg.sender; }

    function requestRandomWords(VRFV25Request.RandomWordsRequest calldata req)
        external returns (uint256 requestId)
    {
        require(req.numWords == 1, "one word only");
        requestId = nextRequestId++;
        requests[requestId] = RequestRecord({
            consumer: msg.sender,
            keyHash: req.keyHash,
            subId: req.subId,
            confirmations: req.requestConfirmations,
            callbackGasLimit: req.callbackGasLimit,
            extraArgs: req.extraArgs
        });
        emit MockRequested(requestId, msg.sender);
    }

    function getRequest(uint256 requestId) external view returns (RequestRecord memory) {
        return requests[requestId];
    }

    function deliver(uint256 requestId, uint256[] calldata words) external {
        if (msg.sender != operator) revert Unauthorized();
        address receiver = requests[requestId].consumer;
        if (receiver == address(0)) revert UnknownRequest();
        // Duplicates deliberately allowed to exercise consumer's ignore logic.
        IRawVRFV25Receiver(receiver).rawFulfillRandomWords(requestId, words);
    }

    function deliverUnknown(address receiver, uint256 requestId,
                            uint256[] calldata words) external {
        if (msg.sender != operator) revert Unauthorized();
        IRawVRFV25Receiver(receiver).rawFulfillRandomWords(requestId, words);
    }
}
