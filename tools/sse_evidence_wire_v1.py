"""WP-08 experimental, EIP-712 authenticated MONITOR OBSERVATIONS.

A signature binds an authorized monitor to exact canonical bytes. It DOES NOT
establish physical service fulfillment, truthful timestamps, monitor independence,
source RPC finality, or produce a WP-07 QualifiedFact.

This is a NEW OFF-CHAIN domain, NOT the currently deployed SSESettlement V1
MonitorVote message. Do not submit these signatures to SSESettlement V1.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import IntEnum

SCHEMA = 'sse-evidence-observation-v1'
SERVICE_KIND = 'HTTP_DELIVERY_EXPERIMENT_V1'
DOMAIN_NAME = 'SSEEvidenceObservation'
DOMAIN_VERSION = '1'
DOMAIN_PREFIX = b'SSE_EVIDENCE_OBSERVATION_V1\x00'
PAYLOAD_PREFIX = b'SSE_EVIDENCE_PAYLOAD_V1\x00'
ZERO_HASH = '0x' + '00' * 32
ADDRESS = re.compile(r'0x[0-9a-fA-F]{40}\Z')
HASH = re.compile(r'0x[0-9a-f]{64}\Z')
SIG = re.compile(r'0x[0-9a-fA-F]{130}\Z')
MAX_WIRE_BYTES = 4096
UINT256 = (1 << 256) - 1


class EvidenceError(ValueError):
    """An observation or its signed envelope does not satisfy this schema."""


class AuthenticationError(EvidenceError):
    """EIP-712 attribution or externally supplied role authorization failed."""


class EvidenceReplay(EvidenceError):
    """An already-used signer/epoch nonce refers to different evidence."""


class ObservationKind(IntEnum):
    RESPONSE_SEEN = 1
    LOCAL_TIMEOUT = 2


def _uint(value: int, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= UINT256:
        raise EvidenceError(f'{name} must be uint256 >= {minimum}')
    return value


def _hash(value: str, name: str, *, nonzero: bool = False) -> str:
    if type(value) is not str or not HASH.fullmatch(value):
        raise EvidenceError(f'{name} must be lowercase canonical bytes32 hex')
    if nonzero and value == ZERO_HASH:
        raise EvidenceError(f'{name} must be nonzero')
    return value


def _address(value: str, name: str) -> str:
    if type(value) is not str or not ADDRESS.fullmatch(value) or int(value[2:], 16) == 0:
        raise EvidenceError(f'{name} must be a nonzero Ethereum address')
    return value.lower()


@dataclass(frozen=True)
class EvidenceScope:
    chain_id: int
    settlement: str
    lease_id: int
    epoch_id: int
    sla_policy_hash: str
    resource_profile_hash: str
    request_hash: str

    def __post_init__(self) -> None:
        _uint(self.chain_id, 'chainId', minimum=1)
        _address(self.settlement, 'settlement')
        _uint(self.lease_id, 'leaseId', minimum=1)
        _uint(self.epoch_id, 'epochId')
        _hash(self.sla_policy_hash, 'slaPolicyHash', nonzero=True)
        _hash(self.resource_profile_hash, 'resourceProfileHash', nonzero=True)
        _hash(self.request_hash, 'requestHash', nonzero=True)

    def normalized(self) -> 'EvidenceScope':
        return EvidenceScope(self.chain_id, self.settlement.lower(), self.lease_id,
                             self.epoch_id, self.sla_policy_hash, self.resource_profile_hash,
                             self.request_hash)


@dataclass(frozen=True)
class ObservationRecord:
    scope: EvidenceScope
    kind: ObservationKind
    response_hash: str
    payload_hash: str
    event_time_lower: int
    event_time_upper: int
    nonce: str

    def __post_init__(self) -> None:
        if not isinstance(self.scope, EvidenceScope):
            raise EvidenceError('invalid observation scope')
        if type(self.kind) is not ObservationKind:
            raise EvidenceError('unrecognized observation kind')
        _hash(self.response_hash, 'responseHash')
        _hash(self.payload_hash, 'payloadHash', nonzero=True)
        _hash(self.nonce, 'nonce', nonzero=True)
        _uint(self.event_time_lower, 'eventTimeLower')
        _uint(self.event_time_upper, 'eventTimeUpper')
        if self.event_time_lower > self.event_time_upper:
            raise EvidenceError('inverted reporter clock interval')
        if self.kind == ObservationKind.LOCAL_TIMEOUT and self.response_hash != ZERO_HASH:
            raise EvidenceError('timeout cannot assert a response hash')
        if self.kind == ObservationKind.RESPONSE_SEEN and self.response_hash == ZERO_HASH:
            raise EvidenceError('observed response must commit to nonzero result')
        # No physical timeliness inference: reporter timestamps remain UNTRUSTED.

    def fields(self) -> dict:
        s = self.scope
        return {
            'schema': SCHEMA, 'serviceKind': SERVICE_KIND, 'chainId': s.chain_id, 'settlement': s.settlement.lower(),
            'leaseId': s.lease_id, 'epochId': s.epoch_id,
            'slaPolicyHash': s.sla_policy_hash, 'resourceProfileHash': s.resource_profile_hash,
            'requestHash': s.request_hash,
            'kind': int(self.kind), 'responseHash': self.response_hash,
            'payloadHash': self.payload_hash, 'eventTimeLower': self.event_time_lower,
            'eventTimeUpper': self.event_time_upper, 'nonce': self.nonce,
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(self.fields(), sort_keys=True, separators=(',', ':'),
                          ensure_ascii=True, allow_nan=False).encode('ascii')

    @classmethod
    def parse(cls, obj: object) -> 'ObservationRecord':
        if not isinstance(obj, dict):
            raise EvidenceError('record must be JSON object')
        expected = {'schema', 'serviceKind', 'chainId', 'settlement', 'leaseId', 'epochId',
                    'slaPolicyHash', 'resourceProfileHash', 'requestHash', 'kind', 'responseHash',
                    'payloadHash', 'eventTimeLower', 'eventTimeUpper', 'nonce'}
        if set(obj) != expected or obj.get('schema') != SCHEMA or obj.get('serviceKind') != SERVICE_KIND:
            raise EvidenceError('unexpected record schema or fields')
        if type(obj['kind']) is not int:
            raise EvidenceError('kind must be canonical integer enum')
        try:
            kind = ObservationKind(obj['kind'])
        except ValueError as exc:
            raise EvidenceError('unsupported observation kind') from exc
        scope = EvidenceScope(obj['chainId'], obj['settlement'], obj['leaseId'],
                              obj['epochId'], obj['slaPolicyHash'], obj['resourceProfileHash'],
                              obj['requestHash'])
        return cls(scope, kind, obj['responseHash'], obj['payloadHash'],
                   obj['eventTimeLower'], obj['eventTimeUpper'], obj['nonce'])


def parse_json_record(raw: bytes) -> ObservationRecord:
    """Reject noncanonical JSON and duplicate keys, not just invalid objects."""
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_WIRE_BYTES:
        raise EvidenceError('record must be bounded UTF-8 bytes')
    try:
        record = ObservationRecord.parse(json.loads(raw.decode('ascii')))
    except (UnicodeDecodeError, ValueError, TypeError, KeyError) as exc:
        raise EvidenceError('malformed record encoding') from exc
    if raw != record.canonical_bytes():
        raise EvidenceError('wire must match canonical JSON exactly')
    return record


def _keccak(raw: bytes) -> bytes:
    try:
        from sse_challenge import keccak256
    except (ImportError, RuntimeError) as exc:
        raise RuntimeError('Keccak requires pycryptodome from requirements.txt') from exc
    return keccak256(raw)


def payload_commitment(payload: bytes) -> str:
    if type(payload) is not bytes or len(payload) > 65536:
        raise EvidenceError('evidence payload must be bytes up to 65536 bytes')
    return '0x' + _keccak(PAYLOAD_PREFIX + payload).hex()


def verify_payload(record: ObservationRecord, payload: bytes) -> bool:
    if not isinstance(record, ObservationRecord):
        raise EvidenceError('observation required')
    return payload_commitment(payload) == record.payload_hash


def record_hash(record: ObservationRecord) -> str:
    return '0x' + _keccak(DOMAIN_PREFIX + record.canonical_bytes()).hex()


def typed_data(record: ObservationRecord) -> dict:
    """New off-chain EIP-712 namespace, separate from Solidity V1 MonitorVote."""
    s = record.scope
    return {
        'types': {
            'EIP712Domain': [
                {'name': 'name', 'type': 'string'},
                {'name': 'version', 'type': 'string'},
                {'name': 'chainId', 'type': 'uint256'},
                {'name': 'verifyingContract', 'type': 'address'},
            ],
            'SSEObservation': [
                {'name': 'leaseId', 'type': 'uint256'},
                {'name': 'epochId', 'type': 'uint256'},
                {'name': 'slaPolicyHash', 'type': 'bytes32'},
                {'name': 'resourceProfileHash', 'type': 'bytes32'},
                {'name': 'requestHash', 'type': 'bytes32'},
                {'name': 'recordHash', 'type': 'bytes32'},
                {'name': 'nonce', 'type': 'bytes32'},
            ],
        },
        'primaryType': 'SSEObservation',
        'domain': {'name': DOMAIN_NAME, 'version': DOMAIN_VERSION,
                   'chainId': s.chain_id, 'verifyingContract': s.settlement},
        'message': {'leaseId': s.lease_id, 'epochId': s.epoch_id,
                    'slaPolicyHash': s.sla_policy_hash, 'resourceProfileHash': s.resource_profile_hash,
            'requestHash': s.request_hash,
                    'recordHash': record_hash(record), 'nonce': record.nonce},
    }


def _eth_api():
    try:
        from eth_account import Account
        from eth_account.messages import encode_typed_data
    except ImportError as exc:
        raise RuntimeError('EIP-712 requires eth-account from requirements.txt') from exc
    return Account, encode_typed_data


def sign_observation(record: ObservationRecord, private_key: str) -> dict:
    """Development signing helper; key custody is explicitly out of scope."""
    Account, encode = _eth_api()
    account = Account.from_key(private_key)
    signed = Account.sign_message(encode(full_message=typed_data(record)), private_key)
    return {'record': record.fields(), 'signer': account.address.lower(),
            'signature': '0x' + bytes(signed.signature).hex()}


@dataclass(frozen=True)
class VerificationContext:
    """EXPECTED chain/committee state. Provided by caller, not verified from RPC."""
    scope: EvidenceScope
    authorized_monitors: frozenset[str]

    def __post_init__(self) -> None:
        if not isinstance(self.scope, EvidenceScope):
            raise EvidenceError('expected scope required')
        if not isinstance(self.authorized_monitors, frozenset) or not self.authorized_monitors:
            raise EvidenceError('explicit authorized monitor set required')
        if any(type(x) is not str or _address(x, 'monitor') != x.lower()
               for x in self.authorized_monitors):
            raise EvidenceError('invalid authorized monitor address')
        if len({x.lower() for x in self.authorized_monitors}) != len(self.authorized_monitors):
            raise EvidenceError('duplicate authorized monitor')


@dataclass(frozen=True)
class VerifiedObservation:
    """Verified signature and expected role only. NOT A PHYSICAL FACT CERTIFICATE."""
    record: ObservationRecord
    signer: str
    evidence_id: str


def verify_observation(envelope: object, context: VerificationContext) -> VerifiedObservation:
    if not isinstance(context, VerificationContext):
        raise EvidenceError('trusted verification context required')
    if not isinstance(envelope, dict) or set(envelope) != {'record', 'signer', 'signature'}:
        raise EvidenceError('unexpected signed envelope shape')
    record = ObservationRecord.parse(envelope['record'])
    if record.fields() != envelope['record']:
        raise EvidenceError('signed record must use canonical field values')
    if record.scope.normalized() != context.scope.normalized():
        raise AuthenticationError('wrong chain/contract/lease/epoch/SLA/request scope')
    signer = _address(envelope['signer'], 'signer')
    if signer not in {address.lower() for address in context.authorized_monitors}:
        raise AuthenticationError('signer was not an expected authorized monitor')
    signature = envelope['signature']
    if type(signature) is not str or not SIG.fullmatch(signature):
        raise AuthenticationError('invalid recoverable EIP-712 signature format')
    Account, encode = _eth_api()
    # eth-account delegates ECDSA recovery to eth-keys, which raises
    # BadSignature (not ValueError) for malformed but correctly sized signatures.
    from eth_keys.exceptions import BadSignature
    try:
        recovered = Account.recover_message(encode(full_message=typed_data(record)),
                                            signature=signature)
    except (ValueError, TypeError, OverflowError, BadSignature) as exc:
        raise AuthenticationError('unrecoverable EIP-712 signature') from exc
    if recovered.lower() != signer:
        raise AuthenticationError('signature not produced by claimed monitor')
    return VerifiedObservation(record, signer, record_hash(record))


class EvidenceLedger:
    """In-memory replay detector (not durable/on-chain replay prevention)."""
    def __init__(self) -> None:
        self._seen: dict[tuple, str] = {}

    def accept(self, item: VerifiedObservation) -> bool:
        if not isinstance(item, VerifiedObservation):
            raise EvidenceError('verified observation required')
        s = item.record.scope
        key = (s.chain_id, s.settlement.lower(), s.lease_id, s.epoch_id,
               item.signer.lower(), item.record.nonce)
        previous = self._seen.get(key)
        if previous is not None:
            if previous != item.evidence_id:
                raise EvidenceReplay('same monitor and epoch nonce reused with different bytes')
            return False  # exact duplicate accepted idempotently
        self._seen[key] = item.evidence_id
        return True


def to_wp07_raw(item: VerifiedObservation):
    """Bridge only to the RAW bucket. Never construct QualifiedFact here."""
    if not isinstance(item, VerifiedObservation):
        raise EvidenceError('verified observation required')
    from sse_evidence_policy_v1 import Binding, RawObservation, RawKind
    mapping = {
        ObservationKind.RESPONSE_SEEN: RawKind.MONITOR_SUCCESS,
        ObservationKind.LOCAL_TIMEOUT: RawKind.MONITOR_TIMEOUT,
    }
    s = item.record.scope
    return RawObservation(Binding(s.lease_id, s.epoch_id, s.sla_policy_hash),
                          item.evidence_id, mapping[item.record.kind], item.signer)
