"""WP-14: durable V2 HTTP+monitor+historical-block provenance tests.

Uses a synthetic trusted-RPC input and an actual localhost signed HTTP server.
The tests DO NOT authenticate Ethereum consensus or physical consumer delivery.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "services" / "provider-agent"))
sys.path.insert(0, str(ROOT / "services" / "monitor-agent"))

from test_sse_v2_chain_authority_v1 import (
    BLOCK, CHAIN, CONTROLLER, POOL, PROFILE, REQUEST, SLA,
    FakeV2RPC, code_hash, scope, spec,
)
from sse_challenge import expected_response_hash, keccak256
from sse_evidence_wire_v1 import (
    AuthenticationError, EvidenceError, EvidenceReplay, ObservationKind,
    ObservationRecord, sign_observation, payload_commitment, ZERO_HASH,
)
from sse_http_signed_delivery_v1 import (
    EvidenceArchive, ProviderResponseInvalid, fetch_provider_payload,
)
from sse_v2_chain_authority_v1 import (
    V2AuthorityError, read_v2_authority,
)
from sse_v2_provenance_archive_v1 import (
    V2ProvenanceArchive, V2ArchiveError,
)

try:
    from eth_account import Account
    from signed_http_service import make_server
    from typed_evidence import Domain
    CRYPTO = True
except ImportError:
    CRYPTO = False

PKEY = "0x" + "21"*32
MKEY = "0x" + "22"*32
OUTSIDER_KEY = "0x" + "23"*32
NONCE = "0x" + "99"*32


class ArchiveInitTests(unittest.TestCase):
    def test_missing_parent_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(V2ArchiveError):
                V2ProvenanceArchive(Path(d) / "missing" / "archive.sqlite")

    def test_empty_new_and_reopened_archive(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "archive.sqlite"
            self.assertEqual(V2ProvenanceArchive(db).count(), 0)
            self.assertEqual(V2ProvenanceArchive(db).count(), 0)

    def test_archive_directory_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(V2ArchiveError):
                V2ProvenanceArchive(d)


@unittest.skipUnless(CRYPTO, "Ethereum EIP712 libraries required")
class V2ProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(0, PKEY, Domain(CHAIN, CONTROLLER), 1, 0, REQUEST)
        cls.root = f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.provider = Account.from_key(PKEY).address.lower()
        cls.monitor = Account.from_key(MKEY).address.lower()
        cls.other = Account.from_key(OUTSIDER_KEY).address.lower()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "v2.sqlite"
        self.archive = V2ProvenanceArchive(self.path)
        self.rpc = FakeV2RPC()
        self.rpc.lease["provider"] = self.provider
        self.rpc.assignment["provider"] = self.provider
        self.rpc.lease["endpointHash"] = "0x" + keccak256(self.root.encode()).hex()
        self.rpc.members[0] = self.monitor
        self.rpc.tickets[self.monitor] = {
            "joined": True, "paid": True, "everSelected": True,
            "confirmed": True, "noShow": False}
        self.spec = spec(endpoint=self.root)
        self.anchor = (50, BLOCK)
        self.raw = fetch_provider_payload(self.root, scope())

    def envelope(self, *, nonce=NONCE, lower=1100, upper=1101,
                 key=MKEY, kind=ObservationKind.RESPONSE_SEEN):
        record = ObservationRecord(
            scope(), kind,
            expected_response_hash(REQUEST) if kind is ObservationKind.RESPONSE_SEEN else ZERO_HASH,
            payload_commitment(self.raw), lower, upper, nonce)
        return sign_observation(record, key)

    def insert(self, envelope=None, raw=None):
        return self.archive.insert_verified(
            self.rpc, self.spec, self.anchor,
            self.envelope() if envelope is None else envelope,
            self.raw if raw is None else raw)

    def modify_db(self, statement, params=()):
        with closing(sqlite3.connect(self.path)) as conn:
            with conn:
                conn.execute(statement, params)

    def stored(self, entry):
        return self.archive.load_verified(self.rpc, self.spec, entry.entry_id)

    def test_actual_local_http_signed_capture_with_atomic_reference(self):
        saved = self.archive.capture(self.rpc, self.spec, MKEY, nonce=NONCE)
        self.assertTrue(saved.new_record)
        self.assertEqual(saved.signer, self.monitor)
        self.assertEqual(saved.provider_bytes, self.raw)
        self.assertEqual(saved.block_hash, BLOCK)
        self.assertEqual(saved.block_number, 50)
        self.assertEqual(self.archive.count(), 1)
        loaded = self.stored(saved)
        self.assertEqual(loaded.provider_bytes, self.raw)
        self.assertEqual(loaded.monitor_envelope, saved.monitor_envelope)
        self.assertEqual(loaded.reference_commitment, saved.reference_commitment)
        self.assertFalse(loaded.new_record)

    def test_one_transaction_preserves_exact_provider_bytes_and_signature(self):
        saved = self.insert()
        with closing(sqlite3.connect(self.path)) as conn:
            fields = conn.execute(
                "SELECT reference_bytes, provider_bytes, envelope_bytes FROM v2_observations"
            ).fetchone()
        reference, raw, envelope_bytes = fields
        self.assertEqual(raw, self.raw)
        self.assertEqual(json.loads(reference)["blockHash"], BLOCK)
        self.assertEqual(json.loads(reference)["committee"][0], self.monitor)
        self.assertEqual(json.loads(envelope_bytes)["signature"], saved.monitor_envelope["signature"])
        self.assertEqual(saved.reference_commitment, "0x" + keccak256(
            b"SSE_V2_AUTHORITY_REFERENCE_V1\x00" + reference).hex())

    def test_reopen_after_restart_rechecks_historical_identity(self):
        saved = self.insert()
        reopened = V2ProvenanceArchive(self.path)
        loaded = reopened.load_verified(self.rpc, self.spec, saved.entry_id)
        self.assertEqual(loaded.entry_id, saved.entry_id)
        self.assertEqual(loaded.signer, self.monitor)
        self.assertEqual(reopened.count(), 1)

    def test_same_nonce_same_record_and_anchor_idempotent(self):
        env = self.envelope()
        a = self.insert(env)
        b = self.insert(env)
        self.assertTrue(a.new_record)
        self.assertFalse(b.new_record)
        self.assertEqual(a.entry_id, b.entry_id)
        self.assertEqual(self.archive.count(), 1)

    def test_nonce_conflict_with_changed_record_rejected_after_restart(self):
        self.insert()
        restarted = V2ProvenanceArchive(self.path)
        env = self.envelope(lower=1102, upper=1103)
        with self.assertRaises(EvidenceReplay):
            restarted.insert_verified(self.rpc, self.spec, self.anchor, env, self.raw)
        self.assertEqual(restarted.count(), 1)

    def test_nonce_conflict_with_different_block_anchor_rejected(self):
        self.insert()
        self.rpc.block_hash = "0x" + "77"*32
        self.rpc.rechecked_hash = self.rpc.block_hash
        other_anchor = (50, self.rpc.block_hash)
        with self.assertRaises(EvidenceReplay):
            self.archive.insert_verified(
                self.rpc, self.spec, other_anchor, self.envelope(), self.raw)
        self.assertEqual(self.archive.count(), 1)

    def test_different_nonce_can_store_distinct_entry_same_block(self):
        a = self.insert(self.envelope(nonce=NONCE))
        b = self.insert(self.envelope(nonce="0x" + "98"*32))
        self.assertNotEqual(a.entry_id, b.entry_id)
        self.assertEqual(self.archive.count(), 2)

    def test_incorrect_monitor_signature_is_never_archived(self):
        with self.assertRaises(AuthenticationError):
            self.insert(self.envelope(key=OUTSIDER_KEY))
        self.assertEqual(self.archive.count(), 0)

    def test_selected_but_not_confirmed_monitor_rejected(self):
        self.rpc.tickets[self.monitor]["confirmed"] = False
        with self.assertRaises(V2AuthorityError):
            self.insert()
        self.assertEqual(self.archive.count(), 0)

    def test_unconfirmed_monitor_key_rejected_before_http_capture(self):
        with self.assertRaises(AuthenticationError):
            self.archive.capture(self.rpc, self.spec, OUTSIDER_KEY)
        self.assertEqual(self.archive.count(), 0)

    def test_invalid_provider_response_never_archived(self):
        with self.assertRaises(EvidenceError):
            self.insert(raw=b"{}")
        self.assertEqual(self.archive.count(), 0)

    def test_signed_timeout_is_not_a_physical_delivery_failure(self):
        with self.assertRaises(V2ArchiveError):
            self.insert(self.envelope(kind=ObservationKind.LOCAL_TIMEOUT))
        self.assertEqual(self.archive.count(), 0)

    def test_body_tampering_is_detected_on_load(self):
        entry = self.insert()
        self.modify_db("UPDATE v2_observations SET provider_bytes=?", (b'{}',))
        with self.assertRaises(EvidenceError):
            self.stored(entry)

    def test_monitor_signature_tampering_detected_on_load(self):
        entry = self.insert()
        envelope = dict(entry.monitor_envelope)
        envelope["signature"] = "0x" + "00"*65
        raw = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
        self.modify_db("UPDATE v2_observations SET envelope_bytes=?", (raw,))
        with self.assertRaises(EvidenceError):
            self.stored(entry)

    def test_authority_snapshot_payload_tamper_detected(self):
        entry = self.insert()
        with closing(sqlite3.connect(self.path)) as conn:
            raw = conn.execute("SELECT reference_bytes FROM v2_observations").fetchone()[0]
        record = json.loads(raw)
        record["quorum"] = 2
        modified = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        self.modify_db("UPDATE v2_observations SET reference_bytes=?", (modified,))
        with self.assertRaises(V2ArchiveError):
            self.stored(entry)

    def test_authority_snapshot_commitment_tamper_detected(self):
        entry = self.insert()
        self.modify_db("UPDATE v2_observations SET reference_commitment=?",
                       ("0x" + "ff"*32,))
        with self.assertRaises(V2ArchiveError):
            self.stored(entry)

    def test_duplicate_json_properties_in_stored_reference_rejected(self):
        entry = self.insert()
        self.modify_db("UPDATE v2_observations SET reference_bytes=?",
                       (b'{"blockHash":"0x0","blockHash":"0x1"}',))
        with self.assertRaises(V2ArchiveError):
            self.stored(entry)

    def test_noncanonical_envelope_json_rejected(self):
        entry = self.insert()
        raw = json.dumps(entry.monitor_envelope, indent=2).encode()
        self.modify_db("UPDATE v2_observations SET envelope_bytes=?", (raw,))
        with self.assertRaises(V2ArchiveError):
            self.stored(entry)

    def test_stored_signer_metadata_tamper_detected(self):
        entry = self.insert()
        self.modify_db("UPDATE v2_observations SET signer=?", (self.other,))
        with self.assertRaises(V2ArchiveError):
            self.stored(entry)

    def test_stored_evidence_id_metadata_tamper_detected(self):
        entry = self.insert()
        self.modify_db("UPDATE v2_observations SET evidence_id=?",
                       ("0x" + "ee"*32,))
        with self.assertRaises(V2ArchiveError):
            self.stored(entry)

    def test_historical_block_reorganization_rejected(self):
        entry = self.insert()
        self.rpc.rechecked_hash = "0x" + "77"*32
        with self.assertRaises(V2AuthorityError):
            self.stored(entry)

    def test_archived_block_cannot_be_ahead_of_finalized_head(self):
        entry = self.insert()
        self.rpc.block_number = 49
        with self.assertRaises(V2AuthorityError):
            self.stored(entry)

    def test_new_chain_code_invalidates_archive_reverification(self):
        entry = self.insert()
        self.rpc.codes[POOL] = "0x6001"
        with self.assertRaises(V2AuthorityError):
            self.stored(entry)

    def test_reverification_requires_same_external_trust_spec(self):
        entry = self.insert()
        changed = spec(endpoint=self.root, pool_code_hash="0x" + "88"*32)
        with self.assertRaises(V2AuthorityError):
            self.archive.load_verified(self.rpc, changed, entry.entry_id)

    def test_finality_mode_cannot_be_silently_changed(self):
        entry = self.insert()
        unfinalized = spec(endpoint=self.root, block_tag="latest", allow_unfinalized=True)
        with self.assertRaises(V2ArchiveError):
            self.archive.load_verified(self.rpc, unfinalized, entry.entry_id)

    def test_excessive_or_broken_archive_entry_id_rejected(self):
        with self.assertRaises(V2ArchiveError):
            self.archive.load_verified(self.rpc, self.spec, "no-id")
        with self.assertRaises(KeyError):
            self.archive.load_verified(self.rpc, self.spec, "0x" + "ff"*32)

    def test_sqlite_trigger_failure_rolls_back_entire_insert(self):
        self.modify_db("""CREATE TRIGGER refuse_write BEFORE INSERT ON v2_observations
                         BEGIN SELECT RAISE(ABORT, 'injected transactional failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert()
        self.assertEqual(self.archive.count(), 0)
        self.modify_db("DROP TRIGGER refuse_write")
        saved = self.insert()
        self.assertEqual(self.archive.count(), 1)
        self.assertTrue(saved.new_record)

    def test_concurrent_writers_are_serialized_and_replay_safe(self):
        envelope = self.envelope()
        def work(_):
            return self.insert(envelope)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(work, range(4)))
        self.assertEqual(self.archive.count(), 1)
        self.assertEqual(len({x.entry_id for x in results}), 1)
        self.assertEqual(sum(x.new_record for x in results), 1)

    def test_coexistence_with_old_wp08b_table_does_not_modify_it(self):
        self.insert()
        old = EvidenceArchive(self.path)
        self.assertEqual(old.count(), 0)
        self.assertEqual(self.archive.count(), 1)
        self.assertEqual(V2ProvenanceArchive(self.path).count(), 1)

    def test_historical_anchor_requires_correct_positive_height(self):
        with self.assertRaises(V2AuthorityError):
            read_v2_authority(self.rpc, self.spec, historical_anchor=(0, BLOCK))
        with self.assertRaises(V2AuthorityError):
            read_v2_authority(self.rpc, self.spec, historical_anchor=(51, BLOCK))
        with self.assertRaises(V2AuthorityError):
            read_v2_authority(self.rpc, self.spec,
                              historical_anchor=(50, "0x" + "66"*32))

    def test_historical_recheck_all_state_calls_pin_original_block(self):
        self.insert()
        self.rpc.calls.clear()
        entry = self.archive.load_verified(
            self.rpc, self.spec,
            self.archive.insert_verified(self.rpc, self.spec, self.anchor, self.envelope(), self.raw).entry_id)
        self.assertEqual(entry.block_hash, BLOCK)
        calls = [(method, params) for method, params in self.rpc.calls
                 if method in ("eth_call", "eth_getCode")]
        self.assertGreater(len(calls), 15)
        self.assertTrue(all(params[-1] == {
            "blockHash": BLOCK, "requireCanonical": True} for _, params in calls))

    def test_historical_canonical_block_survives_new_finalized_head(self):
        entry = self.insert()
        original_request = self.rpc.request
        newer = "0x" + "65"*32
        def advanced_rpc(method, params):
            if method == "eth_getBlockByNumber" and params[0] == "finalized":
                return {"number": hex(51), "hash": newer, "timestamp": hex(1700)}
            return original_request(method, params)
        self.rpc.request = advanced_rpc
        result = self.stored(entry)
        self.assertEqual(result.block_hash, BLOCK)
        self.assertEqual(result.block_number, 50)

    def test_no_eth_send_transaction_in_capture_or_load(self):
        entry = self.archive.capture(self.rpc, self.spec, MKEY, nonce=NONCE)
        self.stored(entry)
        self.assertFalse(any(m.startswith("eth_send") for m, _ in self.rpc.calls))


if __name__ == "__main__":
    unittest.main()
