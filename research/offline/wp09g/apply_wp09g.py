"""Patch a LOCAL checkout of WP09E draft branch; NO GitHub Actions or network.

Default --check is non-writing and fails if exact WP09E anchors differ. The
--apply command makes a .wp09g-prepatch local backup and replaces two .sol
files; run local Foundry afterwards before using the result. This is an
UNCOMPILED implementation candidate, NOT production verified Solidity.
"""
from __future__ import annotations

import argparse
import difflib
from pathlib import Path

POOL_PATH = 'contracts/OpenMonitorCommittee.sol'
SAMPLER_PATH = 'contracts/GlobalRosterSampler.sol'


ADDITIONAL_API = '''    /// @notice Publish the complete deterministic recovery index list.
    /// @dev Off-chain relayers must produce ALL historical Merkle siblings in
    /// strict order; this method gives no authority to choose a seat.
    function globalRecoveryDrawIndexes(uint256 id) external view returns (uint256[] memory) {
        if (!globalBatchedRecoveryEnabled || !pendingGlobalSeedReady[id] ||
            assignments[id].status != RequestStatus.AwaitingRandomness)
            revert InvalidPhase();
        uint256 n = globalSnapshotCount[id];
        uint256 count = n < GLOBAL_RECOVERY_DRAW_LIMIT ? n : GLOBAL_RECOVERY_DRAW_LIMIT;
        return GlobalRosterSampler.draw(pendingGlobalSeed[id], id, n, count);
    }

    /// @notice Prove the NEXT <=8 drawn global identities, never a caller
    /// chosen subset. Provisional chosen seats are bond-locked until this
    /// assignment either completes or expires (same fixed randomnessTimeout).
    /// @dev Still vulnerable to a withholding RSA operator or unavailable
    /// historical proofs. More reserve draws are NOT a VRF or honest quorum.
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
        uint256 sampleCount = n < GLOBAL_RECOVERY_DRAW_LIMIT ? n : GLOBAL_RECOVERY_DRAW_LIMIT;
        uint256 cursor = globalRecoveryCursor[id];
        uint256 batchLength = accounts.length;
        if (batchLength == 0 || batchLength > GLOBAL_RECOVERY_BATCH_LIMIT ||
            siblingPaths.length != batchLength || cursor + batchLength > sampleCount)
            revert InvalidInput();

        // Bounded deterministic enumeration derived from the locked seed.
        uint256[] memory indexes = GlobalRosterSampler.draw(
            pendingGlobalSeed[id], id, n, sampleCount);
        bytes32 frozenRoot = globalSnapshotRoot[id];
        for (uint256 j; j < batchLength; ++j) {
            address account = accounts[j];
            if (!GlobalRosterMerkle.verify(
                frozenRoot, indexes[cursor + j], account, siblingPaths[j]
            )) revert InvalidGlobalProof();
            Candidate storage c = candidates[account];
            if (account == r.consumer || account == r.provider ||
                !c.active || c.bond < minimumBond) continue;

            uint256 filled = globalRecoveryLocks[id];
            if (filled < COMMITTEE_SIZE) {
                r.committee[filled] = account;
                globalRecoveryLocks[id] = filled + 1;
                // Prevent a partially selected monitor from exiting while
                // subsequent proof batches are being submitted.
                ++c.activeAssignments;
            } else {
                standbyRosters[id].push(account);
            }
        }
        cursor += batchLength;
        globalRecoveryCursor[id] = cursor;
        emit GlobalRecoveryBatchAdvanced(id, cursor, sampleCount,
                                         globalRecoveryLocks[id]);
        if (cursor != sampleCount) return;

        if (globalRecoveryLocks[id] != COMMITTEE_SIZE) {
            // Fewer than four live candidates after all bounded proofs:
            // release any provisional seat locks and fail closed. This lets
            // settlement use its already-existing expired lease refund path.
            _clearGlobalRecovery(id);
            delete pendingGlobalSeedReady[id];
            delete pendingGlobalSeed[id];
            r.status = RequestStatus.Expired;
            emit AssignmentExpired(id);
            return;
        }
        r.status = RequestStatus.Assigned;
        delete globalRecoveryLocks[id]; // locks now belong to Assigned state
        delete pendingGlobalSeedReady[id];
        delete pendingGlobalSeed[id];
        emit GlobalRecoveryCompleted(id, cursor, standbyRosters[id].length);
        emit CommitteeSelected(id, r.committee);
    }

    function _clearGlobalRecovery(uint256 id) internal {
        Assignment storage r = assignments[id];
        uint256 count = globalRecoveryLocks[id];
        for (uint256 i; i < count; ++i) {
            --candidates[r.committee[i]].activeAssignments;
        }
        delete r.committee;
        delete standbyRosters[id];
        delete globalRecoveryLocks[id];
        delete globalRecoveryCursor[id];
    }

'''


def replace_once(source: str, old: str, new: str, path: str) -> str:
    occurrences = source.count(old)
    if occurrences != 1:
        raise ValueError(f'{path}: expected exactly one anchor, got {occurrences}: {old[:90]!r}')
    return source.replace(old, new, 1)


