"""Docker-mode tests use mocked Docker inspect; real HTTP worker runs in-process."""
import importlib.util
import json
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'services' / 'provider-agent'))
from compute_workload import compute_result
from sse_compute_docker import inspect_container, local_endpoint, run_compute_probe, ComputeError
from resource_profile import example_profile, profile_hash, verify_lease_profile

spec = importlib.util.spec_from_file_location('sse_compute_worker', ROOT/'services'/'provider-agent'/'compute_http_service.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
IMAGE='sha256:'+'aa'*32
HASH='0x'+'be'*32
ENDPOINT='http://127.0.0.1:8888'


def sample_inspect():
    return {'State': {'Running':True,'Paused':False,'Restarting':False},
            'HostConfig':{'NanoCpus':500_000_000,'Memory':256*2**20,'ReadonlyRootfs':True,
                          'NetworkMode':'bridge','Privileged':False,
                          'PortBindings':{'8877/tcp':[{'HostIp':'127.0.0.1','HostPort':'8888'}]}},
            'Image':IMAGE,'Id':'ab'*32,'Config':{'User':'10001:10001'}}


class ComputeWorkTest(unittest.TestCase):
    def test_same_nonce_is_deterministic(self):
        self.assertEqual(compute_result(7, 0, HASH), compute_result(7,0,HASH))

    def test_epoch_lease_request_are_bound(self):
        digest = compute_result(7,0,HASH)['resultDigest']
        self.assertNotEqual(digest,compute_result(8,0,HASH)['resultDigest'])
        self.assertNotEqual(digest,compute_result(7,1,HASH)['resultDigest'])
        self.assertNotEqual(digest,compute_result(7,0,'0x'+'aa'*32)['resultDigest'])

    def test_invalid_inputs_rejected(self):
        for lease,epoch,challenge in ((True,0,HASH),(7,-1,HASH),(7,0,'oops')):
            with self.assertRaises(ValueError):compute_result(lease,epoch,challenge)

    def test_canonical_profile_matches_mock_lease(self):
        p=example_profile(IMAGE,ENDPOINT,500,256*2**20)
        digest=profile_hash(p)
        lease={'resourceProfileHash':digest, 'serviceEndpointHash':__import__('resource_profile').endpoint_hash(ENDPOINT)}
        self.assertEqual(verify_lease_profile(p,lease,ENDPOINT),digest)
        with self.assertRaises(ValueError):verify_lease_profile(p,{**lease,'resourceProfileHash':'0x'+'11'*32},ENDPOINT)


class LocalDockerInspectTest(unittest.TestCase):
    def setUp(self):
        self.profile=example_profile(IMAGE,ENDPOINT,500,256*2**20)

    def read(self,d):
        with patch('sse_compute_docker.subprocess.run',return_value=type('Result',(),{'returncode':0,'stdout':json.dumps([d])})()):
            return inspect_container(self.profile,ENDPOINT,'sse-compute')

    def test_valid_inspection(self):
        result=self.read(sample_inspect())
        self.assertTrue(result['localDockerConfigurationInspected'])
        self.assertFalse(result['trustedHardwareAttestation'])

    def test_wrong_image_rejected(self):
        d=sample_inspect();d['Image']='sha256:'+'ff'*32
        with self.assertRaisesRegex(ComputeError,'image ID'):self.read(d)

    def test_wrong_cpu_and_memory_rejected(self):
        for key,value in (('NanoCpus', 1_000_000_000),('Memory',128*2**20)):
            d=sample_inspect();d['HostConfig'][key]=value
            with self.assertRaises(ComputeError):self.read(d)

    def test_wrong_port_and_interface_rejected(self):
        for bad in ('0.0.0.0','192.168.1.1'):
            d=sample_inspect();d['HostConfig']['PortBindings']['8877/tcp'][0]['HostIp']=bad
            with self.assertRaises(ComputeError):self.read(d)

    def test_elevated_container_rejected(self):
        d=sample_inspect();d['HostConfig']['Privileged']=True
        with self.assertRaises(ComputeError):self.read(d)

    def test_non_root_required(self):
        d=sample_inspect();d['Config']['User']='root'
        with self.assertRaises(ComputeError):self.read(d)

    def test_only_loopback_endpoint(self):
        for endpoint in ('http://localhost:8888','https://127.0.0.1:8888',
                         'http://127.0.0.1:8888/x','http://127.0.0.1:8888?x=1'):
            with self.assertRaises(ComputeError):local_endpoint(endpoint)

    def test_container_name_no_shell_injection(self):
        with self.assertRaises(ComputeError):inspect_container(self.profile,ENDPOINT,'x; whoami')


class ComputeWorkerHTTPTest(unittest.TestCase):
    def setUp(self):
        self.server=worker.make_server(0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.endpoint=f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)

    def test_real_compute_http_result(self):
        obs=run_compute_probe(self.endpoint,7,0,HASH)
        self.assertTrue(obs['workloadResultVerified'])
        self.assertFalse(obs['trustedHardwareAttestation'])
        self.assertEqual(obs['resultDigest'],compute_result(7,0,HASH)['resultDigest'])

    def test_existing_sse_challenge_contract_compatible(self):
        from sse_challenge import expected_response_hash
        payload=json.dumps({'leaseId':7,'epochId':0,'requestHash':HASH}).encode()
        with urlopen(Request(self.endpoint+'/v1/challenge',payload,{'Content-Type':'application/json'}),timeout=4) as result:
            body=json.load(result)
        self.assertEqual(body['responseHash'],expected_response_hash(HASH))

    def test_reject_bad_compute_request(self):
        payload=json.dumps({'leaseId':True,'epochId':0,'requestHash':HASH}).encode()
        with self.assertRaises(HTTPError) as ctx:
            urlopen(Request(self.endpoint+'/v1/compute',payload,{'Content-Type':'application/json'}),timeout=4)
        self.assertEqual(ctx.exception.code,400)

    def test_wrong_digest_rejected(self):
        import io
        expected=compute_result(7,0,HASH)
        expected['resultDigest']='sha256:'+'00'*32
        class FakeResponse:
            status=200
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def read(self,n):return json.dumps(expected).encode()
        with patch('sse_compute_docker.urlopen',return_value=FakeResponse()):
            with self.assertRaisesRegex(ComputeError,'did not match'):
                run_compute_probe(self.endpoint,7,0,HASH)


if __name__=='__main__':unittest.main()
