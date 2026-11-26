// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Candidate V4 collateral accounting. No identity or physical
/// capacity attestation. The integrating market must authorize transitions,
/// retain collateral until its evidence/slashing horizon, and account for ETH.
library SSEMonitorCapacity {
    error CapacityExceeded();
    error InvalidCapacity();
    struct Position {
        uint256 bond;
        uint256 declaredCapacity;
        uint256 reserved;
    }
    function capacity(Position storage p,uint256 perSeatBond)
        internal view returns(uint256)
    {
        if(perSeatBond==0) revert InvalidCapacity();
        uint256 collateralCapacity=p.bond/perSeatBond;
        return p.declaredCapacity<collateralCapacity?p.declaredCapacity:collateralCapacity;
    }
    function configure(Position storage p,uint256 bond,uint256 declaredCapacity,uint256 perSeatBond)
        internal
    {
        if(perSeatBond==0 || declaredCapacity==0) revert InvalidCapacity();
        if(declaredCapacity<p.reserved || bond/perSeatBond<p.reserved) revert CapacityExceeded();
        p.bond=bond;
        p.declaredCapacity=declaredCapacity;
    }
    function reserve(Position storage p,uint256 perSeatBond) internal {
        if(p.reserved>=capacity(p,perSeatBond)) revert CapacityExceeded();
        ++p.reserved;
    }
    function release(Position storage p) internal {
        if(p.reserved==0) revert InvalidCapacity();
        --p.reserved;
    }
    function available(Position storage p,uint256 perSeatBond) internal view returns(uint256){
        uint256 cap=capacity(p,perSeatBond);
        return cap>p.reserved?cap-p.reserved:0;
    }
}
