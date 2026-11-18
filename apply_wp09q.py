#!/usr/bin/env python3
"""WP09Q experimental local-only 40-index batch patch. No network or git mutations.

--check validates exact source anchors without editing. --apply backs up the three
original Solidity files to .local/wp09q/prepatch/ and applies the opt-in patch,
then installs the accompanying Foundry test. Never invokes Forge itself.
"""
from __future__ import annotations
import argparse
import difflib
from pathlib import Path
import shutil

POOL = Path('contracts/OpenMonitorCommittee.sol')
SETTLEMENT = Path('contracts/SSESettlement.sol')
SAMPLER = Path('contracts/GlobalRosterSampler.sol')
TEST = Path('foundry/test/WP09QBatchedGlobalRecovery.t.sol')

def once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise ValueError(f'{label}: expected one source anchor, found {n}: {old[:80]!r}')
    return text.replace(old, new, 1)

RECOVERY_API = '''    /// @notice Seed-derived, full historical index order for proof relayers.
    /// @dev No caller-controlled replacement, skipping, or seed reroll.
    function globalRecoveryDrawIndexes(uint256 id) external view returns (uint256[] memory) {
        if (!globalBatchedRecoveryEnabled || !pendingGlobalSeedReady[id] ||
            assignments[id].status != RequestStatus.AwaitingRandomness)
            revert InvalidPhase();
        uint256 n = globalSnapshotCount[id];
        uint256 count = n < GLOBAL_RECOVERY_DRAW_LIMIT ? n : GLOBAL_RECOVERY_DRAW_LIMIT;
        return GlobalRosterSampler.draw(pendingGlobalSeed[id], id, n, count);
    }

    /// @notice Verify the NEXT <=8 historical leaves from one committed draw.
    /// @dev Experimental opt-in. Relayers can withhold later batches; partial
    /// selections lock their bonds until successful completion or expiry.
    function advanceGlobalRecovery(
        uint256 id, address[] calldata accounts, bytes32[][] calldata siblingPaths
    ) external {
        if (!globalBatchedRecoveryEnabled || !pendingGlobalSeedReady[id])
            revert InvalidPhase();
        Assignment storage r = assignments[id];
        if (r.status != RequestStatus.AwaitingRandomness ||
            block.timestamp > uint256(r.requestedAt) + randomnessTimeout)
            revert InvalidPhase();
        uint256 n = globalSnapshotCount[id];
        uint256 total = n < GLOBAL_RECOVERY_DRAW_LIMIT ? n : GLOBAL_RECOVERY_DRAW_LIMIT;
        uint256 cursor = globalRecoveryCursor[id];
        uint256 length = accounts.length;
        if (length == 0 || length > GLOBAL_RECOVERY_BATCH_LIMIT ||
            siblingPaths.length != length || cursor + length > total)
            revert InvalidInput();
        uint256[] memory indexes = GlobalRosterSampler.draw(
            pendingGlobalSeed[id], id, n, total
        );
        for (uint256 j; j < length; ++j) {
            _acceptGlobalRecoveryProof(id, indexes[cursor + j], accounts[j],
                                       siblingPaths[j]);
        }
        cursor += length;
        globalRecoveryCursor[id] = cursor;
        emit GlobalRecoveryBatchAdvanced(id, cursor, total, globalRecoveryLocks[id]);
        if (cursor != total) return;
        if (globalRecoveryLocks[id] < COMMITTEE_SIZE) {
            // Fail closed without a new draw; atomically free every partial lock.
            _clearGlobalRecovery(id);
            delete pendingGlobalSeedReady[id];
            delete pendingGlobalSeed[id];
            r.status = RequestStatus.Expired;
            emit AssignmentExpired(id);
            return;
        }
        r.status = RequestStatus.Assigned;
        delete globalRecoveryLocks[id];
        delete pendingGlobalSeedReady[id];
        delete pendingGlobalSeed[id];
        emit GlobalRecoveryCompleted(id, cursor, standbyRosters[id].length);
        emit CommitteeSelected(id, r.committee);
    }

    /// @dev Separate helper bounds stack pressure in the eight-proof loop.
    function _acceptGlobalRecoveryProof(
        uint256 id, uint256 index, address account, bytes32[] calldata siblings
    ) internal {
        if (!GlobalRosterMerkle.verify(globalSnapshotRoot[id], index, account, siblings))
            revert InvalidGlobalProof();
        Assignment storage r = assignments[id];
        Candidate storage c = candidates[account];
        if (account == r.consumer || account == r.provider ||
            !c.active || c.bond < minimumBond) return;
        uint256 selected = globalRecoveryLocks[id];
        if (selected < COMMITTEE_SIZE) {
            r.committee[selected] = account;
            globalRecoveryLocks[id] = selected + 1;
            ++c.activeAssignments; // locks provisional seats against exit
        } else {
            standbyRosters[id].push(account);
        }
    }

    /// @dev Only for pending/expired requests; do not unlock assigned seats.
    function _clearGlobalRecovery(uint256 id) internal {
        Assignment storage r = assignments[id];
        uint256 locked = globalRecoveryLocks[id];
        for (uint256 i; i < locked; ++i) {
            --candidates[r.committee[i]].activeAssignments;
        }
        delete r.committee;
        delete standbyRosters[id];
        delete nextStandbyIndex[id];
        delete globalRecoveryLocks[id];
        delete globalRecoveryCursor[id];
    }

'''

