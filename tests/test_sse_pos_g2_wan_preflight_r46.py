"""R46: real one-host G2 native P2P is NOT a public permissionless network."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools"))
import sse_pos_g2_wan_preflight_r46 as m

class R46ExistingChainPublicWANPreflight(unittest.TestCase):
    def test_fixed_only_current_existing_docker_clients(self):
        self.assertEqual(m.EL, "sse31340-g2-el-r40")
        self.assertEqual(m.BN, "sse31340-g2-bn")
        self.assertEqual(m.VC, "sse31340-g2-vc")

    def test_besu_p2p_disabled_not_counted_as_internet(self):
        def fake(name, fmt):
            if fmt == "{{json .State.Running}}": return True
            if fmt == "{{json .Config}}": return {"Cmd": ["--p2p-enabled=false"]}
            return {"NetworkMode": m.NETWORK, "PortBindings": {}}
        with patch.object(m, "docker_inspect", side_effect=fake):
            report=m.classify_bindings(m.EL)
        self.assertFalse(report["p2pInboundTcpPublished"])
        self.assertFalse(report["p2pInboundUdpPublished"])
        self.assertTrue(report["ethereumExecutionP2pExplicitlyDisabled"])

    def test_beacon_without_internet_ports_is_not_public(self):
        def fake(name, fmt):
            if fmt == "{{json .State.Running}}": return True
            if fmt == "{{json .Config}}": return {"Cmd": ["bn","--http"]}
            return {"NetworkMode": m.NETWORK, "PortBindings": {"5052/tcp": [{"HostIp":"127.0.0.1","HostPort":"15052"}]}}
        with patch.object(m, "docker_inspect", side_effect=fake):
            report=m.classify_bindings(m.BN)
        self.assertFalse(report["p2pInboundTcpPublished"])
        self.assertFalse(report["p2pInboundUdpPublished"])
        self.assertFalse(report["hasExplicitPublicEnrAddress"])

    def test_private_host_and_carrier_grade_nat_addresses_classified_without_echo(self):
        entries=[{"addr_info":[
            {"local":"10.50.56.8"},
            {"local":"100.80.12.1"},
            {"local":"127.0.0.1"},
            {"local":"fe80::10"},
        ]}]
        class Fake:
            returncode=0
            stdout=__import__("json").dumps(entries)
        with patch.object(m.subprocess, "run", return_value=Fake()):
            result=m.interface_ip_observation()
        self.assertFalse(result["hostHasDirectGlobalIpv4"])
        self.assertTrue(result["carrierGradeNatRangePresentOnInterface"])
        self.assertNotIn("10.50.56.8", str(result))
        self.assertNotIn("100.80.12.1", str(result))

    def test_globally_routable_ipv6_is_observation_not_inbound_proof(self):
        entries=[{"addr_info":[{"local":"2001:4860:4860::8888"}]}]
        class Fake:
            returncode=0
            stdout=__import__("json").dumps(entries)
        with patch.object(m.subprocess, "run", return_value=Fake()):
            result=m.interface_ip_observation()
        self.assertTrue(result["hostHasDirectGlobalIpv6"])
        self.assertTrue(result["doesNotProveInboundReachability"])

    def test_real_chain_and_beacon_genesis_required_for_readiness_audit(self):
        with patch.object(m.health, "require_actual_source"):
            with patch.object(m.health, "rpc", return_value="0x1"):
                with self.assertRaisesRegex(m.ReadinessRefused, "31340"):
                    m.run("a"*40)
            with patch.object(m.health, "rpc", return_value=hex(31340)):
                with patch.object(m.health, "beacon", return_value={"genesis_time": "1"}):
                    with self.assertRaisesRegex(m.ReadinessRefused, "genesis"):
                        m.run("a"*40)

    def test_no_false_claim_of_publicly_reachable_node_from_docker_binding(self):
        src = (ROOT/"tools/sse_pos_g2_wan_preflight_r46.py").read_text("utf-8")
        self.assertIn('"incomingInternetReachabilityProven": False', src)
        self.assertIn('"nativeExecutionDevp2pHandshakeProven": False', src)
        self.assertIn('"consensusLibp2pAndDiscv5HandshakeProven": False', src)
        self.assertIn('"existingG2P2pEnabledForExternalPeers": False', src)

    def test_no_source_key_generation_or_docker_mutation(self):
        s=(ROOT/"tools/sse_pos_g2_wan_preflight_r46.py").read_text("utf-8")
        for token in ('"start"', '"stop"', '"restart"', '"rm"', '"run"', '"kill"', "wallet create", "mnemonic"):
            self.assertNotIn(token, s)
        self.assertIn("publicReleaseRequiresAtLeastTwoIndependentSeedOperators", s)
        self.assertIn('"nativeExecutionDevp2pHandshakeProven": False', s)
        self.assertIn('"consensusLibp2pAndDiscv5HandshakeProven": False', s)
        self.assertIn('"clientContainersOrNetworksModified": False', s)

    def test_current_lab_no_fake_independent_operator_proof(self):
        with patch.object(m.health, "require_actual_source"), \
             patch.object(m.health, "rpc", return_value=hex(31340)), \
             patch.object(m.health, "beacon", return_value={"genesis_time": str(m.base.GENESIS_TIME)}):
            with patch.object(m, "classify_bindings", side_effect=[
                {"currentlyRunning":True,"ethereumExecutionP2pExplicitlyDisabled":True,
                 "p2pInboundTcpPublished":False,"p2pInboundUdpPublished":False},
                {"currentlyRunning":True,"p2pInboundTcpPublished":False,
                 "p2pInboundUdpPublished":False},
            ]):
                with patch.object(m.health.internal, "state", side_effect=lambda n: {"Running": n != m.ORIGINAL}):
                    class Fake:
                        returncode=0
                        stdout=b"true\n"
                    with patch.object(m.subprocess, "run", return_value=Fake()):
                        with patch.object(m, "interface_ip_observation", return_value={"hostHasDirectGlobalIpv4":False}):
                            o=m.run("a"*40)
        self.assertFalse(o["existingG2P2pEnabledForExternalPeers"])
        self.assertFalse(o["allNeededP2pPortBindingsConfigured"])
        self.assertFalse(o["permissionlessInternetParticipationProven"])
        self.assertEqual(o["declaredPhysicalOwnerFaultDomains"], 1)

if __name__=="__main__":
    unittest.main()
