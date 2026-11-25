// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Three-history SSE accounting kernel. No authority to interpret evidence.
/// @dev A caller MUST establish world soundness before narrowing a history mask.
library SSEEntitlementBounds {
    uint8 internal constant N = 1;
    uint8 internal constant F = 2;
    uint8 internal constant S = 4;
    error InvalidTerms();
    error InvalidHistory();
    error ExposureExceeded();

    struct Bounds {
        uint256 provider;
        uint256 consumer;
        uint256 unresolved;
    }

    function calculate(uint256 fee, uint256 reservation, uint8 mask)
        internal pure returns (Bounds memory b)
    {
        if (fee == 0 || reservation > fee) revert InvalidTerms();
        if (mask == 0 || mask > 7) revert InvalidHistory();
        uint256 lower = type(uint256).max;
        uint256 upper;
        if ((mask & N) != 0) { lower = reservation; upper = reservation; }
        if ((mask & F) != 0) lower = 0;
        if ((mask & S) != 0) {
            if (fee < lower) lower = fee;
            upper = fee;
        }
        b = Bounds(lower, fee - upper, upper - lower);
    }

    /// @notice Incremental credits from a nonempty subset of prior histories.
    /// @dev Callers persist the mask and release only these deltas exactly once.
    function refine(uint256 fee, uint256 reservation, uint8 prior, uint8 next)
        internal pure returns (Bounds memory updated, uint256 providerDelta,
            uint256 consumerDelta, uint256 exposureReleased)
    {
        Bounds memory old = calculate(fee, reservation, prior);
        if ((next & prior) != next) revert InvalidHistory();
        updated = calculate(fee, reservation, next);
        providerDelta = updated.provider - old.provider;
        consumerDelta = updated.consumer - old.consumer;
        exposureReleased = old.unresolved - updated.unresolved;
    }

    /// @notice Reserve the full next epoch fee before admitting a new obligation.
    /// @dev Subtraction avoids overflow. Escrow, uniqueness and lifecycle checks
    /// remain responsibilities of the market contract.
    function reserve(uint256 current, uint256 fee, uint256 budget)
        internal pure returns (uint256)
    {
        if (fee == 0) revert InvalidTerms();
        if (current > budget || fee > budget - current) revert ExposureExceeded();
        return current + fee;
    }
}
