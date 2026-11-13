"""WP08C regression: RPC-derived context is fail-closed, never physical truth.

The imported chain inspector already has separate RPC/ABI tests; these tests
inject its structured result to exercise the capture authorization boundary.
"""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from sse_challenge import expected_response_hash
from sse_chain_read import ChainReadError
from sse_evidence_wire_v1 import EvidenceScope, VerificationContext
from sse_wp08c_chain_binding import ChainBindingError, bind_capture_to_chain

SETTLEMENT = '0x' + 'cd' * 20
CONSUMER = '0x' + 'aa' * 20
PROVIDER = '0x' + 'bb' * 20
MONITORS = ['0x' + format(i, '02x') * 20 for i in range(1, 5)]
REQ = '0x' + '01' * 32
SLA = '0x' + '02' * 32
RESOURCE = '0x' + '03' * 32
ENDPOINT = 'http://127.0.0.1:8878'


def scope():
    return EvidenceScope(31337, SETTLEMENT, 4, 2, SLA, RESOURCE, REQ)


def snapshot():
    return {
        'schema': 'sse-onchain-inspection-v1',
        'status': 'EPOCH_FOUND',
        'readOnly': True,
        'domainSeparatorMatches': True,
        'endpointCommitmentChecked': True,
        'chainId': 31337, 'settlementAddress': SETTLEMENT,
        'leaseId': 4, 'epochId': 2,
        'blockNumber': 50, 'blockTimestamp': 1000,
        'lease': {
            'consumer': CONSUMER, 'provider': PROVIDER,
            'slaPolicyHash': SLA, 'resourceProfileHash': RESOURCE,
            'stateName': 'Active', 'monitorConfirmations': 4,
            'monitors': MONITORS.copy(),
        },
        'epoch': {
            'exists': True, 'requestHash': REQ,
            'responseHash': expected_response_hash(REQ),
            'monitoringClose': 1010, 'monitoringSealed': False,
            'evidenceClosed': False,
        },
    }


class ChainBoundContextTests(unittest.TestCase):
    def bind(self, data, *, requested_scope=None, provider=PROVIDER):
        with patch('sse_wp08c_chain_binding.inspect_chain', return_value=data) as call:
            result = bind_capture_to_chain(object(), requested_scope or scope(),
                                           ENDPOINT, provider)
            self.assertEqual(call.call_args.kwargs,
                             {'expected_chain_id': 31337, 'endpoint': ENDPOINT})
            self.assertEqual(call.call_args.args[1:4], (SETTLEMENT, 4, 2))
            return result

    def test_valid_active_lease_derives_all_four_monitors_from_chain(self):
        result = self.bind(snapshot())
        self.assertEqual(result.provider, PROVIDER)
        self.assertEqual(result.block_number, 50)
        self.assertEqual(result.block_timestamp, 1000)
        self.assertIsInstance(result.context, VerificationContext)
        self.assertEqual(result.context.scope, scope())
        self.assertEqual(result.context.authorized_monitors, frozenset(MONITORS))
        # Unlike the legacy CLI path, an unrelated monitor is never introduced.
        self.assertNotIn(CONSUMER, result.context.authorized_monitors)

    def test_block_timestamp_at_monitoring_close_still_permitted(self):
        d = snapshot()
        d['blockTimestamp'] = d['epoch']['monitoringClose']
        self.assertEqual(self.bind(d).block_timestamp, 1010)

    def test_rejects_wrong_scopes_roles_and_unsafe_phases(self):
        cases = {
            'not admitted': ('status', 'NO_EPOCH_ADMITTED'),
            'unverified domain': ('domainSeparatorMatches', False),
            'unverified endpoint': ('endpointCommitmentChecked', False),
            'not read only': ('readOnly', False),
            'chain mismatch': ('chainId', 1),
            'lease mismatch': ('leaseId', 9),
            'epoch mismatch': ('epochId', 3),
            'settlement mismatch': ('settlementAddress', '0x' + 'dd'*20),
            'unrecognized schema': ('schema', 'other'),
            'missing epoch': ('epoch', None),
            'missing lease': ('lease', None),
            'bad block': ('blockNumber', -1),
            'bad timestamp': ('blockTimestamp', -1),
        }
        for name, (key, value) in cases.items():
            with self.subTest(name=name):
                d = snapshot()
                d[key] = value
                with self.assertRaises(ChainBindingError):
                    self.bind(d)

    def test_rejects_commitment_and_authorization_mismatches(self):
        cases = [
            ('provider', '0x' + 'ab'*20),
            ('slaPolicyHash', '0x' + '04'*32),
            ('resourceProfileHash', '0x' + '05'*32),
            ('stateName', 'Closed'),
            ('stateName', 'Ready'),
            ('monitorConfirmations', 3),
            ('monitors', MONITORS[:3]),
            ('monitors', MONITORS[:3] + [MONITORS[0]]),
            ('monitors', [CONSUMER] + MONITORS[1:]),
            ('monitors', [PROVIDER] + MONITORS[1:]),
            ('monitors', ['garbage'] + MONITORS[1:]),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                d = snapshot()
                d['lease'][field] = value
                with self.assertRaises(ChainBindingError):
                    self.bind(d)

    def test_rejects_wrong_challenge_and_closed_monitoring(self):
        cases = [
            ('requestHash', '0x' + '06'*32),
            ('responseHash', '0x' + '07'*32),
            ('exists', False),
            ('monitoringClose', 999),
            ('monitoringSealed', True),
            ('evidenceClosed', True),
        ]
        for field, value in cases:
            with self.subTest(field=field):
                d = snapshot()
                d['epoch'][field] = value
                with self.assertRaises(ChainBindingError):
                    self.bind(d)

    def test_rejects_external_provider_mismatch(self):
        with self.assertRaises(ChainBindingError):
            self.bind(snapshot(), provider='0x'+'ee'*20)

    def test_no_fallback_when_inspector_fails(self):
        with patch('sse_wp08c_chain_binding.inspect_chain',
                   side_effect=ChainReadError('RPC unavailable')):
            with self.assertRaisesRegex(ChainReadError, 'RPC unavailable'):
                bind_capture_to_chain(object(), scope(), ENDPOINT, PROVIDER)

    def test_invalid_input_refused_before_chain_read(self):
        with patch('sse_wp08c_chain_binding.inspect_chain') as call:
            with self.assertRaises(ChainBindingError):
                bind_capture_to_chain(object(), None, ENDPOINT, PROVIDER)
            with self.assertRaises(ChainBindingError):
                bind_capture_to_chain(object(), scope(), '', PROVIDER)
            call.assert_not_called()


if __name__ == '__main__':
    unittest.main()
