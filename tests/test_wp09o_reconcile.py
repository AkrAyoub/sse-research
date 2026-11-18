import csv
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import wp09o_reconcile_profiles as m


class Reconciliation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sw=m.read_csv(ROOT/'reference'/'optimizer_sweep.csv')
        cls.ga=m.read_csv(ROOT/'reference'/'success_call_gas.csv')

    def test_01_4_sweep_profiles(self):
        self.assertEqual(len(m.validate_sweep(self.sw)),4)

    def test_02_200_headroom(self):
        self.assertEqual(m.analyze(self.sw,self.ga)['default_200_profile']['headroom'],2176)

    def test_03_historical_discrepancy(self):
        self.assertEqual(m.analyze(self.sw,self.ga)['historical_vs_200_discrepancy_bytes'],1261)

    def test_04_size_arithmetic_rejected(self):
        r=[dict(x) for x in self.sw];r[0]['eip170_headroom']='2'
        with self.assertRaises(ValueError):m.validate_sweep(r)

    def test_05_size_status_rejected(self):
        r=[dict(x) for x in self.sw];r[0]['status']='too_large'
        with self.assertRaises(ValueError):m.validate_sweep(r)

    def test_06_duplicate_run_rejected(self):
        with self.assertRaises(ValueError):m.validate_sweep(self.sw+[self.sw[0]])

    def test_07_16_valid_gas(self):
        self.assertEqual(len(m.validate_gas(self.ga)),16)

    def test_08_missing_sample_rejected(self):
        with self.assertRaises(ValueError):m.validate_gas(self.ga[:-1])

    def test_09_duplicate_sample_rejected(self):
        r=[dict(x) for x in self.ga];r[0]['operation']='vrf_purchase';r[0]['roster_size']='16';r[0]['global_mode']=''
        with self.assertRaises(ValueError):m.validate_gas(r)

    def test_10_16_legacy_vs_global(self):
        x=m.analyze(self.sw,self.ga)['comparison_by_roster']['16'];self.assertEqual(x['global_create_reduction_pct'],51.54)

    def test_11_160_legacy_vs_global(self):
        x=m.analyze(self.sw,self.ga)['comparison_by_roster']['160'];self.assertEqual(x['global_create_reduction_pct'],81.66)

    def test_12_mock_hash(self):
        self.assertEqual(m.git_blob_sha(b'hello'), 'b6fc4c620b67d95f953a5c1c1230aaab5db5a1b0')

    def test_13_report_size_parser(self):
        s='''╭--------\n| contracts/SSESettlement.sol:SSESettlement Contract |\n| Deployment Cost | Deployment Size |\n|----------------|-----------------|\n|        4930346 |           22400 |\n| Function Name | Min | Avg |\n'''
        self.assertEqual(m.parse_gas_report_size(s),22400)

    def test_14_no_report_size(self):
        self.assertIsNone(m.parse_gas_report_size('no gas report'))

    def test_15_no_false_full_tx_claim(self):
        self.assertIn('not full transaction gas',m.analyze(self.sw,self.ga)['metric_scope'])

if __name__=='__main__':unittest.main()
