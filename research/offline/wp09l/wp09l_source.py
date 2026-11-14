"""WP09L single-use ETH service-fee policy on TOP of WP09K patched SSESettlement.

This file only performs exact-anchor source transformations. The coordinator's
subscription balance is NOT denominated in ETH by this policy; sponsor assumes
exchange-rate, fee-spike, and insufficient-subscription risk. No network calls.
"""
from __future__ import annotations


def one(source: str, old: str, new: str, tag: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"{tag}: expected one exact anchor, found {count}: {old[:90]!r}")
    return source.replace(old, new, 1)


STATE = '''    // WP09L: one-price native ETH reimbursement, NOT exact coordinator billing.
    // The bootstrapper pays coordinator subscription expenses externally.
    uint256 public vrfFeeWei;
    uint256 public vrfLifetimeRequestCap;
    uint256 public vrfRequestsUsed;
    bool public vrfFeePolicyConfigured;
    bool private vrfPurchaseEntered;
    mapping(uint256 => bool) public vrfFeeFunded;
    mapping(uint256 => bool) public vrfFeeSpent;
'''

EVENTS = '''    event VrfFeePolicyLocked(uint256 feeWei, uint256 maxLifetimeRequests);
    event VrfFeeFunded(uint256 indexed leaseId, address indexed consumer, uint256 amount);
    event VrfFeeEarned(uint256 indexed leaseId, address indexed sponsor, uint256 amount);
    event VrfFeeRefunded(uint256 indexed leaseId, address indexed consumer, uint256 amount);
'''

POLICY = '''    /// @notice One-time, immutable fixed native-ETH service fee and bounded
    /// lifetime number of subscription-backed coordinator requests.
    /// @dev The fee reimburses the bootstrapper; it is NOT a trustless measure
    /// of LINK/native billing. No VRF requests can be started without funding.
    function configureVrfFeePolicy(uint256 feeWei, uint256 maxLifetimeRequests) external {
        if (msg.sender != bootstrapper || vrfFeePolicyConfigured ||
            address(randomnessAdapter) != address(0) || nextLeaseId != 1 ||
            feeWei == 0 || maxLifetimeRequests == 0) revert InvalidArgument();
        vrfFeePolicyConfigured = true;
        vrfFeeWei = feeWei;
        vrfLifetimeRequestCap = maxLifetimeRequests;
        emit VrfFeePolicyLocked(feeWei, maxLifetimeRequests);
    }

    /// @notice Only the accepted lease's consumer can prepay the VRF request.
    /// @dev Separate from service escrow and report/release incentives.
    /// Prepayment is refundable on lease close UNTIL purchase succeeds.
    function fundVrfRequestFee(uint256 leaseId) external payable onlyConsumer(leaseId) {
        Lease storage lease = leases[leaseId];
        if (!vrfFeePolicyConfigured || address(randomnessAdapter) == address(0) ||
            !isLeaseRandomnessOpen(leaseId, lease.assignmentId) ||
            vrfRequestsUsed >= vrfLifetimeRequestCap ||
            vrfFeeFunded[leaseId] || vrfFeeSpent[leaseId] ||
            msg.value != vrfFeeWei) revert InvalidState();
        vrfFeeFunded[leaseId] = true;
        emit VrfFeeFunded(leaseId, msg.sender, msg.value);
    }

'''

REQUEST_OLD = '''    function requestLeaseRandomness(uint256 leaseId) external returns (uint256 vrfId) {
        if (msg.sender != bootstrapper) revert Unauthorized();
        Lease storage lease = leases[leaseId];
        if (address(randomnessAdapter) == address(0) ||
            !isLeaseRandomnessOpen(leaseId, lease.assignmentId)) revert InvalidState();
        vrfId = randomnessAdapter.requestSeed(leaseId, lease.assignmentId);
        emit LeaseRandomnessRequested(leaseId, lease.assignmentId, vrfId);
    }'''

