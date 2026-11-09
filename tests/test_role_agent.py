import importlib.util
import json
import os
import sys
import threading
import unittest
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from generate_ansible_inventory import render
spec=importlib.util.spec_from_file_location('sse_agent',ROOT/'services/role-agent/agent.py')
agent=importlib.util.module_from_spec(spec);spec.loader.exec_module(agent)

class RoleAgentTest(unittest.TestCase):
    def test_local_heartbeat_is_factual(self):
        conf=agent.config({'SSE_NODE_ID':'cloud-a','SSE_ROLES':'provider,consumer',
                           'SSE_AGENT_HOST':'127.0.0.1','SSE_AGENT_PORT':'9984','SSE_REVISION':'commit-a1'})
        server=agent.make_server(conf)
        th=threading.Thread(target=server.serve_forever,daemon=True);th.start()
        try:
            with urllib.request.urlopen('http://127.0.0.1:9984/v1/status',timeout=3) as response:
                data=json.load(response)
            self.assertEqual(data['roles'],['provider','consumer'])
            self.assertTrue(data['software_running'])
            self.assertIsNone(data['blockchain_synced'])
        finally: server.shutdown();server.server_close();th.join(timeout=3)
    def test_reject_non_loopback(self):
        with self.assertRaises(ValueError):
            agent.config({'SSE_AGENT_HOST':'0.0.0.0'})
    def test_inventory_only_approved_nodes(self):
        sample={'environment':'staging','nodes':[
            {'node_id':'cloud-a','address':'10.2.0.1','ssh_user':'ubuntu','roles':['provider','consumer'],'ethereum_client':'none','status':'approved'},
            {'node_id':'cloud-b','address':'10.2.0.2','ssh_user':'ubuntu','roles':['monitor'],'ethereum_client':'none','status':'pending'}]}
        inv=render(sample)
        self.assertIn('cloud-a ansible_host=10.2.0.1',inv)
        self.assertNotIn('cloud-b ansible_host',inv)
        self.assertIn('[provider]',inv)
        self.assertIn('[consumer]',inv)
    def test_validator_role_remains_descriptive(self):
        sample={'environment':'staging','nodes':[
            {'node_id':'eth-a','address':'10.2.0.3','ssh_user':'ubuntu','roles':['validator'],'ethereum_client':'el_cl_vc','status':'approved'}]}
        result=render(sample)
        self.assertIn('[validator]',result)
        self.assertIn('eth-a ansible_host=10.2.0.3',result)

if __name__=='__main__':unittest.main()
