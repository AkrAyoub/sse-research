"""Offline signed-monitor tests: no funded account, blockchain or external network."""
from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'services' / 'provider-agent'))
sys.path.insert(0, str(ROOT / 'services' / 'monitor-agent'))

from eth_account import Account
from eth_account.messages import encode_typed_data
from sse_challenge import expected_response_hash
from typed_evidence import Domain, ZERO_HASH, signed_vote, typed_message, verify_provider_response
import monitor_agent
import signed_probe

CONTRACT = '0x' + 'cd' * 20
REQUEST = '0x' + '12' * 32
ENDPOINT = 'http://127.0.0.1:8877'


class FakeReply(io.BytesIO):
    status = 200
    headers = {}


class TypedMonitorTests(unittest.TestCase):
    def setUp(self):
        self.provider = Account.create()
        self.monitor = Account.create()
        self.domain = Domain(31337, CONTRACT)
        self.payload = {'leaseId': 3, 'epochId': 0, 'requestHash': REQUEST,
                        'responseHash': expected_response_hash(REQUEST)}
        self.provider_signature = '0x' + bytes(Account.sign_message(
            encode_typed_data(full_message=typed_message(
                self.domain, 'ProviderResponse', self.payload)),
            private_key=self.provider.key).signature).hex()

    def signed_response(self):
        return {**self.payload, 'providerSignature': self.provider_signature}

    def test_provider_typed_data_recovers_expected_address(self):
        self.assertTrue(verify_provider_response(
            self.domain, self.provider.address, self.payload, self.provider_signature))
        self.assertFalse(verify_provider_response(
            self.domain, self.monitor.address, self.payload, self.provider_signature))
        different = Domain(1, CONTRACT)
        self.assertFalse(verify_provider_response(
            different, self.provider.address, self.payload, self.provider_signature))

    def test_probe_recognizes_only_authenticated_provider_response(self):
        with patch.object(signed_probe, 'urlopen', return_value=FakeReply(
                json.dumps(self.signed_response()).encode('utf8'))):
            observed = signed_probe.signed_probe(ENDPOINT, self.domain,
                        self.provider.address, 3, 0, REQUEST)
        self.assertEqual(observed['kind'], 'SUCCESS')
        self.assertEqual(observed['response']['providerSignature'], self.provider_signature)

    def test_probe_rejects_legacy_unsigned_response(self):
        with patch.object(signed_probe, 'urlopen', return_value=FakeReply(
                json.dumps(self.payload).encode('utf8'))):
            observed = signed_probe.signed_probe(ENDPOINT, self.domain,
                        self.provider.address, 3, 0, REQUEST)
        self.assertEqual(observed['kind'], 'INVALID')
        self.assertEqual(observed['reason'], 'unsigned_or_invalid_schema')

    def test_probe_rejects_wrong_signature_and_wrong_challenge(self):
        bad = self.signed_response()
        bad['providerSignature'] = '0x' + '12' * 65
        with patch.object(signed_probe, 'urlopen', return_value=FakeReply(json.dumps(bad).encode())):
            self.assertEqual(signed_probe.signed_probe(ENDPOINT, self.domain,
                        self.provider.address, 3, 0, REQUEST)['kind'], 'INVALID')
        bad = self.signed_response()
        bad['responseHash'] = '0x' + 'ab' * 32
        with patch.object(signed_probe, 'urlopen', return_value=FakeReply(json.dumps(bad).encode())):
            self.assertEqual(signed_probe.signed_probe(ENDPOINT, self.domain,
                        self.provider.address, 3, 0, REQUEST)['kind'], 'INVALID')

    def test_plaintext_remote_url_rejected(self):
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            signed_probe.validate_endpoint('http://example.com:8877')
        with self.assertRaises(ValueError):
            signed_probe.validate_endpoint('https://name:password@example.com:443')

    def test_monitor_vote_signature_binds_message_and_commitment(self):
        observation = {'probes': [{'reason': 'provider authenticated'}]}
        evidence = signed_vote('0x' + bytes(self.monitor.key).hex(), self.domain, 3, 0,
                               REQUEST, 1, self.payload['responseHash'], observation,
                               self.signed_response())
        recovered = Account.recover_message(
            encode_typed_data(full_message=evidence['typedData']),
            signature=evidence['monitorSignature'])
        self.assertEqual(recovered.lower(), self.monitor.address.lower())
        self.assertEqual(evidence['evidenceHash'], evidence['typedData']['message']['evidenceHash'])
        self.assertEqual(evidence['providerResponse']['providerSignature'], self.provider_signature)
        self.assertEqual(evidence['typedData']['primaryType'], 'MonitorVote')

    def test_negative_vote_is_only_an_observation(self):
        evidence = signed_vote('0x' + bytes(self.monitor.key).hex(), self.domain, 3, 0,
                               REQUEST, 2, ZERO_HASH, {'probes': []})
        self.assertEqual(evidence['outcome'], 2)
        self.assertIn('signatures do not prove physical receipt or monitor independence',
                      evidence['limitations'])
        with self.assertRaises(ValueError):
            signed_vote('0x' + bytes(self.monitor.key).hex(), self.domain, 3, 0,
                        REQUEST, 2, expected_response_hash(REQUEST), {})

    def test_observation_never_confuses_invalid_signature_with_success(self):
        current = [1.0]
        def clock(): return current[0]
        def sleep(seconds): current[0] += max(0.1, seconds)
        with patch.object(monitor_agent, 'signed_probe',
                          return_value={'kind': 'INVALID', 'reason': 'unsigned_or_invalid_schema'}):
            result = monitor_agent.observe_until_deadline(
                ENDPOINT, self.domain, self.provider.address, 3, 0, REQUEST,
                1.5, interval=0.25, timeout=0.1, clock=clock, sleeper=sleep)
        self.assertEqual(result['outcome'], 2)
        self.assertEqual(result['responseHash'], ZERO_HASH)
        self.assertGreaterEqual(len(result['observations']), 1)

    def test_no_observation_does_not_produce_failure(self):
        with self.assertRaisesRegex(ValueError, 'after deadline'):
            monitor_agent.observe_until_deadline(
                ENDPOINT, self.domain, self.provider.address, 3, 0,
                REQUEST, 1.0, clock=lambda: 1.0)

    def test_source_probe_requires_selected_monitor(self):
        chain = {
            'chainId': 31337, 'blockTimestamp': 1000,
            'lease': {'stateName': 'Active', 'provider': self.provider.address,
                      'monitors': [Account.create().address for _ in range(4)],
                      'serviceEndpointHash': '0x' + 'ab' * 32,
                      'responsePeriod': 10},
            'epoch': {'responseDeadline': 1010, 'monitoringClose': 1030,
                      'evidenceClosed': False, 'monitoringSealed': False,
                      'requestHash': REQUEST},
        }
        with patch.object(monitor_agent, 'inspect_chain', return_value=chain):
            with self.assertRaisesRegex(ValueError, 'not one of the selected'):
                monitor_agent.produce_vote(object(), CONTRACT, ENDPOINT,
                    self.provider.address, 3, 0, '0x' + bytes(self.monitor.key).hex(),
                    resource_manifest_path='unused.json')


if __name__ == '__main__':
    unittest.main()
