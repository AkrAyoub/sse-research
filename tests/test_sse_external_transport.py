"""Alternative transports never steal existing Tailscale identity."""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_external_transport import decide,TransportError

ON={"BackendState":"Running","Self":{"Online":True,"TailscaleIPs":["100.65.29.101"]}}
OFF={"BackendState":"NeedsLogin"}

class ExternalTransportTests(unittest.TestCase):
    def test_external_existing_account_preserved_in_every_mode(self):
        for pref in ("auto","native-p2p","relay","tailscale","existing-tailnet"):
            with self.subTest(pref=pref):
                r=decide(pref,tailscale_status=ON)
                self.assertTrue(r["mustPreserveExistingTailscale"])
                self.assertFalse(r["existingTailscaleLoggedOut"])
                self.assertFalse(r["existingTailscaleRetagged"])
                self.assertFalse(r["networkReachabilityVerified"])
                self.assertFalse(r["blockchainRoleEligibilityAffectedByTransport"])
                self.assertFalse(r["ethereumTransactionsSent"])

    def test_auto_does_not_join_any_tailnet(self):
        report=decide("auto",tailscale_status=OFF)
        self.assertEqual(report["selectedTransport"],"native-p2p-or-relay")
        self.assertTrue(report["mayOperateWithoutTailscale"])
        self.assertFalse(report["daemonStarted"])

    def test_optional_lab_tailnet_is_not_required_permissionless_admission(self):
        r=decide("tailscale",tailscale_status=ON)
        self.assertIn("ISOLATED_SIDECAR",r["nextNetworkCheck"])
        self.assertFalse(r["mayOperateWithoutTailscale"])
        r=decide("existing-tailnet",tailscale_status=OFF)
        self.assertIn("UNAVAILABLE",r["nextNetworkCheck"])

    def test_invalid_values_do_not_get_network_access(self):
        for bad in ("unknown",[],{},None):
            with self.subTest(pref=bad),self.assertRaises(TransportError):
                decide(bad,tailscale_status=ON)
        with self.assertRaises(TransportError):
            decide("auto",tailscale_status="logged in")

if __name__=="__main__":
    unittest.main()
