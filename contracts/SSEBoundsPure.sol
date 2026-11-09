// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

//financial bounds over admissible contractual histories.
library SSEBoundsPure {
    uint8 internal constant HISTORY_N = 1;
    uint8 internal constant HISTORY_F = 2;
    uint8 internal constant HISTORY_S = 4;

    error InvalidHistory();
    error InvalidFees();

    function bounds(uint8 mask, uint256 fee, uint256 reservationFee)
        internal pure returns (uint256 lower, uint256 upper, uint256 refund, uint256 retained)
    {
        if (fee == 0 || reservationFee > fee) revert InvalidFees();
        if (mask == 0 || (mask & uint8(0xf8)) != 0) revert InvalidHistory();
        lower = fee;
        upper = 0;
        if ((mask & HISTORY_N) != 0) {
            if (reservationFee < lower) lower = reservationFee;
            if (reservationFee > upper) upper = reservationFee;
        }
        if ((mask & HISTORY_F) != 0) lower = 0;
        if ((mask & HISTORY_S) != 0) upper = fee;
        refund = fee - upper;
        retained = upper - lower;
    }
}

contract SSEBoundsHarness {
    function calculate(uint8 mask, uint256 fee, uint256 reservationFee)
        external pure returns (uint256 provider, uint256 consumer, uint256 unresolved)
    {
        (uint256 lower,, uint256 refund, uint256 retained) = SSEBoundsPure.bounds(mask, fee, reservationFee);
        return (lower, refund, retained);
    }
}
