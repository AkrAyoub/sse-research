"""WP08D: signed snapshot provenance validation; never equate RPC with finality."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'services' / 'monitor-agent'))

from eth_account import Account
from sse_evidence_wire_v1 import EvidenceScope, VerificationContext
from sse_wp08d_provenance import (
    BlockAnchor, ProvenanceError, SnapshotReorganized,
    valid_block_hash, sign_anchor, verify_anchor, check_canonical_snapshot,
)
from sse_wp08c_chain_binding import ChainCaptureBinding

KEY = '0x' + '25'*32
OTHER_KEY = '0x' + '26'*32
MONITOR = Account.from_key(KEY).address.lower()
OTHER = Account.from_key(OTHER_KEY).address.lower()
CONTRACT = '0x' + 'cd'*20
EVIDENCE = '0x' + 'ca'*32
BLOCKHASH = '0x' + 'ab'*32
REQUEST = '0x' + '01'*32
SLA = '0x' + '02'*32
PROFILE = '0x' + '03'*32


def context():
    return VerificationContext(
        EvidenceScope(31337, CONTRACT, 4, 2, SLA, PROFILE, REQUEST),
        frozenset({MONITOR}))


def anchor():
    return BlockAnchor(31337, CONTRACT, 4, 2, EVIDENCE, 50, BLOCKHASH, 1000)


class HeaderRPC:
    def __init__(self):
        self.hash = BLOCKHASH
        self.timestamp = 1000
        self.missing_by_hash = False

    def request(self, method, params):
        if method == 'eth_getBlockByNumber':
            if params != [hex(50), False]:
                raise AssertionError('unexpected number query')
        elif method == 'eth_getBlockByHash':
            if params != [BLOCKHASH, False]:
                raise AssertionError('unexpected hash query')
            if self.missing_by_hash:
                return None
        else:
            raise AssertionError('unexpected RPC method')
        return {'number': hex(50), 'hash': self.hash,
                'timestamp': hex(self.timestamp)}


class ProvenanceTests(unittest.TestCase):
    def test_exact_anchor_signature_and_scope(self):
        e = sign_anchor(anchor(), KEY)
        self.assertEqual(e['signer'], MONITOR)
        self.assertEqual(verify_anchor(e, context(), EVIDENCE, MONITOR), anchor())
        check_canonical_snapshot(HeaderRPC(), anchor())

    def test_tamper_every_committed_field(self):
        changes = {'chainId': 1, 'settlement': '0x'+'de'*20,
                   'leaseId': 8, 'epochId': 3,
                   'evidenceId': '0x'+'ba'*32, 'blockNumber': 51,
                   'blockHash': '0x'+'bc'*32, 'blockTimestamp': 1001}
        for field, value in changes.items():
            with self.subTest(field=field):
                env = copy.deepcopy(sign_anchor(anchor(), KEY))
                env['anchor'][field] = value
                with self.assertRaises(ProvenanceError):
                    verify_anchor(env, context(), EVIDENCE, MONITOR)

    def test_wrong_monitor_or_signature_rejected(self):
        with self.assertRaises(ProvenanceError):
            verify_anchor(sign_anchor(anchor(), OTHER_KEY), context(), EVIDENCE)
        data = sign_anchor(anchor(), KEY)
        data['signer'] = OTHER
        with self.assertRaises(ProvenanceError):
            verify_anchor(data, context(), EVIDENCE)

    def test_invalid_provenance_metadata_rejected(self):
        for bad in ('0x'+'00'*32, '0x'+'ab'*31, '0x'+'AB'*32,
                    None, 5, 'invalid'):
            with self.subTest(bad=bad):
                self.assertFalse(valid_block_hash(bad))
                with self.assertRaises(ProvenanceError):
                    BlockAnchor(31337, CONTRACT, 4, 2, EVIDENCE, 50, bad, 1000)

    def test_malformed_envelopes_rejected(self):
        original = sign_anchor(anchor(), KEY)
        for payload in (
                None, {}, {'anchor': original['anchor']},
                {**original, 'extra': 3},
                {**original, 'signature': '0x'+'00'*65},
                {**original, 'anchor': {**original['anchor'], 'schema':'invalid'}}):
            with self.subTest(payload=payload):
                with self.assertRaises(ProvenanceError):
                    verify_anchor(payload, context(), EVIDENCE, MONITOR)

    def test_fork_or_missing_history_is_rejected(self):
        rpc = HeaderRPC()
        rpc.hash = '0x'+'fe'*32
        with self.assertRaises(SnapshotReorganized):
            check_canonical_snapshot(rpc, anchor())
        rpc.hash = BLOCKHASH
        rpc.missing_by_hash = True
        with self.assertRaises(SnapshotReorganized):
            check_canonical_snapshot(rpc, anchor())
        rpc.missing_by_hash = False
        rpc.timestamp = 1001
        with self.assertRaises(SnapshotReorganized):
            check_canonical_snapshot(rpc, anchor())


if __name__ == '__main__':
    unittest.main()
