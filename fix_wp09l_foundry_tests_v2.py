"""Align legacy WP09J/K Foundry test fixtures with the WP09L fee policy.

Run from the repo root: python fix_wp09l_foundry_tests_v2.py
No network, GitHub Actions, or production contract modifications.
This patch is intentionally strict: if an expected source fragment differs,
no files are written.
"""
from pathlib import Path

ADAPTER_TEST = Path('foundry/test/VRFAdapterIntegration.t.sol')
FEE_TEST = Path('foundry/test/VRFFeePolicy.t.sol')


def replace_exact(source: str, old: str, new: str, count: int = 1) -> str:
    occurrences = source.count(old)
    if occurrences != count:
        raise ValueError(
            f'Expected {count} occurrence(s), found {occurrences}: {old[:100]!r}'
        )
    return source.replace(old, new)


def main() -> None:
    for p in (ADAPTER_TEST, FEE_TEST):
        if not p.is_file():
            raise SystemExit(f'Cannot find {p}. Run from the repository root.')

    whole_adapter = ADAPTER_TEST.read_text(encoding='utf-8')
    fee = FEE_TEST.read_text(encoding='utf-8')

    if 'adapter.apply(' in whole_adapter or 'adapter.apply(' in fee:
        raise SystemExit(
            'First apply the reserved-keyword fix: rename adapter.apply( to '
            'adapter.applyRandomness( in tests and the function declaration.'
        )

    marker = 'contract VRFAdapterGlobalMerkleTest is Test {'
    if whole_adapter.count(marker) != 1:
        raise ValueError('Unexpected number of global Merkle test contracts')
    primary, global_tests = whole_adapter.split(marker, 1)

    primary = replace_exact(
        primary,
        'contract VRFAdapterIntegrationTest is Test {',
        'contract VRFAdapterIntegrationTest is Test {\n'
        '    uint256 internal constant VRF_FEE = 0.001 ether;',
    )
    primary = replace_exact(
        primary,
        '        adapter.bindPoolAndSettlement(address(pool), address(settlement));\n'
        '        settlement.bindRandomnessAdapter(address(adapter));',
        '        adapter.bindPoolAndSettlement(address(pool), address(settlement));\n'
        '        settlement.configureVrfFeePolicy(VRF_FEE, 50);\n'
        '        settlement.bindRandomnessAdapter(address(adapter));',
    )
    primary = replace_exact(
        primary,
        '        vm.deal(provider, 10 ether);',
        '        vm.deal(provider, 10 ether);\n'
        '        vm.deal(outsider, 1 ether);',
    )

    old_helper = '''    function _request(uint256 leaseId) internal returns (uint256 vrfId) {
        // Test contract is deployer/bootstrapper and has the temporary
        // authorization needed to spend the subscription.
        vrfId = settlement.requestLeaseRandomness(leaseId);
    }
'''
    new_helper = '''    function _fund(uint256 leaseId) internal {
        // A reverted coordinator request preserves the prepaid fee.
        if (!settlement.vrfFeeFunded(leaseId)) {
            vm.prank(consumer);
            settlement.fundVrfRequestFee{value: VRF_FEE}(leaseId);
        }
    }

    function _request(uint256 leaseId) internal returns (uint256 vrfId) {
        _fund(leaseId);
        vrfId = settlement.requestLeaseRandomness(leaseId);
    }
'''
    primary = replace_exact(primary, old_helper, new_helper)

    # The WP09L fee gate, not the adapter, rejects repeat paid purchases.
    primary = replace_exact(
        primary,
        'vm.expectRevert(SSEVRFV25Adapter.BadState.selector);\n'
        '        settlement.requestLeaseRandomness(leaseId);',
        'vm.expectRevert(SSESettlement.InvalidState.selector);\n'
        '        settlement.requestLeaseRandomness(leaseId);',
        count=3,
    )

    old_test_header = '''    /// @notice No third party can spend subscription funds. Even the sponsor
    /// must wait until the provider explicitly accepts this lease.
    function testSubscriptionSpendRequiresSponsorAndProviderAcceptance() public {
'''
    old_test_end = '''    /// @notice Closing a lease while VRF is pending MUST NOT lock otherwise
'''
    if primary.count(old_test_header) != 1 or primary.count(old_test_end) != 1:
        raise ValueError('Cannot locate outdated subscription-spending test')
    start, after_header = primary.split(old_test_header, 1)
    _old_test_body, end = after_header.split(old_test_end, 1)
    replacement = '''    /// @notice WP09L: only the accepted consumer can prepay; after prepayment,
    /// anyone can request the one permitted coordinator purchase.
    function testSubscriptionSpendRequiresSponsorAndProviderAcceptance() public {
        uint256 leaseId = _createOfferedLease();
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.requestLeaseRandomness(leaseId); // no prepaid fee
        vm.prank(provider);
        settlement.acceptLease(leaseId);
        vm.prank(outsider);
        vm.expectRevert(SSESettlement.Unauthorized.selector);
        settlement.fundVrfRequestFee{value: VRF_FEE}(leaseId);
        vm.expectRevert(SSESettlement.InvalidState.selector);
        settlement.requestLeaseRandomness(leaseId); // still no prepaid fee
        vm.prank(consumer);
        settlement.fundVrfRequestFee{value: VRF_FEE}(leaseId);
        vm.prank(outsider);
        uint256 vrfId = settlement.requestLeaseRandomness(leaseId);
        assertEq(vrfId, 1);
        assertEq(coordinator.nextRequestId(), 2);
        assertEq(adapter.leaseForAssignment(1), leaseId);
        assertEq(settlement.vrfRequestsUsed(), 1);
    }

'''
    primary = start + replacement + old_test_end + end

    # These adjacent assertions are mutually contradictory. The latter
    # (Expired) is the actual WP09K cancellation semantics.
    primary = replace_exact(
        primary,
        '''        assertEq(uint8(pool.assignmentStatus(1)),
                 uint8(OpenMonitorCommittee.RequestStatus.AwaitingRandomness));
        assertEq(settlement.withdrawable(consumer), 25);
        // Closing an unfinalized lease atomically CANCELS pool selection.
''',
        '''        assertEq(settlement.withdrawable(consumer), 25);
        // Closing an unfinalized lease atomically CANCELS pool selection.
''',
    )

    # Existing fee survives a coordinator revert; don't try purchasing without
    # prepayment, and don't pay it again on successful retry.
    primary = replace_exact(
        primary,
        '''        uint256 leaseId = _createLease();
        coordinator.configureFailures(true, address(0), 0);
''',
        '''        uint256 leaseId = _createLease();
        _fund(leaseId);
        coordinator.configureFailures(true, address(0), 0);
''',
    )

    global_tests = replace_exact(
        global_tests,
        '        settlement.bindRandomnessAdapter(address(adapter));',
        '        settlement.configureVrfFeePolicy(0.001 ether, 10);\n'
        '        settlement.bindRandomnessAdapter(address(adapter));',
    )
    global_tests = replace_exact(
        global_tests,
        '        uint256 vrfId = settlement.requestLeaseRandomness(leaseId);',
        '        vm.prank(address(0xA100));\n'
        '        settlement.fundVrfRequestFee{value: 0.001 ether}(leaseId);\n'
        '        uint256 vrfId = settlement.requestLeaseRandomness(leaseId);',
        count=2,
    )

    # vm.deal is necessary to test contract authorization rather than EVM
    # value-transfer solvency. The unauthorized caller must have enough ETH.
    fee_head, sep, fee_tail = fee.partition('contract VRFFeeGlobalMerkleTest is Test {')
    if not sep:
        raise ValueError('Missing fee-policy global-Merkle test contract')
    fee_head = replace_exact(
        fee_head,
        '        vm.deal(provider, 10 ether);',
        '        vm.deal(provider, 10 ether);\n'
        '        vm.deal(outsider, 1 ether);',
    )

    # Do not modify either file until EVERY anchor has been checked.
    updated_adapter = primary + marker + global_tests
    updated_fee = fee_head + sep + fee_tail
    ADAPTER_TEST.write_text(updated_adapter, encoding='utf-8')
    FEE_TEST.write_text(updated_fee, encoding='utf-8')
    print('Updated', ADAPTER_TEST)
    print('Updated', FEE_TEST)
    print('Changed TESTS ONLY; production Solidity contracts untouched.')
    print('Next: forge build && forge test -vv')


if __name__ == '__main__':
    main()
