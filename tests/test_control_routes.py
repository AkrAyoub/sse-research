"""API route and authorization tests."""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
MODULE=ROOT/'apps/control-plane/api.py'
spec=importlib.util.spec_from_file_location('sse_control',MODULE)
control=importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


class ControlRoutesTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=dict(os.environ)
        os.environ['SSE_CONTROL_TOKEN']='lab-admin-token-very-long-and-random'
        os.environ['SSE_READ_TOKEN']='lab-observer-token-very-long-and-random'
        os.environ['SSE_PROPOSALS_DIR']=self.temp.name
        self.client=TestClient(control.app)
        self.admin={'Authorization':'Bearer lab-admin-token-very-long-and-random'}
        self.observer={'Authorization':'Bearer lab-observer-token-very-long-and-random'}
    def tearDown(self):
        self.temp.cleanup();os.environ.clear();os.environ.update(self.old)
    def test_local_dashboard_is_served(self):
        res=self.client.get('/')
        self.assertEqual(res.status_code,200)
        self.assertIn('SSE Control Plane',res.text)
        self.assertIn('id="nodes"',res.text)
        self.assertEqual(self.client.get('/dashboard.js').status_code,200)
    def test_no_authorization_does_not_leak_inventory(self):
        self.assertEqual(self.client.get('/v1/nodes').status_code,401)
        self.assertEqual(self.client.get('/v1/proposals').status_code,401)
        self.assertFalse(self.client.get('/healthz').json()['remote_execution'])
    def test_reader_cannot_propose_or_approve(self):
        self.assertEqual(self.client.get('/v1/nodes',headers=self.observer).status_code,200)
        self.assertEqual(self.client.post('/v1/enrollment-proposals',headers=self.observer,json=self.request()).status_code,401)
        self.assertEqual(self.client.post('/v1/proposals/a-node/approve',headers=self.observer).status_code,401)
    def request(self):
        return {'node_id':'cloud-c','private_ip':'10.43.1.77','ssh_user':'ubuntu',
                'roles':['provider','monitor'],'ethereum_client':'none','environment':'staging'}
    def test_proposal_approval_remains_offline_and_audited(self):
        r=self.client.post('/v1/enrollment-proposals',headers=self.admin,json=self.request())
        self.assertEqual(r.status_code,202,r.text)
        self.assertFalse(r.json()['connected'])
        r=self.client.post('/v1/proposals/cloud-c/approve',headers=self.admin)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['status'],'approved')
        self.assertFalse(r.json()['role_activated'])
        self.assertEqual(len(self.client.get('/v1/audit',headers=self.admin).json()['events']),2)
        self.assertEqual(self.client.post('/v1/proposals/cloud-c/approve',headers=self.admin).status_code,409)
    def test_duplicate_address_is_rejected(self):
        self.client.post('/v1/enrollment-proposals',headers=self.admin,json=self.request())
        second={**self.request(),'node_id':'cloud-d'}
        self.assertEqual(self.client.post('/v1/enrollment-proposals',headers=self.admin,json=second).status_code,409)
    def test_invalid_deployment_path_and_no_execute(self):
        self.assertEqual(self.client.post('/v1/deployment-plans',headers=self.admin,json={'paths':['../../etc/passwd']}).status_code,422)
        res=self.client.post('/v1/deployment-plans',headers=self.admin,json={'paths':['services/monitor-agent/monitor_agent.py']})
        self.assertEqual(res.status_code,200)
        self.assertEqual(res.json()['auto_candidate_roles'],['monitor'])
        self.assertFalse(res.json()['executed'])
    def test_weak_or_missing_tokens_fail_closed(self):
        os.environ['SSE_CONTROL_TOKEN']='short'
        self.assertEqual(self.client.get('/v1/nodes',headers=self.admin).status_code,503)

if __name__=='__main__': unittest.main()
