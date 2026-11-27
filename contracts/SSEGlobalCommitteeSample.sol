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
    /// @notice Uniform ordered primary + standby indices, conditional on a
    /// uniform seed/hash model. Unlike Floyd's output order, every position
    /// is randomized. Standby ordering must be fixed before confirmations.
    /// @dev This is a sampling primitive, not committee activation or VRF.
    function drawOrdered(uint256 population,uint256 primary,uint256 standby,
                         bytes32 seed,bytes32 context)
        internal pure returns(uint256[] memory ordered)
    {
        if(primary==0 || primary>64 || standby>64-primary ||
           primary+standby>population) revert InvalidSample();
        uint256 count=primary+standby;
        // Uniform subset from Floyd, then independent Fisher-Yates shuffle.
        // Separate domains ensure the permutation does not reuse draw hashes.
        bytes32 domain=keccak256(abi.encode(
            "SSE_ORDERED_PRIMARY_STANDBY_V1",context,population,primary,standby
        ));
        ordered=draw(population,count,seed,domain);
        for(uint256 i=count;i>1;--i){
            uint256 threshold=addmod(type(uint256).max,1,i);
            uint256 r;
            bool accepted;
            for(uint256 attempt=0;attempt<16;++attempt){
                uint256 x=uint256(keccak256(abi.encode(
                    "SSE_STANDBY_PERMUTATION_V1",seed,domain,i,attempt
                )));
                if(x>=threshold){r=x%i;accepted=true;break;}
            }
            if(!accepted) revert InvalidSample();
            (ordered[i-1],ordered[r])=(ordered[r],ordered[i-1]);
        }
    }
}
