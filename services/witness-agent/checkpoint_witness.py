"""WP08E local witness CLI: separately signs a bounded RPC-observed snapshot.

This is not Ethereum finality; the witness trusts its configured loopback RPC.
Use disposable lab keys. Never sign a live chain checkpoint as a finality proof.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

from sse_chain_read import LocalRPC
from sse_wp08d_provenance import BlockAnchor
from sse_wp08e_witness import sign_witness


def main():
    parser = argparse.ArgumentParser(description='Sign an RPC-observed SSE block checkpoint')
    parser.add_argument('--rpc-url', required=True, help='numeric IPv4 loopback RPC only')
    parser.add_argument('--anchor', required=True, help='existing BlockAnchor canonical JSON file')
    parser.add_argument('--output', required=True, help='new witness JSON; will not overwrite')
    args = parser.parse_args()
    key = os.environ.get('SSE_WP08E_WITNESS_KEY')
    if not key:
        parser.error('set SSE_WP08E_WITNESS_KEY (local test key only)')
    source = Path(args.anchor)
    dest = Path(args.output)
    if not source.is_file() or not dest.parent.is_dir() or dest.exists():
        parser.error('anchor must exist and output must be a new file in an existing directory')
    raw = source.read_bytes()
    if not 1 <= len(raw) <= 4096:
        parser.error('anchor file must be bounded')
    anchor = BlockAnchor.parse(json.loads(raw.decode('ascii')))
    signed = sign_witness(anchor, key, LocalRPC(args.rpc_url))
    with dest.open('x', encoding='ascii') as handle:
        handle.write(json.dumps(signed, sort_keys=True, separators=(',', ':')) + '\n')
    print(f'Witness signed RPC-only checkpoint: {signed["signer"]}')
    print('Not verified Ethereum consensus finality or physical SLA fulfillment.')


if __name__ == '__main__':
    main()
