"""Read-only audit of SSE local-demo evidence for the Milestone 3 experiment.

Two distinct checks:
  - Offline: retained JSON files match the run-record Keccak commitments.
  - Optional online: those commitments match SSESettlement storage at one block.

Neither check proves the truth of observations, independent monitor hosts, or
accurate timestamps. No transactions or key operations are performed.

Examples:
  python tools/m3_evidence_audit.py --run .local/sse-e2e-runs/lease-3/run.json
  python tools/m3_evidence_audit.py --run .local/sse-e2e-runs/lease-3/run.json \\
    --rpc-url http://127.0.0.1:8545
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys

from sse_challenge import keccak256
from sse_chain_read import LocalRPC, ChainReadError, inspect_chain, _call, _words

HASH = re.compile(r"0x[0-9a-fA-F]{64}\Z")
ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")

class EvidenceAuditError(ValueError):
    pass


def _require(condition: bool, error: str):
    if not condition:
        raise EvidenceAuditError(error)


def canonical_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')


def _read_json(path: Path) -> dict:
    try:
        content = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise EvidenceAuditError(f'unreadable JSON file {path.name}: {exc}') from exc
    _require(isinstance(content, dict), f'{path.name} must be JSON object')
    return content


def verify_offline(run_path: Path) -> dict:
    """Verify commitments and cross-references without trusting the archive path list."""
    run = _read_json(run_path)
    _require(run.get('schema') == 'sse-local-full-cycle-v1', 'unexpected run schema')
    _require(run.get('status') == 'SUCCESS_COMPLETE', 'run is not completed')
    _require(type(run.get('chainId')) is int and run['chainId'] > 0, 'invalid chain')
    _require(type(run.get('leaseId')) is int and run['leaseId'] > 0, 'invalid lease')
    _require(ADDRESS.fullmatch(str(run.get('settlement', ''))) is not None, 'invalid contract')
    _require(HASH.fullmatch(str(run.get('requestHash', ''))) is not None, 'invalid request hash')
    _require(HASH.fullmatch(str(run.get('responseHash', ''))) is not None, 'invalid response hash')
    commits = run.get('evidenceCommitments')
    names = run.get('evidenceFiles')
    _require(isinstance(commits, dict) and commits, 'missing commitments')
    _require(isinstance(names, list) and len(names) == len(commits), 'evidence list/count mismatch')
    _require(len(commits) <= 4, 'unexpected number of monitor commitments')
    used_names = set()
    used_monitors = set()
    rows = []
    for name in names:
        _require(isinstance(name, str), 'invalid evidence filename')
        # Ignore platform-specific directory prefixes; NEVER read outside run_dir.
        filename = name.replace('\\', '/').split('/')[-1]
        _require(re.fullmatch(r'monitor_[1-4]_evidence\.json', filename) is not None,
                 'unexpected evidence filename')
        _require(filename not in used_names, 'duplicate evidence filename')
        used_names.add(filename)
        file_path = run_path.parent / filename
        _require(file_path.is_file() and not file_path.is_symlink(), 'missing/nonregular evidence file: ' + filename)
        evidence = _read_json(file_path)
        monitor = evidence.get('monitor')
        _require(isinstance(monitor, str) and ADDRESS.fullmatch(monitor) is not None, 'invalid monitor address')
        _require(monitor.lower() not in used_monitors, 'duplicate monitor identity')
        used_monitors.add(monitor.lower())
        expected = {k.lower(): v for k,v in commits.items()}
        _require(monitor.lower() in expected, 'monitor not in commitment map')
        declared = expected[monitor.lower()]
        _require(isinstance(declared, str) and HASH.fullmatch(declared) is not None, 'invalid commitment hash')
        for key in ('chainId', 'leaseId', 'epochId'):
            expected_value = run[key] if key in run else 0
            _require(evidence.get(key) == expected_value, f'{filename} wrong {key}')
        for key in ('settlement', 'requestHash', 'responseHash'):
            _require(str(evidence.get(key, '')).lower() == str(run[key]).lower(),
                     f'{filename} wrong {key}')
        for key in ('responseDeadline', 'monitoringClose'):
            _require(evidence.get(key) == run.get(key), f'{filename} wrong {key}')
        obs = evidence.get('observation')
        _require(isinstance(obs, dict) and obs.get('outcome') == 'SUCCESS_OBSERVED',
                 f'{filename} missing successful observation')
        _require(obs.get('leaseId') == run['leaseId'] and obs.get('epochId') == 0,
                 f'{filename} observation identity mismatch')
        _require(isinstance(obs.get('requestHash'), str) and
                 obs['requestHash'].lower() == run['requestHash'].lower(),
                 f'{filename} observation challenge mismatch')
        calculated = '0x' + keccak256(canonical_bytes(evidence)).hex()
        _require(calculated.lower() == declared.lower(), f'{filename} evidence bytes do not match commitment')
        rows.append({'monitor': monitor.lower(), 'file': filename, 'evidenceHash': calculated})
    return {
        'leaseId': run['leaseId'], 'chainId': run['chainId'],
        'settlement': run['settlement'].lower(), 'epochId': 0,
        'requestHash': run['requestHash'].lower(), 'responseHash': run['responseHash'].lower(),
        'offlineCommitmentsVerified': True, 'onChainCommitmentsVerified': False,
        'evidence': rows, 'truthOrIndependenceProven': False,
    }


def verify_on_chain(summary: dict, rpc) -> dict:
    chain = inspect_chain(rpc, summary['settlement'], summary['leaseId'], 0,
                          expected_chain_id=summary['chainId'])
    epoch = chain['epoch']
    _require(epoch['requestHash'] == summary['requestHash'], 'chain request hash mismatch')
    _require(epoch['responseHash'] == summary['responseHash'], 'chain response hash mismatch')
    block_tag = hex(chain['blockNumber'])
    for e in summary['evidence']:
        addr = int(e['monitor'], 16)
        encoded = _call(rpc, summary['settlement'],
                        'monitorEvidenceHash(uint256,uint256,address)',
                        (summary['leaseId'], 0, addr), block_tag)
        value = '0x' + _words(encoded, 1)[0]
        _require(value == e['evidenceHash'], f'chain commitment mismatch for {e["monitor"]}')
    return {**summary, 'onChainCommitmentsVerified': True, 'snapshotBlockNumber': chain['blockNumber']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True, help='Path to a local run.json')
    parser.add_argument('--rpc-url', help='Optional read-only local Ethereum RPC')
    args = parser.parse_args(argv)
    try:
        result = verify_offline(args.run)
        if args.rpc_url:
            result = verify_on_chain(result, LocalRPC(args.rpc_url))
    except (EvidenceAuditError, ChainReadError) as exc:
        print('EVIDENCE_AUDIT_FAILED: ' + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