def patch_pool(source: str) -> str:
    if 'function advanceGlobalRecovery(' in source:
        raise ValueError('WP09G already applied')
    p = POOL_PATH
    source = replace_once(source,
        '    uint256 public constant GLOBAL_SAMPLE_LIMIT = 10;',
        '    uint256 public constant GLOBAL_SAMPLE_LIMIT = 10;\n'
        '    uint256 public constant GLOBAL_RECOVERY_DRAW_LIMIT = 40;\n'
        '    uint256 public constant GLOBAL_RECOVERY_BATCH_LIMIT = 8;', p)
    source = replace_once(source,
        '    bool public globalMerkleElectionEnabled;\n    bool private entered;',
        '    bool public globalMerkleElectionEnabled;\n'
        '    bool public globalBatchedRecoveryEnabled;\n    bool private entered;', p)
    source = replace_once(source,
        '    mapping(uint256 => bool) public pendingGlobalSeedReady;',
        '    mapping(uint256 => bool) public pendingGlobalSeedReady;\n'
        '    mapping(uint256 => uint256) public globalRecoveryCursor;\n'
        '    mapping(uint256 => uint256) public globalRecoveryLocks;', p)
    source = replace_once(source,
        '    event GlobalCommitteeProved(uint256 indexed requestId, bytes32 frozenRoot,',
        '    event GlobalRecoveryBatchAdvanced(uint256 indexed requestId,\n'
        '                                      uint256 cursor, uint256 total, uint256 locked);\n'
        '    event GlobalRecoveryCompleted(uint256 indexed requestId,\n'
        '                                  uint256 processed, uint256 standbyCount);\n'
        '    event GlobalCommitteeProved(uint256 indexed requestId, bytes32 frozenRoot,', p)
    source = replace_once(source,
        '    function globalRosterRoot() external view returns (bytes32) {',
        '''    /// @notice Opt-in staged global election; requires global Merkle
    /// enrollment mode and one-way choice BEFORE settlement binding.
    function enableGlobalBatchedRecovery() external {
        if (msg.sender != bootstrapper || settlement != address(0) ||
            !globalMerkleElectionEnabled || globalBatchedRecoveryEnabled ||
            totalRegistrations != 0) revert Unauthorized();
        globalBatchedRecoveryEnabled = true;
    }

    function globalRosterRoot() external view returns (bytes32) {''', p)
    source = replace_once(source,
        '    function finalizeGlobalCommittee(\n'
        '        uint256 id, address[] calldata accounts, bytes32[][] calldata siblingPaths\n'
        '    ) external {\n',
        '    function finalizeGlobalCommittee(\n'
        '        uint256 id, address[] calldata accounts, bytes32[][] calldata siblingPaths\n'
        '    ) external {\n'
        '        if (globalBatchedRecoveryEnabled) revert InvalidPhase();\n', p)
    source = replace_once(source,
        '    function expire(uint256 id) external {',
        ADDITIONAL_API + '    function expire(uint256 id) external {', p)
    source = replace_once(source,
        '        if (!globalMerkleElectionEnabled) _unlockSnapshot(id);',
        '        if (globalBatchedRecoveryEnabled) _clearGlobalRecovery(id);\n'
        '        if (!globalMerkleElectionEnabled) _unlockSnapshot(id);', p)
    return source


def patch_sampler(source: str) -> str:
    if 'count > 40' in source:
        raise ValueError('WP09G already applied')
    source = replace_once(source, 'k <= 10', 'k <= 40', SAMPLER_PATH)
    source = replace_once(source, 'count > 10 || count == 0',
                          'count > 40 || count == 0', SAMPLER_PATH)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True, help='LOCAL checkout of WP09E')
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument('--check', action='store_true', help='dry-run (default), no writes')
    choice.add_argument('--apply', action='store_true', help='modify local files with backups')
    args = parser.parse_args()
    repo = args.repo.expanduser().resolve()
    old_pool = (repo/POOL_PATH).read_text(encoding='utf-8')
    old_sampler = (repo/SAMPLER_PATH).read_text(encoding='utf-8')
    new_pool = patch_pool(old_pool)
    new_sampler = patch_sampler(old_sampler)
    print('WP09G source anchors validated; 2 Solidity files to patch; zero remote calls.')
    if not args.apply:
        for path, old, new in ((POOL_PATH, old_pool, new_pool), (SAMPLER_PATH, old_sampler, new_sampler)):
            diff = difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        fromfile=f'a/{path}', tofile=f'b/{path}')
            print(''.join(diff))
        print('DRY RUN ONLY: pass --apply to write to the local checkout.')
        return
    for path, old, new in ((POOL_PATH, old_pool, new_pool), (SAMPLER_PATH, old_sampler, new_sampler)):
        dest = repo/path
        backup = dest.with_name(dest.name + '.wp09g-prepatch')
        if backup.exists():
            raise FileExistsError(f'Backup already exists; refusing overwrite: {backup}')
        backup.write_text(old, encoding='utf-8')
        dest.write_text(new, encoding='utf-8')
        print(f'PATCHED locally: {dest} (backup {backup})')
    print('NEXT: forge build && forge test -vv && forge snapshot, ALL LOCAL. NO GITHUB ACTIONS.')


if __name__ == '__main__':
    main()
