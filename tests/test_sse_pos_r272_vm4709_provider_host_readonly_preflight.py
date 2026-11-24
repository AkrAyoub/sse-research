"""R272 real host metadata and local Unix Docker socket: READ-ONLY mocked tests."""
import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r272_vm4709_provider_host_readonly_preflight as m


class TestR272Vm4709ProviderReadOnlyHostAudit(unittest.TestCase):
    def test_actual_linux_memavailable_parsing(self):
        self.assertEqual(m.available_memory("MemTotal: 2000000 kB\nMemAvailable: 10600000 kB\n"),
                         10600000*1024)
        for malformed in ("", "MemAvailable: nope kB", "MemAvailable: 0 kB",
                          "MemAvailable: 222 MB"):
            with self.subTest(malformed=malformed),self.assertRaises(m.Refused):
                m.available_memory(malformed)

    def test_missing_and_fake_socket_never_assumed_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            missing=folder/"missing"
            self.assertEqual(m.classify_docker_socket(missing)["state"],"ABSENT")
            fake=folder/"file"
            fake.write_text("not a UNIX Docker socket")
            self.assertEqual(m.classify_docker_socket(fake)["state"],"NOT_UNIX_SOCKET")
            symbolic=folder/"symbolic"
            symbolic.symlink_to(fake)
            self.assertEqual(m.classify_docker_socket(symbolic)["state"],"SYMLINK_REFUSED")

    def test_local_live_unix_socket_not_a_remote_docker_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"docker.sock"
            sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            try:
                sock.bind(str(path))
                result=m.classify_docker_socket(path)
                self.assertEqual(result["state"],"ACCESSIBLE")
                self.assertTrue(result["ownerWritable"])
            finally:
                sock.close()

    def test_docker_listing_uses_only_local_unix_socket_readonly_ps(self):
        seen=[]
        def fake(cmd,**kwargs):
            seen.append((cmd,kwargs))
            return subprocess.CompletedProcess(cmd,0,"sse31340-node-el Up 6 hours\nsse31340-node-bn Up 6 hours\n","")
        result=m.docker_container_listing(run=fake)
        self.assertEqual(result["dockerListingStatus"],"ACTUAL_CONTAINERS_READONLY_LISTED")
        self.assertEqual(result["dockerContainerNames"],["sse31340-node-el","sse31340-node-bn"])
        self.assertEqual(seen[0][0],[
            "docker","--host","unix:///var/run/docker.sock",
            "ps","--format","{{.Names}} {{.Status}}"])
        self.assertFalse(seen[0][1]["shell"])

    def test_denied_docker_does_not_stop_cpu_disk_or_escalate(self):
        calls=[]
        def fake_query():
            calls.append("read-only docker ps")
            return {"dockerListingStatus":"ACCESS_DENIED_OR_DAEMON_UNAVAILABLE",
                    "dockerContainerNames":[],"dockerContainersInspected":False}
        def fake_spec(mod):
            return None if mod=="eth_account" else SimpleNamespace()
        with patch.object(m.os,"geteuid",return_value=1011),patch.object(
            m.pwd,"getpwuid",return_value=SimpleNamespace(pw_name=m.EXPECTED_OWNER)
        ),patch.object(
            m.os,"cpu_count",return_value=4
        ),patch.object(
            m.shutil,"disk_usage",return_value=SimpleNamespace(free=92*1024**3)
        ),patch.object(m.shutil,"which",return_value="/usr/bin/docker"),patch.object(
            m,"classify_docker_socket",return_value={
                "state":"PERMISSION_DENIED","ownerWritable":False}
        ),patch.object(m.importlib.util,"find_spec",side_effect=fake_spec):
            result=m.collect(meminfo="MemAvailable: 10485760 kB",
                             docker_query=fake_query)
        self.assertEqual(calls,["read-only docker ps"])
        self.assertEqual(result["logicalCpus"],4)
        self.assertTrue(result["resourceMinimumsMetForProposedIsolatedWorker"])
        self.assertFalse(result["ethAccountInstalledInThisPython"])
        self.assertFalse(result["newProviderWalletCreated"])
        self.assertFalse(result["dockerOrNodeMutated"])
        self.assertFalse(result["nativeTransactionSent"])
        self.assertEqual(result["operatorActionNeeded"],
            "REVIEW_READONLY_PRIVILEGED_DOCKER_INSPECTION_WITH_OWNER")

    def test_no_non_vm4709_or_root_accounts(self):
        with patch.object(m.os,"geteuid",return_value=0):
            with self.assertRaisesRegex(m.Refused,"non-root"):
                m.collect(meminfo="MemAvailable: 10000000 kB")
        with patch.object(m.os,"geteuid",return_value=1055),patch.object(
             m.pwd,"getpwuid",return_value=SimpleNamespace(pw_name="wrong")):
            with self.assertRaisesRegex(m.Refused,"VM4709"):
                m.collect(meminfo="MemAvailable: 10000000 kB")

    def test_failed_docker_cli_does_not_fake_running_provider(self):
        result=m.docker_container_listing(run=lambda cmd,**kwargs:
            subprocess.CompletedProcess(cmd,1,"","permission denied"))
        self.assertEqual(result["dockerListingStatus"],"ACCESS_DENIED_OR_DAEMON_UNAVAILABLE")
        self.assertFalse(result["dockerContainersInspected"])

if __name__=="__main__":
    unittest.main()
