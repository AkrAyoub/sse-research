"""WP-08 experimental signed observations: NEVER physical fulfillment certificates."""
import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

from sse_evidence_wire_v1 import (
    EvidenceScope, ObservationRecord, ObservationKind, EvidenceError, EvidenceReplay,
    AuthenticationError, VerificationContext, EvidenceLedger, VerifiedObservation,
    ZERO_HASH, parse_json_record, sign_observation, verify_observation, typed_data,
    to_wp07_raw, record_hash, payload_commitment, verify_payload,
)

try:
    from eth_account import Account
    from Crypto.Hash import keccak  # required by sse_challenge
    HAS_SIGNATURES = True
except ImportError:
    HAS_SIGNATURES = False

KEY = '0x' + '11' * 32    # local test only, never deployment key
K2 = '0x' + '22' * 32
SLA = '0x' + 'a1' * 32
RESOURCE = '0x' + 'a9' * 32
REQUEST = '0x' + 'c3' * 32
RESULT = '0x' + 'b2' * 32
PAYLOAD = '0x' + 'd4' * 32
NONCE = '0x' + 'e5' * 32
CONTRACT = '0x' + 'f6' * 20


def scope(**kwargs):
    x = {'chain_id': 31337, 'settlement': CONTRACT, 'lease_id': 2,
         'epoch_id': 3, 'sla_policy_hash': SLA, 'resource_profile_hash': RESOURCE, 'request_hash': REQUEST}
    x.update(kwargs)
    return EvidenceScope(**x)


def record(kind=ObservationKind.RESPONSE_SEEN, **kwargs):
    x = {'scope': scope(), 'kind': kind,
         'response_hash': RESULT if kind == ObservationKind.RESPONSE_SEEN else ZERO_HASH,
         'payload_hash': PAYLOAD, 'event_time_lower': 100, 'event_time_upper': 104,
         'nonce': NONCE}
    x.update(kwargs)
    return ObservationRecord(**x)


