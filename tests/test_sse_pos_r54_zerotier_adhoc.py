"""R54 controllerless IPv6 ad-hoc ZeroTier plan and explicit join safeguards."""
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r54_zerotier_adhoc as m

class ZeroTierAdhocChain31340Tests(unittest.TestCase):
    def test_exact_public_controllerless_port_range_encoding(self):
        self.assertEqual(m.NETWORK_ID,"ff2328775f000000")
        self.assertEqual(int(m.NETWORK_ID[2:6],16),9000)
        self.assertEqual(int(m.NETWORK_ID[6:10],16),30303)
        self.assertTrue(m.protocol_guard()["ipv6UnicastOnly"])

    def test_ethereum_native_tcp_udp_ports_available(self):
        self.assertTrue(all(9000 <= p <= 30303 for p in (9000,9001,30303)))
        self.assertTrue(m.protocol_guard()["ethereumP2pTcpUdpPortsInRange"])

    def test_ssh_and_engine_ports_excluded(self):
        report=m.protocol_guard()
        self.assertTrue(report["ssh22ExcludedByNetwork"])
        self.assertTrue(report["engineJwtApi8551ExcludedByNetwork"])

    def test_public_join_requires_no_central_admin_registration(self):
        self.assertFalse(m.protocol_guard()["networkRegistrationOrPerNodeAdminApproval"])
        self.assertTrue(m.protocol_guard()["zeroTierPlanetaryInfraStillRequired"])

    def test_plan_uses_only_status_and_no_join(self):
        with patch.object(m,"refuse_owner_host"):
            with patch.object(m,"local_status",return_value={
                    "zeroTierInstalled":False,"adhocNetworkJoinedAndOk":False}):
                with patch.object(m,"command",side_effect=AssertionError("never join")):
                    data=m.plan()
        self.assertTrue(data["noSourceSystemDockerOrNetworkChangedByPlan"])
        self.assertFalse(data["nativeEthereumPermissionlessInternetJoinVerified"])

    def test_block_owner_signing_state(self):
        with patch.object(m.ORIGINAL_SIGNER_PATH.__class__,"exists",return_value=True):
            with self.assertRaises(m.AdhocRefused):
                m.refuse_owner_host()

    def test_refuse_join_without_installed_zerotier(self):
        with patch.object(m,"plan",return_value={"zeroTierInstalled":False}):
            with self.assertRaises(m.AdhocRefused):
                m.join()

    def test_refuse_join_without_explicit_tty_consent(self):
        with patch.object(m,"plan",return_value={"zeroTierInstalled":True,"adhocNetworkJoinedAndOk":False}):
            with patch.object(m.sys.stdin,"isatty",return_value=False):
                with self.assertRaises(m.AdhocRefused):
                    m.join()

    def test_existing_join_does_not_change_network(self):
        with patch.object(m,"plan",return_value={"zeroTierInstalled":True,"adhocNetworkJoinedAndOk":True}):
            with patch.object(m,"command",side_effect=AssertionError("no duplicate join")):
                self.assertEqual(m.join()["mode"],"already_joined_no_change")

    def test_source_never_starts_docker_or_original_clients(self):
        src=(ROOT/"tools/sse_pos_r54_zerotier_adhoc.py").read_text("utf-8")
        self.assertNotIn('"start", "sse31340-g2-vc"',src)
        self.assertNotIn('"docker", "run"',src)
        self.assertNotIn('"zerotier-cli", "leave"',src)
        self.assertIn('"zerotier-cli", "join", NETWORK_ID',src)

    def test_internet_p2p_requires_independent_evidence(self):
        with patch.object(m,"refuse_owner_host"):
            with patch.object(m,"local_status",return_value={
                    "zeroTierInstalled":True,"adhocNetworkJoinedAndOk":True}):
                report=m.plan()
        self.assertFalse(report["nativeEthereumPermissionlessInternetJoinVerified"])
        self.assertTrue(report["physicalOperatorIndependenceNotClaimed"])

if __name__=="__main__":
    unittest.main()
