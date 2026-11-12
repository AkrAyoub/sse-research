// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {SSEVRFV25Adapter, IVRFV25CoordinatorSSE} from "../../contracts/SSEVRFV25Adapter.sol";
import {ScalableMonitorCommitteeV2} from "../../contracts/ScalableMonitorCommitteeV2.sol";

/// @dev Simulates the coordinator callback contract boundary only.
/// Does NOT generate/verify a VRF proof and MUST NOT be used in production.
contract WP11MockCoordinator is IVRFV25CoordinatorSSE {
    uint256 public nextId = 71;
    mapping(uint256 => address) public consumerForRequest;
    bytes32 public lastKeyHash;
    uint256 public lastSubId;
    uint16 public lastConfirmations;
    uint32 public lastGasLimit;
    uint32 public lastNumWords;
    bytes public lastExtraArgs;

    function requestRandomWords(RandomWordsRequest calldata req) external returns (uint256 id) {
        id = nextId++;
        consumerForRequest[id] = msg.sender;
        lastKeyHash = req.keyHash;
        lastSubId = req.subId;
        lastConfirmations = req.requestConfirmations;
        lastGasLimit = req.callbackGasLimit;
        lastNumWords = req.numWords;
        lastExtraArgs = req.extraArgs;
    }

    function deliver(uint256 requestId, uint256[] calldata words) external {
        address consumer = consumerForRequest[requestId];
        require(consumer != address(0), "unknown mock request");
        SSEVRFV25Adapter(consumer).rawFulfillRandomWords(requestId, words);
    }

    /// @dev Deliberate adversary test: try a made-up request ID from coordinator.
    function spoofUnknown(address target, uint256 requestId, uint256[] calldata words) external {
        SSEVRFV25Adapter(target).rawFulfillRandomWords(requestId, words);
    }

    function setNextId(uint256 id) external { nextId = id; }
}

contract WP11PoolController {
    function open(ScalableMonitorCommitteeV2 pool, ScalableMonitorCommitteeV2.Terms calldata t)
        external returns (uint256) { return pool.requestAssignment(t); }
}

/// @dev Deliberately misconfigured: coordinator is also the request operator.
/// Attempts to initiate an extra billable request synchronously.
contract WP11ReentrantCoordinator is IVRFV25CoordinatorSSE {
    SSEVRFV25Adapter public adapter;
    uint256 public assignmentId;
    uint256 public count;
    bool public secondRequestSucceeded;

    function configure(SSEVRFV25Adapter target, uint256 assignment) external {
        adapter = target;
        assignmentId = assignment;
    }
    function start() external returns (uint256) {
        return adapter.requestRandomness(assignmentId);
    }
    function requestRandomWords(RandomWordsRequest calldata) external returns (uint256) {
        ++count;
        if (count == 1) {
            try adapter.requestRandomness(assignmentId) returns (uint256) {
                secondRequestSucceeded = true;
            } catch {}
        }
        return 800 + count;
    }
}