class WireSchemaTests(unittest.TestCase):
    def test_canonical_is_identical_across_input_dict_key_order(self):
        data = record().fields()
        reversed_dict = dict(reversed(list(data.items())))
        a, b = ObservationRecord.parse(data), ObservationRecord.parse(reversed_dict)
        self.assertEqual(a.canonical_bytes(), b.canonical_bytes())

    def test_roundtrip_wire(self):
        r = record()
        self.assertEqual(parse_json_record(r.canonical_bytes()), r)
        self.assertEqual(json.loads(r.canonical_bytes()), r.fields())

    def test_extra_missing_and_wrong_schema_rejected(self):
        for change in ('extra', 'missing', 'schema'):
            d = record().fields()
            if change == 'extra': d['unsignedExtra'] = 'ignored?'  # must not be ignored
            if change == 'missing': del d['nonce']
            if change == 'schema': d['schema'] = 'other'
            with self.subTest(change=change), self.assertRaises(EvidenceError):
                ObservationRecord.parse(d)

    def test_cross_service_rejected_before_signature(self):
        d = record().fields()
        d['serviceKind'] = 'STORAGE'
        with self.assertRaises(EvidenceError): ObservationRecord.parse(d)

    def test_json_duplicate_keys_rejected_by_canonical_encoding(self):
        raw = record().canonical_bytes()
        duplicated = raw[:-1] + b',"nonce":"' + NONCE[0:].encode() + b'"}'
        with self.assertRaises(EvidenceError): parse_json_record(duplicated)

    def test_json_whitespace_not_canonical(self):
        raw = json.dumps(record().fields(), indent=2).encode('ascii')
        with self.assertRaises(EvidenceError): parse_json_record(raw)

    def test_response_hash_rules(self):
        with self.assertRaises(EvidenceError): record(response_hash=ZERO_HASH)
        with self.assertRaises(EvidenceError): record(ObservationKind.LOCAL_TIMEOUT, response_hash=RESULT)

    def test_uint_type_and_range_rejected(self):
        for bad in (True, -1, 2**256, 3.1):
            with self.subTest(bad=bad), self.assertRaises(EvidenceError):
                scope(lease_id=bad)
        with self.assertRaises(EvidenceError): scope(chain_id=0)
        with self.assertRaises(EvidenceError): scope(epoch_id=-1)

    def test_hash_format_and_zero_rejected(self):
        for invalid in ('0x'+'A1'*32, ZERO_HASH, '0x1234', 'f'*64, True):
            with self.subTest(invalid=invalid), self.assertRaises(EvidenceError):
                scope(sla_policy_hash=invalid)
        with self.assertRaises(EvidenceError): scope(request_hash=ZERO_HASH)
        with self.assertRaises(EvidenceError): record(payload_hash=ZERO_HASH)
        with self.assertRaises(EvidenceError): record(nonce=ZERO_HASH)

    def test_invalid_clock_interval_rejected(self):
        with self.assertRaises(EvidenceError): record(event_time_lower=105, event_time_upper=104)
        with self.assertRaises(EvidenceError): record(event_time_lower=True)

    def test_untrusted_clock_can_cross_contract_deadline(self):
        r = record(event_time_lower=109, event_time_upper=112)
        self.assertEqual((r.event_time_lower, r.event_time_upper), (109,112))
        # The SDK does not pretend a monitor's clock bound was authenticated.

    def test_fixed_limit_and_bounded_wire(self):
        with self.assertRaises(EvidenceError): parse_json_record(b'x' * 4097)
        with self.assertRaises(EvidenceError): parse_json_record(b'')
        with self.assertRaises(EvidenceError): parse_json_record('Ω'.encode())

    def test_response_and_timeout_are_distinct_observations(self):
        self.assertNotEqual(record().canonical_bytes(), record(ObservationKind.LOCAL_TIMEOUT).canonical_bytes())

    def test_signing_domain_is_distinct_from_current_solidity_vote_domain(self):
        # No physical or on-chain authorization claim; this is a new OFFCHAIN schema.
        from sse_evidence_wire_v1 import DOMAIN_NAME
        self.assertEqual(DOMAIN_NAME, 'SSEEvidenceObservation')

    def test_enum_requires_exact_type(self):
        with self.assertRaises(EvidenceError): record(kind=1)
        with self.assertRaises(EvidenceError): ObservationRecord.parse({**record().fields(), 'kind':True})
        with self.assertRaises(EvidenceError): ObservationRecord.parse({**record().fields(), 'kind':99})

    def test_context_requires_authorized_set(self):
        with self.assertRaises(EvidenceError): VerificationContext(scope(), frozenset())
        with self.assertRaises(EvidenceError): VerificationContext(scope(), {'not-an-address'})

    def test_signature_field_schema_always_checked_before_crypto(self):
        with self.assertRaises(EvidenceError): verify_observation({}, VerificationContext(scope(), frozenset({CONTRACT})))
        with self.assertRaises(EvidenceError): verify_observation({'record':{},'signer':CONTRACT,'signature':'0x00'}, VerificationContext(scope(),frozenset({CONTRACT})))

    def test_verified_observation_cannot_be_used_directly_as_physical_fact(self):
        from sse_evidence_policy_v1 import QualifiedFact
        self.assertFalse(issubclass(VerifiedObservation, QualifiedFact))


