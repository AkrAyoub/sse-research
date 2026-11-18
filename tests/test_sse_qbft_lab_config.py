"""Test key-free QBFT genesis and benchmark design."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from sse_qbft_lab_config import ConfigError, genesis, qbft_extra_data, rlp_encode, trials

V = ["0x" + char * 40 for char in ("1", "2", "3", "4")]


class QBFTGenesisTests(unittest.TestCase):
    def test_besu_extra_data_structure(self):
        extra = qbft_extra_data(V)
        self.assertTrue(extra.startswith("0xf87aa0"))
        self.assertTrue(extra.endswith("c080c0"))
        self.assertEqual(len(bytes.fromhex(extra[2:])), 124)

    def test_exact_four_distinct_public_keys(self):
        for vals in (V[:3], [V[0]] * 4, V + [V[0]]):
            with self.assertRaises(ConfigError):
                qbft_extra_data(vals)
        with self.assertRaises(ConfigError):
            genesis(V[:3])

    def test_isolated_chain_and_conflict_checks(self):
        for chain in (1, 31337, 0):
            with self.assertRaises(ConfigError):
                genesis(V, chain_id=chain)
        with self.assertRaises(ConfigError):
            genesis(V, block_period=1)
        with self.assertRaises(ConfigError):
            genesis(V, gas_limit=123)
        with self.assertRaises(ConfigError):
            genesis(V, funded=[V[0], V[0]])

    def test_protocol_and_evm_compatibility(self):
        g = genesis(V, funded=V[:2])
        self.assertEqual(g['config']['qbft']['blockreward'], '10000000000000')
        self.assertEqual(g['config']['qbft']['requesttimeoutseconds'], 10)
        self.assertEqual(g['config']['shanghaiTime'], 0)
        self.assertEqual(g['config']['cancunTime'], 0)
        self.assertEqual(int(g['gasLimit'], 16), 15_000_000)
        self.assertEqual(len(g['alloc']), 2)
        self.assertNotIn('privateKey', str(g))

    def test_benchmark_matrix_is_preregistered(self):
        plan = trials()
        self.assertEqual(plan['preRegisteredVariables']['replicationsPerCondition'], 5)
        self.assertEqual(plan['preRegisteredVariables']['validatorOutages'], [0, 1, 2])


if __name__ == '__main__':
    unittest.main()
