"""WP-08B laboratory HTTP evidence transport + crash-persistent raw archive.

Two distinct cryptographic statements:
(1) provider EIP-712 ProviderResponse (current SSESettlement V1 wire type),
(2) monitor WP-08A SSEObservation about its own received HTTP payload.

Neither statement proves contractual *consumer* delivery, physical CPU use,
truthful local time, authenticity of the supplied chain view or SLA soundness.
All network interactions are loopback-only for this laboratory increment.
"""
from __future__ import annotations

import json
from contextlib import closing
import math
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener

from sse_challenge import expected_response_hash
from sse_evidence_wire_v1 import (
    EvidenceScope, ObservationKind, ObservationRecord, VerificationContext,
    EvidenceReplay, EvidenceError, AuthenticationError, payload_commitment,
    verify_payload, sign_observation, verify_observation, ZERO_HASH,
)

MAX_HTTP_BYTES = 4096


class TransportFailure(ValueError):
    """Local HTTP transport failed; NEVER means physical SLA nonfulfillment."""


class ProviderResponseInvalid(ValueError):
    """Received bytes do not authenticate a valid challenge response."""


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError('duplicate JSON property')
        d[k] = v
    return d


def _strict_json_bytes(raw: bytes) -> dict:
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_HTTP_BYTES:
        raise ProviderResponseInvalid('HTTP response exceeds the bounded envelope')
    try:
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    except (ValueError, UnicodeDecodeError, TypeError) as exc:
        raise ProviderResponseInvalid('malformed provider JSON') from exc
    if type(result) is not dict:
        raise ProviderResponseInvalid('provider response must be an object')
    return result


def validate_provider_payload(raw: bytes, domain, provider: str, scope: EvidenceScope) -> dict:
    """Verify the exact **Solidity V1** ProviderResponse signature and challenge.

    Domain/provider/scope are expected *external context*, NOT chain verified here.
    Note: ProviderResponse V1 signs lease, epoch and challenge, not SLA/resource hash.
    """
    from typed_evidence import Domain, verify_provider_response
    if not isinstance(domain, Domain) or not isinstance(scope, EvidenceScope):
        raise ProviderResponseInvalid('expected domain and scope required')
    if domain.chain_id != scope.chain_id or domain.contract.lower() != scope.settlement.lower():
        raise ProviderResponseInvalid('scope differs from provider signing domain')
    result = _strict_json_bytes(raw)
    required = {'leaseId', 'epochId', 'requestHash', 'responseHash', 'providerSignature'}
    if set(result) != required:
        raise ProviderResponseInvalid('unexpected or missing provider fields')
    if (type(result['leaseId']) is not int or result['leaseId'] != scope.lease_id or
            type(result['epochId']) is not int or result['epochId'] != scope.epoch_id or
            type(result['requestHash']) is not str or
            result['requestHash'] != scope.request_hash or
            type(result['responseHash']) is not str or
            result['responseHash'] != expected_response_hash(scope.request_hash)):
        raise ProviderResponseInvalid('wrong lease, epoch, request or response commitment')
    if not verify_provider_response(domain, provider, {
            'leaseId': scope.lease_id, 'epochId': scope.epoch_id,
            'requestHash': scope.request_hash,
            'responseHash': result['responseHash'],
    }, result['providerSignature']):
        raise ProviderResponseInvalid('provider signature cannot be attributed')
    return result


def fetch_provider_payload(endpoint: str, scope: EvidenceScope, timeout: float = 2.0) -> bytes:
    """One bounded loopback-only HTTP request. No negative truth inference."""
    from signed_probe import validate_endpoint
    if not isinstance(scope, EvidenceScope):
        raise ValueError('expected evidence scope required')
    # WP-08B is local only: HTTPS remote and DNS/TLS policy require separate review.
    url = validate_endpoint(endpoint)
    if not url.startswith('http://127.0.0.1:'):
        raise ValueError('WP-08B requires numeric IPv4 loopback (no DNS or remote URL)')
    if type(timeout) not in (float, int) or not math.isfinite(timeout) or not 0 < timeout <= 60:
        raise ValueError('timeout must be finite and in (0,60]')
    payload = json.dumps({'leaseId': scope.lease_id, 'epochId': scope.epoch_id,
                          'requestHash': scope.request_hash}, sort_keys=True,
                         separators=(',', ':')).encode('ascii')
    req = Request(url, data=payload, headers={'Content-Type':'application/json'}, method='POST')
    # stdlib urlopen follows redirects by default: a loopback server could redirect
    # to a remote endpoint. Explicitly refuse redirects and ignore env HTTP proxies.
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=float(timeout)) as response:
            if response.status != 200:
                raise TransportFailure('provider returned non-success HTTP status')
            length = response.headers.get('Content-Length')
            if length is not None:
                try:
                    declared = int(length)
                except (TypeError, ValueError) as exc:
                    raise ProviderResponseInvalid('invalid provider Content-Length') from exc
                if not 0 <= declared <= MAX_HTTP_BYTES:
                    raise ProviderResponseInvalid('provider Content-Length exceeds limit')
            raw = response.read(MAX_HTTP_BYTES + 1)
            if length is not None and len(raw) != declared:
                raise ProviderResponseInvalid('HTTP body length does not match Content-Length')
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise TransportFailure('provider unavailable to this monitor') from exc
    if len(raw) > MAX_HTTP_BYTES:
        raise ProviderResponseInvalid('provider response body exceeds limit')
    return raw


