// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";

/// @notice WP-09P: measure deployed EVM runtime rather than infer it from
/// artifact metadata or a gas report. Test-only. No production contracts edited.
contract WP09PBytecodeTruthTest is Test {
    function testActualRuntimeCodeLengthUnderEIP170() public {
        // SSESettlement's constructor only requires a nonzero pool address.
        // We don't interact with that pool in this test.
        SSESettlement settlement = new SSESettlement(address(0xBEEF));
        uint256 deployedSize = address(settlement).code.length;
        console2.log("WP09P_ACTUAL_RUNTIME_BYTES", deployedSize);
        assertGt(deployedSize, 0, "No runtime code was deployed");
        assertLe(deployedSize, 24576, "EIP-170 runtime code size exceeded");
    }
}
