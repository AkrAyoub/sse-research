"""R55 actual, non-synthetic controllerless ZeroTier IPv6 TCP+UDP traffic test."""
import pathlib, sys, unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r55_zerotier_ipv6_transport as m
class R55Tests(unittest.TestCase):
    def test_fixed_open_overlay_id(self):
        self.assertEqual(m.NETWORK,"ff2328775f000000")
    def test_all_test_ports_within_adhoc_port_range(self):
        self.assertTrue(all(9000<=p<=30303 for p in
                            (m.TCP_PORT,m.UDP_PORT,m.UDP_CLIENT_PORT)))
    def test_udp_reply_requires_allowed_client_source_port(self):
        self.assertEqual(m.UDP_CLIENT_PORT,29002)
        self.assertNotEqual(m.UDP_CLIENT_PORT,m.UDP_PORT)
    def test_restrict_target_to_6plane(self):
        self.assertEqual(m.guarded_ip("fca0:2328:77b8:6578:a55::1"),
                         "fca0:2328:77b8:6578:a55::1")
        for ip in ("::1","fe80::1","2606:4700:4700::1111","10.50.56.8"):
            with self.assertRaises(m.R55Refused):
                m.guarded_ip(ip)
    def test_real_membership_network_id_must_match(self):
        with patch.object(m,"cli_json",return_value=[]):
            with self.assertRaises(m.R55Refused):
                m.membership()
    def test_real_membership_must_be_ok_and_public(self):
        with patch.object(m,"cli_json",return_value=[{
            "nwid":m.NETWORK,"status":"REQUESTING_CONFIGURATION",
            "type":"PRIVATE","assignedAddresses":[]}]):
            with self.assertRaises(m.R55Refused):
                m.membership()
    def test_real_membership_parses_ipv6_cidr(self):
        with patch.object(m,"cli_json",return_value=[{
            "nwid":m.NETWORK,"status":"OK","type":"PUBLIC",
            "assignedAddresses":["fca0:2328:77b8:6578:a55::1/40"],
            "portDeviceName":"ztTEST"}]):
            data=m.membership()
        self.assertEqual(data["localOverlayIpv6"],"fca0:2328:77b8:6578:a55::1")
    def test_plan_no_ethereum_or_connection_claim(self):
        with patch.object(m,"membership",return_value={
          "localOverlayIpv6":"fca0:2328:77b8:6578:a55::1",
          "networkId":m.NETWORK}):
            data=m.plan()
        self.assertTrue(data["noHostOrBlockchainChange"])
        self.assertFalse(data["actualCrossHostTcpUdpObserved"])
    def test_source_never_invokes_docker_or_zero_tier_modifying_methods(self):
        src=(ROOT/"tools/sse_pos_r55_zerotier_ipv6_transport.py").read_text()
        for forbidden in ("docker",'"join"', '"leave"', "systemctl", "engine.jwt",
                          "slashing", "sudo apt", "rm -rf"):
            self.assertNotIn(forbidden,src)
    def test_client_uses_actual_socket_ipv6_and_binds_udp_inbound_port(self):
        src=(ROOT/"tools/sse_pos_r55_zerotier_ipv6_transport.py").read_text()
        self.assertIn('socket.AF_INET6, socket.SOCK_STREAM',src)
        self.assertIn('socket.AF_INET6, socket.SOCK_DGRAM',src)
        self.assertIn('u.bind((me["localOverlayIpv6"], UDP_CLIENT_PORT))',src)
        self.assertIn('u.sendto(PROBE, (ip, UDP_PORT))',src)
        self.assertIn('t.connect((ip, TCP_PORT))',src)
    def test_server_binds_specific_ipv6_not_unspecified_global(self):
        src=(ROOT/"tools/sse_pos_r55_zerotier_ipv6_transport.py").read_text()
        self.assertIn('t.bind((ip, TCP_PORT))',src)
        self.assertIn('u.bind((ip, UDP_PORT))',src)
        self.assertNotIn('t.bind(("::",',src)
        self.assertNotIn('u.bind(("::",',src)
    def test_no_self_target_fake_success(self):
        with patch.object(m,"plan",return_value={"localOverlayIpv6":"fca0:2328:77b8:6578:a55::1"}):
            with self.assertRaises(m.R55Refused):
                m.client("fca0:2328:77b8:6578:a55::1")
if __name__=="__main__":
    unittest.main()
