#!/usr/bin/env python3
"""WP09K offline WP09E→VRF hardening generator. NEVER calls GitHub or CI.

Default: emits patched Solidity files to a separate output directory.
Uses exact anchored replacements; aborts on unknown repository versions.
"""
from __future__ import annotations
import argparse
import difflib
import json
from pathlib import Path

from harden_source import (harden_settlement_patch, harden_pool_patch,
                           harden_close_lease)


POOL_ANCHOR = "    function assignmentStatus(uint256 id) external view returns (RequestStatus) { return assignments[id].status; }"
POOL_REPLACEMENT = """    /// @notice Original request time anchors VRF timeout; immutable per ID.
    function assignmentRequestedAt(uint256 id) external view returns (uint64) {
        return assignments[id].requestedAt;
    }
    function assignmentStatus(uint256 id) external view returns (RequestStatus) { return assignments[id].status; }"""

SETTLEMENT_HEADER = "contract SSESettlement is EIP712 {"
SETTLEMENT_HEADER_NEW = """interface ISSEVRFAdapter {
    function pool() external view returns (address);
    function settlement() external view returns (address);
    function requestSeed(uint256 assignmentId) external returns (uint256);
}

contract SSESettlement is EIP712 {"""

SETTLEMENT_BIND_ANCHOR = "    function bindResourceBoard(address board) external {"
SETTLEMENT_BIND_NEW = """    /// @notice One-way, optional binding BEFORE the first lease. Legacy V1
    /// keeps adapter unset, preserving previous functionality and gas paths.
    function bindRandomnessAdapter(address adapter) external {
        if (msg.sender != bootstrapper || address(randomnessAdapter) != address(0) ||
            nextLeaseId != 1 || adapter == address(0) || adapter.code.length == 0)
            revert Unauthorized();
        ISSEVRFAdapter candidate = ISSEVRFAdapter(adapter);
        if (candidate.pool() != address(committeePool) ||
            candidate.settlement() != address(this) ||
            committeePool.randomnessSource() != adapter ||
            committeePool.delayedBlockEntropyEnabled() ||
            address(committeePool.rsaEntropyVerifier()) != address(0))
            revert InvalidArgument();
        randomnessAdapter = candidate;
        emit RandomnessAdapterBound(adapter);
    }

    function bindResourceBoard(address board) external {"""

SETTLEMENT_REQUEST_ANCHOR = "    function finalizeMonitorCommittee(uint256 leaseId) external {"
SETTLEMENT_REQUEST_NEW = """    /// @notice Permissionless request after lease creation; exactly ONE VRF
    /// request for the lease's frozen assignment, with no alternative seed.
    /// @dev The adapter checks the original pool timestamp/deadline and binds
    /// the returned coordinator request ID to that immutable snapshot.
    function requestLeaseRandomness(uint256 leaseId) external returns (uint256 vrfId) {
        Lease storage lease = leases[leaseId];
        if (address(randomnessAdapter) == address(0) ||
            lease.consumer == address(0) ||
            (lease.state != LeaseState.Offered && lease.state != LeaseState.Accepted) ||
            lease.monitors[0] != address(0) ||
            committeePool.assignmentStatus(lease.assignmentId) !=
                OpenMonitorCommittee.RequestStatus.AwaitingRandomness)
            revert InvalidState();
        vrfId = randomnessAdapter.requestSeed(lease.assignmentId);
        emit LeaseRandomnessRequested(leaseId, lease.assignmentId, vrfId);
    }

    function finalizeMonitorCommittee(uint256 leaseId) external {"""

SETTLEMENT_STATE_ANCHOR = "    address public resourceBoard;"
SETTLEMENT_STATE_REPLACEMENT = "    address public resourceBoard;\n    ISSEVRFAdapter public randomnessAdapter;"
SETTLEMENT_EVENT_ANCHOR = "    event ResourceBoardBound(address indexed board);"
SETTLEMENT_EVENT_REPLACEMENT = """    event ResourceBoardBound(address indexed board);
    event RandomnessAdapterBound(address indexed adapter);
    event LeaseRandomnessRequested(uint256 indexed leaseId,
                                  uint256 indexed assignmentId, uint256 vrfId);"""


