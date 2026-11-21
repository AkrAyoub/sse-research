"""R58: local unit tests for read-only pinned client IPv6 flag audit.

All subprocess/ZeroTier/Docker responses are mocked. These do NOT constitute
real network, Besu, Lighthouse or validator measurements.
"""
import json
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import sse_pos_r58_native_ipv6_cli_audit as m


class R58NativeIpv6AuditTests(unittest.TestCase):
    def test_hash_preserves_original_owner_public_archive(self):
        self.assertEqual(m.ARCHIVE_SHA, "1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7")

    def test_exact_client_ids_match_repo_pins(self):
        pins = json.loads((ROOT / "config/pos_client_image_pins.json").read_text("utf-8"))["images"]
        self.assertEqual(m.BESU_REF, pins["besu"]["ref"])
        self.assertEqual(m.BESU_ID, pins["besu"]["imageId"])
        self.assertEqual(m.LIGHTHOUSE_REF, pins["lighthouse"]["ref"])
        self.assertEqual(m.LIGHTHOUSE_ID, pins["lighthouse"]["imageId"])

    def test_positive_and_negative_flag_detection(self):
        example = "  --port6 <PORT> and --port <PORT> and --enr-tcp6-port"
        self.assertTrue(m.flag_present(example, "port"))
        self.assertTrue(m.flag_present(example, "port6"))
        self.assertFalse(m.flag_present(example, "port60"))
        self.assertTrue(m.flag_present(example, "enr-tcp6-port"))
        self.assertFalse(m.flag_present(example, "enr-udp6-port"))

    def test_reject_untrusted_flag_input(self):
        with self.assertRaises(m.R58Refused):
            m.flag_present("test", "port; rm -rf")
        with self.assertRaises(m.R58Refused):
            m.flag_present("test", "port_foo")

    def test_membership_requires_exact_public_controllerless_id(self):
        payload = [{"nwid": m.NETWORK, "type": "PUBLIC", "status": "OK",
                    "portDeviceName": "ztrb6cq527",
                    "assignedAddresses": ["fca0:2328:77b8:6578:a55::1/40"]}]
        with patch.object(m, "run", side_effect=[json.dumps(payload),
                       "5: ztrb6cq527 inet6 fca0:2328:77b8:6578:a55::1/40"]):
            self.assertEqual(m.membership(),
                             ("ztrb6cq527", "fca0:2328:77b8:6578:a55::1"))

    def test_refuse_non_public_or_wrong_overlay(self):
        for override in ({"nwid": "ff2328775f000001"}, {"type": "PRIVATE"}, {"status": "REQUESTING_CONFIGURATION"}):
            payload = {"nwid": m.NETWORK, "type": "PUBLIC", "status": "OK",
                       "portDeviceName": "ztrb6cq527",
                       "assignedAddresses": ["fca0:2328:77b8:6578:a55::1/40"]}
            payload.update(override)
            with self.subTest(override=override), patch.object(m, "run", return_value=json.dumps([payload])):
                with self.assertRaises(m.R58Refused):
                    m.membership()

    def test_refuse_wrong_overlay_address(self):
        payload = [{"nwid": m.NETWORK, "type": "PUBLIC", "status": "OK",
                    "portDeviceName": "ztrb6cq527",
                    "assignedAddresses": ["::1/128", "fe80::a/64"]}]
        with patch.object(m, "run", return_value=json.dumps(payload)):
            with self.assertRaises(m.R58Refused):
                m.membership()

    def test_cli_help_is_actual_offline_no_ports_no_mounts(self):
        calls = []
        with patch.object(m, "run", side_effect=lambda cmd, timeout=0: (calls.append(cmd), "help")[1]):
            m.offline_help(m.BESU_REF)
            m.offline_help(m.BESU_REF, experimental=True)
            m.offline_help(m.LIGHTHOUSE_REF, lighthouse=True)
        self.assertEqual(len(calls), 3)
        for cmd in calls:
            self.assertIn("--network", cmd)
            self.assertEqual(cmd[cmd.index("--network")+1], "none")
            self.assertIn("--read-only", cmd)
            self.assertIn("--cap-drop", cmd)
            self.assertIn("ALL", cmd)
            self.assertIn("--security-opt", cmd)
            self.assertNotIn("--publish", cmd)
            self.assertNotIn("--mount", cmd)
            self.assertNotIn("--privileged", cmd)
            self.assertNotIn("host", [cmd[i+1] for i,v in enumerate(cmd[:-1]) if v == "--network"])
        self.assertEqual(calls[1][-1], "--Xhelp")
        self.assertEqual(calls[2][-2:], ["bn", "--help"])
        self.assertEqual(calls[2][calls[2].index("--entrypoint")+1], "lighthouse")

    def test_help_result_does_not_require_xhelp(self):
        with patch.object(m, "signer_guard"), patch.object(m, "archive_guard", return_value=16218), \
             patch.object(m, "membership", return_value=("ztrb6cq527", "fca0:2328:77b8:6578:a55::1")), \
             patch.object(m, "run", side_effect=["29.1.3", ""]), \
             patch.object(m, "verify_image"), \
             patch.object(m, "offline_help", side_effect=["--p2p-interface-ipv6 --p2p-host-ipv6",
                   "--listen-address --enable-private-discovery", m.R58Refused("Xhelp unavailable")]):
            report = m.audit()
        self.assertTrue(report["originalChain31340PublicArchiveSha256Verified"])
        self.assertFalse(report["besuExtendedHelpAvailable"])
        self.assertFalse(report["actualEthereumPeerHandshakeObserved"])
        self.assertFalse(report["readyToExecuteNativeNodeWithoutDesignReview"])

    def test_refuse_unverified_image_id(self):
        with patch.object(m, "run", side_effect=["sha256:"+"a"*64, "linux/amd64"]):
            with self.assertRaises(m.R58Refused):
                m.verify_image(m.BESU_REF, m.BESU_ID)

    def test_refuse_private_keys_owner_signer(self):
        with patch.object(m.platform, "system", return_value="Linux"), \
             patch.object(m.platform, "machine", return_value="x86_64"), \
             patch.object(m.Path, "home", return_value=ROOT):
            # Only mock exact owner signer-path detection, don't touch on-disk secrets.
            with patch.object(m.Path, "exists", return_value=True):
                with self.assertRaises(m.R58Refused):
                    m.signer_guard()

    def test_no_chain_launcher_or_network_modifiers_in_source(self):
        src = (ROOT/"tools/sse_pos_r58_native_ipv6_cli_audit.py").read_text("utf-8")
        for bad in ('"docker", "pull"', '"--apply"', '"--server"', '"--join"', '"wallet create"',
                    '"--network", "host"', '"docker", "start"', '"docker", "network", "create"',
                    '"--publish"', '"--mount"', '"--privileged"'):
            self.assertNotIn(bad, src)
        self.assertIn('"--network", "none"', src)
        self.assertIn('"--pull", "never"', src)
        self.assertIn('"actualELCLServiceOrP2pStarted": False', src)
        self.assertIn('"actualEthereumPeerHandshakeObserved": False', src)

if __name__ == "__main__":
    unittest.main()
