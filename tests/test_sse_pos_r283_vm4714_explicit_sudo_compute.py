"""R283: dedicated VM4714 explicit sudo Docker ONLY; mocked, no privilege calls."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_compute_docker as docker

NAME="sse-compute-vm4714"
ENDPOINT="http://127.0.0.1:8877"
IMAGE="sha256:"+"ab"*32
PROFILE={
    "endpoint":ENDPOINT,"imageId":IMAGE,
    "cpuMilli":500,"memoryBytes":256*2**20
}


class RootfulLocalSocket:
    def is_symlink(self):return False
    def exists(self):return True
    def stat(self):return SimpleNamespace(st_mode=0o140660,st_uid=0)


class TestR283OwnerVm4714ExplicitSudoOnly(unittest.TestCase):
    def fixture(self,*,privileged=False):
        return {
            "State":{"Running":True,"Paused":False,"Restarting":False},
            "Image":IMAGE,"Id":"cd"*32,
            "Config":{"User":"10001:10001"},
            "Mounts":[],
            "HostConfig":{
                "NanoCpus":500000000,
                "Memory":256*2**20,"MemorySwap":256*2**20,
                "ReadonlyRootfs":True,"NetworkMode":"bridge",
                "Privileged":privileged,
                "PortBindings":{"8877/tcp":[
                    {"HostIp":"127.0.0.1","HostPort":"8877"}]},
                "PidsLimit":32,"CapDrop":["ALL"],
                "SecurityOpt":["no-new-privileges","seccomp=builtin"],
                "AutoRemove":True,"Binds":None,"Mounts":[],"Devices":[]
            }
        }

    def test_owned_sudo_rootful_read_only_fixed_host_actual_policy(self):
        seen=[]
        def run(args,**kwargs):
            seen.append((args,kwargs))
            return subprocess.CompletedProcess(args,0,json.dumps([self.fixture()]),"")
        with patch.object(docker.os,"geteuid",return_value=1001),patch.object(
            docker.pwd,"getpwuid",return_value=SimpleNamespace(pw_name="ayoubakrvm4714")
        ),patch.object(docker,"Path",return_value=RootfulLocalSocket()),patch.object(
            docker.subprocess,"run",side_effect=run),patch.dict(docker.os.environ,{
            "DOCKER_HOST":"tcp://remote.example:2375",
            "DOCKER_CONTEXT":"untrusted-rootless",
            "DOCKER_TLS_VERIFY":"1","DOCKER_CERT_PATH":"/tmp/certs",
        }):
            out=docker.inspect_container(PROFILE,ENDPOINT,NAME,
                strict_hardening=True,dedicated_vm4714_sudo_docker=True)
        self.assertEqual(seen[0][0],[
            "sudo","-n","docker","--host","unix:///var/run/docker.sock",
            "container","inspect",NAME
        ])
        self.assertFalse(seen[0][1]["shell"])
        for secret in ("DOCKER_HOST","DOCKER_CONTEXT",
                       "DOCKER_TLS_VERIFY","DOCKER_CERT_PATH"):
            self.assertNotIn(secret,seen[0][1]["env"])
        self.assertTrue(out["localDockerConfigurationInspected"])
        self.assertEqual(out["dockerDaemonSelection"],
                         "DEDICATED_VM4714_EXPLICIT_SUDO_ROOTFUL_UNIX_SOCKET")

    def test_other_vm_owner_can_never_use_vm4714_sudo(self):
        with patch.object(docker.os,"geteuid",return_value=1001),patch.object(
            docker.pwd,"getpwuid",return_value=SimpleNamespace(pw_name="ayoubakrvm4709")
        ),patch.object(docker.subprocess,"run") as run:
            with self.assertRaisesRegex(docker.ComputeError,"limited to nonroot VM4714"):
                docker.inspect_container(PROFILE,ENDPOINT,NAME,
                    strict_hardening=True,dedicated_vm4714_sudo_docker=True)
            run.assert_not_called()

    def test_root_process_refuses_privileged_docker_path(self):
        with patch.object(docker.os,"geteuid",return_value=0),patch.object(
            docker.subprocess,"run") as run:
            with self.assertRaises(docker.ComputeError):
                docker.inspect_container(PROFILE,ENDPOINT,NAME,
                    strict_hardening=True,dedicated_vm4714_sudo_docker=True)
            run.assert_not_called()

    def test_cannot_mix_sudo_rootful_with_rootless_socket(self):
        with patch.object(docker.subprocess,"run") as run:
            with self.assertRaisesRegex(docker.ComputeError,"requires strict policy"):
                docker.inspect_container(PROFILE,ENDPOINT,NAME,
                    strict_hardening=True,docker_socket="/run/user/1001/docker.sock",
                    dedicated_vm4714_sudo_docker=True)
            run.assert_not_called()

    def test_unhardened_sudo_is_disallowed(self):
        with patch.object(docker.subprocess,"run") as run:
            with self.assertRaisesRegex(docker.ComputeError,"requires strict policy"):
                docker.inspect_container(PROFILE,ENDPOINT,NAME,
                    dedicated_vm4714_sudo_docker=True)
            run.assert_not_called()

    def test_dedicated_sudo_rejects_unsafe_name_or_endpoint(self):
        with patch.object(docker.os,"geteuid",return_value=1001),patch.object(
            docker.pwd,"getpwuid",return_value=SimpleNamespace(pw_name="ayoubakrvm4714")
        ),patch.object(docker,"Path",return_value=RootfulLocalSocket()),patch.object(
            docker.subprocess,"run") as run:
            for name,url in (("sse-compute-vm4709-worker",ENDPOINT),
                             (NAME,"http://127.0.0.1:8899")):
                with self.subTest(name=name,url=url),self.assertRaisesRegex(
                    docker.ComputeError,"only exact dedicated"):
                    docker.inspect_container({
                        "endpoint":url,"imageId":IMAGE,
                        "cpuMilli":500,"memoryBytes":256*2**20
                    },url,name,strict_hardening=True,
                    dedicated_vm4714_sudo_docker=True)
            run.assert_not_called()

    def test_sudo_readonly_inspect_still_refuses_privileged_worker(self):
        with patch.object(docker.os,"geteuid",return_value=1001),patch.object(
            docker.pwd,"getpwuid",return_value=SimpleNamespace(pw_name="ayoubakrvm4714")
        ),patch.object(docker,"Path",return_value=RootfulLocalSocket()),patch.object(
            docker.subprocess,"run",return_value=subprocess.CompletedProcess(
                [],0,json.dumps([self.fixture(privileged=True)]),"")):
            with self.assertRaisesRegex(docker.ComputeError,"privileged"):
                docker.inspect_container(PROFILE,ENDPOINT,NAME,
                    strict_hardening=True,dedicated_vm4714_sudo_docker=True)

    def test_owner_script_noninteractive_explicit_sudo_refuses_before_mutation(self):
        p=ROOT/"scripts"/"r281_vm4714_real_compute_worker.sh"
        result=subprocess.run(["bash","-n",str(p)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        with tempfile.TemporaryDirectory() as d:
            fake=Path(d)
            (fake/"id").write_text(
                '#!/bin/sh\n'
                'case "$1" in -u) echo 1001 ;; -un) echo ayoubakrvm4714 ;; esac\n'
            )
            (fake/"git").write_text(
                '#!/bin/sh\n'
                'case "$1" in rev-parse) echo "'+('a'*40)+
                '" ;; status) exit 0 ;; esac\n'
            )
            (fake/"sudo").write_text(
                '#!/bin/sh\n'
                'echo SUDO_SHOULD_NOT_HAVE_BEEN_CALLED >&2\n'
                'exit 99\n'
            )
            for cmd in ("id","git","sudo"):
                (fake/cmd).chmod(0o700)
            env=dict(os.environ,PATH=str(fake)+os.pathsep+os.environ.get("PATH",""))
            run=subprocess.run(
                ["bash",str(p),'a'*40,"--run-sudo"],
                input="\n",capture_output=True,text=True,timeout=15,env=env
            )
            self.assertNotEqual(run.returncode,0)
            self.assertIn("real owner TTY required",run.stderr)
            self.assertNotIn("SUDO_SHOULD_NOT_HAVE_BEEN_CALLED",run.stderr)


if __name__=="__main__":
    unittest.main()