def patch_pool(source: str) -> str:
    if 'function advanceGlobalRecovery(' in source:
        raise ValueError('WP09Q recovery already exists; refusing to patch twice')
    s = source
    s = once(s,'    uint256 public constant GLOBAL_SAMPLE_LIMIT = 10;',
             '    uint256 public constant GLOBAL_SAMPLE_LIMIT = 10;\n'
             '    uint256 public constant GLOBAL_RECOVERY_DRAW_LIMIT = 40;\n'
             '    uint256 public constant GLOBAL_RECOVERY_BATCH_LIMIT = 8;', 'pool constants')
    s = once(s,'    bool public globalMerkleElectionEnabled;\n    bool private entered;',
             '    bool public globalMerkleElectionEnabled;\n'
             '    bool public globalBatchedRecoveryEnabled;\n    bool private entered;', 'pool mode')
    s = once(s,'    mapping(uint256 => bool) public pendingGlobalSeedReady;',
             '    mapping(uint256 => bool) public pendingGlobalSeedReady;\n'
             '    mapping(uint256 => uint256) public globalRecoveryCursor;\n'
             '    mapping(uint256 => uint256) public globalRecoveryLocks;', 'pool mappings')
    s = once(s,'    event GlobalCommitteeProved(uint256 indexed requestId, bytes32 frozenRoot,',
             '    event GlobalRecoveryBatchAdvanced(uint256 indexed requestId, uint256 cursor,\n'
             '                                      uint256 total, uint256 locked);\n'
             '    event GlobalRecoveryCompleted(uint256 indexed requestId, uint256 processed,\n'
             '                                  uint256 standbyCount);\n'
             '    event GlobalCommitteeProved(uint256 indexed requestId, bytes32 frozenRoot,', 'pool events')
    s = once(s,'    function globalRosterRoot() external view returns (bytes32) {',
             '''    /// @notice One-way experimental opt-in BEFORE candidates or leases.
    function enableGlobalBatchedRecovery() external {
        if (msg.sender != bootstrapper || settlement != address(0) ||
            !globalMerkleElectionEnabled || globalBatchedRecoveryEnabled ||
            totalRegistrations != 0) revert Unauthorized();
        globalBatchedRecoveryEnabled = true;
    }

    function globalRosterRoot() external view returns (bytes32) {''','pool opt-in')
    s = once(s,
        '    function finalizeGlobalCommittee(\n'
        '        uint256 id, address[] calldata accounts, bytes32[][] calldata siblingPaths\n'
        '    ) external {\n',
        '    function finalizeGlobalCommittee(\n'
        '        uint256 id, address[] calldata accounts, bytes32[][] calldata siblingPaths\n'
        '    ) external {\n'
        '        if (globalBatchedRecoveryEnabled) revert InvalidPhase();\n', 'legacy finalization guard')
    s = once(s,'    function cancelUnassigned(uint256 id) external onlySettlement {\n'
                '        Assignment storage r = assignments[id];\n'
                '        RequestStatus previous = r.status;\n'
                '        if (previous == RequestStatus.AwaitingRandomness) {\n'
                '            if (!globalMerkleElectionEnabled) _unlockSnapshot(id);',
                '    function cancelUnassigned(uint256 id) external onlySettlement {\n'
                '        Assignment storage r = assignments[id];\n'
                '        RequestStatus previous = r.status;\n'
                '        if (previous == RequestStatus.AwaitingRandomness) {\n'
                '            if (globalBatchedRecoveryEnabled) _clearGlobalRecovery(id);\n'
                '            if (!globalMerkleElectionEnabled) _unlockSnapshot(id);',
                'cancel pending partial locks')
    s = once(s, '    function expire(uint256 id) external {\n'
                '        Assignment storage r = assignments[id];\n'
                '        if (r.status != RequestStatus.AwaitingRandomness ||\n'
                '            block.timestamp <= uint256(r.requestedAt) + randomnessTimeout) revert InvalidPhase();\n'
                '        if (!globalMerkleElectionEnabled) _unlockSnapshot(id);',
                '    function expire(uint256 id) external {\n'
                '        Assignment storage r = assignments[id];\n'
                '        if (r.status != RequestStatus.AwaitingRandomness ||\n'
                '            block.timestamp <= uint256(r.requestedAt) + randomnessTimeout) revert InvalidPhase();\n'
                '        if (globalBatchedRecoveryEnabled) _clearGlobalRecovery(id);\n'
                '        if (!globalMerkleElectionEnabled) _unlockSnapshot(id);',
                'timeout pending partial locks')
    s = once(s, '    function expire(uint256 id) external {', RECOVERY_API + '    function expire(uint256 id) external {', 'recovery implementation')
    return s

