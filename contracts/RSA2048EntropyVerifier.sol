// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice WP09D EXPERIMENTAL deterministic RSA-2048 proof verification.
/// @dev NOT a standardized/audited VRF. Assumes a correctly generated RSA
/// modulus, secret exponent, honest key setup, and a signer that does not
/// selectively withhold responses. Never substitute a test private key.
contract RSA2048EntropyVerifier {
    uint256 public constant MODULUS_BYTES = 256;
    uint256 public constant PUBLIC_EXPONENT = 65537;
    bytes32 public constant REPRESENTATIVE_DOMAIN =
        keccak256("SSERSA2048RepresentativeV1");

    bytes public modulus;

    error BadModulus();

    constructor(bytes memory n) {
        // The representative's top bit is zero, so a full 2048-bit modulus
        // must exceed it. Parity/length alone do NOT prove genuine RSA setup.
        if (n.length != MODULUS_BYTES ||
            (uint8(n[0]) & 0x80) == 0 ||
            (uint8(n[MODULUS_BYTES - 1]) & 1) == 0) revert BadModulus();
        modulus = n;
    }

    /// @notice Deterministic 2047-bit encoded request representative.
    /// @dev Eight independent Keccak-256 blocks with distinct ABI indices.
    /// The first bit is cleared to ensure m < any 2048-bit modulus.
    /// This is a custom research encoding; do NOT call it standard RSA-FDH.
    function representative(bytes32 requestDigest) public pure returns (bytes memory m) {
        m = new bytes(MODULUS_BYTES);
        for (uint256 i; i < 8; ++i) {
            bytes32 chunk = keccak256(abi.encode(
                REPRESENTATIVE_DOMAIN, requestDigest, i
            ));
            assembly {
                mstore(add(add(m, 32), mul(i, 32)), chunk)
            }
        }
        m[0] = bytes1(uint8(m[0]) & 0x7f);
    }

    /// @notice Verify a canonical 256-byte RSA root of representative(digest).
    /// @dev EIP-198/2565 modular exponentiation precompile, exponent 65537.
    /// No arbitrary external verifier callback can mint an entropy proof.
    function verify(bytes32 requestDigest, bytes calldata proof)
        external view returns (bool)
    {
        if (proof.length != MODULUS_BYTES) return false;
        bytes memory n = modulus;

        // Proof must be a canonical residue, 0 <= proof < n. Otherwise a
        // valid signature plus n could yield a SECOND entropy output.
        bool strictlySmaller;
        for (uint256 i; i < MODULUS_BYTES; ++i) {
            uint8 signatureByte = uint8(proof[i]);
            uint8 modulusByte = uint8(n[i]);
            if (signatureByte < modulusByte) {
                strictlySmaller = true;
                break;
            }
            if (signatureByte > modulusByte) return false;
        }
        if (!strictlySmaller) return false;

        bytes memory input = abi.encodePacked(
            uint256(MODULUS_BYTES), uint256(3), uint256(MODULUS_BYTES),
            proof, hex"010001", n
        );
        (bool ok, bytes memory result) = address(0x05).staticcall(input);
        return ok && result.length == MODULUS_BYTES &&
            keccak256(result) == keccak256(representative(requestDigest));
    }
}
