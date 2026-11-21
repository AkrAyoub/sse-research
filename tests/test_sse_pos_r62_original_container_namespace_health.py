"""R62 tests: read-only owner original Docker network namespace API diagnostics.

All Docker, namespace and API readings mocked. No VM or real chain evidence.
"""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r62_original_container_namespace_health as m

class R62OriginalNetnsReadOnlyTests(unittest.TestCase):
    def test_requested_vs_effective_docker_port_publication(self):
        requested=json.dumps({"8545/tcp":[{"HostIp":"127.0.0.1","HostPort":"18545"}],
                              "8551/tcp":None})
        effective=json.dumps({"8545/tcp":None,"8551/tcp":None})
        self.assertEqual(m.host_ports(requested)["8545/tcp"],
                         [{"hostIp":"127.0.0.1","hostPort":18545}])
        self.assertIsNone(m.host_ports(effective)["8545/tcp"])
        self.assertIsNone(m.host_ports(effective)["8551/tcp"])

    def test_no_assumed_publication_from_exposed_ports(self):
        self.assertEqual(m.host_ports('{"8545/tcp":null,"5052/tcp":null}'),
                         {"8545/tcp":None,"5052/tcp":None})
        self.assertEqual(m.host_ports("{}"),{})
        self.assertEqual(m.host_ports("null"),{})

    def test_deny_invalid_port_mapping_json(self):
        for text in ("false",'{"8545/tcp":"not-an-array"}',
                     '{"8545/tcp":[{"HostIp":"root;shutdown","HostPort":"18545"}]}',
                     '{"8545/tcp":[{"HostIp":"::","HostPort":"not-a-number"}]}'):
            with self.subTest(text=text),self.assertRaises(m.R62Refused):
                m.host_ports(text)

    def test_only_one_original_execution_and_beacon_node(self):
        self.assertEqual(m.OWNER_CLIENTS,(
            ("sse31340-g2-el-r40","execution"),
            ("sse31340-g2-bn","beacon")))
        self.assertEqual(m.r60.VC,"sse31340-g2-vc")

    def test_original_container_must_remain_running(self):
        with patch.object(m.r60,"docker",return_value=json.dumps({"Running":False,"Pid":0})):
            with self.assertRaises(m.R62Refused):
                m.inspect_owner(m.r60.EL)

    def test_original_container_must_stay_on_original_network(self):
        with patch.object(m.r60,"docker",side_effect=[
            json.dumps({"Running":True,"Pid":12345}),"bridge"]):
            with self.assertRaises(m.R62Refused):
                m.inspect_owner(m.r60.EL)

    def test_inspect_owner_records_requested_and_effective_distinct(self):
        response=[
            json.dumps({"Running":True,"Pid":12345}),m.r60.NET,
            '{"8545/tcp":[{"HostIp":"127.0.0.1","HostPort":"18545"}]}',
            '{"8545/tcp":null}'
        ]
        with patch.object(m.r60,"docker",side_effect=response):
            outcome=m.inspect_owner(m.r60.EL)
        self.assertEqual(outcome["pid"],12345)
        self.assertEqual(outcome["requestedHostBindings"]["8545/tcp"][0]["hostPort"],18545)
        self.assertIsNone(outcome["effectiveHostBindings"]["8545/tcp"])
        self.assertTrue(outcome["noSecretsOrContainerEnvInspected"])

    def test_network_namespace_probe_only_uses_host_python_local_api(self):
        source=(ROOT/"tools/sse_pos_r62_original_container_namespace_health.py").read_text("utf-8")
        self.assertIn('["sudo","-n","nsenter","--target",str(pid),"--net"',source)
        self.assertIn('sys.executable,"-B","-c",NS_PROBE,kind',source)
        self.assertIn("http://127.0.0.1:8545",source)
        self.assertIn("http://127.0.0.1:5052",source)
        self.assertNotIn("http://10.50.",source)
        self.assertIn('urllib.request.ProxyHandler({})',source)

    def test_namespace_probe_json_accepts_only_allowed_method_results(self):
        fake={name:{"status":"connection_error","reasonType":"ConnectionRefusedError"}
              for name in ("eth_chainId","eth_blockNumber","net_peerCount")}
        class FakeProc:
            returncode=0
            stdout=json.dumps(fake)
        with patch.object(m.shutil,"which",return_value="/usr/bin/nsenter"), \
             patch.object(m.subprocess,"run",return_value=FakeProc()) as called:
            result=m.contained_net_probe(4321,"execution")
        self.assertEqual(result,fake)
        args=called.call_args.args[0]
        self.assertEqual(args[:6],["sudo","-n","nsenter","--target","4321","--net"])
        self.assertNotIn("docker",args)

    def test_network_namespace_probe_refuses_unknown_result_structure(self):
        class FakeProc:
            returncode=0
            stdout='{"malicious":"unexpected"}'
        with patch.object(m.shutil,"which",return_value="/usr/bin/nsenter"), \
             patch.object(m.subprocess,"run",return_value=FakeProc()):
            with self.assertRaises(m.R62Refused):
                m.contained_net_probe(4321,"execution")

    def test_original_health_summarizes_only_checked_real_results(self):
        fake={
            "execution":{"eth_chainId":{"status":"ok","value":hex(31340)},
                         "eth_blockNumber":{"status":"ok","value":"0x14"},
                         "net_peerCount":{"status":"ok","value":"0x0"}},
            "beacon":{"genesis":{"status":"ok","genesisTime":m.r60.GENESIS_TIME},
                      "head":{"status":"ok","headSlot":"400","headRoot":"0x"+"a"*64},
                      "finality":{"status":"ok","finalizedEpoch":"10","finalizedRoot":"0x"+"b"*64}},
        }
        def inspect(name):
            return {"pid":111 if name==m.r60.EL else 222,"requestedHostBindings":{},
                    "effectiveHostBindings":{},"status":"running"}
        with patch.object(m.r60,"owner_guard"),patch.object(m.shutil,"which",return_value="/usr/bin/nsenter"),\
             patch.object(m,"inspect_owner",side_effect=inspect),\
             patch.object(m.r60,"docker",return_value="true"),\
             patch.object(m,"contained_net_probe",side_effect=lambda pid,kind:fake[kind]):
            output=m.audit("a"*40)
        self.assertTrue(output["internalExecutionChainIdMatches31340"])
        self.assertTrue(output["internalBeaconGenesisTimeMatchesOriginal"])
        self.assertTrue(output["internalBeaconFinalizedCheckpointObserved"])
        self.assertNotIn("pid",output["execution"])
        self.assertFalse(output["actualExternalEthereumP2pPeersVerified"])

    def test_no_docker_network_changes_or_signer_material(self):
        source=(ROOT/"tools/sse_pos_r62_original_container_namespace_health.py").read_text("utf-8")
        for forbidden in ('"docker","start"','"docker","stop"',
                          '"docker","run"','"docker","network","connect"',
                          '"docker","network","create"','"zerotier-cli","join"',
                          '"--apply"','"wallet create"','"engine.jwt", "read"',
                          'docker(["logs"', 'Config.Env', 'Config.Cmd',
                          'docker(["exec"','--publish','--privileged'):
            self.assertNotIn(forbidden,source)
        self.assertIn('"noExistingDockerContainerOrBlockchainFilesChanged":True',source)
        self.assertIn('"sameOpenJoinOverlayNativeConnectivityStillUnverified":True',source)

if __name__=="__main__":
    unittest.main()
