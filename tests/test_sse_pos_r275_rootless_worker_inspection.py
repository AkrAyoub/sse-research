"""R275 local private rootless Docker inspector: mocked only, no host changes."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_compute_docker as worker
from compute_workload import compute_result
import sse_pos_r233_public_v2_compute_terms as terms

spec=importlib.util.spec_from_file_location(
    "sse_r275_real_provider",
    ROOT/"services"/"provider-agent"/"v2_compute_response_server.py")
server=importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

ENDPOINT="http://127.0.0.1:8877"
NAME="sse-compute-vm4709-worker"
ROOTLESS="/run/user/1001/docker.sock"
HASH="0x"+"ab"*32
PROFILE={
    "schema":terms.RESOURCE_SCHEMA,
    "serviceKind":"deterministic_compute",
    "workloadSpec":terms.WORKLOAD,
    "origin":"https://compute.example.org",
    "dockerImageId":"sha256:"+"ef"*32,
    "cpuMilli":500,
    "memoryBytes":256*2**20,
}
LOCAL_PROFILE={
    "endpoint":ENDPOINT,
    "imageId":PROFILE["dockerImageId"],
    "cpuMilli":500,
    "memoryBytes":256*2**20,
}


def strict_docker_fixture():
    return {
        "State":{"Running":True,"Paused":False,"Restarting":False},
        "HostConfig":{
            "NanoCpus":500_000_000,
            "Memory":256*2**20,
            "MemorySwap":256*2**20,
            "ReadonlyRootfs":True,
            "NetworkMode":"bridge",
            "Privileged":False,
            "PortBindings":{"8877/tcp":[{"HostIp":"127.0.0.1","HostPort":"8877"}]},
            "PidsLimit":32,
            "CapDrop":["ALL"],
            "SecurityOpt":["no-new-privileges","seccomp=builtin"],
            "AutoRemove":True,
            "Binds":None,
            "Mounts":[],
            "Devices":[],
        },
        "Image":PROFILE["dockerImageId"],
        "Id":"cd"*32,
        "Config":{"User":"10001:10001"},
        "Mounts":[],
    }


class TestR275RootlessDockerExplicitOnly(unittest.TestCase):
    def test_strict_inspector_rejects_remote_or_rootful_sockets(self):
        with patch.object(worker.os,"geteuid",return_value=1001):
            for path in (
                "/var/run/docker.sock",
                "tcp://127.0.0.1:2375",
                "unix:///run/user/1001/docker.sock",
                "/run/user/1002/docker.sock",
                "/tmp/docker.sock",
            ):
                with self.subTest(path=path),self.assertRaises(worker.ComputeError):
                    worker.require_local_owner_rootless_socket(path)

    def test_strict_inspector_denies_root_even_if_socket_path_matches(self):
        with patch.object(worker.os,"geteuid",return_value=0):
            with self.assertRaisesRegex(worker.ComputeError,"nonroot"):
                worker.require_local_owner_rootless_socket("/run/user/0/docker.sock")

    def test_expected_socket_missing_no_silent_fallback(self):
        with patch.object(worker.os,"geteuid",return_value=1001),patch.object(
            worker,"Path",side_effect=lambda path:Path("/nonexistent/r275/docker.sock")
        ),patch.object(worker.subprocess,"run") as run:
            with self.assertRaises(worker.ComputeError):
                worker.inspect_container(
                    LOCAL_PROFILE,ENDPOINT,NAME,strict_hardening=True,
                    docker_socket=ROOTLESS)
            run.assert_not_called()

    def test_symlink_socket_never_authorized(self):
        with tempfile.TemporaryDirectory() as tmp:
            real=Path(tmp)/"real"
            real.write_text("not an actual socket")
            link=Path(tmp)/"docker.sock"
            link.symlink_to(real)
            with patch.object(worker.os,"geteuid",return_value=1001),patch.object(
                worker,"Path",side_effect=lambda path:link):
                with self.assertRaises(worker.ComputeError):
                    worker.require_local_owner_rootless_socket(ROOTLESS)

    def test_inspector_optin_explicit_docker_host_unix_no_default(self):
        calls=[]
        def fake_run(cmd,**kwargs):
            calls.append((cmd,kwargs))
            return subprocess.CompletedProcess(cmd,0,json.dumps([strict_docker_fixture()]),"")
        with patch.object(worker,"require_local_owner_rootless_socket",
                          return_value="unix://"+ROOTLESS
        ) as validate, patch.object(worker.subprocess,"run",side_effect=fake_run):
            result=worker.inspect_container(
                LOCAL_PROFILE,ENDPOINT,NAME,strict_hardening=True,
                docker_socket=ROOTLESS)
        validate.assert_called_once_with(ROOTLESS)
        self.assertEqual(calls[0][0],[
            "docker","--host","unix://"+ROOTLESS,"container","inspect",NAME
        ])
        self.assertFalse(calls[0][1]["shell"])
        self.assertEqual(result["dockerDaemonSelection"],"EXACT_OWNER_ROOTLESS_UNIX_SOCKET")
        self.assertTrue(result["localDockerConfigurationInspected"])

    def test_strict_inspector_refuses_docker_policy_violation_even_on_rootless(self):
        wrong=strict_docker_fixture()
        wrong["HostConfig"]["Privileged"]=True
        with patch.object(worker,"require_local_owner_rootless_socket",
                          return_value="unix://"+ROOTLESS
        ),patch.object(worker.subprocess,"run",
                       return_value=subprocess.CompletedProcess(
                           [],0,json.dumps([wrong]),"")):
            with self.assertRaisesRegex(worker.ComputeError,"privileged"):
                worker.inspect_container(
                    LOCAL_PROFILE,ENDPOINT,NAME,strict_hardening=True,
                    docker_socket=ROOTLESS)

    def test_v2_provider_rootless_per_request_inspect_never_default(self):
        expected=compute_result(1,0,HASH)
        observed={"workloadResultVerified":True,
                  "resultDigest":expected["resultDigest"],
                  "rounds":expected["rounds"]}
        with patch.object(server.os,"geteuid",return_value=1001),patch.object(
            server,"inspect_container",return_value={"runtimeReportedRunning":True}
        ) as inspect,patch.object(
            server,"run_compute_probe",return_value=observed
        ) as probe:
            execute=server.make_docker_executor(
                PROFILE,ENDPOINT,NAME,rootless_docker=True)
            result=execute(1,0,HASH)
        self.assertEqual(result,expected)
        self.assertEqual(inspect.call_args.kwargs,{
            "strict_hardening":True,"docker_socket":ROOTLESS
        })
        self.assertEqual(probe.call_count,1)

    def test_v2_provider_rootless_refuses_root_process(self):
        with patch.object(server.os,"geteuid",return_value=0):
            execute=server.make_docker_executor(
                PROFILE,ENDPOINT,NAME,rootless_docker=True)
            with self.assertRaisesRegex(server.Refused,"forbids root"):
                execute(1,0,HASH)

    def test_v2_default_compatibility_does_not_add_rootless_socket_option(self):
        expected=compute_result(1,0,HASH)
        with patch.object(server,"inspect_container",
                          return_value={"runtimeReportedRunning":True}
        ) as inspect,patch.object(server,"run_compute_probe",
            return_value={
                "workloadResultVerified":True,
                "resultDigest":expected["resultDigest"],
                "rounds":expected["rounds"]}):
            result=server.make_docker_executor(PROFILE,ENDPOINT,NAME)(1,0,HASH)
        self.assertEqual(result,expected)
        self.assertEqual(inspect.call_args.kwargs,{"strict_hardening":True})


if __name__=="__main__":
    unittest.main()
