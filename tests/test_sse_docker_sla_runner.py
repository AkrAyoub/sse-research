"""R7: selected-provider Docker worker isolation and signed-result gating tests.

Offline by default: all Docker daemon responses are stubbed. Nothing is
launched, no host mounts are modified, and no blockchain transaction is sent.
"""
from __future__ import annotations

import json
import tempfile
import sys
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
sys.path.insert(0,str(ROOT/"services"/"monitor-agent"))

from eth_account import Account
from compute_workload import compute_result
from sse_challenge import keccak256, expected_response_hash
from sse_sla_manifest import proposed_policy, policy_hash
from sse_resource_profile_v2 import make_profile, resource_hash
from sse_docker_sla_runner import (DockerSLAError, validate_setup,
                                   docker_launch_argv, make_docker_runner)
from sse_compute_docker import inspect_container, ComputeError
from sse_direct_delivery import (ExchangeError, prepare_request, create_response,
                                 validate_response)
from sse_sla_manifest import canonical_policy
from sse_resource_profile_v2 import canonical_profile

sys.path.insert(0,str(ROOT/"services"/"provider-agent"))
import direct_work_service as provider_service

ENDPOINT="https://provider.demo.ts.net"
WORKER="http://127.0.0.1:8877"
CONTAINER="sse-compute-lease01"
SETTLEMENT="0x"+"22"*20
IMAGE="sha256:"+"a3"*32
HASH="0x"+"de"*32


def setup():
    profile=make_profile("deterministic_compute",ENDPOINT,image_digest=IMAGE,
                         cpu_milli=500,memory_bytes=512*2**20)
    policy=proposed_policy(service_kind="deterministic_compute",
                           chain_id=31337,settlement=SETTLEMENT,
                           resource_profile_hash=resource_hash(profile))
    return profile,policy


def inspected(profile, **changes):
    host={"NanoCpus":profile["cpuMilli"]*1_000_000,
          "Memory":profile["memoryBytes"],
          "MemorySwap":profile["memoryBytes"],
          "ReadonlyRootfs":True,
          "NetworkMode":"bridge",
          "Privileged":False,
          "PortBindings":{"8877/tcp":[{"HostIp":"127.0.0.1","HostPort":"8877"}]},
          "PidsLimit":64,"CapDrop":["ALL"],
          "SecurityOpt":["no-new-privileges:true","seccomp=builtin"],
          "CapAdd":None,"Devices":None,"Binds":None,
          "AutoRemove":True}
    host.update(changes)
    return {"State":{"Running":True,"Paused":False,"Restarting":False},
            "HostConfig":host,
            "Image":profile["imageDigest"],
            "Id":"a"*64,
            "Config":{"User":"10001:10001"}}


