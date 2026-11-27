// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {SSEEntitlementBounds as Bounds} from "./SSEEntitlementBounds.sol";

/// @notice Stateful accounting for one prepaid SSE service lease.
/// @dev Internal library, not a deployed custody contract or evidence oracle.
/// The integrating market MUST authenticate actors and qualified evidence,
/// enforce deadlines, and back all credits with real escrow. No ETH is moved here.
library SSEExposureAccounting {
    error InvalidState();
    error InvalidRequest();
    error InsufficientEscrow();
    error InvalidAllocation();

    struct Epoch {
        bytes32 requestHash;
        uint8 mask;
        bool evidenceClosed;
        bool residualAllocated;
        uint256 providerCredit;
        uint256 consumerCredit;
        uint256 unresolved;
    }

    struct Lease {
        uint256 fee;
        uint256 reservationFee;
        uint256 budget;
        uint256 maxEpochs;
        uint256 funded;
        uint256 available;
        uint256 exposure;
        uint256 providerCredit;
        uint256 consumerCredit;
        uint256 nextEpoch;
        bool closed;
        mapping(uint256 => Epoch) epochs;
        mapping(bytes32 => bool) usedRequests;
    }

    function initialize(Lease storage l, uint256 fee, uint256 reservationFee,
        uint256 budget, uint256 maxEpochs, uint256 funded) internal
    {
        if (l.fee != 0 || maxEpochs == 0 || maxEpochs > 64)
            revert InvalidState();
        Bounds.calculate(fee,reservationFee,7);
        Bounds.reserve(0,fee,budget);
        if (funded != fee * maxEpochs) revert InsufficientEscrow();
        l.fee=fee;
        l.reservationFee=reservationFee;
        l.budget=budget;
        l.maxEpochs=maxEpochs;
        l.funded=funded;
        l.available=funded;
    }

    function admit(Lease storage l, bytes32 requestHash) internal returns (uint256 id) {
        if (l.fee == 0 || l.closed || l.nextEpoch >= l.maxEpochs) revert InvalidState();
        if (requestHash == bytes32(0) || l.usedRequests[requestHash]) revert InvalidRequest();
        if (l.available < l.fee) revert InsufficientEscrow();
        l.exposure=Bounds.reserve(l.exposure,l.fee,l.budget);
        l.available-=l.fee;
        l.usedRequests[requestHash]=true;
        id=l.nextEpoch++;
        Epoch storage e=l.epochs[id];
        e.requestHash=requestHash;
        e.mask=7;
        e.unresolved=l.fee;
    }

    /// @dev nextMask MUST be derived from authenticated, sound evidence by caller,
    /// never accepted as an arbitrary user-supplied verdict.
    function refine(Lease storage l, uint256 id, uint8 nextMask)
        internal returns (uint256 providerDelta, uint256 consumerDelta)
    {
        Epoch storage e=l.epochs[id];
        if (e.mask == 0 || e.evidenceClosed || e.residualAllocated) revert InvalidState();
        (Bounds.Bounds memory b,uint256 dp,uint256 dc,uint256 released)=
            Bounds.refine(l.fee,l.reservationFee,e.mask,nextMask);
        e.mask=nextMask;
        e.providerCredit=b.provider;
        e.consumerCredit=b.consumer;
        e.unresolved=b.unresolved;
        l.providerCredit+=dp;
        l.consumerCredit+=dc;
        l.exposure-=released;
        return (dp,dc);
    }

    function closeEvidence(Lease storage l,uint256 id) internal {
        Epoch storage e=l.epochs[id];
        if (e.mask == 0 || e.evidenceClosed) revert InvalidState();
        e.evidenceClosed=true;
    }

    /// @dev Caller MUST verify bilateral EIP-712 consent and expiry. Consent
    /// allocation is not evidence refinement; preserve the history mask.
    function allocateResidual(Lease storage l,uint256 id,uint256 providerShare,
        uint256 consumerShare) internal
    {
        Epoch storage e=l.epochs[id];
        uint256 residual=e.unresolved;
        if (!e.evidenceClosed || e.residualAllocated || residual == 0) revert InvalidState();
        if (providerShare > residual || consumerShare != residual-providerShare)
            revert InvalidAllocation();
        e.residualAllocated=true;
        e.unresolved=0;
        e.providerCredit+=providerShare;
        e.consumerCredit+=consumerShare;
        l.exposure-=residual;
        l.providerCredit+=providerShare;
        l.consumerCredit+=consumerShare;
    }

    /// @notice Stop new obligations, refund only unused service escrow.
    /// Existing evidence windows and retained residuals remain intact.
    function close(Lease storage l) internal returns (uint256 refund) {
        if (l.fee == 0 || l.closed) revert InvalidState();
        l.closed=true;
        refund=l.available;
        l.available=0;
        l.consumerCredit+=refund;
    }

    function conserved(Lease storage l) internal view returns (bool) {
        return l.funded == l.available+l.exposure+l.providerCredit+l.consumerCredit;
    }
}