contract SSEVRFV25AdapterTest is Test {
    WP11MockCoordinator coordinator;
    WP11PoolController requester;
    SSEVRFV25Adapter adapter;
    ScalableMonitorCommitteeV2 pool;
    bytes32 constant KEY_HASH = keccak256("lane");
    address consumer = address(0xC001);
    address provider = address(0xB002);

    function setUp() public {
        vm.warp(90_000);
        coordinator = new WP11MockCoordinator();
        requester = new WP11PoolController();
        adapter = new SSEVRFV25Adapter(
            address(coordinator), address(this), KEY_HASH, 987, 3, 300_000, false);
        pool = new ScalableMonitorCommitteeV2(
            address(adapter), address(adapter), 1 ether, 0.1 ether, 1 days);
        adapter.bindPool(address(pool));
        pool.bindController(address(requester));
    }

    function params() internal view returns (ScalableMonitorCommitteeV2.Terms memory t) {
        t.consumer = consumer;
        t.provider = provider;
        t.size = 4;
        t.quorum = 3;
        t.reserves = 2;
        t.enrollmentPeriod = 10;
        t.randomnessPeriod = 20;
        t.selectionPeriod = 50;
        t.confirmationPeriod = 20;
        t.servicePeriod = 300;
    }

    function roster(uint256 count) internal returns (uint256 assignment) {
        assignment = requester.open(pool, params());
        for (uint256 i; i < count; ++i) {
            address who = address(uint160(0xA000 + i));
            vm.deal(who, 2 ether);
            vm.startPrank(who);
            pool.register{value: 1 ether}();
            pool.join{value: 0.1 ether}(assignment);
            vm.stopPrank();
        }
        vm.warp(pool.enrollmentDeadline(assignment) + 1);
        pool.sealEnrollment(assignment);
    }

    function words(uint256 value) internal pure returns (uint256[] memory w) {
        w = new uint256[](1);
        w[0] = value;
    }

    function requestFor(uint256 assignment) internal returns (uint256) {
        return adapter.requestRandomness(assignment);
    }

    function callback(uint256 requestId, uint256 value) internal {
        coordinator.deliver(requestId, words(value));
    }

    function testBindAndCoordinatorParameters() public {
        assertEq(address(adapter.pool()), address(pool));
        assertEq(pool.randomnessSource(), address(adapter));
        assertEq(address(pool.verifier()), address(adapter));
        uint256 assignment = roster(6);
        uint256 requestId = requestFor(assignment);
        assertEq(requestId, 71);
        assertEq(coordinator.lastKeyHash(), KEY_HASH);
        assertEq(coordinator.lastSubId(), 987);
        assertEq(coordinator.lastConfirmations(), 3);
        assertEq(coordinator.lastGasLimit(), 300_000);
        assertEq(coordinator.lastNumWords(), 1);
        assertEq(
            keccak256(coordinator.lastExtraArgs()),
            keccak256(abi.encodeWithSelector(adapter.EXTRA_ARGS_V1_TAG(), false))
        );
        assertEq(coordinator.consumerForRequest(requestId), address(adapter));
        assertEq(adapter.requestForAssignment(assignment), requestId);
    }

    function testCannotRebindPoolOrBindMisconfiguredPool() public {
        vm.expectRevert(SSEVRFV25Adapter.Unauthorized.selector);
        adapter.bindPool(address(pool));
        SSEVRFV25Adapter separate = new SSEVRFV25Adapter(
            address(coordinator), address(this), KEY_HASH, 999, 3, 300_000, false);
        vm.expectRevert(SSEVRFV25Adapter.InvalidInput.selector);
        separate.bindPool(address(pool));
    }

    function testOnlyTrustedRequesterCanSpendSubscription() public {
        uint256 assignment = roster(6);
        vm.expectRevert(SSEVRFV25Adapter.Unauthorized.selector);
        vm.prank(address(0xDEAD));
        adapter.requestRandomness(assignment);
        assertEq(adapter.requestForAssignment(assignment), 0);
    }

    function testRosterMustBeSealedBeforeRequest() public {
        uint256 assignment = requester.open(pool, params());
        vm.expectRevert(SSEVRFV25Adapter.InvalidState.selector);
        adapter.requestRandomness(assignment);
    }

    function testCannotAskTwiceOrGrindAfterReveal() public {
        uint256 assignment = roster(5);
        uint256 id = requestFor(assignment);
        vm.expectRevert(SSEVRFV25Adapter.InvalidState.selector);
        requestFor(assignment);
        callback(id, 17);
        vm.expectRevert(SSEVRFV25Adapter.InvalidState.selector);
        requestFor(assignment);
    }

    function testCoordinatorOnlyCallbackAndNoUnknownRequest() public {
        uint256 assignment = roster(6);
        uint256 id = requestFor(assignment);
        uint256[] memory value = words(42);
        vm.expectRevert(SSEVRFV25Adapter.Unauthorized.selector);
        adapter.rawFulfillRandomWords(id, value);
        vm.expectRevert(SSEVRFV25Adapter.UnknownRequest.selector);
        coordinator.spoofUnknown(address(adapter), id + 999, value);
    }

    function testCallbackMustHaveOneWordAndCannotBeReplayed() public {
        uint256 assignment = roster(6);
        uint256 id = requestFor(assignment);
        uint256[] memory missing = new uint256[](0);
        vm.expectRevert(SSEVRFV25Adapter.InvalidCoordinatorFulfillment.selector);
        coordinator.deliver(id, missing);
        callback(id, 44);
        vm.expectRevert(SSEVRFV25Adapter.InvalidCoordinatorFulfillment.selector);
        callback(id, 44);
    }

    function testValidCoordinatorWordActivatesSeededSelectionPermissionlessly() public {
        uint256 assignment = roster(6);
        bytes32 committed = pool.assignmentCommitment(assignment);
        uint256 id = requestFor(assignment);
        callback(id, 42);
        vm.prank(address(0xDEAD));
        adapter.finalizeRandomness(assignment);
        assertEq(uint8(pool.status(assignment)), uint8(ScalableMonitorCommitteeV2.Status.Selecting));
        assertEq(adapter.requestForAssignment(assignment), id);
        (uint256 aid, bytes32 capturedCommitment, bytes32 seeded, uint256 rawWord,
         bool fulfilled, bool delivered) = adapter.requests(id);
        assertEq(aid, assignment);
        assertEq(capturedCommitment, committed);
        assertEq(rawWord, 42);
        assertTrue(fulfilled && delivered);
        assertEq(seeded, keccak256(abi.encode(42, committed, assignment, block.chainid, address(adapter))));
        pool.processSelection(assignment, 16);
        pool.finalizeSelection(assignment);
        assertEq(pool.selectedCount(assignment), 4);
    }

    function testVerifyOnlyRespondsToPoolNotArbitraryCaller() public {
        uint256 assignment = roster(5);
        uint256 id = requestFor(assignment);
        callback(id, 43);
        adapter.finalizeRandomness(assignment);
        (, bytes32 commitment, bytes32 seed,,,) = adapter.requests(id);
        assertFalse(adapter.verify(commitment, seed, abi.encode(id)));
        assertFalse(adapter.verify(commitment, seed, hex"00"));
    }

    function testCannotFinalizeWithoutCoordinatorWord() public {
        uint256 assignment = roster(5);
        requestFor(assignment);
        vm.expectRevert(SSEVRFV25Adapter.InvalidState.selector);
        adapter.finalizeRandomness(assignment);
    }

    function testCannotFinalizeWrongAssignment() public {
        uint256 assignment = roster(5);
        uint256 id = requestFor(assignment);
        callback(id, 45);
        vm.expectRevert(SSEVRFV25Adapter.InvalidState.selector);
        adapter.finalizeRandomness(assignment + 1);
        adapter.finalizeRandomness(assignment);
    }

    function testCannotFinalizeTwiceOrResupplyDirectSeed() public {
        uint256 assignment = roster(5);
        uint256 id = requestFor(assignment);
        callback(id, 48);
        adapter.finalizeRandomness(assignment);
        vm.expectRevert(SSEVRFV25Adapter.InvalidState.selector);
        adapter.finalizeRandomness(assignment);
        vm.expectRevert(ScalableMonitorCommitteeV2.Unauthorized.selector);
        pool.supplyRandomness(assignment, bytes32(uint256(47)), abi.encode(id));
    }

    function testLateCoordinatorCallbackDoesNotForceExpiredPool() public {
        uint256 assignment = roster(5);
        uint256 id = requestFor(assignment);
        vm.warp(pool.seedDeadline(assignment) + 1);
        callback(id, 55);
        vm.expectRevert(SSEVRFV25Adapter.InvalidState.selector);
        adapter.finalizeRandomness(assignment);
        vm.prank(address(0xDEAD));
        pool.expire(assignment);
        assertEq(uint8(pool.status(assignment)), uint8(ScalableMonitorCommitteeV2.Status.Aborted));
        vm.expectRevert(SSEVRFV25Adapter.InvalidState.selector);
        adapter.finalizeRandomness(assignment);
    }

    function testNoRequestAfterDeadline() public {
        uint256 assignment = roster(5);
        vm.warp(pool.seedDeadline(assignment) + 1);
        vm.expectRevert(SSEVRFV25Adapter.InvalidState.selector);
        requestFor(assignment);
    }

    function testNoSecondRequestEvenIfCoordinatorWouldReuseId() public {
        uint256 assignment = roster(6);
        uint256 id = requestFor(assignment);
        // Create a second assignment using existing registered pool participants.
        uint256 other = requester.open(pool, params());
        for (uint256 i; i < 6; ++i) {
            address who = address(uint160(0xA000 + i));
            vm.prank(who);
            pool.join{value:0.1 ether}(other);
        }
        vm.warp(pool.enrollmentDeadline(other) + 1);
        pool.sealEnrollment(other);
        coordinator.setNextId(id); // malicious coordinator repeats a request ID.
        vm.expectRevert(SSEVRFV25Adapter.InvalidCoordinatorFulfillment.selector);
        requestFor(other);
        assertEq(adapter.requestForAssignment(other), 0);
    }

    function testSameCoordinatorWordDistinctAssignmentSeed() public {
        uint256 first = roster(6);
        uint256 firstId = requestFor(first);
        callback(firstId, 99);
        adapter.finalizeRandomness(first);
        uint256 second = requester.open(pool, params());
        for (uint256 i; i < 6; ++i) {
            address who = address(uint160(0xA000 + i));
            vm.prank(who);
            pool.join{value:0.1 ether}(second);
        }
        vm.warp(pool.enrollmentDeadline(second) + 1);
        pool.sealEnrollment(second);
        uint256 secondId = requestFor(second);
        callback(secondId, 99);
        adapter.finalizeRandomness(second);
        (, ,bytes32 seed1,,,) = adapter.requests(firstId);
        (, ,bytes32 seed2,,,) = adapter.requests(secondId);
        assertTrue(seed1 != seed2);
    }

    function testRequestIsCommittedBeforeExternalCoordinatorCall() public {
        WP11ReentrantCoordinator hostile = new WP11ReentrantCoordinator();
        SSEVRFV25Adapter localAdapter = new SSEVRFV25Adapter(
            address(hostile), address(hostile), KEY_HASH, 987, 3, 300_000, false);
        ScalableMonitorCommitteeV2 localPool = new ScalableMonitorCommitteeV2(
            address(localAdapter), address(localAdapter), 1 ether, 0.1 ether, 1 days);
        localAdapter.bindPool(address(localPool));
        localPool.bindController(address(requester));
        uint256 assignment = requester.open(localPool, params());
        for (uint256 i; i < 5; ++i) {
            // Distinct from configured provider address(0xB002).
            address who = address(uint160(0xE000 + i));
            vm.deal(who, 2 ether);
            vm.startPrank(who);
            localPool.register{value: 1 ether}();
            localPool.join{value: 0.1 ether}(assignment);
            vm.stopPrank();
        }
        vm.warp(localPool.enrollmentDeadline(assignment) + 1);
        localPool.sealEnrollment(assignment);
        hostile.configure(localAdapter, assignment);
        uint256 id = hostile.start();
        assertEq(id, 801);
        assertEq(hostile.count(), 1);
        assertFalse(hostile.secondRequestSucceeded());
        assertTrue(localAdapter.requestStarted(assignment));
        assertEq(localAdapter.requestForAssignment(assignment), 801);
    }

    function testConstructorRejectsInvalidCoordinatorOrGas() public {
        vm.expectRevert(SSEVRFV25Adapter.InvalidInput.selector);
        new SSEVRFV25Adapter(address(0xDEAD), address(this), KEY_HASH, 7, 3, 300_000, false);
        vm.expectRevert(SSEVRFV25Adapter.InvalidInput.selector);
        new SSEVRFV25Adapter(address(coordinator), address(this), KEY_HASH, 7, 0, 300_000, false);
        vm.expectRevert(SSEVRFV25Adapter.InvalidInput.selector);
        new SSEVRFV25Adapter(address(coordinator), address(this), KEY_HASH, 7, 3, 100, false);
    }
}