@unittest.skipUnless(HAS_SIGNATURES, 'eth-account and pycryptodome are required for EIP-712 execution')
class SigningTests(unittest.TestCase):
    def setUp(self):
        self.signer = Account.from_key(KEY).address.lower()
        self.other = Account.from_key(K2).address.lower()
        self.context = VerificationContext(scope(), frozenset({self.signer}))
        self.record = record()
        self.envelope = sign_observation(self.record, KEY)

    def test_recover_exact_authorized_signer(self):
        result = verify_observation(self.envelope, self.context)
        self.assertEqual(result.signer, self.signer)
        self.assertEqual(result.evidence_id, record_hash(self.record))

    def test_keccak_domain_separates_wire_hash(self):
        self.assertRegex(record_hash(self.record), r'^0x[0-9a-f]{64}$')
        self.assertNotEqual(record_hash(self.record), record_hash(record(nonce='0x'+'ae'*32)))

    def test_cross_chain_rejected(self):
        with self.assertRaises(AuthenticationError):
            verify_observation(self.envelope, VerificationContext(scope(chain_id=1), frozenset({self.signer})))

    def test_cross_contract_rejected(self):
        with self.assertRaises(AuthenticationError):
            verify_observation(self.envelope, VerificationContext(scope(settlement='0x'+'9f'*20), frozenset({self.signer})))

    def test_cross_lease_epoch_sla_and_request_rejected(self):
        variants = [dict(lease_id=99), dict(epoch_id=99),
                    dict(sla_policy_hash='0x'+'77'*32),
                    dict(resource_profile_hash='0x'+'77'*32), dict(request_hash='0x'+'88'*32)]
        for kw in variants:
            with self.subTest(**kw), self.assertRaises(AuthenticationError):
                verify_observation(self.envelope, VerificationContext(scope(**kw), frozenset({self.signer})))

    def test_tampered_record_rejected(self):
        for name, value in [('payloadHash','0x'+'98'*32),('eventTimeLower',101),('nonce','0x'+'75'*32),('kind',2)]:
            bad = copy.deepcopy(self.envelope)
            bad['record'][name] = value
            if name == 'kind': bad['record']['responseHash'] = ZERO_HASH
            with self.subTest(name=name), self.assertRaises(AuthenticationError):
                verify_observation(bad, self.context)

    def test_unauthorized_signer_rejected_even_with_valid_signature(self):
        bad = sign_observation(self.record, K2)
        with self.assertRaises(AuthenticationError): verify_observation(bad, self.context)

    def test_forged_signer_label_rejected(self):
        bad = {**self.envelope,'signer':self.other}
        context = VerificationContext(scope(), frozenset({self.other}))
        with self.assertRaises(AuthenticationError):verify_observation(bad, context)

    def test_malformed_signature_rejected(self):
        bad = {**self.envelope,'signature':'0x'+'00'*65}
        with self.assertRaises(AuthenticationError):verify_observation(bad, self.context)

    def test_duplicate_exact_record_is_idempotent(self):
        item = verify_observation(self.envelope, self.context)
        ledger = EvidenceLedger()
        self.assertTrue(ledger.accept(item))
        self.assertFalse(ledger.accept(item))

    def test_same_nonce_different_signed_record_rejected(self):
        ledger = EvidenceLedger()
        ledger.accept(verify_observation(self.envelope, self.context))
        new_record = record(payload_hash='0x'+'99'*32)
        new_item = verify_observation(sign_observation(new_record, KEY), self.context)
        with self.assertRaises(EvidenceReplay): ledger.accept(new_item)

    def test_payload_commitment_check_detects_missing_or_altered_payload(self):
        payload = b'local evidence bytes'
        committed = payload_commitment(payload)
        observed = record(payload_hash=committed)
        self.assertTrue(verify_payload(observed, payload))
        self.assertFalse(verify_payload(observed, payload+b'!'))

    def test_same_nonce_allowed_different_epoch(self):
        ledger = EvidenceLedger()
        ledger.accept(verify_observation(self.envelope, self.context))
        second = record(scope=scope(epoch_id=4))
        second_context = VerificationContext(second.scope, frozenset({self.signer}))
        self.assertTrue(ledger.accept(verify_observation(sign_observation(second, KEY), second_context)))

    def test_verify_maps_only_to_wp07_raw_not_qualified(self):
        from sse_evidence_policy_v1 import PhysicalPolicyState, PolicyManifest, PolicyMode, Binding
        from sse_formal_reference import SLA as FinancialSLA, ALL_WORLDS
        result = verify_observation(self.envelope, self.context)
        raw = to_wp07_raw(result)
        policy = PolicyManifest(Binding(2,3,SLA), PolicyMode.PHYSICAL_DELIVERY,100,110)
        state = PhysicalPolicyState(policy, FinancialSLA(25,5)).with_raw(raw)
        self.assertEqual(state.histories, ALL_WORLDS)
        self.assertEqual(state.decision().funds.unresolved,25)

    def test_typed_data_contains_all_scope_fields(self):
        typed = typed_data(self.record)
        self.assertEqual(typed['domain']['chainId'],31337)
        self.assertEqual(typed['domain']['verifyingContract'],CONTRACT)
        self.assertEqual(typed['message']['slaPolicyHash'],SLA)
        self.assertEqual(typed['message']['resourceProfileHash'],RESOURCE)
        self.assertEqual(typed['message']['nonce'],NONCE)


if __name__ == '__main__':
    unittest.main()
