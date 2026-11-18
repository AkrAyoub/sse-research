#!/usr/bin/env python3
"""Safely repair WP-09N's ambiguous console2 overload in the *test harness*.

No production contract changes, Git operations, RPC calls, or downloads.
Run from the repository root: python fix_wp09n_benchmark.py
"""
from pathlib import Path
import sys

TARGET = Path('foundry/test/WP09NGasBench.t.sol')
OLD = 'console2.log("WP09N|vrf_purchase|n_active", 16);'
NEW = 'console2.log("WP09N|vrf_purchase|n_active", uint256(16));'
OLD_APPLY = 'console2.log("WP09N|vrf_apply|gas", applyGas);'
NEW_APPLY = ('console2.log("WP09N|vrf_apply|n_active", uint256(16));\n'
             '        console2.log("WP09N|vrf_apply|gas", applyGas);')


def patch(source: str) -> tuple[str, bool]:
    if source.count(NEW) == 1:
        if OLD in source:
            raise RuntimeError('Mixed old/new benchmark anchors; refusing to change')
        if source.count(NEW_APPLY) == 1:
            return source, False
        if source.count(OLD_APPLY) != 1:
            raise RuntimeError('Missing or duplicated VRF apply log anchor')
        return source.replace(OLD_APPLY, NEW_APPLY, 1), True
    if source.count(OLD) != 1 or source.count(NEW) != 0:
        raise RuntimeError('Expected exactly one original ambiguous console2.log call')
    if source.count(OLD_APPLY) != 1:
        raise RuntimeError('Expected exactly one VRF apply log anchor')
    return source.replace(OLD, NEW, 1).replace(OLD_APPLY, NEW_APPLY, 1), True


def main() -> int:
    if not Path('foundry.toml').is_file() or not Path('contracts/SSESettlement.sol').is_file():
        print('ERROR: Run this script from the SSE repository root containing foundry.toml', file=sys.stderr)
        return 2
    if not TARGET.is_file():
        print(f'ERROR: Missing {TARGET}', file=sys.stderr)
        return 2
    original = TARGET.read_text(encoding='utf-8')
    try:
        fixed, changed = patch(original)
    except RuntimeError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    if changed:
        TARGET.write_text(fixed, encoding='utf-8')
        print(f'PATCHED: {TARGET}')
        print('Fixed Solidity literal overload and added VRF-apply roster metadata.')
    else:
        print(f'ALREADY PATCHED: {TARGET}')
    print('Production contracts untouched. No CI, remote actions, or network calls.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
