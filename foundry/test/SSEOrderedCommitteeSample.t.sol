// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {Test} from "forge-std/Test.sol";
import {SSEGlobalCommitteeSample} from "../../contracts/SSEGlobalCommitteeSample.sol";

contract OrderedSampleHarness {
    function draw(uint256 population,uint256 primary,uint256 standby,bytes32 seed,bytes32 context)
        external pure returns(uint256[] memory)
    {
        return SSEGlobalCommitteeSample.drawOrdered(population,primary,standby,seed,context);
    }
}

contract SSEOrderedCommitteeSampleTest is Test {
    OrderedSampleHarness private h;
    function setUp() public { h=new OrderedSampleHarness(); }
    function testFuzz_uniqueAndDeterministic(uint256 population,uint256 primary,uint256 standby,bytes32 seed) public {
        population=bound(population,1,1000000);
        primary=bound(primary,1,population<64?population:64);
        uint256 remaining=population-primary;
        standby=bound(standby,0,remaining<64-primary?remaining:64-primary);
        uint256[] memory a=h.draw(population,primary,standby,seed,bytes32(uint256(1)));
        uint256[] memory b=h.draw(population,primary,standby,seed,bytes32(uint256(1)));
        assertEq(a.length,primary+standby);
        assertEq(keccak256(abi.encode(a)),keccak256(abi.encode(b)));
        for(uint256 i=0;i<a.length;++i){
            assertLt(a[i],population);
            for(uint256 j=0;j<i;++j) assertTrue(a[i]!=a[j]);
        }
    }
    function testFullPopulationCanChangeOrder() public {
        bytes32 context=bytes32(uint256(1));
        bytes32 first=keccak256(abi.encode(h.draw(6,4,2,bytes32(uint256(0)),context)));
        bool changed;
        for(uint256 i=1;i<16;++i){
            if(keccak256(abi.encode(h.draw(6,4,2,bytes32(i),context)))!=first) changed=true;
        }
        assertTrue(changed);
    }
    function testInvalidInputs() public {
        vm.expectRevert(SSEGlobalCommitteeSample.InvalidSample.selector);
        h.draw(6,0,2,bytes32(0),bytes32(0));
        vm.expectRevert(SSEGlobalCommitteeSample.InvalidSample.selector);
        h.draw(6,4,3,bytes32(0),bytes32(0));
        vm.expectRevert(SSEGlobalCommitteeSample.InvalidSample.selector);
        h.draw(100,64,1,bytes32(0),bytes32(0));
    }
}
