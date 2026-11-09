import importlib.util, os, tempfile,unittest
from pathlib import Path
from fastapi.testclient import TestClient
MODULE=Path(__file__).resolve().parents[1]/'apps/control-plane/api.py'
spec=importlib.util.spec_from_file_location('sse_control',MODULE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class ControlAPI(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ['SSE_PROPOSALS_DIR']=self.tmp.name
        os.environ['SSE_CONTROL_TOKEN']='this-is-a-test-token-not-a-secret'
        self.client=TestClient(mod.app)
    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop('SSE_PROPOSALS_DIR',None)
        os.environ.pop('SSE_CONTROL_TOKEN',None)
    def test_unauthorized(self):
        self.assertEqual(self.client.get('/v1/nodes').status_code,401)
    def test_health_does_not_claim_deployment(self):
        self.assertFalse(self.client.get('/healthz').json()['remote_execution'])
    def test_proposal_only_with_credential(self):
        headers={'Authorization':'Bearer this-is-a-test-token-not-a-secret'}
        r=self.client.post('/v1/enrollment-proposals',headers=headers,json={
            'node_id':'new-provider','private_ip':'10.23.0.8','roles':['provider','monitor'], 'ethereum_client':'none'})
        self.assertEqual(r.status_code,202,r.text)
        self.assertEqual(r.json()['status'],'pending')
        self.assertTrue((Path(self.tmp.name)/'new-provider.json').exists())
        r2=self.client.post('/v1/enrollment-proposals',headers=headers,json={
            'node_id':'new-provider','private_ip':'10.23.0.8','roles':['provider'], 'ethereum_client':'none'})
        self.assertEqual(r2.status_code,409)
    def test_bad_roles_rejected(self):
        r=self.client.post('/v1/enrollment-proposals',headers={'Authorization':'Bearer this-is-a-test-token-not-a-secret'},json={
            'node_id':'new-node','private_ip':'10.23.0.8','roles':['root'], 'ethereum_client':'none'})
        self.assertEqual(r.status_code,422)

if __name__=='__main__':unittest.main()
