// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Restricted three-history evidence policy for adaptive SSE.
/// @dev This is a policy under explicit assumptions, NOT a physical oracle.
/// A qualified positive/negative observation must be established by the
/// integrating contract and its committed measurement policy. A timeout,
/// arbitrary report hash or numerical quorum alone is not qualification.
library SSEHistoryPolicy {
    error ConflictingEvidence();
    error InvalidHistory();

    uint8 internal constant N = 1;
    uint8 internal constant F = 2;
    uint8 internal constant S = 4;

    /// @param bindingReceipt Provider's authenticated contractual admission
    /// of receipt, NOT independently verified network delivery time.
    /// @param qualifiedSuccess Evidence soundly establishing fulfillment.
    /// @param qualifiedNegative Evidence soundly excluding fulfillment.
    /// @return mask All remaining admissible histories.
    function admissible(bool bindingReceipt, bool qualifiedSuccess,
        bool qualifiedNegative) internal pure returns (uint8 mask)
    {
        if (qualifiedSuccess && qualifiedNegative) revert ConflictingEvidence();
        mask = N | F | S;
        if (bindingReceipt) mask &= F | S;
        if (qualifiedSuccess) mask &= S;
        if (qualifiedNegative) mask &= N | F;
    }

    /// @notice Combine previously accepted and newly qualified predicates.
    /// Never undo a credited entitlement by expanding accepted histories.
    /// Contradictions are rejected, not resolved by arbitrary priority.
    function narrow(uint8 previous, uint8 additional)
        internal pure returns (uint8 mask)
    {
        if (previous == 0 || previous > 7 || additional == 0 || additional > 7)
            revert InvalidHistory();
        mask = previous & additional;
        if (mask == 0) revert ConflictingEvidence();
    }
}
