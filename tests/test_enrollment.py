import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from propose_node import build_proposal

class EnrollmentChecks(unittest.TestCase):
    def test_multirole(self):
        d=build_proposal('cloud-c','10.0.0.12',['provider','consumer','monitor'],'none')
        self.assertEqual(d['nodes'][0]['status'],'pending')
    def test_full_node(self):
        d=build_proposal('eth-p2p','10.0.0.13',['ethereum_full_node'],'el_cl')
        self.assertEqual(d['nodes'][0]['ethereum_client'],'el_cl')
    def test_validator_requires_validator_client(self):
        with self.assertRaises(ValueError): build_proposal('new-val','10.0.0.14',['validator'],'none')
    def test_no_shell_in_ip(self):
        with self.assertRaises(ValueError): build_proposal('bad','10.0.0.1; rm -rf /',['provider'],'none')
    def test_no_automatic_active_role(self):
        self.assertEqual(build_proposal('mon-a','10.0.0.15',['monitor'],'none')['nodes'][0]['status'],'pending')

if __name__=='__main__': unittest.main()
