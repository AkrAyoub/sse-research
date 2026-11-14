"""WP-08F lab regressions: trusted Beacon REST claims, never BLS/PoS proofs."""
from __future__ import annotations

import copy
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / 'tools'))
from sse_wp08d_provenance import BlockAnchor
from sse_wp08f_beacon_finality import (
    BeaconFinalityError, BeaconReportedFinalizedExecution,
    LoopbackBeaconREST, cross_check_reported_finality,
)

ROOT = '0x' + '10' * 32
H0 = '0x' + 'ab' * 32
H1 = '0x' + 'bc' * 32
H2 = '0x' + 'cd' * 32
P0 = '0x' + '01' * 32
SETTLEMENT = '0x' + 'fe' * 20
EVIDENCE = '0x' + '12' * 32


def anchor():
    return BlockAnchor(31337, SETTLEMENT, 4, 2, EVIDENCE, 50, H0, 1000)


def claim():
    return BeaconReportedFinalizedExecution(ROOT, 200, 52, H2, 1002)


class FakeExecutionRPC:
    def __init__(self, url='http://127.0.0.1:18888'):
        self.url = url
        self.chain_id = 31337
        self.blocks = {
            50: {'hash': H0, 'parentHash': P0, 'number': '0x32', 'timestamp': '0x3e8'},
            51: {'hash': H1, 'parentHash': H0, 'number': '0x33', 'timestamp': '0x3e9'},
            52: {'hash': H2, 'parentHash': H1, 'number': '0x34', 'timestamp': '0x3ea'},
        }

    def request(self, method, params):
        if method == 'eth_chainId':
            return hex(self.chain_id)
        if method == 'eth_getBlockByNumber':
            return self.blocks.get(int(params[0], 16))
        if method == 'eth_getBlockByHash':
            return next((b for b in self.blocks.values() if b['hash'] == params[0]), None)
        raise AssertionError('unexpected RPC method ' + method)


class BeaconServer:
    def __init__(self):
        self.genesis = ROOT
        self.finalized = True
        self.optimistic = False
        self.version = 'deneb'
        self.block_hash = H2
        self.block_number = '52'
        self.execution_timestamp = '1002'
        self.slot = '200'
        self.redirect = False
        self.bad_json = False
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if server.redirect:
                    self.send_response(302)
                    self.send_header('Location', 'http://example.org/unsafe')
                    self.end_headers()
                    return
                if self.path == '/eth/v1/beacon/genesis':
                    payload = {'data': {'genesis_validators_root': server.genesis}}
                elif self.path == '/eth/v2/beacon/blocks/finalized':
                    payload = {
                        'version': server.version,
                        'finalized': server.finalized,
                        'execution_optimistic': server.optimistic,
                        'data': {'message': {'slot': server.slot, 'body': {
                            'execution_payload': {
                                'block_hash': server.block_hash,
                                'block_number': server.block_number,
                                'timestamp': server.execution_timestamp,
                            }
                        }}},
                    }
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                data = b'{"finalized":true,"finalized":true}' if server.bad_json else json.dumps(payload).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format, *args):
                pass

        self.http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = 'http://127.0.0.1:' + str(self.http.server_port)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=5)


class BeaconApiTests(unittest.TestCase):
    def setUp(self):
        self.server = BeaconServer()
        self.client = LoopbackBeaconREST(self.server.url, ROOT)

    def tearDown(self):
        self.server.close()

    def test_explicit_genesis_and_finalized_payload_accepted_as_report_only(self):
        view = self.client.get_reported_finalized_execution()
        self.assertEqual(view, claim())
        self.assertFalse(cross_check_reported_finality(anchor(), view,
                         FakeExecutionRPC()).pos_finality_proven)

    def test_archive_strict_loader_cross_checks_beacon_report(self):
        import tempfile
        from sse_http_signed_delivery_v1 import EvidenceArchive
        with tempfile.TemporaryDirectory() as folder:
            archive = EvidenceArchive(Path(folder) / 'capture.sqlite')
            fake_loaded = ({'record': True}, b'response', anchor(), [], ('witness',))
            with patch.object(archive, 'load_witnessed', return_value=fake_loaded) as loaded:
                outcome = archive.load_beacon_reported(
                    EVIDENCE, object(), object(), '0x'+'11'*20,
                    FakeExecutionRPC(), object(), self.client)
                self.assertEqual(outcome[-1].ancestry_depth, 2)
                self.assertFalse(outcome[-1].pos_finality_proven)
                self.assertEqual(outcome[1], b'response')
                loaded.assert_called_once()
                self.server.optimistic = True
                with self.assertRaises(BeaconFinalityError):
                    archive.load_beacon_reported(EVIDENCE, object(), object(),
                        '0x'+'11'*20, FakeExecutionRPC(), object(), self.client)

    def test_wrong_genesis_is_fail_closed(self):
        self.server.genesis = '0x' + '55' * 32
        with self.assertRaisesRegex(BeaconFinalityError, 'genesis'):
            self.client.get_reported_finalized_execution()

    def test_not_finalized_or_optimistic_or_unsupported_fork_rejected(self):
        for field, value in [('finalized', False), ('optimistic', True),
                             ('version', 'gloas')]:
            with self.subTest(field=field):
                old = getattr(self.server, field)
                setattr(self.server, field, value)
                with self.assertRaisesRegex(BeaconFinalityError, 'not explicitly finalized'):
                    self.client.get_reported_finalized_execution()
                setattr(self.server, field, old)

    def test_missing_or_invalid_execution_payload_fields(self):
        for field, value in [('block_hash', '0x' + '00' * 32),
                             ('block_number', '-1'), ('execution_timestamp', '1.0'),
                             ('slot', '0002')]:
            with self.subTest(field=field):
                old = getattr(self.server, field)
                setattr(self.server, field, value)
                with self.assertRaises(BeaconFinalityError):
                    self.client.get_reported_finalized_execution()
                setattr(self.server, field, old)

    def test_proxy_redirect_and_duplicate_json_not_accepted(self):
        self.server.redirect = True
        with self.assertRaises(BeaconFinalityError):
            self.client.get_reported_finalized_execution()
        self.server.redirect = False
        self.server.bad_json = True
        with self.assertRaises(BeaconFinalityError):
            self.client.get_reported_finalized_execution()

    def test_remote_beacon_and_no_pinned_genesis_rejected(self):
        for url in ('http://example.org:5052', 'http://localhost:5052',
                    'http://127.0.0.1:5052/unsafe',
                    'http://127.0.0.1:5052/?x=1'):
            with self.subTest(url=url):
                with self.assertRaises(BeaconFinalityError):
                    LoopbackBeaconREST(url, ROOT)
        with self.assertRaises(BeaconFinalityError):
            LoopbackBeaconREST(self.server.url, '0x' + '00' * 32)


