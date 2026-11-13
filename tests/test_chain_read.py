"""Offline regression tests for checkpoint B1; no running Anvil required."""

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from sse_challenge import expected_response_hash, keccak256

spec = importlib.util.spec_from_file_location('sse_chain_read', ROOT / 'tools' / 'sse_chain_read.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)

CONTRACT = '0x0DCd1Bf9A1b36cE34237eEaFef220932846BCD82'
PROVIDER = '0x' + '22' * 20
CONSUMER = '0x' + '11' * 20
ENDPOINT = 'http://127.0.0.1:8877'
HASH = '0x' + '11' * 32


def encode_word(kind, value):
    if kind == 'address':
        return int(value, 16).to_bytes(32, 'big').hex()
    if kind == 'bytes32':
        return value[2:]
    if kind == 'bool':
        return (1 if value else 0).to_bytes(32, 'big').hex()
    return value.to_bytes(32, 'big').hex()


def encode_fields(fields, obj):
    words = []
    for name, kind in fields:
        if kind == 'address[4]':
            words.extend(encode_word('address', item) for item in obj[name])
        else:
            words.append(encode_word(kind, obj[name]))
    return '0x' + ''.join(words)


class FakeRPC:
    def __init__(self, admitted=True):
        self.chain_id = 31337
        self.code = '0x6000'
        self.next_id = 2
        self.domain = reader._domain_separator(31337, CONTRACT)
        self.lease = dict.fromkeys((name for name, _ in reader.LEASE_FIELDS), 0)
        self.lease.update({
            'consumer': CONSUMER, 'provider': PROVIDER,
            'monitors': ['0x' + ('%02x' % i) * 20 for i in range(3, 7)],
            'assignmentId': 1,
            'serviceEndpointHash': '0x' + keccak256(ENDPOINT.encode()).hex(),
            'resourceProfileHash': '0x' + 'ab' * 32,
            'slaPolicyHash': '0x' + 'cd' * 32,
            'totalEscrow': 25, 'uncommittedEscrow': 0,
            'epochFee': 25, 'reservationFee': 5, 'exposureBudget': 25,
            'maxEpochs': 1, 'responsePeriod': 10, 'monitoringGrace': 10,
            'evidenceWindow': 20, 'nextEpochId': 1 if admitted else 0,
            'monitorConfirmations': 4, 'state': 3 if admitted else 2,
        })
        self.epoch = dict.fromkeys((name for name, _ in reader.EPOCH_FIELDS), 0)
        self.epoch.update({
            'requestHash': HASH, 'responseHash': expected_response_hash(HASH),
            'fee': 25, 'reservationFee': 5, 'responseDeadline': 1000,
            'monitoringClose': 1010, 'evidenceClose': 1030,
            'unresolvedExposure': 25, 'exists': True,
            'acknowledged': False, 'responseAuthenticated': False,
            'monitoringSealed': False, 'evidenceClosed': False, 'outcome': 0,
        })
        self.calls = []
        self.block_hash = '0x' + 'b1' * 32
        self.second_block_hash = None

    def request(self, method, params):
        self.calls.append((method, params))
        if method == 'eth_chainId':
            return hex(self.chain_id)
        if method == 'eth_blockNumber':
            return '0x10'
        if method == 'eth_getBlockByNumber':
            assert params == ['0x10', False]
            num_same = sum(method == 'eth_getBlockByNumber' for method, _ in self.calls)
            block_hash = self.second_block_hash if num_same > 1 and self.second_block_hash else self.block_hash
            return {'number': '0x10', 'timestamp': '0x3e0', 'hash': block_hash}
        if method == 'eth_getCode':
            assert params[1] in ('0x10', {'blockHash': self.block_hash, 'requireCanonical': True})
            return self.code
        if method == 'eth_call':
            assert params[1] in ('0x10', {'blockHash': self.block_hash, 'requireCanonical': True})
            data = params[0]['data']
            if data == reader._function_call('domainSeparator()'):
                return self.domain
            if data == reader._function_call('nextLeaseId()'):
                return '0x' + encode_word('uint256', self.next_id)
            if data == reader._function_call('getLease(uint256)', (1,)):
                return encode_fields(reader.LEASE_FIELDS, self.lease)
            if data == reader._function_call('getEpoch(uint256,uint256)', (1, 0)):
                return encode_fields(reader.EPOCH_FIELDS, self.epoch)
        raise AssertionError(f'unexpected RPC: {method} {params}')


class ChainReadTest(unittest.TestCase):
    def inspect(self, rpc=None, **kwargs):
        return reader.inspect_chain(rpc or FakeRPC(), CONTRACT, 1, 0, now=1000.1, **kwargs)

    def test_known_deployed_domain_separator(self):
        self.assertEqual(reader._domain_separator(31337, CONTRACT),
                         '0x0f07cf8a65b1bf22a20e753e3c6c2fb3479d3309d7612df07212419b0f583e26')

    def test_valid_epoch_read_is_not_a_timing_certificate(self):
        result = self.inspect(endpoint=ENDPOINT)
        self.assertEqual(result['status'], 'EPOCH_FOUND')
        self.assertEqual(result['lease']['provider'], PROVIDER)
        self.assertEqual(result['lease']['nextEpochId'], 1)
        self.assertEqual(result['epoch']['requestHash'], HASH)
        self.assertEqual(result['epoch']['responseDeadline'], 1000)
        self.assertTrue(result['chainDeadlineRead'])
        self.assertFalse(result['deadlineTimelinessCertified'])
        self.assertFalse(result['providerSignatureVerified'])
        self.assertTrue(result['endpointCommitmentChecked'])
        self.assertEqual(result['localMinusBlockSeconds'], 8.1)

    def test_no_epoch_admitted_is_explicit(self):
        result = self.inspect(FakeRPC(admitted=False))
        self.assertEqual(result['status'], 'NO_EPOCH_ADMITTED')
        self.assertIsNone(result['epoch'])
        self.assertFalse(result['chainDeadlineRead'])

    def test_block_hash_pin_used_for_all_contract_reads(self):
        rpc = FakeRPC()
        view = self.inspect(rpc, endpoint=ENDPOINT, pin_block_hash=True)
        self.assertEqual(view['blockHash'], rpc.block_hash)
        self.assertTrue(view['blockHashPinned'])
        for method, params in rpc.calls:
            if method in ('eth_call', 'eth_getCode'):
                self.assertEqual(params[1], {'blockHash': rpc.block_hash, 'requireCanonical': True})
        self.assertEqual([method for method, _ in rpc.calls].count('eth_getBlockByNumber'), 2)

    def test_pinned_block_replacement_is_rejected(self):
        rpc = FakeRPC()
        rpc.second_block_hash = '0x' + 'f1'*32
        with self.assertRaisesRegex(reader.ChainReadError, 'reorged'):
            self.inspect(rpc, pin_block_hash=True)

    def test_missing_block_hash_fails_closed_when_requested(self):
        rpc = FakeRPC()
        rpc.block_hash = None
        with self.assertRaisesRegex(reader.ChainReadError, 'missing canonical block hash'):
            self.inspect(rpc, pin_block_hash=True)

    def test_wrong_chain_rejected(self):
        rpc = FakeRPC()
        rpc.chain_id = 1
        with self.assertRaisesRegex(reader.ChainReadError, 'wrong chain'):
            self.inspect(rpc)

    def test_bad_domain_rejected(self):
        rpc = FakeRPC()
        rpc.domain = '0x' + '00' * 32
        with self.assertRaisesRegex(reader.ChainReadError, 'EIP-712 domain'):
            self.inspect(rpc)

    def test_no_contract_rejected(self):
        rpc = FakeRPC()
        rpc.code = '0x'
        with self.assertRaisesRegex(reader.ChainReadError, 'no deployed'):
            self.inspect(rpc)

    def test_unallocated_lease_rejected(self):
        rpc = FakeRPC()
        rpc.next_id = 1
        with self.assertRaisesRegex(reader.ChainReadError, 'not allocated'):
            self.inspect(rpc)

    def test_response_hash_mismatch_rejected(self):
        rpc = FakeRPC()
        rpc.epoch['responseHash'] = '0x' + 'ab' * 32
        with self.assertRaisesRegex(reader.ChainReadError, 'response hash'):
            self.inspect(rpc)

    def test_missing_epoch_in_allocated_index_rejected(self):
        rpc = FakeRPC()
        rpc.epoch['exists'] = False
        with self.assertRaisesRegex(reader.ChainReadError, 'epoch missing'):
            self.inspect(rpc)

    def test_wrong_endpoint_hash_rejected(self):
        rpc = FakeRPC()
        with self.assertRaisesRegex(reader.ChainReadError, 'endpoint does not match'):
            self.inspect(rpc, endpoint='http://127.0.0.1:9999')

    def test_invalid_deadlines_rejected(self):
        rpc = FakeRPC()
        rpc.epoch['monitoringClose'] = 999
        with self.assertRaisesRegex(reader.ChainReadError, 'monitoring windows'):
            self.inspect(rpc)

    def test_bad_struct_word_count_rejected(self):
        with self.assertRaisesRegex(reader.ChainReadError, 'ABI result size'):
            reader.decode_struct('0x00', reader.LEASE_FIELDS)

    def test_rpc_must_be_loopback(self):
        with self.assertRaisesRegex(reader.ChainReadError, '127.0.0.1'):
            reader.LocalRPC('http://example.org:8545')


if __name__ == '__main__':
    unittest.main()
