"""Standard-library tests for the source-of-truth EIP-712 message template."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from sse_residual_typed_data import residual_typed_data


class ResidualTypedDataTests(unittest.TestCase):
    def setUp(self):
        self.params = dict(
            chain_id=31337,
            settlement='0x' + '1a' * 20,
            lease_id=7,
            epoch_id=1,
            unresolved=5,
            provider_share=2,
            consumer_share=3,
            nonce=9,
            expiry=1893456000,
        )

    def test_schema_matches_contract_and_eip712_domain(self):
        result = residual_typed_data(**self.params)
        self.assertEqual(result['primaryType'], 'ResidualAgreement')
        self.assertEqual(result['domain']['name'], 'SSESettlement')
        self.assertEqual(result['domain']['chainId'], 31337)
        self.assertEqual(result['domain']['verifyingContract'], self.params['settlement'])
        self.assertEqual(
            [f['name'] for f in result['types']['ResidualAgreement']],
            ['leaseId','epochId','unresolvedAmount','providerShare','consumerShare','nonce','expiry']
        )
        self.assertEqual(result['message']['providerShare'], 2)
        self.assertEqual(result['message']['consumerShare'], 3)

    def test_invalid_shares_are_refused(self):
        for bad in ((2, 2), (2, 4), (6, 0)):
            with self.subTest(shares=bad), self.assertRaises(ValueError):
                residual_typed_data(**{**self.params, 'provider_share':bad[0], 'consumer_share':bad[1]})

    def test_invalid_uint_and_address_are_refused(self):
        for key, bad in [('lease_id',0), ('epoch_id',-1), ('nonce',-1),
                         ('chain_id',True), ('provider_share',2**256), ('settlement','0x123')]:
            with self.subTest(field=key), self.assertRaises(ValueError):
                residual_typed_data(**{**self.params,key:bad})

    def test_whole_amount_can_be_allocated_to_either_party(self):
        for p,c in ((0,5),(5,0)):
            data = residual_typed_data(**{**self.params, 'provider_share':p, 'consumer_share':c})
            self.assertEqual(data['message']['providerShare'] + data['message']['consumerShare'],5)


if __name__ == '__main__':
    unittest.main()
