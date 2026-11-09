import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from plan_deploy import plan
from validate_inventory import validate
class GitOpsTests(unittest.TestCase):
    def test_monitor_only(self):
        self.assertEqual(plan(['services/monitor-agent/a.py'])['auto_candidate_roles'],['monitor'])
    def test_sensitive_contract_never_auto(self):
        x=plan(['contracts/SSEBoundsPure.sol'])
        self.assertFalse(x['auto_candidate_roles']); self.assertTrue(x['manual_review'])
    def test_reject_duplicate(self):
        n={'node_id':'node-a','address':'192.0.2.10','ssh_user':'ubuntu','roles':['provider'],'ethereum_client':'none','status':'pending'}
        with self.assertRaises(ValueError): validate({'environment':'staging','nodes':[n,n]})
    def test_reject_false_validator(self):
        n={'node_id':'node-a','address':'192.0.2.10','ssh_user':'ubuntu','roles':['validator'],'ethereum_client':'none','status':'pending'}
        with self.assertRaises(ValueError): validate({'environment':'staging','nodes':[n]})