REQUEST_NEW = '''    /// @notice Permissionless dispatch only AFTER consumer funds this lease.
    /// @dev Reimburse sponsor once on purchase; NEVER on callback success.
    /// Spending a request's fixed fee does not depend on randomness delivery.
    /// Coordinator revert atomically restores fee, quota and request state.
    function requestLeaseRandomness(uint256 leaseId) external returns (uint256 vrfId) {
        Lease storage lease = leases[leaseId];
        if (!vrfFeePolicyConfigured || vrfPurchaseEntered ||
            !vrfFeeFunded[leaseId] || vrfFeeSpent[leaseId] ||
            vrfRequestsUsed >= vrfLifetimeRequestCap ||
            address(randomnessAdapter) == address(0) ||
            !isLeaseRandomnessOpen(leaseId, lease.assignmentId)) revert InvalidState();
        // Effects BEFORE calling the external coordinator via the adapter.
        // Protects unrelated, separately funded leases from reentrant buys.
        vrfPurchaseEntered = true;
        vrfFeeFunded[leaseId] = false;
        vrfFeeSpent[leaseId] = true;
        ++vrfRequestsUsed;
        withdrawable[bootstrapper] += vrfFeeWei;
        vrfId = randomnessAdapter.requestSeed(leaseId, lease.assignmentId);
        vrfPurchaseEntered = false;
        emit VrfFeeEarned(leaseId, bootstrapper, vrfFeeWei);
        emit LeaseRandomnessRequested(leaseId, lease.assignmentId, vrfId);
    }'''

CLOSE_OLD = '''        if (lease.state == LeaseState.Closed) revert InvalidState();
        if (address(randomnessAdapter) != address(0) &&
            lease.monitors[0] == address(0)) {'''

CLOSE_NEW = '''        if (lease.state == LeaseState.Closed) revert InvalidState();
        // The consumer gets the unspent VRF fee back on lease closure.
        // Once the coordinator purchase succeeded the sponsor already earned
        // the fee, EVEN IF the VRF request later times out or is withheld.
        if (vrfFeeFunded[leaseId] && !vrfFeeSpent[leaseId]) {
            vrfFeeFunded[leaseId] = false;
            withdrawable[lease.consumer] += vrfFeeWei;
            emit VrfFeeRefunded(leaseId, lease.consumer, vrfFeeWei);
        }
        if (address(randomnessAdapter) != address(0) &&
            lease.monitors[0] == address(0)) {'''


def patch_settlement(wp09k_settlement: str) -> str:
    """Fail closed unless input is exactly the expected WP09K source shape."""
    s = wp09k_settlement
    if 'function configureVrfFeePolicy' in s or 'function fundVrfRequestFee' in s:
        raise ValueError('already patched; refusing duplicate WP09L fee policy')
    s = one(s, '    ISSEVRFAdapter public randomnessAdapter;',
            '    ISSEVRFAdapter public randomnessAdapter;\n' + STATE,
            'state')
    s = one(s, '    event RandomnessAdapterBound(address indexed adapter);',
            '    event RandomnessAdapterBound(address indexed adapter);\n' + EVENTS,
            'events')
    s = one(s, '    function bindRandomnessAdapter(address adapter) external {',
            POLICY + '    function bindRandomnessAdapter(address adapter) external {',
            'policy functions')
    s = one(s, '''        if (msg.sender != bootstrapper || address(randomnessAdapter) != address(0) ||
            nextLeaseId != 1 || adapter == address(0) || adapter.code.length == 0)''',
            '''        if (msg.sender != bootstrapper || !vrfFeePolicyConfigured ||
            address(randomnessAdapter) != address(0) || nextLeaseId != 1 ||
            adapter == address(0) || adapter.code.length == 0)''',
            'fee policy required before VRF adapter binding')
    s = one(s, REQUEST_OLD, REQUEST_NEW, 'fee-funded purchase')
    s = one(s, CLOSE_OLD, CLOSE_NEW, 'unspent fee refund on close')
    return s
