// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Candidate V4 sampling primitive, not a deployed market.
/// @dev Samples globally indexed immutable eligible roster without replacement.
/// Requires an independently established unbiased seed. Does not provide VRF.
/// Sparse permutation uses O(k^2) comparisons and O(k) memory, no N-sized array.
library SSEGlobalCommitteeSample {
    error InvalidSample();
    function draw(uint256 population,uint256 seats,bytes32 seed,bytes32 context)
        internal pure returns(uint256[] memory selected)
    {
        if(seats==0 || seats>population || seats>64) revert InvalidSample();
        selected=new uint256[](seats);
        // Floyd sampling: each step selects a previously unused index.
        // Rejection sampling avoids modulo bias; bounded retries fail closed.
        for(uint256 i=0;i<seats;++i){
            uint256 j=population-seats+i;
            uint256 bound=j+1;
            uint256 threshold=addmod(type(uint256).max,1,bound);
            uint256 r;
            bool accepted;
            for(uint256 attempt=0;attempt<16;++attempt){
                uint256 x=uint256(keccak256(abi.encode(seed,context,i,attempt)));
                if(x>=threshold){r=x%bound;accepted=true;break;}
            }
            if(!accepted) revert InvalidSample();
            bool duplicate;
            for(uint256 z=0;z<i;++z) if(selected[z]==r){duplicate=true;break;}
            selected[i]=duplicate?j:r;
        }
    }
}
