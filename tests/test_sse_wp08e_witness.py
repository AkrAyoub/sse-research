"""WP08E witness-quorum and portable evidence replication regressions.

All RPC views are local/fake; no proof of Ethereum finality or physical delivery.
"""
import base64
import copy
import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'services' / 'monitor-agent'))
sys.path.insert(0, str(ROOT / 'services' / 'provider-agent'))

from eth_account import Account
from sse_wp08d_provenance import BlockAnchor, SnapshotReorganized
from sse_wp08e_witness import (
    WitnessError, WitnessPolicy, sign_witness, verify_witnesses,
    WITNESS_DOMAIN,
)
from sse_wp08c_chain_binding import ChainCaptureBinding
from sse_evidence_wire_v1 import EvidenceScope, VerificationContext
from sse_http_signed_delivery_v1 import (
    EvidenceArchive, EvidenceError, EvidenceReplay, capture_response,
)
from typed_evidence import Domain

SETTLEMENT = '0x' + 'cd' * 20
MONITOR_KEY = '0x' + '27' * 32
PROVIDER_KEY = '0x' + '21' * 32
WITNESS_KEYS = ['0x' + b * 32 for b in ('31', '32', '33')]
MONITOR = Account.from_key(MONITOR_KEY).address.lower()
PROVIDER = Account.from_key(PROVIDER_KEY).address.lower()
WITNESSES = [Account.from_key(k).address.lower() for k in WITNESS_KEYS]
REQ = '0x' + '01' * 32
SLA = '0x' + '02' * 32
PROFILE = '0x' + '03' * 32
HASH = '0x' + 'ab' * 32
EVIDENCE = '0x' + 'ae' * 32
DOM = Domain(31337, SETTLEMENT)


def context():
    return VerificationContext(
        EvidenceScope(31337, SETTLEMENT, 4, 2, SLA, PROFILE, REQ),
        frozenset({MONITOR}))


def anchor(evidence_id=EVIDENCE):
    return BlockAnchor(31337, SETTLEMENT, 4, 2, evidence_id, 50, HASH, 1000)


class FakeRPC:
    def __init__(self):
        self.hash = HASH
        self.timestamp = 1000
        self.absent = False

    def request(self, method, params):
        if method not in ('eth_getBlockByNumber', 'eth_getBlockByHash'):
            raise AssertionError(f'unexpected RPC {method}')
        if method == 'eth_getBlockByNumber' and params != ['0x32', False]:
            raise AssertionError('wrong requested block number')
        if method == 'eth_getBlockByHash' and params != [HASH, False]:
            raise AssertionError('wrong requested block hash')
        if self.absent and method == 'eth_getBlockByHash':
            return None
        return {'number': '0x32', 'hash': self.hash,
                'timestamp': hex(self.timestamp)}


class WitnessValidationTests(unittest.TestCase):
    def setUp(self):
        self.rpc = FakeRPC()
        self.a = anchor()
        self.ctx = context()
        self.policy = WitnessPolicy(frozenset(WITNESSES), 2)

    def signed(self):
        return [sign_witness(self.a, k, self.rpc) for k in WITNESS_KEYS[:2]]

    def test_quorum_of_two_distinct_external_keys(self):
        signatures = self.signed()
        self.assertEqual(set(verify_witnesses(signatures, self.a,
                         self.ctx, PROVIDER, self.policy)), set(WITNESSES[:2]))
        self.assertEqual(signatures[0]['checkpoint']['claim'],
                         'RPC_CANONICAL_OBSERVED_ONLY')
        self.assertNotEqual(WITNESS_DOMAIN, 'SSEChainObservationAnchor')

    def test_one_signature_and_duplicate_signer_do_not_reach_quorum(self):
        signed = self.signed()
        for bad in ([signed[0]], [signed[0], signed[0]]):
            with self.assertRaises(WitnessError):
                verify_witnesses(bad, self.a, self.ctx, PROVIDER, self.policy)

    def test_unknown_monitor_or_provider_key_never_counts_as_external(self):
        for key in (MONITOR_KEY, PROVIDER_KEY):
            signed = [self.signed()[0], sign_witness(self.a, key, self.rpc)]
            with self.assertRaises(WitnessError):
                verify_witnesses(signed, self.a, self.ctx, PROVIDER, self.policy)
        with self.assertRaises(WitnessError):
            WitnessPolicy(frozenset({MONITOR, WITNESSES[0]}), 2) if False else verify_witnesses(
                self.signed(), self.a, self.ctx, PROVIDER,
                WitnessPolicy(frozenset({MONITOR, WITNESSES[0]}), 2))

    def test_checkpoint_tampering_or_conflicting_hash_rejected(self):
        signed = self.signed()
        for field, replacement in (
            ('blockHash', '0x' + 'ee' * 32), ('evidenceId', '0x'+'ed'*32),
            ('blockNumber', 51), ('claim', 'FINALIZED'), ('leaseId', 8),
            ('blockTimestamp', 999),
        ):
            with self.subTest(field=field):
                altered = copy.deepcopy(signed)
                altered[1]['checkpoint'][field] = replacement
                with self.assertRaises(WitnessError):
                    verify_witnesses(altered, self.a, self.ctx, PROVIDER, self.policy)

    def test_signature_recovery_and_mismatched_expected_anchor(self):
        signed = self.signed()
        signed[0]['signer'] = WITNESSES[1]
        with self.assertRaises(WitnessError):
            verify_witnesses(signed, self.a, self.ctx, PROVIDER, self.policy)
        with self.assertRaises(WitnessError):
            verify_witnesses(self.signed(), anchor('0x'+'ef'*32),
                             self.ctx, PROVIDER, self.policy)

    def test_reorganized_block_cannot_be_witnessed(self):
        self.rpc.hash = '0x'+'bb'*32
        with self.assertRaises(SnapshotReorganized):
            sign_witness(self.a, WITNESS_KEYS[0], self.rpc)

    def test_policy_cryptographic_key_validation(self):
        for policy_set, threshold in ((frozenset({WITNESSES[0]}), 1),
                                      (frozenset(WITNESSES), 1),
                                      (frozenset(WITNESSES), 4),
                                      (frozenset({WITNESSES[0], WITNESSES[1].upper()}), 2)):
            with self.assertRaises(WitnessError):
                WitnessPolicy(policy_set, threshold)


class WitnessedArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from signed_http_service import make_server
        cls.service = make_server(0, PROVIDER_KEY, DOM, 4, 2, REQ)
        cls.endpoint = f'http://127.0.0.1:{cls.service.server_port}'
        cls.thread = Thread(target=cls.service.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.service.shutdown()
        cls.service.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        self.rpc = FakeRPC()
        self.ctx = context()
        self.policy = WitnessPolicy(frozenset(WITNESSES), 2)

    def capture(self, path):
        archive = EvidenceArchive(path)
        cap = capture_response(
            self.endpoint, DOM, PROVIDER, self.ctx.scope, MONITOR_KEY,
            self.ctx, archive, chain_binding=ChainCaptureBinding(
                self.ctx, PROVIDER, 50, 1000, HASH), rpc=self.rpc)
        a = anchor(cap.evidence_id)
        witnesses = [sign_witness(a, k, self.rpc) for k in WITNESS_KEYS[:2]]
        return archive, cap, witnesses

    def test_separate_archive_can_import_and_reverify_complete_signed_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            a, cap, witnesses = self.capture(Path(folder) / 'source.sqlite')
            with self.assertRaises(WitnessError):
                a.load_witnessed(cap.evidence_id, self.ctx, DOM,
                                 PROVIDER, self.rpc, self.policy)
            self.assertTrue(a.store_witnesses(cap.evidence_id, self.ctx, DOM,
                                              PROVIDER, self.rpc, self.policy, witnesses))
            self.assertFalse(a.store_witnesses(cap.evidence_id, self.ctx, DOM,
                                               PROVIDER, self.rpc, self.policy, list(reversed(witnesses))))
            bundle = a.export_witnessed(cap.evidence_id, self.ctx, DOM,
                                        PROVIDER, self.rpc, self.policy)
            b = EvidenceArchive(Path(folder) / 'replica.sqlite')
            self.assertTrue(b.import_witnessed(bundle, self.ctx, DOM,
                                               PROVIDER, self.rpc, self.policy))
            self.assertFalse(b.import_witnessed(bundle, self.ctx, DOM,
                                                PROVIDER, self.rpc, self.policy))
            _, raw, pinned, _, signers = b.load_witnessed(
                cap.evidence_id, self.ctx, DOM, PROVIDER, self.rpc, self.policy)
            self.assertEqual(raw, cap.raw_bytes)
            self.assertEqual(pinned.evidence_id, cap.evidence_id)
            self.assertEqual(set(signers), set(WITNESSES[:2]))
            self.rpc.hash = '0x'+'bc'*32
            for archive in (a, b):
                with self.assertRaises(SnapshotReorganized):
                    archive.load_witnessed(cap.evidence_id, self.ctx,
                                           DOM, PROVIDER, self.rpc, self.policy)

    def test_tampered_bundle_fails_before_replica_write(self):
        with tempfile.TemporaryDirectory() as folder:
            src, cap, witnesses = self.capture(Path(folder) / 'source.sqlite')
            src.store_witnesses(cap.evidence_id, self.ctx, DOM,
                                PROVIDER, self.rpc, self.policy, witnesses)
            original = json.loads(src.export_witnessed(
                cap.evidence_id, self.ctx, DOM, PROVIDER,
                self.rpc, self.policy))
            for key, replacement in (
                ('providerRawB64', base64.b64encode(b'{}').decode('ascii')),
                ('evidenceId', '0x'+'a1'*32),
                ('anchorEnvelope', {}),
                ('witnessEnvelopes', [witnesses[0]]),
            ):
                with self.subTest(key=key):
                    malformed = copy.deepcopy(original)
                    malformed[key] = replacement
                    replica = EvidenceArchive(Path(folder) / f'{key}.sqlite')
                    with self.assertRaises(EvidenceError):
                        replica.import_witnessed(
                            json.dumps(malformed).encode('ascii'), self.ctx,
                            DOM, PROVIDER, self.rpc, self.policy)
                    self.assertEqual(replica.count(), 0)

    def test_stored_witness_set_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            src, cap, witnesses = self.capture(Path(folder) / 'source.sqlite')
            self.assertTrue(src.store_witnesses(
                cap.evidence_id, self.ctx, DOM, PROVIDER,
                self.rpc, self.policy, witnesses))
            another_valid = [witnesses[0], sign_witness(
                anchor(cap.evidence_id), WITNESS_KEYS[2], self.rpc)]
            with self.assertRaises(EvidenceReplay):
                src.store_witnesses(cap.evidence_id, self.ctx, DOM,
                                    PROVIDER, self.rpc, self.policy, another_valid)
            self.assertEqual(src.count(), 1)


if __name__ == '__main__':
    unittest.main()
