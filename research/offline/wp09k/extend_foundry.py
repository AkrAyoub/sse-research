from pathlib import Path
p=Path(__file__).parent/'foundry_test/VRFAdapterIntegration.t.sol'
s=p.read_text()
anchor='''    function testNonexistentOrClosedLeaseCannotStartPaidRequest() public {'''
added='''    /// @notice No third party can spend subscription funds. Even the sponsor
    /// must wait until the provider explicitly accepts this lease.
    function testSubscriptionSpendRequiresSponsorAndProviderAcceptance() public {
        uint256 leaseId = _createOfferedLease();
        vm.prank(outsider);
        vm.expectRevert(SSESettlement.Unauthorized.selector);
        settlement.requestLeaseRandomness(leaseId);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.requestLeaseRandomness(leaseId);
        vm.prank(provider);
        settlement.acceptLease(leaseId);
        vm.prank(consumer);
        vm.expectRevert(SSESettlement.Unauthorized.selector);
        settlement.requestLeaseRandomness(leaseId);
        assertEq(coordinator.nextRequestId(), 1);
        uint256 vrfId = _request(leaseId);
        assertEq(vrfId, 1);
        assertEq(coordinator.nextRequestId(), 2);
        assertEq(adapter.leaseForAssignment(1), leaseId);
    }

    /// @notice Closing a lease while VRF is pending MUST NOT lock otherwise
    /// idle monitor bonds, even if the coordinator already returned a seed.
    function testCloseDuringPendingVRFBlocksLateSeedApplicationAndRefunds() public {
        uint256 leaseId = _createLease();
        uint256 vrfId = _request(leaseId);
        assertTrue(settlement.isLeaseRandomnessOpen(leaseId, 1));
        _deliver(vrfId, 98765);
        vm.prank(consumer);
        settlement.closeLease(leaseId);
        assertFalse(settlement.isLeaseRandomnessOpen(leaseId, 1));
        vm.expectRevert(SSEVRFV25Adapter.BadState.selector);
        adapter.apply(1);
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.AwaitingRandomness));
        assertEq(settlement.withdrawable(consumer), 25);
        for (uint256 i; i < 6; ++i) {
            (,,uint32 pending,uint32 locked,,) = pool.candidates(monitors[i]);
            assertEq(locked, 0);
            // Existing non-global snapshots remain locked until expiry.
            assertEq(pending, 1);
        }
        vm.warp(block.timestamp + pool.randomnessTimeout() + 1);
        adapter.expire(1);
        pool.expire(1);
        for (uint256 i; i < 6; ++i) {
            (,,uint32 pending,uint32 locked,,) = pool.candidates(monitors[i]);
            assertEq(pending, 0);
            assertEq(locked, 0);
        }
    }

    /// @notice Coordinator failed purchase must not consume the one-request
    /// allowance: EVM reverts all checks/effects atomically.
    function testCoordinatorFailureRollsBackRequestAndAllowsSingleRetry() public {
        uint256 leaseId = _createLease();
        coordinator.configureFailures(true, address(0), 0);
        vm.expectRevert(MockVRFV25Coordinator.Unauthorized.selector);
        settlement.requestLeaseRandomness(leaseId);
        assertFalse(adapter.assignmentEverRequested(1));
        assertEq(adapter.leaseForAssignment(1), 0);
        assertEq(coordinator.nextRequestId(), 1);
        coordinator.configureFailures(false, address(0), 0);
        assertEq(_request(leaseId), 1);
        assertTrue(adapter.assignmentEverRequested(1));
        vm.expectRevert(SSEVRFV25Adapter.BadState.selector);
        settlement.requestLeaseRandomness(leaseId);
    }

    /// @notice Mock coordinator attempts to reenter subscription-spend path.
    /// A real public coordinator should not do this; guard must reject it.
    function testCoordinatorReentryCannotSpendSecondVRFRequest() public {
        uint256 leaseId = _createLease();
        coordinator.configureFailures(false, address(settlement), leaseId);
        uint256 vrfId = _request(leaseId);
        assertEq(vrfId, 1);
        assertTrue(coordinator.lastReentryAttempted());
        assertFalse(coordinator.lastReentrySucceeded());
        assertTrue(adapter.assignmentEverRequested(1));
        assertEq(coordinator.nextRequestId(), 2);
    }

'''
if s.count(anchor)!=1: raise ValueError('Could not locate test insertion point')
s=s.replace(anchor,added+anchor)
p.write_text(s)
print('total scenarios',s.count('function test'))
