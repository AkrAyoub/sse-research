"""WP-14: atomic SQLite provenance archive for authenticated V2 RAW observations.

An entry binds exact HTTP bytes, provider+monitor EIP-712 signatures, and the
original canonical-block-pinned V2 authority reference in ONE transaction.
At both insertion and read, the authority is reconstructed from an independently
provided V2AuthoritySpec and a trusted RPC at that historical block.

Does NOT independently prove Ethereum consensus, physical consumer receipt,
monitor independence, message timeliness, or entitlement to automatic payouts.
The legacy WP-08B ProviderResponse wire domain is distinct from the V2
controller's bilateral EIP-712 allocation domain.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import json
import math
from pathlib import Path
import secrets
import sqlite3
import time

from sse_challenge import keccak256
from sse_evidence_wire_v1 import (
    AuthenticationError, EvidenceError, EvidenceReplay, ObservationKind,
    ObservationRecord, payload_commitment, sign_observation, verify_observation,
    verify_payload,
)
from sse_http_signed_delivery_v1 import (
    fetch_provider_payload, validate_provider_payload,
)
from sse_v2_chain_authority_v1 import (
    V2AuthoritySpec, V2AuthoritySnapshot, V2AuthorityError,
    read_v2_authority,
)

REFERENCE_PREFIX = b"SSE_V2_AUTHORITY_REFERENCE_V1\x00"
ENTRY_PREFIX = b"SSE_V2_ARCHIVE_ENTRY_V1\x00"
MAX_REF_BYTES = 8192
MAX_ENVELOPE_BYTES = 8192


class V2ArchiveError(EvidenceError):
    """Archived evidence or its provenance could not be verified."""


@dataclass(frozen=True)
class ArchivedV2Observation:
    """Authenticated RAW observation and pinned RPC attribution, NOT QualifiedFact."""
    entry_id: str
    evidence_id: str
    signer: str
    block_number: int
    block_hash: str
    reference_commitment: str
    provider_bytes: bytes
    monitor_envelope: dict
    new_record: bool


def _strict_canonical_object(raw: bytes, max_bytes: int, name: str) -> dict:
    if type(raw) is not bytes or not 1 <= len(raw) <= max_bytes:
        raise V2ArchiveError(f"{name} missing or exceeds record limit")
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise V2ArchiveError(f"{name} duplicate JSON key")
            out[key] = value
        return out
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
    except (ValueError, UnicodeError, TypeError) as exc:
        raise V2ArchiveError(f"{name} is not canonical ASCII JSON") from exc
    if type(value) is not dict:
        raise V2ArchiveError(f"{name} must be a JSON object")
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False).encode("ascii")
    if raw != canonical:
        raise V2ArchiveError(f"{name} JSON encoding differs from canonical bytes")
    return value


def _envelope_bytes(envelope: object) -> bytes:
    if type(envelope) is not dict:
        raise V2ArchiveError("signed envelope must be an object")
    try:
        result = json.dumps(envelope, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise V2ArchiveError("invalid signed envelope structure") from exc
    _strict_canonical_object(result, MAX_ENVELOPE_BYTES, "monitor envelope")
    return result


def _entry_id(evidence_id: str, signer: str, reference_commitment: str) -> str:
    try:
        return "0x" + keccak256(
            ENTRY_PREFIX + bytes.fromhex(evidence_id[2:]) +
            bytes.fromhex(signer[2:]) + bytes.fromhex(reference_commitment[2:])
        ).hex()
    except (ValueError, TypeError) as exc:
        raise V2ArchiveError("invalid archive identity fields") from exc


def _verify_raw(snapshot: V2AuthoritySnapshot, envelope: dict,
                provider_bytes: bytes):
    from typed_evidence import Domain  # legacy V1 off-chain ProviderResponse domain
    item = verify_observation(envelope, snapshot.context())
    if item.record.kind is not ObservationKind.RESPONSE_SEEN:
        raise V2ArchiveError("this archive accepts positive authenticated HTTP responses only")
    if not verify_payload(item.record, provider_bytes):
        raise V2ArchiveError("HTTP body differs from signed observation payload commitment")
    verified_provider = validate_provider_payload(
        provider_bytes, Domain(snapshot.chain_id, snapshot.controller),
        snapshot.provider, snapshot.scope)
    if verified_provider["responseHash"] != item.record.response_hash:
        raise V2ArchiveError("provider signature and monitor response commitment disagree")
    return item


class V2ProvenanceArchive:
    """One-file append-only-by-API SQLite log; host-disk adversary remains in scope.

    The schema protects crash consistency, nonce collision and response tampering
    when a verifier reopens the archive. An administrator with raw DB access
    can delete the entire database or replace its contents; external append-only
    publication and independent availability remain separate research work.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.parent.is_dir():
            raise V2ArchiveError("archive parent directory does not exist")
        if self.path.exists() and not self.path.is_file():
            raise V2ArchiveError("archive destination must be a regular file")
        with closing(self._db()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS v2_observations (
                    entry_id TEXT PRIMARY KEY,
                    chain_id TEXT NOT NULL,
                    controller TEXT NOT NULL,
                    lease_id TEXT NOT NULL,
                    epoch_id TEXT NOT NULL,
                    signer TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    reference_commitment TEXT NOT NULL,
                    reference_bytes BLOB NOT NULL,
                    provider_bytes BLOB NOT NULL,
                    envelope_bytes BLOB NOT NULL,
                    UNIQUE(chain_id,controller,lease_id,epoch_id,signer,nonce)
                );
            """)

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def count(self) -> int:
        with closing(self._db()) as db:
            return int(db.execute("SELECT COUNT(*) FROM v2_observations").fetchone()[0])

    def insert_verified(self, rpc, spec: V2AuthoritySpec,
                        historical_anchor: tuple[int, str],
                        monitor_envelope: dict, provider_bytes: bytes
                        ) -> ArchivedV2Observation:
        """Reread/re-authenticate the exact historical chain state before storage.

        The caller may suggest a block reference, but MUST NOT invent authorization
        merely by constructing a V2AuthoritySnapshot dataclass.
        """
        if not isinstance(spec, V2AuthoritySpec):
            raise V2ArchiveError("independent V2 authority specification is required")
        snapshot = read_v2_authority(rpc, spec, historical_anchor=historical_anchor)
        item = _verify_raw(snapshot, monitor_envelope, provider_bytes)
        ref = snapshot.canonical_bytes()
        envelope_bytes = _envelope_bytes(monitor_envelope)
        if len(ref) > MAX_REF_BYTES:
            raise V2ArchiveError("authority reference exceeds size limit")
        commitment = snapshot.commitment()
        entry_id = _entry_id(item.evidence_id, item.signer, commitment)
        s = snapshot.scope
        key = (str(s.chain_id), snapshot.controller, str(s.lease_id),
               str(s.epoch_id), item.signer, item.record.nonce)
        row = (entry_id, *key, item.evidence_id, commitment,
               ref, provider_bytes, envelope_bytes)

        with closing(self._db()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                previous = db.execute("""
                    SELECT entry_id,chain_id,controller,lease_id,epoch_id,signer,nonce,
                           evidence_id,reference_commitment,reference_bytes,
                           provider_bytes,envelope_bytes FROM v2_observations
                    WHERE chain_id=? AND controller=? AND lease_id=? AND epoch_id=?
                      AND signer=? AND nonce=?
                """, key).fetchone()
                if previous is not None:
                    if previous != row:
                        raise EvidenceReplay("nonce reused with different evidence or block reference")
                    db.execute("COMMIT")
                    return ArchivedV2Observation(
                        entry_id, item.evidence_id, item.signer, snapshot.block_number,
                        snapshot.block_hash, commitment, provider_bytes, monitor_envelope, False)
                db.execute("""
                    INSERT INTO v2_observations (
                        entry_id,chain_id,controller,lease_id,epoch_id,signer,nonce,
                        evidence_id,reference_commitment,reference_bytes,
                        provider_bytes,envelope_bytes
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, row)
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise

        return ArchivedV2Observation(
            entry_id, item.evidence_id, item.signer, snapshot.block_number,
            snapshot.block_hash, commitment, provider_bytes, monitor_envelope, True)

    def load_verified(self, rpc, spec: V2AuthoritySpec,
                      entry_id: str) -> ArchivedV2Observation:
        """Reconstruct the archived state at its ORIGINAL historical block.

        Never authorize from the stored reference alone, and never silently
        replace that historical block with the current pool roster or epoch.
        """
        if not isinstance(spec, V2AuthoritySpec):
            raise V2ArchiveError("independent authority specification required")
        if type(entry_id) is not str or len(entry_id) != 66 or not entry_id.startswith("0x"):
            raise V2ArchiveError("invalid archive entry ID")
        with closing(self._db()) as db:
            row = db.execute("""
                SELECT entry_id,chain_id,controller,lease_id,epoch_id,signer,nonce,
                       evidence_id,reference_commitment,reference_bytes,
                       provider_bytes,envelope_bytes FROM v2_observations
                WHERE entry_id=?
            """, (entry_id,)).fetchone()
        if row is None:
            raise KeyError("archived V2 evidence entry does not exist")
        (stored_id, chain_id, controller, lease_id, epoch_id, signer, nonce,
         evidence_id, commitment, reference_bytes, provider_bytes, envelope_bytes) = row
        reference = _strict_canonical_object(reference_bytes, MAX_REF_BYTES, "authority reference")
        envelope = _strict_canonical_object(envelope_bytes, MAX_ENVELOPE_BYTES, "monitor envelope")
        if reference.get("schema") != "sse-v2-rpc-authority-reference-v1":
            raise V2ArchiveError("unexpected authority reference schema")
        height, block_hash = reference.get("blockNumber"), reference.get("blockHash")
        if (type(height) is not int or height < 1 or
                type(block_hash) is not str):
            raise V2ArchiveError("invalid archived canonical block reference")
        if reference.get("requestedTag") != spec.block_tag:
            raise V2ArchiveError("archived finality assumption differs from verification configuration")

        snapshot = read_v2_authority(
            rpc, spec, historical_anchor=(height, block_hash))
        if (snapshot.canonical_bytes() != reference_bytes or
                snapshot.commitment() != commitment or
                "0x" + keccak256(REFERENCE_PREFIX + reference_bytes).hex() != commitment):
            raise V2ArchiveError("stored authority reference differs from chain-reconstructed state")
        item = _verify_raw(snapshot, envelope, provider_bytes)
        s = snapshot.scope
        expected_key = (str(s.chain_id), snapshot.controller,
                        str(s.lease_id), str(s.epoch_id),
                        item.signer, item.record.nonce)
        if ((chain_id, controller, lease_id, epoch_id, signer, nonce) != expected_key or
                evidence_id != item.evidence_id or
                stored_id != _entry_id(item.evidence_id, item.signer, snapshot.commitment())):
            raise V2ArchiveError("stored archive metadata differs from authenticated evidence")
        return ArchivedV2Observation(
            stored_id, item.evidence_id, item.signer, height, block_hash,
            commitment, provider_bytes, envelope, False)

    def capture(self, rpc, spec: V2AuthoritySpec, monitor_private_key: str,
                *, nonce: str | None = None, timeout: float = 2.0
                ) -> ArchivedV2Observation:
        """HTTP provider -> local signed monitor observation -> atomic V2 archive.

        Local event_time_lower/upper are untrusted wall-clock observations.
        Historical blockchain membership is verified twice (before HTTP and
        before the SQLite write); neither read proves consumer-side delivery.
        """
        from eth_account import Account
        from typed_evidence import Domain

        snapshot = read_v2_authority(rpc, spec)
        signer = Account.from_key(monitor_private_key).address.lower()
        if signer not in snapshot.context().authorized_monitors:
            raise AuthenticationError("monitor key is not a selected confirmed V2 signer")
        lower = int(time.time())
        raw = fetch_provider_payload(snapshot.endpoint, snapshot.scope, timeout)
        validated = validate_provider_payload(
            raw, Domain(snapshot.chain_id, snapshot.controller),
            snapshot.provider, snapshot.scope)
        upper = max(lower, math.ceil(time.time()))
        report = ObservationRecord(
            snapshot.scope, ObservationKind.RESPONSE_SEEN,
            validated["responseHash"], payload_commitment(raw),
            lower, upper,
            nonce if nonce is not None else "0x" + secrets.token_bytes(32).hex(),
        )
        envelope = sign_observation(report, monitor_private_key)
        return self.insert_verified(
            rpc, spec, (snapshot.block_number, snapshot.block_hash), envelope, raw)
