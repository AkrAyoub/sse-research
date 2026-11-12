// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IVRFV25CoordinatorSSE, SSEVRFV25Adapter} from "../../contracts/SSEVRFV25Adapter.sol";

/// @dev INSECURE LAB FIXTURE. Does not produce or verify a Chainlink VRF proof.
/// May only be deployed on an isolated ephemeral Anvil chain.
contract WP15LabCoordinator is IVRFV25CoordinatorSSE {
    uint256 public nextRequestId = 700;
    mapping(uint256 => address) public consumers;

    function requestRandomWords(RandomWordsRequest calldata request)
        external returns (uint256 requestId)
    {
        require(request.numWords == 1 && request.subId != 0, "invalid test VRF request");
        requestId = ++nextRequestId;
        consumers[requestId] = msg.sender;
    }

    function deliver(uint256 requestId, uint256 word) external {
        address consumer = consumers[requestId];
        require(consumer != address(0), "unknown test VRF request");
        uint256[] memory values = new uint256[](1);
        values[0] = word;
        SSEVRFV25Adapter(consumer).rawFulfillRandomWords(requestId, values);
    }
}
