import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'wp09n_local.py'
spec = importlib.util.spec_from_file_location('wp09n_local', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class TestWP09NLocal(unittest.TestCase):
    def test_01_parse_one_benchmark(self):
        rows = m.parse_benchmarks('WP09N|register|n_active 64\nWP09N|register|global_mode 1\nWP09N|register|gas 350000\n')
        self.assertEqual(rows, [{'operation': 'register', 'roster_size': 64,
                                 'global_mode': 1, 'proof_count': '', 'gasleft_delta': 350000}])

    def test_02_parse_success_only(self):
        rows = m.parse_benchmarks('[FAIL] testOtherRevert gas 900\nWP09N|vrf_purchase|gas 555\n')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['gasleft_delta'], 555)

    def test_03_parse_four_samples(self):
        rows = m.parse_benchmarks('\n'.join([
            'WP09N|register|n_active 16', 'WP09N|register|global_mode 0', 'WP09N|register|gas 100',
            'WP09N|register|n_active 160', 'WP09N|register|global_mode 1', 'WP09N|register|gas 200',
            'WP09N|global_finalize|n_active 160', 'WP09N|global_finalize|n_proofs 10', 'WP09N|global_finalize|gas 300',
            'WP09N|vrf_apply|gas 400']))
        self.assertEqual([x['gasleft_delta'] for x in rows], [100,200,300,400])
        self.assertEqual(rows[2]['proof_count'], 10)
        self.assertEqual(rows[2]['roster_size'], 160)

    def test_04_bytecode_length(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'artifact.json'
            p.write_text(json.dumps({'deployedBytecode':{'object':'0x60016002'}}))
            self.assertEqual(m.byte_length(p), 4)

    def test_05_bad_bytecode(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'artifact.json'
            p.write_text(json.dumps({'deployedBytecode':{'object':'garbage'}}))
            with self.assertRaises(RuntimeError): m.byte_length(p)

    def test_06_profile_env_is_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            env=m.build_env(50,Path(tmp))
            self.assertEqual(env['FOUNDRY_OPTIMIZER_RUNS'],'50')
            self.assertEqual(env['FOUNDRY_OFFLINE'],'true')
            self.assertTrue(env['FOUNDRY_OUT'].startswith(tmp))
            self.assertTrue(env['FOUNDRY_CACHE_PATH'].startswith(tmp))

    def test_07_repo_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError): m.repo_paths(Path(tmp))

    def test_08_install_only_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);(r/'contracts').mkdir();(r/'foundry.toml').write_text('[profile.default]\n')
            (r/'contracts'/'SSESettlement.sol').write_text('contract SSESettlement {}')
            m.install(r)
            self.assertTrue((r/'foundry/test/WP09NGasBench.t.sol').is_file())
            m.install(r) # idempotent
            (r/'foundry/test/WP09NGasBench.t.sol').write_text('CUSTOM')
            with self.assertRaises(RuntimeError):m.install(r)

    def test_09_config_rejects_wrong_optimization(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'dest'
            with patch.object(m,'command',return_value=(0,json.dumps({'optimizer_runs':200,'out':str(out/'out')}))):
                with self.assertRaises(RuntimeError):m.verify_config(Path(tmp),{},1,out)

    def test_10_config_rejects_nonisolated_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'dest'
            with patch.object(m,'command',return_value=(0,json.dumps({'optimizer_runs':1,'out':'out'}))):
                with self.assertRaises(RuntimeError):m.verify_config(Path(tmp),{},1,out)

    def test_11_config_accepts_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'dest'
            with patch.object(m,'command',return_value=(0,json.dumps({'optimizer_runs':1,'out':str(out/'out')}))):
                m.verify_config(Path(tmp),{},1,out)

    def test_12_invalid_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);(r/'contracts').mkdir();(r/'foundry.toml').write_text('[profile.default]\n')
            (r/'contracts'/'SSESettlement.sol').write_text('contract SSESettlement {}')
            with self.assertRaises(ValueError):m.main(['sweep','--repo',str(r),'--runs','0'])

    def test_13_synthetic_sweep(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);(r/'contracts').mkdir();(r/'foundry.toml').write_text('[profile.default]\n')
            (r/'contracts'/'SSESettlement.sol').write_text('contract SSESettlement {}')
            out=r/'.local/wp09n'
            def mock_build(cmd,*,cwd,env=None):
                runs=int(env['FOUNDRY_OPTIMIZER_RUNS'])
                if cmd[:2]==['forge','config']:
                    return 0,json.dumps({'optimizer_runs':runs,'out':env['FOUNDRY_OUT']})
                artifact=Path(env['FOUNDRY_OUT'])/'SSESettlement.sol'/'SSESettlement.json'
                artifact.parent.mkdir(parents=True,exist_ok=True)
                artifact.write_text(json.dumps({'deployedBytecode':{'object':'0x'+'11'*(23000-runs)}}))
                return 0,'Compiler run successful\n'
            with patch.object(m,'command',side_effect=mock_build):
                self.assertEqual(m.sweep(r,out,(1,200)),0)
            with (out/'optimizer_sweep.csv').open() as f:
                rows=list(csv.DictReader(f))
            self.assertEqual([int(x['runtime_bytes']) for x in rows],[22999,22800])

    def test_14_synthetic_gas_bench(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);(r/'contracts').mkdir();(r/'foundry.toml').write_text('[profile.default]\n')
            (r/'contracts'/'SSESettlement.sol').write_text('contract SSESettlement {}')
            m.install(r)
            logfile=''
            for i in range(16):
                logfile+=f'WP09N|register|n_active {i+4}\nWP09N|register|gas {10000+i}\n'
            with patch.object(m,'command',return_value=(0,logfile)):
                self.assertEqual(m.benchmark(r,r/'.local/wp09n'),0)
            with (r/'.local/wp09n/success_call_gas.csv').open() as f:
                self.assertEqual(len(list(csv.DictReader(f))),16)

    def test_15_no_report_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);(r/'contracts').mkdir();(r/'foundry.toml').write_text('[profile.default]\n')
            (r/'contracts'/'SSESettlement.sol').write_text('contract SSESettlement {}')
            m.install(r)
            with patch.object(m,'command',return_value=(1,'error bad test')):
                self.assertEqual(m.benchmark(r,r/'.local/wp09n'),1)
            self.assertFalse((r/'.local/wp09n/success_call_gas.csv').exists())

if __name__ == '__main__':
    unittest.main()
