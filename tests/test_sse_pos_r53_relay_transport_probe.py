"""R53: harmless public TCP/UDP relay proof, not fake Ethereum peers."""
import pathlib
import socket
import sys
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r53_relay_transport_probe as m

class R53PublicRawTransportTests(unittest.TestCase):
    def test_two_distinct_local_loopback_ports_not_rpc_or_p2p(self):
        self.assertEqual((m.TCP_LOCAL_PORT,m.UDP_LOCAL_PORT),(23353,23354))
        self.assertNotIn(m.TCP_LOCAL_PORT,(30303,8545,8551,9000,9001))
    def test_only_test_payload_never_validator_credentials(self):
        self.assertEqual(m.REQUEST,b"SSE_R53_PUBLIC_RAW_TRANSPORT_TEST_31340")
        self.assertEqual(m.REPLY,b"SSE_R53_RAW_TRANSPORT_ACK_31340")
    def test_invalid_port_refused(self):
        for p in (0,-1,65536):
            with self.assertRaises(m.RelayRefused):
                m.validate_port(p)
    def test_no_private_ipv4_endpoint_allowed(self):
        fake=[(socket.AF_INET,socket.SOCK_STREAM,6,"",("10.50.56.8",5000))]
        with patch.object(m.socket,"getaddrinfo",return_value=fake):
            with self.assertRaises(m.RelayRefused):
                m.public_ips("private.example",5000,socket.SOCK_STREAM)
    def test_global_ipv4_endpoint_permitted(self):
        fake=[(socket.AF_INET,socket.SOCK_DGRAM,17,"",("8.8.8.8",51000))]
        with patch.object(m.socket,"getaddrinfo",return_value=fake):
            self.assertEqual(m.public_ips("relay.example",51000,socket.SOCK_DGRAM)[0][3],
                             ("8.8.8.8",51000))
    def test_both_real_echoes_needed_to_pass(self):
        with patch.object(m,"send_tcp",return_value=True):
            with patch.object(m,"send_udp",return_value=False):
                report=m.check("relay.example",43000,"relay.example",43001)
        self.assertFalse(report["bothPublicTransportsActuallyWorked"])
        self.assertFalse(report["permissionlessNetworkReleaseReady"])
        self.assertTrue(report["noBesuDevp2pOrLighthouseDiscv5HandshakeYet"])
    def test_correct_status_if_both_echoes_observed(self):
        with patch.object(m,"send_tcp",return_value=True):
            with patch.object(m,"send_udp",return_value=True):
                report=m.check("relay.example",43000,"relay.example",43001)
        self.assertTrue(report["bothPublicTransportsActuallyWorked"])
        self.assertFalse(report["tcpAndUdpSameRelayIPv4OrAdvertisedPortProven"])
    def test_no_docker_or_original_chain_mutation_in_probe_source(self):
        src=(ROOT/"tools/sse_pos_r53_relay_transport_probe.py").read_text("utf-8")
        for prohibited in ("sudo", "docker run", "docker stop", "mnemonic",
                           "private key", "slashing", "engine.jwt"):
            self.assertNotIn(prohibited,src)
        self.assertIn('tcp.bind(("127.0.0.1", TCP_LOCAL_PORT))',src)
        self.assertIn('udp.bind(("127.0.0.1", UDP_LOCAL_PORT))',src)
if __name__=="__main__":
    unittest.main()
