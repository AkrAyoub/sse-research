from pathlib import Path
p=Path(__file__).parent/'foundry_test/VRFAdapterIntegration.t.sol'
s=p.read_text()
before='''        for (uint256 i; i < 6; ++i) {
            (,,uint32 pending,uint32 locked,,) = pool.candidates(monitors[i]);
            assertEq(locked, 0);
            // Existing non-global snapshots remain locked until expiry.
            assertEq(pending, 1);
        }
        vm.warp(block.timestamp + pool.randomnessTimeout() + 1);
        adapter.expire(1);
        pool.expire(1);'''
after='''        // Closing an unfinalized lease atomically CANCELS pool selection.
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.Expired));
        for (uint256 i; i < 6; ++i) {
            (,,uint32 pending,uint32 locked,,) = pool.candidates(monitors[i]);
            assertEq(locked, 0);
            assertEq(pending, 0);
        }
        vm.warp(block.timestamp + pool.randomnessTimeout() + 1);
        adapter.expire(1);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.expire(1);'''
if s.count(before)!=1: raise ValueError('pending asserts anchor')
s=s.replace(before,after)
anchor='''    function testNonexistentOrClosedLeaseCannotStartPaidRequest() public {'''
added='''    function testCloseBeforeVRFRequestReleasesAllPendingSnapshotLocks() public {
        uint256 leaseId = _createOfferedLease();
        for (uint256 i; i < 6; ++i) {
            (,,uint32 pending,,,) = pool.candidates(monitors[i]);
            assertEq(pending, 1);
        }
        vm.prank(consumer);
        settlement.closeLease(leaseId);
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.Expired));
        assertEq(coordinator.nextRequestId(), 1); // no subscription charge
        for (uint256 i; i < 6; ++i) {
            (,,uint32 pending,uint32 active,,) = pool.candidates(monitors[i]);
            assertEq(pending, 0);
            assertEq(active, 0);
        }
    }

    function testCloseAfterSeedAppliedBeforeCommitteeCopyReleasesBondLocks() public {
        uint256 leaseId = _createLease();
        uint256 vrfId = _request(leaseId);
        _deliver(vrfId, 2353);
        adapter.apply(1);
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.Assigned));
        address[4] memory committee = pool.getCommittee(1);
        for (uint256 i; i < 4; ++i) {
            (,,,uint32 active,,) = pool.candidates(committee[i]);
            assertEq(active, 1);
        }
        vm.prank(consumer);
        settlement.closeLease(leaseId);
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.Released));
        assertEq(settlement.withdrawable(consumer), 25);
        for (uint256 i; i < 4; ++i) {
            (,,,uint32 active,,) = pool.candidates(committee[i]);
            assertEq(active, 0);
        }
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.finalizeMonitorCommittee(leaseId);
    }

    function testOnlySettlementCanCancelPendingOrSelectedAssignment() public {
        _createOfferedLease();
        vm.prank(outsider);
        vm.expectRevert(OpenMonitorCommittee.Unauthorized.selector);
        pool.cancelUnassigned(1);
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.AwaitingRandomness));
    }

'''
if s.count(anchor)!=1: raise ValueError('new closure tests insertion anchor')
s=s.replace(anchor,added+anchor)
anchor='''        assertEq(pool.standbyRemaining(1), 2);
    }
}'''
added='''        assertEq(pool.standbyRemaining(1), 2);
    }

    function testCloseAfterSeedStagedBeforeGlobalProofPreventsBondLock() public {
        address consumer = address(0xA100);
        address provider = address(0xB100);
        vm.prank(consumer);
        uint256 leaseId = settlement.createLease{value: 25}(
            provider, keccak256("endpoint"), keccak256("profile"),
            25, 5, 25, 1, 100, 100, 100
        );
        vm.prank(provider);
        settlement.acceptLease(leaseId);
        uint256 vrfId = settlement.requestLeaseRandomness(leaseId);
        uint256[] memory word = new uint256[](1);
        word[0] = 888;
        coordinator.deliver(vrfId, word);
        adapter.apply(1);
        assertTrue(pool.pendingGlobalSeedReady(1));
        uint256[] memory indexes = pool.globalDrawIndexes(1);
        address[] memory accounts = new address[](indexes.length);
        bytes32[][] memory proofs = new bytes32[][](indexes.length);
        for (uint256 i; i < indexes.length; ++i) {
            accounts[i] = historicalRoster[indexes[i]];
            proofs[i] = new bytes32[](20);
            uint256 cursor = CAPACITY + indexes[i];
            for (uint256 level; level < 20; ++level) {
                proofs[i][level] = historicalTree[cursor ^ 1];
                cursor >>= 1;
            }
        }
        vm.prank(consumer);
        settlement.closeLease(leaseId);
        assertFalse(pool.pendingGlobalSeedReady(1));
        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.Expired));
        assertEq(settlement.withdrawable(consumer), 25);
        vm.expectRevert(OpenMonitorCommittee.InvalidPhase.selector);
        pool.finalizeGlobalCommittee(1, accounts, proofs);
        for (uint256 i; i < historicalRoster.length; ++i) {
            (,,uint32 pending,uint32 locked,,) = pool.candidates(historicalRoster[i]);
            assertEq(pending, 0);
            assertEq(locked, 0);
        }
    }
}'''
if s.count(anchor)!=1: raise ValueError('global test insertion anchor')
s=s.replace(anchor,added)
p.write_text(s)
print('Foundry authored test functions',s.count('function test'))