@dataclass(frozen=True)
class CaptureResult:
    evidence_id: str
    monitor: str
    provider: str
    response_hash: str
    stored_new: bool
    raw_bytes: bytes  # exact HTTP bytes, not a parsed/re-serialized response


class EvidenceArchive:
    """SQLite archive. Atomically store exact response bytes and monitor signature.

    SQLite protects crash consistency and concurrent writers; it does NOT make an
    adversarial disk operator honest, replace an immutable log, or prove chain state.
    """
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.exists() and not self.path.is_file():
            raise EvidenceError('archive destination must be a regular SQLite file')
        if not self.path.parent.is_dir():
            raise EvidenceError('archive parent directory must already exist')
        with closing(self._db()) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS records (
                    evidence_id TEXT PRIMARY KEY,
                    chain_id TEXT NOT NULL,
                    settlement TEXT NOT NULL,
                    lease_id TEXT NOT NULL,
                    epoch_id TEXT NOT NULL,
                    monitor TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    provider_raw BLOB NOT NULL,
                    monitor_envelope TEXT NOT NULL,
                    UNIQUE(chain_id, settlement, lease_id, epoch_id, monitor, nonce)
                );
                CREATE TABLE IF NOT EXISTS chain_anchors (
                    evidence_id TEXT PRIMARY KEY REFERENCES records(evidence_id),
                    anchor_envelope TEXT NOT NULL
                );
            ''')

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.execute('PRAGMA busy_timeout=15000')
        db.execute('PRAGMA synchronous=FULL')
        return db

    def insert(self, envelope: dict, raw_payload: bytes, context: VerificationContext,
               domain, expected_provider: str, *,
               anchor_envelope: dict | None = None) -> tuple[str, bool]:
        """Re-authenticate BOTH provider and monitor before committing the bytes."""
        item = verify_observation(envelope, context)
        if not verify_payload(item.record, raw_payload):
            raise EvidenceError('stored HTTP bytes differ from monitor commitment')
        if item.record.kind is not ObservationKind.RESPONSE_SEEN:
            raise EvidenceError('this archive version only accepts positive signed HTTP responses')
        valid_provider = validate_provider_payload(raw_payload, domain, expected_provider, item.record.scope)
        if valid_provider['responseHash'] != item.record.response_hash:
            raise EvidenceError('provider response and monitor claim disagree')
        scope = item.record.scope
        key = (str(scope.chain_id), scope.settlement.lower(), str(scope.lease_id),
               str(scope.epoch_id), item.signer.lower(), item.record.nonce)
        serialized = json.dumps(envelope, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
        anchor_json = None
        if anchor_envelope is not None:
            from sse_wp08d_provenance import verify_anchor
            verify_anchor(anchor_envelope, context, item.evidence_id, item.signer)
            anchor_json = json.dumps(anchor_envelope, sort_keys=True,
                                     separators=(',', ':'), ensure_ascii=True)
        with closing(self._db()) as db:
            try:
                db.execute('BEGIN IMMEDIATE')
                old = db.execute('''SELECT evidence_id, provider_raw, monitor_envelope
                                    FROM records WHERE chain_id=? AND settlement=?
                                    AND lease_id=? AND epoch_id=? AND monitor=? AND nonce=?''', key).fetchone()
                if old is not None:
                    if old != (item.evidence_id, raw_payload, serialized):
                        raise EvidenceReplay('nonce reused with different committed evidence')
                    if anchor_json is not None:
                        previous = db.execute(
                            'SELECT anchor_envelope FROM chain_anchors WHERE evidence_id=?',
                            (item.evidence_id,)).fetchone()
                        if previous != (anchor_json,):
                            raise EvidenceReplay('duplicate evidence has different/missing snapshot anchor')
                    db.execute('COMMIT')
                    return item.evidence_id, False
                db.execute('''INSERT INTO records(evidence_id,chain_id,settlement,lease_id,
                              epoch_id,monitor,nonce,provider_raw,monitor_envelope)
                              VALUES(?,?,?,?,?,?,?,?,?)''', (item.evidence_id, *key, raw_payload, serialized))
                if anchor_json is not None:
                    db.execute('INSERT INTO chain_anchors(evidence_id,anchor_envelope) VALUES(?,?)',
                               (item.evidence_id, anchor_json))
                db.execute('COMMIT')
                return item.evidence_id, True
            except Exception:
                db.execute('ROLLBACK')
                raise

    def load(self, evidence_id: str, context: VerificationContext,
             domain, expected_provider: str) -> tuple[dict, bytes]:
        """Recheck both EIP-712 signatures and exact HTTP bytes on retrieval."""
        with closing(self._db()) as db:
            row = db.execute('SELECT monitor_envelope,provider_raw FROM records WHERE evidence_id=?',
                             (evidence_id,)).fetchone()
        if row is None:
            raise KeyError('evidence not present')
        envelope = json.loads(row[0])
        verified = verify_observation(envelope, context)
        if verified.evidence_id != evidence_id or not verify_payload(verified.record, row[1]):
            raise EvidenceError('archive record no longer matches committed evidence')
        validated = validate_provider_payload(row[1], domain, expected_provider, verified.record.scope)
        if validated['responseHash'] != verified.record.response_hash:
            raise EvidenceError('archived provider and monitor response hashes disagree')
        return envelope, row[1]

    def load_anchored(self, evidence_id: str, context: VerificationContext,
                      domain, expected_provider: str, rpc) -> tuple[dict, bytes, object]:
        """Reverify three signatures (provider, observation, snapshot) and RPC chain.

        Strict: old WP08B archive rows without a signed anchor are rejected.
        A local trusted RPC can fabricate history; this is not a finality proof.
        """
        from sse_wp08d_provenance import (verify_anchor, check_canonical_snapshot,
                                          ProvenanceError)
        envelope, raw = self.load(evidence_id, context, domain, expected_provider)
        verified = verify_observation(envelope, context)
        with closing(self._db()) as db:
            row = db.execute('SELECT anchor_envelope FROM chain_anchors WHERE evidence_id=?',
                             (evidence_id,)).fetchone()
        if row is None:
            raise ProvenanceError('evidence has no signed block-snapshot anchor')
        try:
            anchor_envelope = json.loads(row[0])
        except (TypeError, ValueError) as exc:
            raise ProvenanceError('invalid stored anchor JSON') from exc
        anchor = verify_anchor(anchor_envelope, context, evidence_id, verified.signer)
        check_canonical_snapshot(rpc, anchor)
        return envelope, raw, anchor

    def count(self) -> int:
        with closing(self._db()) as db:
            return int(db.execute('SELECT COUNT(*) FROM records').fetchone()[0])


def capture_response(endpoint: str, domain, expected_provider: str, scope: EvidenceScope,
                     monitor_private_key: str, context: VerificationContext,
                     archive: EvidenceArchive, *, nonce: str | None = None,
                     timeout: float = 2.0, chain_binding=None, rpc=None) -> CaptureResult:
    """Signed provider response -> signed raw monitor observation -> archive.

    No conversion to QualifiedFact and no on-chain vote/submission.
    """
    from eth_account import Account
    if scope.normalized() != context.scope.normalized():
        raise AuthenticationError('monitor verification scope differs from request')
    sender = Account.from_key(monitor_private_key).address.lower()
    if sender not in {x.lower() for x in context.authorized_monitors}:
        raise AuthenticationError('monitor key not authorized by supplied context')
    lower = int(time.time())
    raw = fetch_provider_payload(endpoint, scope, timeout)
    verified_provider = validate_provider_payload(raw, domain, expected_provider, scope)
    upper = max(lower, math.ceil(time.time()))
    chosen_nonce = nonce or ('0x' + secrets.token_bytes(32).hex())
    observation = ObservationRecord(
        scope=scope, kind=ObservationKind.RESPONSE_SEEN,
        response_hash=verified_provider['responseHash'], payload_hash=payload_commitment(raw),
        event_time_lower=lower, event_time_upper=upper, nonce=chosen_nonce,
    )
    envelope = sign_observation(observation, monitor_private_key)
    anchor_env = None
    if chain_binding is not None:
        from sse_wp08c_chain_binding import ChainCaptureBinding
        from sse_wp08d_provenance import (BlockAnchor, valid_block_hash, sign_anchor,
                                          check_canonical_snapshot)
        from sse_evidence_wire_v1 import record_hash
        if (rpc is None or not isinstance(chain_binding, ChainCaptureBinding) or
                chain_binding.context != context or
                chain_binding.provider != expected_provider.lower() or
                not valid_block_hash(chain_binding.block_hash)):
            raise AuthenticationError('validated hash-pinned chain binding required')
        anchor = BlockAnchor(scope.chain_id, scope.settlement.lower(),
                             scope.lease_id, scope.epoch_id,
                             record_hash(observation), chain_binding.block_number,
                             chain_binding.block_hash, chain_binding.block_timestamp)
        # Prevent archiving stale observations after an observed local reorg.
        check_canonical_snapshot(rpc, anchor)
        anchor_env = sign_anchor(anchor, monitor_private_key)
    evidence_id, stored_new = archive.insert(
        envelope, raw, context, domain, expected_provider,
        anchor_envelope=anchor_env)
    return CaptureResult(evidence_id, sender, expected_provider.lower(),
                         verified_provider['responseHash'], stored_new, raw)
