// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {MessageHashUtils} from "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";

/// @notice Domain-bound provider receipt and residual consent authentication.
/// @dev The integrating market supplies its own EIP-712 domain separator,
/// stored parties, request hash, evidence deadline, residual and nonce.
/// This library authenticates consent, not physical delivery or fulfillment.
library SSEAuthenticatedEvidence {
    error InvalidEvidence();
    error InvalidSignature();
    error Expired();

    bytes32 internal constant ACK_TYPEHASH = keccak256(
        "ProviderAck(uint256 leaseId,uint256 epochId,bytes32 requestHash)"
    );
    bytes32 internal constant ALLOCATION_TYPEHASH = keccak256(
        "ResidualAgreement(uint256 leaseId,uint256 epochId,bytes32 requestHash,uint256 unresolvedAmount,uint256 providerShare,uint256 consumerShare,uint256 nonce,uint256 expiry)"
    );

    struct Context {
        uint256 leaseId;
        uint256 epochId;
        bytes32 requestHash;
    }
    struct Allocation {
        uint256 unresolvedAmount;
        uint256 providerShare;
        uint256 consumerShare;
        uint256 nonce;
        uint256 expiry;
    }

    function acknowledgmentDigest(bytes32 domain, Context memory c)
        internal pure returns(bytes32)
    {
        if(domain == bytes32(0) || c.leaseId == 0 || c.requestHash == bytes32(0))
            revert InvalidEvidence();
        return MessageHashUtils.toTypedDataHash(domain,keccak256(abi.encode(
            ACK_TYPEHASH,c.leaseId,c.epochId,c.requestHash
        )));
    }

    function verifyAcknowledgment(bytes32 domain, Context memory c,
        address provider, uint256 deadline, bytes calldata signature) internal view
    {
        if(block.timestamp > deadline) revert Expired();
        if(provider == address(0)) revert InvalidEvidence();
        if(ECDSA.recover(acknowledgmentDigest(domain,c),signature)!=provider)
            revert InvalidSignature();
    }

    function allocationDigest(bytes32 domain, Context memory c, Allocation memory a)
        internal pure returns(bytes32)
    {
        if(domain == bytes32(0) || c.leaseId == 0 || c.requestHash == bytes32(0)
            || a.unresolvedAmount == 0 || a.providerShare > a.unresolvedAmount
            || a.consumerShare != a.unresolvedAmount-a.providerShare)
            revert InvalidEvidence();
        return MessageHashUtils.toTypedDataHash(domain,keccak256(abi.encode(
            ALLOCATION_TYPEHASH,c.leaseId,c.epochId,c.requestHash,
            a.unresolvedAmount,a.providerShare,a.consumerShare,a.nonce,a.expiry
        )));
    }

    /// @dev Caller must atomically consume the stored nonce and allocate
    /// exactly the stored residual. Evidence closure must be enforced by caller.
    function verifyAllocation(bytes32 domain, Context memory c, Allocation memory a,
        address provider,address consumer,uint256 storedResidual,uint256 storedNonce,
        bytes calldata providerSig,bytes calldata consumerSig) internal view
    {
        if(block.timestamp > a.expiry) revert Expired();
        if(provider == address(0) || consumer == address(0) || provider == consumer
            || a.unresolvedAmount != storedResidual || a.nonce != storedNonce)
            revert InvalidEvidence();
        bytes32 digest=allocationDigest(domain,c,a);
        if(ECDSA.recover(digest,providerSig)!=provider
            || ECDSA.recover(digest,consumerSig)!=consumer) revert InvalidSignature();
    }
}
