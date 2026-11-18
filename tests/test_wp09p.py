from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "tools" / "wp09p_runtime_truth.py"
spec = importlib.util.spec_from_file_location("wp09p_runtime_truth", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class WP09PTests(unittest.TestCase):
    def test_parse_actual(self):
        self.assertEqual(mod.parse_actual_runtime('Logs:\n  WP09P_ACTUAL_RUNTIME_BYTES 22400\n'),22400)

    def test_reject_missing_actual(self):
        with self.assertRaises(RuntimeError):mod.parse_actual_runtime('none')

    def test_reject_duplicate_actual(self):
        with self.assertRaises(RuntimeError):mod.parse_actual_runtime('WP09P_ACTUAL_RUNTIME_BYTES 1\nWP09P_ACTUAL_RUNTIME_BYTES 2')

    def test_gas_report_parse(self):
        sample = '│ contracts/SSESettlement.sol:SSESettlement Contract │ x │\n│ Deployment Cost │ Deployment Size │\n│----------------------------------│-----------------│\n│ 4930346 │ 23661 │\n'
        self.assertEqual(mod.parse_gas_report(sample),23661)

    def test_gas_report_missing(self):
        self.assertIsNone(mod.parse_gas_report('not present'))

    def test_same_artifact(self):
        r=mod.analyze(22400,22400,22400,23661)
        self.assertTrue(r['artifact_matches_live'])
        self.assertFalse(r['gas_report_matches_live'])
        self.assertEqual(r['actual_evm_runtime_headroom_bytes'],2176)

    def test_different_artifact(self):
        r=mod.analyze(22400,22400,23661,23661)
        self.assertFalse(r['artifact_matches_live'])
        self.assertTrue(r['gas_report_matches_live'])
        self.assertEqual(r['actual_evm_runtime_headroom_bytes'],915)

    def test_build_artifact_changed(self):
        r=mod.analyze(22400,23661,23661,23661)
        self.assertTrue(r['artifact_changed_during_test'])

if __name__ == '__main__':unittest.main()