def patch_settlement(source: str) -> str:
    # The preexisting conditional only cancels pending snapshots when the
    # optional VRF adapter is bound. A batched legacy-source pool ALSO needs
    # atomic close cleanup; existing pool.cancelUnassigned handles both modes.
    return once(source,
        '        if (address(randomnessAdapter) != address(0) &&\n'
        '            lease.monitors[0] == address(0)) {',
        '        if (lease.monitors[0] == address(0)) {',
        'close unfinalized assignment in all entropy modes')

def patch_sampler(source: str) -> str:
    s = source
    s = once(s, 'k <= 10', 'k <= 40', 'sampler docs')
    s = once(s, 'count > 10 || count == 0', 'count > 40 || count == 0', 'sampler bound')
    return s

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = args.repo.resolve()
    orig_pool = (root/POOL).read_text(encoding='utf-8')
    orig_sampler = (root/SAMPLER).read_text(encoding='utf-8')
    orig_settlement = (root/SETTLEMENT).read_text(encoding='utf-8')
    patched_pool = patch_pool(orig_pool)
    patched_sampler = patch_sampler(orig_sampler)
    patched_settlement = patch_settlement(orig_settlement)
    src_test = Path(__file__).resolve().parent/'foundry/test/WP09QBatchedGlobalRecovery.t.sol'
    if not src_test.is_file():
        raise FileNotFoundError(f'missing packaged test {src_test}')
    if (root/TEST).exists():
        raise FileExistsError(f'will not overwrite existing Foundry test: {root/TEST}')
    print('WP09Q: exact source anchors pass; new global batch feature remains opt-in.')
    if args.check:
        for path, old, new in [(POOL,orig_pool,patched_pool),(SAMPLER,orig_sampler,patched_sampler),
                               (SETTLEMENT,orig_settlement,patched_settlement)]:
            print(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),
                    fromfile=f'a/{path}',tofile=f'b/{path}')))
        print('DRY RUN: no files changed')
        return
    backup = root/'.local/wp09q/prepatch'
    if any((backup/path).exists() for path in (POOL,SAMPLER,SETTLEMENT)):
        raise FileExistsError(f'WP09Q backups already exist under {backup}; refusing second apply')
    for path, contents in ((POOL,orig_pool),(SAMPLER,orig_sampler),(SETTLEMENT,orig_settlement)):
        dest = backup/path
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(contents,encoding='utf-8')
    (root/POOL).write_text(patched_pool,encoding='utf-8')
    (root/SAMPLER).write_text(patched_sampler,encoding='utf-8')
    (root/SETTLEMENT).write_text(patched_settlement,encoding='utf-8')
    (root/TEST).parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(src_test,root/TEST)
    print('PATCHED three local .sol files; INSTALLED one Foundry test.')
    print('BACKUPS: .local/wp09q/prepatch/ (do not commit)')
    print('NOW RUN: forge build; forge test --match-path foundry/test/WP09QBatchedGlobalRecovery.t.sol -vv; forge test -vv')

if __name__ == '__main__':
    main()
