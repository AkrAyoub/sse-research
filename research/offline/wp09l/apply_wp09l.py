#!/usr/bin/env python3
"""Make WP09E→WP09K→WP09L contracts in an isolated output folder.

NO GitHub, network access, package managers, hosted runners or deployment.
Requires a read-only local checkout of WP09E with original contracts.
"""
from __future__ import annotations
import argparse
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'policy_reference'))
from apply_wp09k import patch_pool, patch_settlement as patch_wp09k_settlement
from wp09l_source import patch_settlement as patch_wp09l_settlement


def generate(repo: Path, out: Path) -> dict[str, str]:
    repo = repo.resolve()
    out = out.resolve()
    if not repo.is_dir():
        raise ValueError('source repo not a directory')
    if repo == out or repo in out.parents or out in repo.parents:
        raise ValueError('output must be separate from source repo')
    if out.exists() and any(out.iterdir()):
        raise ValueError('refusing overwrite of nonempty output')
    paths = ('contracts/OpenMonitorCommittee.sol', 'contracts/SSESettlement.sol')
    source = {}
    for path in paths:
        source[path] = (repo / path).read_text(encoding='utf-8')
    for path in ['contracts/SSEVRFV25Adapter.sol','contracts/MockVRFV25Coordinator.sol']:
        if (repo / path).exists():
            raise ValueError(f'expected clean WP09E base, found {path}')
    revised = {
        'contracts/OpenMonitorCommittee.sol': patch_pool(source[paths[0]]),
        'contracts/SSESettlement.sol': patch_wp09l_settlement(
            patch_wp09k_settlement(source[paths[1]])),
        'contracts/SSEVRFV25Adapter.sol': (ROOT/'policy_reference/contracts/SSEVRFV25Adapter.sol').read_text(),
        'contracts/MockVRFV25Coordinator.sol': (ROOT/'policy_reference/contracts/MockVRFV25Coordinator.sol').read_text(),
        'foundry/test/VRFFeePolicy.t.sol': (ROOT/'foundry_test/VRFFeePolicy.t.sol').read_text(),
    }
    changes = []
    for path in paths:
        changes.append(''.join(difflib.unified_diff(
            source[path].splitlines(keepends=True),
            revised[path].splitlines(keepends=True),
            fromfile='a/'+path, tofile='b/'+path)))
    for path, data in revised.items():
        f = out/path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(data, encoding='utf-8')
    (out/'WP09L.patch').write_text('\n'.join(changes), encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps({
        'base':'WP09E', 'includes':'WP09K cancellation + WP09L fee policy',
        'source_checkout':str(repo), 'generated_contracts':list(revised),
        'source_writes':0, 'github_actions':0,
        'solidity_compiled':False, 'foundry_executed':False
    }, indent=2)+'\n')
    return revised


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    args=p.parse_args()
    result=generate(args.repo,args.out)
    print('Generated',len(result),'offline files; source unchanged. NO EVM compilation/test performed.')

if __name__=='__main__':
    main()
