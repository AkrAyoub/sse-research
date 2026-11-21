"""R51: strictly read-only no-router-mapping NAT protocol capability detection."""
import json
import struct
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools"))
import sse_pos_r51_gateway_mapping_capability as r

class RealGatewayProtocolDiscoveryTests(unittest.TestCase):
    def test_pcp_announce_exact_24_bytes_no_lifetime(self):
        request=r.pcp_announce_request("10.50.56.8")
        self.assertEqual(len(request),24)
        self.assertEqual(request[:8],b"\x02\x00\x00\x00\x00\x00\x00\x00")
        self.assertEqual(request[8:],r.ipaddress.IPv6Address("::ffff:10.50.56.8").packed)

    def test_pcp_positive_reply_no_port_mapping_claim(self):
        packet=bytes((2,128,0,0))+b"\0"*20
        actual=r.parse_pcp_announce(packet)
        self.assertTrue(actual["pcpAnnounceSucceededWithoutMapping"])
        self.assertFalse(actual["pcpMapOrPeerOpcodeSent"])
        self.assertFalse(actual["pcpGatewayIngressReachabilityProven"])

    def test_pcp_error_not_misidentified_as_mapping(self):
        packet=bytes((2,128,0,2))+b"\0"*20
        actual=r.parse_pcp_announce(packet)
        self.assertTrue(actual["pcpAnnounceProtocolResponseRecognized"])
        self.assertFalse(actual["pcpAnnounceSucceededWithoutMapping"])
        self.assertEqual(actual["pcpResultCode"],2)

    def test_natpmp_exact_global_ipv4_without_exposure(self):
        reply=bytes((0,128))+struct.pack("!HI",0,1234)+bytes((8,8,8,8))
        actual=r.parse_natpmp_public_address(reply)
        self.assertTrue(actual["natPmpQuerySucceededWithoutMapping"])
        self.assertTrue(actual["natPmpGatewayReportedGlobalIPv4"])
        self.assertNotIn("8.8.8.8",str(actual))
        self.assertFalse(actual["natPmpPortMappingOpcodeSent"])

    def test_natpmp_no_response_never_proves_capability(self):
        actual=r.parse_natpmp_public_address(b"")
        self.assertFalse(actual["natPmpQuerySucceededWithoutMapping"])
        self.assertFalse(actual["natPmpGatewayIngressReachabilityProven"])

    def test_unique_private_default_gateway_no_raw_ip_output(self):
        fake=type("Result",(),{"returncode":0,"stdout":json.dumps([
            {"dst":"default","gateway":"10.50.56.1","dev":"eth0"}
        ])})()
        with patch.object(r.subprocess,"run",return_value=fake):
            self.assertEqual(r.gateway_route(),"10.50.56.1")
        self.assertNotIn("10.50.56.1",json.dumps(r.parse_pcp_announce(b"")))

    def test_ambiguous_multiple_gateways_refuse_probe(self):
        fake=type("Result",(),{"returncode":0,"stdout":json.dumps([
            {"dst":"default","gateway":"10.1.0.1"},
            {"dst":"default","gateway":"10.2.0.1"}
        ])})()
        with patch.object(r.subprocess,"run",return_value=fake):
            self.assertIsNone(r.gateway_route())

    def test_plan_does_not_transmit_any_gateway_packets(self):
        baseline={"privateDockerNetworkInternal":True}
        with patch.object(r.owner,"run",return_value=baseline):
            with patch.object(r,"gateway_route",return_value="10.0.0.1"):
                with patch.object(r,"query_gateway",side_effect=AssertionError("do not send")):
                    result=r.report("a"*40,False)
        self.assertTrue(result["noExternalNetworkTrafficDuringPlan"])
        self.assertEqual(result["probeStatus"],"READ_ONLY_NO_GATEWAY_PACKETS")

    def test_probe_gateway_no_public_route_does_not_send_packets(self):
        baseline={"privateDockerNetworkInternal":True}
        with patch.object(r.owner,"run",return_value=baseline):
            with patch.object(r,"gateway_route",return_value=None):
                with patch.object(r,"query_gateway",side_effect=AssertionError("do not send")):
                    result=r.report("a"*40,True)
        self.assertEqual(result["probeStatus"],"PRIVATE_DEFAULT_GATEWAY_NOT_DETERMINED")
        self.assertFalse(result["nativeInternetInboundTcpUdpProven"])

    def test_source_contains_no_mapping_requests_or_docker_mutation(self):
        src=(ROOT/"tools/sse_pos_r51_gateway_mapping_capability.py").read_text("utf-8")
        self.assertIn("PCP_ANNOUNCE_OPCODE = 0",src)
        self.assertIn("NATPMP_PUBLIC_ADDRESS_OPCODE = 0",src)
        self.assertIn("PORT = 5351",src)
        for forbidden in ('"run"', '"start"', '"stop"', '"restart"', '"kill"', '"rm"',
                          "wallet create", "mnemonic", "validators-dir", "secrets-dir"):
            self.assertNotIn(forbidden,src)

    def test_gateway_is_local_private_ipv4_only(self):
        for address in ("127.0.0.1","8.8.8.8","::1","not-an-ip"):
            with self.assertRaises(r.GatewayRefused):
                r.query_gateway(address)

if __name__ == "__main__":
    unittest.main()