class ExecutionAncestryTests(unittest.TestCase):
    def test_2_independent_rpc_views_agree_on_parent_chain(self):
        a = FakeExecutionRPC()
        b = FakeExecutionRPC('http://127.0.0.1:18889')
        result = cross_check_reported_finality(anchor(), claim(), a, second_rpc=b)
        self.assertEqual(result.ancestry_depth, 2)
        self.assertEqual(result.execution_rpc_views, 2)
        self.assertTrue(result.consensus_rest_trusted)
        self.assertFalse(result.pos_finality_proven)

    def test_wrong_anchor_hash_or_timestamp_or_finalized_hash(self):
        fake = FakeExecutionRPC()
        with self.assertRaises(BeaconFinalityError):
            cross_check_reported_finality(
                BlockAnchor(31337, SETTLEMENT, 4, 2, EVIDENCE, 50,
                            '0x' + 'ee' * 32, 1000), claim(), fake)
        with self.assertRaises(BeaconFinalityError):
            cross_check_reported_finality(
                BlockAnchor(31337, SETTLEMENT, 4, 2, EVIDENCE, 50, H0, 999), claim(), fake)
        with self.assertRaises(BeaconFinalityError):
            cross_check_reported_finality(anchor(),
                BeaconReportedFinalizedExecution(ROOT, 200, 52, '0x' + 'ee' * 32, 1002), fake)

    def test_peer_conflicting_canonical_height_is_rejected(self):
        a = FakeExecutionRPC()
        b = FakeExecutionRPC('http://127.0.0.1:18889')
        b.blocks[51]['hash'] = '0x' + 'fe' * 32
        with self.assertRaises(BeaconFinalityError):
            cross_check_reported_finality(anchor(), claim(), a, second_rpc=b)

    def test_forged_parent_link_or_head_time_rejected(self):
        a = FakeExecutionRPC()
        a.blocks[52]['parentHash'] = '0x' + 'dc' * 32
        with self.assertRaises(BeaconFinalityError):
            cross_check_reported_finality(anchor(), claim(), a)
        a = FakeExecutionRPC()
        a.blocks[52]['timestamp'] = '0x3eb'
        with self.assertRaises(BeaconFinalityError):
            cross_check_reported_finality(anchor(), claim(), a)

    def test_chain_id_mismatch_rejected(self):
        a = FakeExecutionRPC()
        a.chain_id = 1
        with self.assertRaisesRegex(BeaconFinalityError, 'chain ID'):
            cross_check_reported_finality(anchor(), claim(), a)

    def test_checkpoint_before_anchor_or_far_ahead_rejected(self):
        a = FakeExecutionRPC()
        with self.assertRaisesRegex(BeaconFinalityError, 'precedes'):
            cross_check_reported_finality(anchor(),
                BeaconReportedFinalizedExecution(ROOT, 100, 49, H1, 1001), a)
        with self.assertRaisesRegex(BeaconFinalityError, 'distance'):
            cross_check_reported_finality(anchor(),
                BeaconReportedFinalizedExecution(ROOT, 1000, 400, H2, 1002), a)

    def test_same_rpc_instance_or_endpoint_not_independent(self):
        a = FakeExecutionRPC()
        b = FakeExecutionRPC()
        with self.assertRaises(BeaconFinalityError):
            cross_check_reported_finality(anchor(), claim(), a, second_rpc=a)
        with self.assertRaises(BeaconFinalityError):
            cross_check_reported_finality(anchor(), claim(), a, second_rpc=b)

    def test_removed_or_changed_historical_block_fails(self):
        a = FakeExecutionRPC()
        a.blocks.pop(50)
        with self.assertRaises(BeaconFinalityError):
            cross_check_reported_finality(anchor(), claim(), a)
        a = FakeExecutionRPC()
        a.blocks[50]['hash'] = '0x' + 'dd' * 32
        with self.assertRaises(BeaconFinalityError):
            cross_check_reported_finality(anchor(), claim(), a)

    def test_historical_anchor_equal_finalized_block(self):
        a = FakeExecutionRPC()
        immediate = BeaconReportedFinalizedExecution(ROOT, 201, 50, H0, 1000)
        checked = cross_check_reported_finality(anchor(), immediate, a)
        self.assertEqual(checked.ancestry_depth, 0)


if __name__ == '__main__':
    unittest.main()