def one(content: str, before: str, after: str, path: str) -> str:
    count = content.count(before)
    if count != 1:
        raise ValueError(f"Refusing patch on {path}: anchor occurs {count} times: {before[:100]!r}")
    if after == before:
        raise ValueError("no change")
    return content.replace(before, after, 1)


def patch_pool(content: str) -> str:
    if 'function assignmentRequestedAt(uint256 id)' in content:
        raise ValueError('Already patched pool; refusing duplicate getter')
    return harden_pool_patch(one(
        content, POOL_ANCHOR, POOL_REPLACEMENT, "OpenMonitorCommittee.sol"
    ))


def patch_settlement(content: str) -> str:
    if 'interface ISSEVRFAdapter' in content or 'function requestLeaseRandomness(uint256 leaseId)' in content:
        raise ValueError('Already patched settlement; refusing duplicate hooks')
    path = "SSESettlement.sol"
    for old, new in [
        (SETTLEMENT_HEADER, SETTLEMENT_HEADER_NEW),
        (SETTLEMENT_STATE_ANCHOR, SETTLEMENT_STATE_REPLACEMENT),
        (SETTLEMENT_EVENT_ANCHOR, SETTLEMENT_EVENT_REPLACEMENT),
        (SETTLEMENT_BIND_ANCHOR, SETTLEMENT_BIND_NEW),
        (SETTLEMENT_REQUEST_ANCHOR, SETTLEMENT_REQUEST_NEW),
    ]:
        content = one(content, old, new, path)
    return harden_close_lease(harden_settlement_patch(content))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True, help='Read-only SSE clone of WP09E branch')
    parser.add_argument('--out', type=Path, required=True, help='Separate directory for generated contracts and test files')
    args = parser.parse_args()
    repo = args.repo.resolve()
    out = args.out.resolve()
    if repo == out or repo in out.parents:
        raise SystemExit('Refusing output inside the source repository: choose a separate folder.')
    if out.exists() and any(out.iterdir()):
        raise SystemExit('Refusing to overwrite non-empty output directory')
    source = Path(__file__).resolve().parent
    files = {
        'contracts/OpenMonitorCommittee.sol': patch_pool,
        'contracts/SSESettlement.sol': patch_settlement,
    }
    patched = {}
    diffs = []
    for name, apply in files.items():
        original = (repo / name).read_text(encoding='utf8')
        modified = apply(original)
        patched[name] = modified
        diffs.append(''.join(difflib.unified_diff(
            original.splitlines(keepends=True), modified.splitlines(keepends=True),
            fromfile='a/' + name, tofile='b/' + name)))
    for name in ('contracts/SSEVRFV25Adapter.sol',
                 'contracts/MockVRFV25Coordinator.sol'):
        if (repo / name).exists():
            raise SystemExit(f'Refusing existing file in repo: {name}')
        patched[name] = (source / name).read_text(encoding='utf8')
    patched['foundry/test/VRFAdapterIntegration.t.sol'] = (
        source / 'foundry_test' / 'VRFAdapterIntegration.t.sol').read_text(encoding='utf8')
    for name, data in patched.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data, encoding='utf8')
    (out / 'wp09k_changes.patch').write_text('\n'.join(diffs), encoding='utf8')
    (out / 'manifest.json').write_text(json.dumps({
        'mode': 'offline-output-only',
        'scope': 'WP09E+WP09J+WP09K',
        'source': str(repo),
        'output': str(out),
        'patched_existing': list(files),
        'added': list(patched)[2:],
        'github_actions': 'never called',
        'evm_validation': 'not run by patcher',
    }, indent=2) + '\n', encoding='utf8')
    print(f'Validated {len(files)} source anchors and wrote {len(patched)} files to {out}.')
    print('Source tree untouched. Solidity compilation and EVM tests NOT run.')


if __name__ == '__main__':
    main()