class DockerSlaTests(unittest.TestCase):
    def setUp(self):
        self.profile,self.policy=setup()

    def test_argv_uses_pinned_image_and_actual_cpu_memory_cgroup_limits(self):
        argv=docker_launch_argv(self.profile,self.policy,WORKER,CONTAINER)
        self.assertEqual(argv[:3],["docker","run","--detach"])
        self.assertEqual(argv[-1],IMAGE)
        self.assertIn("never",argv)
        self.assertEqual(argv[argv.index("--cpus")+1],"0.500")
        self.assertEqual(argv[argv.index("--memory")+1],str(512*2**20))
        self.assertEqual(argv[argv.index("--memory-swap")+1],str(512*2**20))
        self.assertEqual(argv[argv.index("--publish")+1],"127.0.0.1:8877:8877")
        self.assertEqual(argv[argv.index("--user")+1],"10001:10001")
        self.assertEqual(argv[argv.index("--cap-drop")+1],"ALL")
        self.assertIn("no-new-privileges:true",argv)
        self.assertIn("seccomp=builtin",argv)
        self.assertNotIn("--privileged",argv)
        self.assertNotIn("--volume",argv)
        self.assertNotIn("--mount",argv)
        self.assertIn("--read-only",argv)

    def test_unbound_resource_or_external_worker_is_denied(self):
        bad=dict(self.profile,memoryBytes=128*2**20)
        for profile,policy,url,name in [
            (bad,self.policy,WORKER,CONTAINER),
            (self.profile,self.policy,"https://external.example",CONTAINER),
            (self.profile,self.policy,WORKER,"bad;rm -rf"),
            (self.profile,self.policy,WORKER,"anything"),
        ]:
            with self.subTest(profile=profile,url=url,name=name),self.assertRaises(DockerSLAError):
                make_docker_runner(profile,policy,url,name)

    def test_strict_local_inspect_valid(self):
        record=inspected(self.profile)
        fake=type("Completed",(),{"returncode":0,"stdout":json.dumps([record])})()
        with patch("sse_compute_docker.subprocess.run",return_value=fake):
            result=inspect_container({
                "endpoint":WORKER,"imageId":IMAGE,
                "cpuMilli":500,"memoryBytes":512*2**20
            },WORKER,CONTAINER,strict_hardening=True)
        self.assertTrue(result["localDockerConfigurationInspected"])
        self.assertFalse(result["trustedHardwareAttestation"])

    def test_wrong_hardening_flags_fail_closed(self):
        invalid=[
          {"MemorySwap":2*512*2**20},
          {"PidsLimit":0},
          {"CapDrop":[]},
          {"SecurityOpt":["seccomp=unconfined"]},
          {"SecurityOpt":["no-new-privileges:true","seccomp=unconfined"]},
          {"SecurityOpt":["no-new-privileges:true","seccomp=builtin",
                          "apparmor=unconfined"]},
          {"NetworkMode":"host"},
          {"Binds":["/var/run/docker.sock:/var/run/docker.sock"]},
          {"Mounts":[{"Type":"bind","Source":"/var/run/docker.sock"}]},
          {"IpcMode":"host"},
          {"UsernsMode":"host"},
          {"Devices":[{"PathOnHost":"/dev/sda"}]},
          {"AutoRemove":False},
          {"PortBindings":{"8877/tcp":[{"HostIp":"127.0.0.1","HostPort":"8877"}],
                           "8000/tcp":[{"HostIp":"0.0.0.0","HostPort":"8000"}]}},
        ]
        for changes in invalid:
            with self.subTest(changes=changes):
                record=inspected(self.profile,**changes)
                fake=type("Completed",(),{"returncode":0,"stdout":json.dumps([record])})()
                with patch("sse_compute_docker.subprocess.run",return_value=fake):
                    with self.assertRaises(ComputeError):
                        inspect_container({
                            "endpoint":WORKER,"imageId":IMAGE,"cpuMilli":500,
                            "memoryBytes":512*2**20},
                            WORKER,CONTAINER,strict_hardening=True)

    def test_runner_requires_real_container_inspection_each_request(self):
        runner=make_docker_runner(self.profile,self.policy,WORKER,CONTAINER)
        expected=compute_result(1,0,HASH)
        fake_observation={"workloadResultVerified":True,
                          "resultDigest":expected["resultDigest"],
                          "rounds":expected["rounds"]}
        with patch("sse_docker_sla_runner.inspect_container",return_value={
                 "imageId":IMAGE,"runtimeReportedRunning":True}) as inspected_docker, \
             patch("sse_docker_sla_runner.run_compute_probe",
                   return_value=fake_observation) as observed:
            self.assertEqual(runner(1,0,HASH),expected)
        self.assertTrue(inspected_docker.call_args.kwargs["strict_hardening"])
        observed.assert_called_once_with(WORKER,1,0,HASH)

    def test_docker_error_refuses_provider_signature(self):
        runner=make_docker_runner(self.profile,self.policy,WORKER,CONTAINER)
        with patch("sse_docker_sla_runner.inspect_container",
                   side_effect=ComputeError("no trusted container")):
            with self.assertRaises(DockerSLAError):
                runner(1,0,HASH)

    def test_real_provider_serve_fails_closed_without_docker_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            policy_path=Path(temp)/"policy.json"
            profile_path=Path(temp)/"resource.json"
            policy_path.write_bytes(canonical_policy(self.policy))
            profile_path.write_bytes(canonical_profile(self.profile))
            args=[
                "--policy",str(policy_path),
                "--resource-profile",str(profile_path),
                "--endpoint",ENDPOINT,
                "--rpc-url","http://127.0.0.1:8545",
                "--signer-file","/run/sse/test-provider.key",
                "--journal-file",str(Path(temp)/"journal.sqlite"),
                "--port","8881","--serve",
            ]
            with patch.object(provider_service,"make_server",
                              side_effect=AssertionError("must not launch")), \
                 patch.object(provider_service,"_load_signer",
                              side_effect=AssertionError("must not read signer")), \
                 redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(provider_service.main(args),1)

    def test_validated_result_is_actually_signed_but_tamper_rejected(self):
        consumer,provider=Account.create(),Account.create()
        snapshot={
            "schema":"sse-onchain-inspection-v1","chainId":31337,
            "settlementAddress":SETTLEMENT,"domainSeparatorMatches":True,
            "blockHashPinned":True,"leaseId":1,"epochId":0,
            "lease":{"stateName":"Active","consumer":consumer.address.lower(),
                     "provider":provider.address.lower(),"slaPolicyHash":policy_hash(self.policy),
                     "resourceProfileHash":resource_hash(self.profile),
                     "reservationFee":0,"marketplaceRequestId":1,"totalEscrow":25,
                     "serviceEndpointHash":"0x"+keccak256(ENDPOINT.encode()).hex()},
            "epoch":{"exists":True,"requestHash":HASH,
                     "responseHash":expected_response_hash(HASH)},
        }
        nonce="0x"+"11"*32
        request=prepare_request(snapshot,self.policy,ENDPOINT,consumer,nonce)
        expected=compute_result(1,0,HASH)
        signed=create_response(request,snapshot,self.policy,ENDPOINT,provider,
                               compute_runner=lambda *_:expected)
        self.assertEqual(signed["result"],expected)
        self.assertEqual(validate_response(signed,request,snapshot,self.policy,ENDPOINT)
                         ["provider"],provider.address.lower())
        with self.assertRaises(ExchangeError):
            create_response(request,snapshot,self.policy,ENDPOINT,provider,
                            compute_runner=lambda *_:{**expected,"rounds":0})
        with self.assertRaises(ExchangeError):
            create_response(request,snapshot,self.policy,ENDPOINT,provider,
                            compute_runner=lambda *_: (_ for _ in ()).throw(
                                DockerSLAError("worker not available")))


if __name__=="__main__":
    unittest.main()
