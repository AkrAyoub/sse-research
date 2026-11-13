"""WP08B lab integration: provider EIP-712 -> monitor EIP-712 -> durable raw archive.

Evidence authenticates signatures and observations, not physical fulfillment.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'services' / 'provider-agent'))
sys.path.insert(0, str(ROOT / 'services' / 'monitor-agent'))

from sse_http_signed_delivery_v1 import (
    EvidenceArchive, ProviderResponseInvalid, TransportFailure, CaptureResult,
    _strict_json_bytes, validate_provider_payload, fetch_provider_payload,
    capture_response,
)
from sse_evidence_wire_v1 import (
    EvidenceScope, VerificationContext, EvidenceError, EvidenceReplay,
    AuthenticationError, ObservationKind, VerifiedObservation,
    verify_observation, verify_payload, ZERO_HASH,
)
from sse_challenge import expected_response_hash
from typed_evidence import Domain

try:
    from eth_account import Account
    HAS_SIGNATURES = True
except ImportError:
    HAS_SIGNATURES = False

PKEY = '0x' + '21' * 32  # research-only private keys
MKEY = '0x' + '22' * 32
OTHER = '0x' + '23' * 32
SETTLEMENT = '0x' + 'cd' * 20
REQ = '0x' + '01' * 32
SLA = '0x' + '02' * 32
RESOURCE = '0x' + '03' * 32
DOMAIN = Domain(31337, SETTLEMENT)


def scope(**kw):
    x = dict(chain_id=31337, settlement=SETTLEMENT, lease_id=4, epoch_id=2,
             sla_policy_hash=SLA, resource_profile_hash=RESOURCE, request_hash=REQ)
    x.update(kw)
    return EvidenceScope(**x)


class WireDecodeTests(unittest.TestCase):
    def test_non_json_and_wrong_types_rejected(self):
        for data in (b'', b'[]', b'"hello"', b'{}x', b'{"x": NaN}', b'\xff', b'x' * 4097):
            with self.subTest(data=data[:15]), self.assertRaises(ProviderResponseInvalid):
                _strict_json_bytes(data)

    def test_duplicate_key_rejected(self):
        with self.assertRaises(ProviderResponseInvalid):
            _strict_json_bytes(b'{"leaseId":2,"leaseId":3}')

    def test_unavailable_endpoint_never_counted_as_failure_evidence(self):
        # Invalid endpoint is rejected before network access.
        with self.assertRaises(ValueError):
            fetch_provider_payload('http://example.com:8000', scope())
        with self.assertRaises(ValueError):
            fetch_provider_payload('http://localhost:8000', scope())  # no DNS name
        with self.assertRaises(ValueError):
            fetch_provider_payload('http://127.0.0.1:1', scope(), timeout=float('nan'))

    def test_archive_requires_existing_directory(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(EvidenceError):
                EvidenceArchive(Path(d) / 'missing' / 'a.sqlite')

    def test_default_archive_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(EvidenceArchive(Path(d) / 'new.sqlite').count(), 0)


@unittest.skipUnless(HAS_SIGNATURES, 'eth-account required for EIP-712 and local network integration')
class ProviderCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from signed_http_service import make_server
        cls.server = make_server(0, PKEY, DOMAIN, 4, 2, REQ)
        cls.endpoint = f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.provider = Account.from_key(PKEY).address.lower()
        cls.monitor = Account.from_key(MKEY).address.lower()
        cls.context = VerificationContext(scope(), frozenset({cls.monitor}))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_provider_signature_matches_existing_v1_signed_probe(self):
        from signed_probe import signed_probe
        res = signed_probe(self.endpoint, DOMAIN, self.provider, 4, 2, REQ)
        self.assertEqual(res['kind'], 'SUCCESS')
        self.assertEqual(res['response']['responseHash'], expected_response_hash(REQ))
        self.assertRegex(res['response']['providerSignature'], r'^0x[0-9a-f]{130}$')

    def test_redirect_is_not_followed_even_when_target_is_loopback(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        class Redirector(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(302)
                self.send_header('Location', self_server_endpoint + '/v1/challenge')
                self.end_headers()
            def log_message(self,*args):pass
        self_server_endpoint = self.endpoint
        server = ThreadingHTTPServer(('127.0.0.1',0), Redirector)
        thread = Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with self.assertRaises(TransportFailure):
                fetch_provider_payload(f'http://127.0.0.1:{server.server_port}',scope())
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)

    def test_provider_health_disclaims_chain_verification(self):
        with urlopen(self.endpoint + '/healthz', timeout=2) as r:
            d = json.loads(r.read())
        self.assertFalse(d['chainLeaseVerified'])
        self.assertTrue(d['experimental'])

    def test_bad_request_cannot_ask_provider_to_sign_other_lease(self):
        body = json.dumps({'leaseId':5,'epochId':2,'requestHash':REQ}).encode()
        with self.assertRaises(HTTPError) as ctx:
            urlopen(Request(self.endpoint+'/v1/challenge',body,method='POST'), timeout=2)
        self.assertEqual(ctx.exception.code,400)

    def test_bad_request_cannot_ask_provider_to_sign_other_epoch(self):
        body = json.dumps({'leaseId':4,'epochId':3,'requestHash':REQ}).encode()
        with self.assertRaises(HTTPError):
            urlopen(Request(self.endpoint+'/v1/challenge',body,method='POST'), timeout=2)

    def test_bad_request_cannot_ask_provider_to_sign_other_challenge(self):
        body = json.dumps({'leaseId':4,'epochId':2,'requestHash':'0x'+'ff'*32}).encode()
        with self.assertRaises(HTTPError):
            urlopen(Request(self.endpoint+'/v1/challenge',body,method='POST'), timeout=2)

    def test_noncanonical_duplicate_request_keys_rejected(self):
        raw = b'{"leaseId":4,"leaseId":4,"epochId":2,"requestHash":"' + REQ.encode() + b'"}'
        with self.assertRaises(HTTPError):
            urlopen(Request(self.endpoint+'/v1/challenge',raw,method='POST'), timeout=2)

    def test_missing_and_extra_provider_fields_rejected(self):
        raw = fetch_provider_payload(self.endpoint, scope())
        data = json.loads(raw)
        del data['providerSignature']
        with self.assertRaises(ProviderResponseInvalid):
            validate_provider_payload(json.dumps(data).encode(), DOMAIN, self.provider, scope())
        data['providerSignature'] = '0x'+'11'*65
        data['extra'] = 'ignored?'
        with self.assertRaises(ProviderResponseInvalid):
            validate_provider_payload(json.dumps(data).encode(), DOMAIN, self.provider, scope())

    def test_wrong_provider_is_rejected(self):
        raw = fetch_provider_payload(self.endpoint, scope())
        with self.assertRaises(ProviderResponseInvalid):
            validate_provider_payload(raw, DOMAIN, Account.from_key(OTHER).address.lower(), scope())

    def test_wrong_domain_and_scope_are_rejected(self):
        raw = fetch_provider_payload(self.endpoint, scope())
        with self.assertRaises(ProviderResponseInvalid):
            validate_provider_payload(raw, Domain(1,SETTLEMENT), self.provider, scope())
        with self.assertRaises(ProviderResponseInvalid):
            validate_provider_payload(raw, DOMAIN, self.provider, scope(epoch_id=3))
        with self.assertRaises(ProviderResponseInvalid):
            validate_provider_payload(raw, DOMAIN, self.provider, scope(request_hash='0x'+'04'*32))

    def test_tampered_provider_signature_and_result_rejected(self):
        raw = fetch_provider_payload(self.endpoint, scope())
        for field, value in [('providerSignature', '0x'+'00'*65),('responseHash','0x'+'fe'*32)]:
            with self.subTest(field=field):
                data = json.loads(raw)
                data[field] = value
                with self.assertRaises(ProviderResponseInvalid):
                    validate_provider_payload(json.dumps(data).encode(), DOMAIN, self.provider, scope())

    def test_capture_stores_exact_wire_bytes_and_reopen_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.sqlite'
            archive = EvidenceArchive(path)
            cap = capture_response(self.endpoint, DOMAIN, self.provider, scope(), MKEY,
                                   self.context, archive, nonce='0x'+'ae'*32)
            self.assertIsInstance(cap, CaptureResult)
            self.assertEqual(archive.count(),1)
            self.assertTrue(cap.stored_new)
            envelope, raw = EvidenceArchive(path).load(cap.evidence_id, self.context, DOMAIN, self.provider)
            self.assertEqual(raw, cap.raw_bytes)
            self.assertEqual(envelope['record']['payloadHash'],
                             verify_observation(envelope,self.context).record.payload_hash)
            self.assertTrue(verify_payload(verify_observation(envelope,self.context).record,raw))

    def test_monitor_signature_maps_only_to_raw_observation(self):
        from sse_evidence_wire_v1 import to_wp07_raw
        from sse_evidence_policy_v1 import RawKind, QualifiedFact
        with tempfile.TemporaryDirectory() as d:
            archive=EvidenceArchive(Path(d)/'archive.sqlite')
            cap=capture_response(self.endpoint,DOMAIN,self.provider,scope(),MKEY,self.context,archive)
            env,raw=archive.load(cap.evidence_id,self.context,DOMAIN,self.provider)
            item=verify_observation(env,self.context)
            self.assertEqual(item.record.kind,ObservationKind.RESPONSE_SEEN)
            self.assertEqual(to_wp07_raw(item).kind, RawKind.MONITOR_SUCCESS)
            self.assertFalse(isinstance(item,QualifiedFact))

    def test_capture_idempotent_for_same_nonce_and_response(self):
        with tempfile.TemporaryDirectory() as d:
            archive=EvidenceArchive(Path(d)/'archive.sqlite')
            nonce='0x'+'aa'*32
            a=capture_response(self.endpoint, DOMAIN, self.provider, scope(), MKEY, self.context,archive,nonce=nonce)
            # Explicitly use fixed claimed timestamp interval: raw event time varies by second otherwise.
            env,raw=archive.load(a.evidence_id,self.context,DOMAIN,self.provider)
            self.assertEqual(archive.insert(env,raw,self.context,DOMAIN,self.provider),(a.evidence_id,False))
            self.assertEqual(archive.count(),1)

    def test_nonce_conflict_rejected_persistently(self):
        from sse_evidence_wire_v1 import ObservationRecord, sign_observation, payload_commitment
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'archive.sqlite'
            archive=EvidenceArchive(path)
            result=capture_response(self.endpoint,DOMAIN,self.provider,scope(),MKEY,self.context,archive,nonce='0x'+'aa'*32)
            env,raw=archive.load(result.evidence_id,self.context,DOMAIN,self.provider)
            orig=verify_observation(env,self.context).record
            other=ObservationRecord(scope(),ObservationKind.RESPONSE_SEEN,orig.response_hash,
                                    payload_commitment(raw),orig.event_time_lower+1,
                                    orig.event_time_upper+1,orig.nonce)
            env2=sign_observation(other,MKEY)
            with self.assertRaises(EvidenceReplay):
                EvidenceArchive(path).insert(env2,raw,self.context,DOMAIN,self.provider)
            self.assertEqual(EvidenceArchive(path).count(),1)

    def test_tamper_archive_bytes_detected_on_read(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'archive.sqlite'
            archive=EvidenceArchive(path)
            result=capture_response(self.endpoint,DOMAIN,self.provider,scope(),MKEY,self.context,archive)
            import sqlite3
            from contextlib import closing
            # sqlite3.Connection.__exit__ commits/rolls back, but does NOT close.
            # On Windows, tempfile cannot remove a SQLite file held open by a connection.
            with closing(sqlite3.connect(path)) as conn:
                with conn:
                    conn.execute('UPDATE records SET provider_raw=? WHERE evidence_id=?',
                                 (b'{}', result.evidence_id))
            with self.assertRaises(EvidenceError):
                EvidenceArchive(path).load(result.evidence_id,self.context,DOMAIN,self.provider)

    def test_unauthorized_monitor_cannot_capture_or_store(self):
        wrong=VerificationContext(scope(),frozenset({Account.from_key(OTHER).address.lower()}))
        with tempfile.TemporaryDirectory() as d:
            archive=EvidenceArchive(Path(d)/'archive.sqlite')
            with self.assertRaises(AuthenticationError):
                capture_response(self.endpoint,DOMAIN,self.provider,scope(),MKEY,wrong,archive)
            self.assertEqual(archive.count(),0)

    def test_invalid_provider_never_mints_monitor_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            archive=EvidenceArchive(Path(d)/'archive.sqlite')
            with patch('sse_http_signed_delivery_v1.fetch_provider_payload',return_value=b'{"error":"fake"}'):
                with self.assertRaises(ProviderResponseInvalid):
                    capture_response(self.endpoint,DOMAIN,self.provider,scope(),MKEY,self.context,archive)
            self.assertEqual(archive.count(),0)

    def test_nonresponsive_provider_is_not_turned_into_negative_fulfillment_fact(self):
        with tempfile.TemporaryDirectory() as d:
            archive=EvidenceArchive(Path(d)/'archive.sqlite')
            with patch('sse_http_signed_delivery_v1.fetch_provider_payload',side_effect=TransportFailure('timeout')):
                with self.assertRaises(TransportFailure):
                    capture_response(self.endpoint,DOMAIN,self.provider,scope(),MKEY,self.context,archive)
            self.assertEqual(archive.count(),0)

    def test_archive_rejects_mismatched_payload_bytes(self):
        from sse_evidence_wire_v1 import ObservationRecord, sign_observation, payload_commitment
        raw=fetch_provider_payload(self.endpoint,scope())
        obs=ObservationRecord(scope(),ObservationKind.RESPONSE_SEEN, expected_response_hash(REQ),
                              payload_commitment(raw), 100,101,'0x'+'55'*32)
        env=sign_observation(obs,MKEY)
        with tempfile.TemporaryDirectory() as d:
            archive=EvidenceArchive(Path(d)/'archive.sqlite')
            with self.assertRaises(EvidenceError):
                archive.insert(env,raw+b' ',self.context,DOMAIN,self.provider)
            self.assertEqual(archive.count(),0)

    def test_block_anchor_is_atomic_with_verified_raw_payload(self):
        from sse_wp08c_chain_binding import ChainCaptureBinding
        from sse_wp08d_provenance import SnapshotReorganized, ProvenanceError
        from contextlib import closing
        import sqlite3

        blockhash = '0x'+'ab'*32

        class ChainRPC:
            block = blockhash

            def request(self, method, params):
                if method not in ('eth_getBlockByNumber', 'eth_getBlockByHash'):
                    raise AssertionError('unexpected RPC method')
                return {'hash': self.block, 'number': hex(50), 'timestamp': hex(1000)}

        rpc = ChainRPC()
        bound = ChainCaptureBinding(self.context, self.provider, 50, 1000, blockhash)
        with tempfile.TemporaryDirectory() as folder:
            dbpath = Path(folder) / 'archive.sqlite'
            archive = EvidenceArchive(dbpath)
            saved = capture_response(self.endpoint, DOMAIN, self.provider, scope(), MKEY,
                                     self.context, archive, nonce='0x'+'a1'*32,
                                     chain_binding=bound, rpc=rpc)
            envelope, raw, pinned = EvidenceArchive(dbpath).load_anchored(
                saved.evidence_id, self.context, DOMAIN, self.provider, rpc)
            self.assertEqual(raw, saved.raw_bytes)
            self.assertEqual(pinned.evidence_id, saved.evidence_id)
            self.assertEqual(pinned.block_hash, blockhash)
            with closing(sqlite3.connect(dbpath)) as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM chain_anchors').fetchone()[0], 1)
                # Tampering the separately signed snapshot cannot keep attribution.
                with conn:
                    conn.execute('UPDATE chain_anchors SET anchor_envelope=? WHERE evidence_id=?',
                                 ('{}', saved.evidence_id))
            with self.assertRaises(ProvenanceError):
                EvidenceArchive(dbpath).load_anchored(
                    saved.evidence_id, self.context, DOMAIN, self.provider, rpc)
            self.assertEqual(archive.count(), 1)

    def test_legacy_unsigned_snapshot_does_not_get_provenance_implicitly(self):
        from sse_wp08d_provenance import ProvenanceError
        with tempfile.TemporaryDirectory() as folder:
            archive = EvidenceArchive(Path(folder) / 'archive.sqlite')
            saved = capture_response(self.endpoint, DOMAIN, self.provider, scope(), MKEY,
                                     self.context, archive)
            with self.assertRaisesRegex(ProvenanceError, 'no signed'):
                archive.load_anchored(saved.evidence_id, self.context,
                                      DOMAIN, self.provider, object())

    def test_reorg_prevents_atomic_capture_insert(self):
        from sse_wp08c_chain_binding import ChainCaptureBinding
        from sse_wp08d_provenance import SnapshotReorganized

        class ReorgRPC:
            def request(self, method, params):
                return None

        bound = ChainCaptureBinding(self.context, self.provider, 50, 1000,
                                    '0x'+'ab'*32)
        with tempfile.TemporaryDirectory() as folder:
            archive = EvidenceArchive(Path(folder) / 'archive.sqlite')
            with self.assertRaises(SnapshotReorganized):
                capture_response(self.endpoint, DOMAIN, self.provider, scope(), MKEY,
                                 self.context, archive, chain_binding=bound,
                                 rpc=ReorgRPC())
            self.assertEqual(archive.count(), 0)

    def test_direct_signing_key_is_never_present_in_http_body(self):
        raw=fetch_provider_payload(self.endpoint,scope())
        self.assertNotIn(PKEY.encode(),raw)
        self.assertNotIn(MKEY.encode(),raw)

    def test_restarted_process_can_read_existing_archive(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'archive.sqlite'
            first=EvidenceArchive(path)
            cap=capture_response(self.endpoint,DOMAIN,self.provider,scope(),MKEY,self.context,first)
            del first
            second=EvidenceArchive(path)
            self.assertEqual(second.count(),1)
            env,raw=second.load(cap.evidence_id,self.context,DOMAIN,self.provider)
            self.assertTrue(raw)
            self.assertEqual(env['signer'],self.monitor)

    def test_separate_provider_and_monitor_processes(self):
        """Actual subprocess processes and loopback HTTP, not a mocked function call."""
        from signed_http_service import make_server
        with tempfile.TemporaryDirectory() as d:
            # Pick an unused local TCP port. The short release->bind race only causes a test failure.
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0))
                port=sock.getsockname()[1]
            env=os.environ.copy()
            env['SSE_WP08B_PROVIDER_KEY']=PKEY
            args=[sys.executable,str(ROOT/'services'/'provider-agent'/'signed_http_service.py'),
                  '--port',str(port),'--chain-id','31337','--settlement',SETTLEMENT,
                  '--lease-id','4','--epoch-id','2','--request-hash',REQ]
            proc=subprocess.Popen(args,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            try:
                ready=False
                for _ in range(40):
                    if proc.poll() is not None:
                        break
                    try:
                        with urlopen(f'http://127.0.0.1:{port}/healthz',timeout=.3) as res:
                            ready=(res.status==200)
                        if ready:break
                    except OSError:
                        time.sleep(.1)
                self.assertTrue(ready,'provider did not start')
                monitor_env=os.environ.copy()
                monitor_env['SSE_WP08B_MONITOR_KEY']=MKEY
                archive_path=Path(d)/'evidence.sqlite'
                cmd=[sys.executable,str(ROOT/'services'/'monitor-agent'/'evidence_capture.py'),
                     '--endpoint',f'http://127.0.0.1:{port}', '--chain-id','31337',
                     '--settlement',SETTLEMENT,'--lease-id','4','--epoch-id','2',
                     '--sla-policy-hash',SLA,'--resource-profile-hash',RESOURCE,
                     '--request-hash',REQ,'--provider',self.provider,'--archive',str(archive_path)]
                output=subprocess.run(cmd,env=monitor_env,check=True,capture_output=True,text=True,timeout=15)
                self.assertIn('physical consumer delivery NOT proven',output.stdout)
                self.assertEqual(EvidenceArchive(archive_path).count(),1)
            finally:
                proc.terminate()
                try:proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill();proc.communicate(timeout=5)


if __name__=='__main__':
    unittest.main()
