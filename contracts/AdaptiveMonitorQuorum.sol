// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Pure candidate math for a FUTURE adaptive monitoring implementation.
/// @dev NOT WIRED to the existing SSESettlement/OpenMonitorCommittee V1 contracts.
/// The live V1 retains hardcoded 4 seats / 3 votes and MUST NOT be called adaptive.
/// All inputs are publicly committed per lease BEFORE the randomness draw.
library AdaptiveMonitorQuorum {
    error InvalidMonitoringPolicy();
    error InsufficientIndependentEligibleMonitors();
    error InsufficientMonitorRewardBudget();

    struct Decision {
        uint256 seats;
        uint256 quorum;
        uint256 modeledByzantineTolerance;
        uint256 requiredMinimumSeats;
    }

    /// @notice For k equal-weight independent seats: strict >2/3 quorum.
    /// @dev This only ensures quorum intersection and models at most
    /// floor((k-1)/3) Byzantine seats. Bonded EOAs or TEST ETH do not prove
    /// independence and cannot establish the Byzantine bound on their own.
    function strictTwoThirdsQuorum(uint256 seats) internal pure returns (uint256) {
        if (seats < 4) revert InvalidMonitoringPolicy();
        return seats - ((seats - 1) / 3);
    }

    /// @param eligibleCount Unbiased snapshot of independent eligible monitors
    /// (physical/fault-domain independence NOT proven by this library).
    /// @param requiredFaultTolerance SLA-selected lower bound f >= 1.
    /// @param gasBoundSeats Maximum affordable seats per single assignment
    /// from measured EVM gas budget; NOT a limit on network monitor members.
    /// @param monitorBudget Only the EVM escrow reserved for monitor reports.
    /// @param epochs Number of leased epochs paid from the budget.
    /// @param paymentPerSeatEpoch Guaranteed report reward per seat per epoch.
    function decide(
        uint256 eligibleCount,
        uint256 requiredFaultTolerance,
        uint256 gasBoundSeats,
        uint256 monitorBudget,
        uint256 epochs,
        uint256 paymentPerSeatEpoch
    ) internal pure returns (Decision memory d) {
        if (requiredFaultTolerance == 0 || epochs == 0 ||
            paymentPerSeatEpoch == 0 || gasBoundSeats == 0 ||
            requiredFaultTolerance > (type(uint256).max - 1) / 3) {
            revert InvalidMonitoringPolicy();
        }
        uint256 requiredSeats = 3 * requiredFaultTolerance + 1;
        if (eligibleCount < requiredSeats) {
            revert InsufficientIndependentEligibleMonitors();
        }
        if (gasBoundSeats < requiredSeats) {
            revert InvalidMonitoringPolicy();
        }
        // Overflow is a fail-closed Solidity 0.8 checked-arithmetic revert.
        uint256 costPerSeat = epochs * paymentPerSeatEpoch;
        uint256 payableSeats = monitorBudget / costPerSeat;
        if (payableSeats < requiredSeats) {
            revert InsufficientMonitorRewardBudget();
        }
        uint256 selected = eligibleCount;
        if (gasBoundSeats < selected) selected = gasBoundSeats;
        if (payableSeats < selected) selected = payableSeats;
        d.seats = selected;
        d.quorum = strictTwoThirdsQuorum(selected);
        d.modeledByzantineTolerance = (selected - 1) / 3;
        d.requiredMinimumSeats = requiredSeats;
    }
}
