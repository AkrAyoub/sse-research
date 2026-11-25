// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import "forge-std/Test.sol";
import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {SSEAuthenticatedEvidence as E} from "../../contracts/SSEAuthenticatedEvidence.sol";

contract SSEEvidenceHarness is EIP712 {
    constructor() EIP712("SSEEvidenceTest", "1") {}
    function ackDigest(E.Context memory c) external view returns(bytes32) {
        return E.acknowledgmentDigest(_domainSeparatorV4(),c);
    }
    function allocationDigest(E.Context memory c,E.Allocation memory a) external view returns(bytes32) {
        return E.allocationDigest(_domainSeparatorV4(),c,a);
    }
    function ack(E.Context memory c,address provider,uint256 deadline,bytes calldata sig) external view {
        E.verifyAcknowledgment(_domainSeparatorV4(),c,provider,deadline,sig);
    }
    function allocate(E.Context memory c,E.Allocation memory a,address provider,address consumer,
        uint256 residual,uint256 nonce,bytes calldata p,bytes calldata q) external view {
        E.verifyAllocation(_domainSeparatorV4(),c,a,provider,consumer,residual,nonce,p,q);
    }
}

contract SSEAuthenticatedEvidenceTest is Test {
    SSEEvidenceHarness private h;
    E.Context private ctx;
    uint256 private constant P=0x12345;
    uint256 private constant C=0x67890;
    address private provider;
    address private consumer;

    function setUp() public {
        h=new SSEEvidenceHarness();
        provider=vm.addr(P);
        consumer=vm.addr(C);
        ctx=E.Context(1,0,keccak256("unit-test request"));
    }
    function sign(uint256 key,bytes32 digest) private pure returns(bytes memory) {
        (uint8 v,bytes32 r,bytes32 s)=vm.sign(key,digest);
        return abi.encodePacked(r,s,v);
    }
    function testValidReceipt() public {
        h.ack(ctx,provider,block.timestamp+60,sign(P,h.ackDigest(ctx)));
    }
    function testWrongSignerAndExpiredReceipt() public {
        bytes memory wrong=sign(C,h.ackDigest(ctx));
        vm.expectRevert(E.InvalidSignature.selector);
        h.ack(ctx,provider,block.timestamp+60,wrong);
        bytes memory valid=sign(P,h.ackDigest(ctx));
        uint256 deadline=block.timestamp+60;
        vm.warp(deadline+1);
        vm.expectRevert(E.Expired.selector);
        h.ack(ctx,provider,deadline,valid);
    }
    function testReceiptBoundToLeaseEpochAndRequest() public {
        bytes memory sig=sign(P,h.ackDigest(ctx));
        E.Context memory other=ctx;
        other.leaseId=2;
        vm.expectRevert(E.InvalidSignature.selector);
        h.ack(other,provider,block.timestamp+60,sig);
        other=ctx;
        other.epochId=1;
        vm.expectRevert(E.InvalidSignature.selector);
        h.ack(other,provider,block.timestamp+60,sig);
        other=ctx;
        other.requestHash=keccak256("other request");
        vm.expectRevert(E.InvalidSignature.selector);
        h.ack(other,provider,block.timestamp+60,sig);
    }
    function testReceiptBoundToContractAndChain() public {
        bytes memory sig=sign(P,h.ackDigest(ctx));
        SSEEvidenceHarness other=new SSEEvidenceHarness();
        vm.expectRevert(E.InvalidSignature.selector);
        other.ack(ctx,provider,block.timestamp+60,sig);
        vm.chainId(block.chainid+1);
        vm.expectRevert(E.InvalidSignature.selector);
        h.ack(ctx,provider,block.timestamp+60,sig);
    }
    function terms() private view returns(E.Allocation memory) {
        return E.Allocation(20,7,13,0,block.timestamp+60);
    }
    function testValidBilateralAllocation() public {
        E.Allocation memory a=terms();
        bytes32 d=h.allocationDigest(ctx,a);
        h.allocate(ctx,a,provider,consumer,20,0,sign(P,d),sign(C,d));
    }
    function testRejectStaleNonceAndResidual() public {
        E.Allocation memory a=terms();
        bytes32 d=h.allocationDigest(ctx,a);
        bytes memory p=sign(P,d);
        bytes memory c=sign(C,d);
        vm.expectRevert(E.InvalidEvidence.selector);
        h.allocate(ctx,a,provider,consumer,20,1,p,c);
        vm.expectRevert(E.InvalidEvidence.selector);
        h.allocate(ctx,a,provider,consumer,19,0,p,c);
    }
    function testRejectChangedAllocationAndMissingConsent() public {
        E.Allocation memory a=terms();
        bytes32 d=h.allocationDigest(ctx,a);
        bytes memory p=sign(P,d);
        bytes memory c=sign(C,d);
        vm.expectRevert(E.InvalidSignature.selector);
        h.allocate(ctx,a,provider,consumer,20,0,p,p);
        a.providerShare=8;
        a.consumerShare=12;
        vm.expectRevert(E.InvalidSignature.selector);
        h.allocate(ctx,a,provider,consumer,20,0,p,c);
    }
    function testRejectExpiredAllocation() public {
        E.Allocation memory a=terms();
        bytes32 d=h.allocationDigest(ctx,a);
        bytes memory p=sign(P,d);
        bytes memory c=sign(C,d);
        vm.warp(a.expiry+1);
        vm.expectRevert(E.Expired.selector);
        h.allocate(ctx,a,provider,consumer,20,0,p,c);
    }
}
