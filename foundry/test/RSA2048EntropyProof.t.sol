// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {OpenMonitorCommittee} from "../../contracts/OpenMonitorCommittee.sol";
import {RSA2048EntropyVerifier} from "../../contracts/RSA2048EntropyVerifier.sol";
import {SSESettlement} from "../../contracts/SSESettlement.sol";

/// @notice Research TEST PRIVATE KEY IS PUBLIC. This test suite cannot prove
/// unpredictability, secure key generation, Sybil resistance or liveness.
/// One mocked verifier success is used to test dynamic pool state; the static
/// real RSA proof test and LIVE ANVIL integration exercise real modexp.
contract RSA2048EntropyProofTest is Test {
    bytes internal constant LAB_MODULUS = hex"a5b3e2f79d2868274d7e32c960ccf7188a1a84ab2550dbf314832abfaa8bfd11ca102f8922e2125103f0c031d4e27cfcf1da3149164ee9e7b23b9d6833130435f4b94a62c384f26d30e6bc9ec941cfcb4dbbb2318b89bbb55de56d9302c74842496ad3f3c484a0cac09ced75dc0c576e97f66391d7cb3f1e5dc0f2d4e6817c91e7892cb8cf8bcfa21a6cacb4bd10317d19e95ccae1db41dad18ab7266f0b8c1c4d3987e3dce250255d6a8cc86665bf3823a1edbe83190c64246f91cf03351aeb4b7509ac0d46098faf6bacf91d201d91dcafd6fd1a6eb483dddde65d1be9895dba05fc7c1c29ac60a80fb6f87b7ae06026b456be3413ae1ded0c2fcd62d79fdf";
    bytes internal constant STATIC_PROOF = hex"0353358280d4834231da8d65085d0a28e043101bda43239a7c721ceabd91d1fcfac832ce2f282e45878598e0e3254de3fa8352a40c10b4db0dfd7a8c56027993c38e2b69b5092a6c93899b9bc1d66958e3b0d12a15474b00c5c0ce193fd0adeb0e9685c9649fc9b9f85e07123d4c10ae210ad2cd1674f57de42c02d9fdb0a1337eb26dff797ca5b1a8174df6d213a2fc259f2847ca639ef09b18c16a87c60e72a29922c5dcc388c9f724c3f6d97f4199c76e8483056f0eeccd49528a2f578fa507fa3e4806cf9c0672b445c46aa3c4533bb5b885ad354c6d0c49f1f27c5362610c757a436f312a5a34c4c1db48f86909adce8a9a6a035653a0913c65f9191d22";
    bytes internal constant STATIC_REPRESENTATIVE = hex"7e60bc5d982dc39f410836c4adf1259f2708baa1bfa088b16c7956a3090a69231bcb2d23ff1adfb6c3bca6a115ec269c45fb3fe7cb67427df4200a87cb9db201dbac9f68a400452a40480c7e9187a61febd2f1976c1accf7a6cf70239f0abc28d37c6809a7ed201171caa12151383acaf8a51672667e6809441fec3b7d6f736b7464ccdfab699a369c26f969c378bebc4d1ec64f7cb7e312a9c94f0462f3e830b0c966da059150fe2b4f9129494f914184e7ff4ffb1d576877f87e2eeb1cfdc2f65f652a5c5f5a2171638ae418bdba63a7e700ce4dfe8275035cec18a6a6a8a9cd573d9f3847cdf971cd63df6a3593ac3e037a72957f1071c8215f66e5c97df4";

    OpenMonitorCommittee pool;
    RSA2048EntropyVerifier verifier;
    SSESettlement settlement;
    address consumer = address(0xA100);
    address provider = address(0xB100);
    address outsider = address(0xDADA);

    function setUp() public {
        vm.warp(100_000);
        vm.roll(100);
        pool = new OpenMonitorCommittee(address(this), 1 ether, 7 days, 1 days);
        pool.enableRSAProofEntropy(LAB_MODULUS);
        verifier = pool.rsaEntropyVerifier();
        settlement = new SSESettlement(address(pool));
        pool.bindSettlement(address(settlement));
        vm.deal(consumer, 10 ether);
        vm.deal(provider, 10 ether);
        for (uint256 i; i < 5; ++i) {
            address monitor = address(uint160(0xC100 + i));
            vm.deal(monitor, 2 ether);
            vm.prank(monitor);
            pool.register{value: 1 ether}();
        }
    }

    function _lease() internal returns (uint256) {
        vm.prank(consumer);
        return settlement.createLease{value: 25}(
            provider, keccak256("rsa-lab-endpoint"), keccak256("rsa-lab-profile"),
            25, 5, 25, 1, 100, 100, 100
        );
    }

    function testIndependentStaticRSA2048ProofRealPrecompile() public {
        bytes32 digest = bytes32(uint256(17));
        assertEq(verifier.representative(digest), STATIC_REPRESENTATIVE);
        assertTrue(verifier.verify(digest, STATIC_PROOF));
        assertFalse(verifier.verify(bytes32(uint256(18)), STATIC_PROOF));
        assertFalse(verifier.verify(digest, hex"0001"));
        bytes memory corrupted = STATIC_PROOF;
        corrupted[255] = bytes1(uint8(corrupted[255]) ^ 1);
        assertFalse(verifier.verify(digest, corrupted));
        assertEq(verifier.PUBLIC_EXPONENT(), 65537);
        assertEq(verifier.modulus(), LAB_MODULUS);
    }

    function testNoncanonicalProofPlusModulusRejectedEvenThoughSameRSAResidue() public {
        bytes memory differentEncoding = new bytes(256);
        uint256 carry;
        for (uint256 i = 256; i > 0; --i) {
            uint256 value = uint8(STATIC_PROOF[i - 1]) +
                uint8(LAB_MODULUS[i - 1]) + carry;
            differentEncoding[i - 1] = bytes1(uint8(value));
            carry = value >> 8;
        }
        assertEq(carry, 0);
        assertFalse(verifier.verify(bytes32(uint256(17)), differentEncoding));
    }

    function testCannotDeployMalformedRSAKeyOrSwapEntropyMode() public {
        vm.expectRevert(RSA2048EntropyVerifier.BadModulus.selector);
        new RSA2048EntropyVerifier(hex"1234");
        bytes memory bad = LAB_MODULUS;
        bad[0] = 0x01;
        vm.expectRevert(RSA2048EntropyVerifier.BadModulus.selector);
        new RSA2048EntropyVerifier(bad);
        bad = LAB_MODULUS;
        bad[255] = 0x02;
        vm.expectRevert(RSA2048EntropyVerifier.BadModulus.selector);
        new RSA2048EntropyVerifier(bad);

        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        pool.enableDelayedBlockEntropy();
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        pool.enableRSAProofEntropy(LAB_MODULUS);
        vm.prank(outsider);
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        pool.enableRSAProofEntropy(LAB_MODULUS);
        assertFalse(pool.delayedBlockEntropyEnabled());
        assertEq(address(pool.rsaEntropyVerifier()), address(verifier));
    }

    function testFrozenRequestAndUnauthorizedSeedCannotSelectCommittee() public {
        uint256 id = _lease();
        assertEq(id, 1);
        assertEq(pool.snapshotSize(id), 5);
        assertTrue(pool.snapshotCommitment(id) != bytes32(0));
        bytes32 digest = pool.rsaRequestDigest(id);
        bytes32 manual = keccak256(abi.encode(
            pool.RSA_ENTROPY_DOMAIN(), block.chainid, address(pool), id,
            pool.assignmentRequestedBlock(id), pool.snapshotCommitment(id)
        ));
        assertEq(digest, manual);
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        pool.fulfillRandomness(id, 1234);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.fulfillDelayedBlockEntropy(id);
        vm.prank(outsider);
        vm.expectRevert(OpenMonitorCommittee.InvalidEntropyProof.selector);
        pool.fulfillRSAProofEntropy(id, STATIC_PROOF);
        assertEq(uint8(pool.assignmentStatus(id)),
                 uint8(OpenMonitorCommittee.RequestStatus.AwaitingRandomness));

        // This is a state-machine mock only: a static signature for digest 17
        // obviously does not match this dynamic lease digest. The real modexp
        // of a lease-scoped proof is tested by the fresh Anvil integration.
        vm.mockCall(address(verifier),
                    abi.encodeWithSelector(verifier.verify.selector, digest, STATIC_PROOF),
                    abi.encode(true));
        vm.prank(outsider);
        pool.fulfillRSAProofEntropy(id, STATIC_PROOF);
        vm.clearMockedCalls();
        assertEq(uint8(pool.assignmentStatus(id)),
                 uint8(OpenMonitorCommittee.RequestStatus.Assigned));
        uint256 seed = uint256(keccak256(abi.encode(
            pool.RSA_ENTROPY_DOMAIN(), digest, keccak256(STATIC_PROOF)
        )));
        address[] memory shuffled = new address[](5);
        for (uint256 i; i < 5; ++i) {
            shuffled[i] = address(uint160(0xC100 + i));
        }
        for (uint256 i; i < 5; ++i) {
            uint256 j = i + uint256(keccak256(abi.encode(seed, id, i))) % (5 - i);
            (shuffled[i], shuffled[j]) = (shuffled[j], shuffled[i]);
        }
        address[4] memory selected = pool.getCommittee(id);
        for (uint256 i; i < 4; ++i) assertEq(selected[i], shuffled[i]);
        assertEq(pool.standbyRemaining(id), 1);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.fulfillRSAProofEntropy(id, STATIC_PROOF);
    }

    function testEntropyProofWithheldUntilExpiryReleasesBondsAndRefundsConsumer() public {
        uint256 id = _lease();
        for (uint256 i; i < 5; ++i) {
            (,, uint32 pending,,,) = pool.candidates(pool.candidateAt(i));
            assertEq(pending, 1);
        }
        vm.warp(block.timestamp + pool.randomnessTimeout() + 1);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.fulfillRSAProofEntropy(id, STATIC_PROOF);
        pool.expire(id);
        assertEq(uint8(pool.assignmentStatus(id)),
                 uint8(OpenMonitorCommittee.RequestStatus.Expired));
        for (uint256 i; i < 5; ++i) {
            (,, uint32 pending, uint32 assignments,,) = pool.candidates(pool.candidateAt(i));
            assertEq(pending, 0);
            assertEq(assignments, 0);
        }
        vm.prank(consumer);
        settlement.closeLease(id);
        assertEq(settlement.withdrawable(consumer), 25);
        assertEq(address(settlement).balance, 25);
    }

    function testWrongPoolCannotReuseProofAndSecondSnapshotHasDifferentDigest() public {
        uint256 id = _lease();
        bytes32 first = pool.rsaRequestDigest(id);
        uint256 second = _lease();
        assertTrue(pool.rsaRequestDigest(second) != first);
        assertTrue(pool.snapshotCommitment(second) != pool.snapshotCommitment(id));
        // A second pool address is also domain-separated.
        OpenMonitorCommittee other =
            new OpenMonitorCommittee(address(this), 1 ether, 7 days, 1 days);
        other.enableRSAProofEntropy(LAB_MODULUS);
        assertTrue(address(other.rsaEntropyVerifier()) != address(verifier));
    }
}
