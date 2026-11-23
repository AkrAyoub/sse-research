"""R188 strict recovery code regression tests; no actual Docker or chain operations."""
from pathlib import Path
import sys
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r188_vm4709_guarded_existing_client_recovery as m

class R188(unittest.TestCase):
    def test_el_hardened_direct_native_entrypoint(self):
        argv=m.runner_args("el",["--network-id=31340"],["127.0.0.1:28545:8545/tcp"])
        self.assertEqual(argv[argv.index("--entrypoint")+1],"/opt/besu/bin/besu")
        self.assertIn("--read-only",argv)
        self.assertIn("ALL",argv)
        self.assertIn("no-new-privileges",argv)
        self.assertNotIn("--privileged",argv)
        self.assertNotIn("--checkpoint-state=/checkpoint/checkpoint-state.ssz",argv)
        self.assertNotIn("rm",argv)
        self.assertIn("type=bind,source="+str(m.ROOT/"testnet")+",target=/testnet,readonly",argv)
    def test_bn_fresh_db_exact_checkpoint_and_no_weak_subjectivity_bypass(self):
        argv=m.runner_args("bn",[
            "--testnet-dir=/testnet","bn","--allow-insecure-genesis-sync"],
            ["127.0.0.1:25052:5052/tcp"])
        self.assertIn("type=bind,source="+str(m.FRESH_BEACON)+",target=/data",argv)
        self.assertIn("type=bind,source="+str(m.CHECKPOINT)+",target=/checkpoint,readonly",argv)
        self.assertIn("--checkpoint-state=/checkpoint/checkpoint-state.ssz",argv)
        self.assertIn("--checkpoint-block=/checkpoint/checkpoint-block.ssz",argv)
        self.assertNotIn("--ignore-ws-check",argv)
        self.assertNotIn("--allow-insecure-genesis-sync",argv)
        self.assertNotIn("purge",str(argv))
    def test_observer_port_enforced(self):
        data={"HostConfig":{"PortBindings":{
            "30404/tcp":[{"HostIp":"fca0:2328:77e5:740c:ce60::1",
                           "HostPort":"30404"}],
            "30404/udp":[{"HostIp":"fca0:2328:77e5:740c:ce60::1",
                           "HostPort":"30404"}],
            "8545/tcp":[{"HostIp":"127.0.0.1","HostPort":"28545"}]}}}
        bindings=m.get_port_bindings("el",data)
        self.assertEqual(len(bindings),3)
        data["HostConfig"]["PortBindings"]["8545/tcp"][0]["HostIp"]="0.0.0.0"
        with self.assertRaisesRegex(m.Refused,"LOOPBACK"):
            m.get_port_bindings("el",data)
    def test_wrong_exact_image_refused(self):
        data={"Name":"/"+m.OLD["el"],"Image":"sha256:wrong"}
        with mock.patch.object(m,"exact_inspect",return_value=data):
            with self.assertRaisesRegex(m.Refused,"IMAGE"):
                m.verify_container("el")
if __name__=="__main__":unittest.main()
