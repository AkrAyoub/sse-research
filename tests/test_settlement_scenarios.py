import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
calculator=load('sse_scenarios',ROOT/'tools/settlement_scenarios.py')
network=load('sse_network',ROOT/'tools/check_ethereum_network.py')
class SettlementScenariosTest(unittest.TestCase):
    def test_partial_refund_is_exactly_20(self):
        rows={r['scenario']:r for r in calculator.report()['results']}
        self.assertEqual(rows['certified-failure-no-ack']['consumer_refund'],20)
        self.assertEqual(rows['certified-failure-no-ack']['unresolved'],5)
        self.assertEqual(rows['certified-success']['provider_credit'],25)
    def test_scenario_response(self):
        payload=calculator.report()
        self.assertEqual(payload['mode'],'simulation')
        self.assertIn('results',payload)
    def test_conservation_all_fees(self):
        for fee in range(1,25):
            for reservation in range(fee+1):
                for row in calculator.scenarios(fee,reservation):
                    self.assertEqual(row['provider_credit']+row['consumer_refund']+row['unresolved'],fee)
    def test_rpc_snapshot_tells_truth_about_evidence(self):
        with patch.object(network,'rpc',side_effect=['0x7e7e','0xa','0x3']):
            data=network.inspect('http://127.0.0.1:8545',32382)
        self.assertEqual(data['ethereum_execution']['peer_count'],3)
        self.assertFalse(data['fresh_block_production_verified'])
        self.assertFalse(data['unknown_validators_joined'])
        self.assertFalse(data['sse_transaction_verified'])
    def test_mismatched_chain_detectable(self):
        with patch.object(network,'rpc',side_effect=['0x1','0x1','0x2']):
            data=network.inspect('http://127.0.0.1:8545',32382)
        self.assertFalse(data['chain_id_matches'])
if __name__=='__main__':unittest.main()
