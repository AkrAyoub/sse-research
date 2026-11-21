"""R59 original chain31340 nonsigning native IPv6 Docker deployment guards.

Pure unit/source checks, no Docker, keys, genesis or actual peer traffic.
"""
import json
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import sse_pos_r59_native_ipv6_observer as m


class R59NativeObserverTests(unittest.TestCase):
    def test_exact_pinned_clients_and_original_public_genesis(self):
        pins = json.loads((ROOT / "config/pos_client_image_pins.json").read_text("utf-8"))["images"]
        self.assertEqual(m.BESU_REF, pins["besu"]["ref"])
        self.assertEqual(m.BESU_ID, pins["besu"]["imageId"])
        self.assertEqual(m.LIGHTHOUSE_REF, pins["lighthouse"]["ref"])
        self.assertEqual(m.LIGHTHOUSE_ID, pins["lighthouse"]["imageId"])
        self.assertEqual(m.ARCHIVE_SHA, "1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7")
        self.assertEqual(m.EXPECTED["genesis.ssz"], "8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82")

    def test_overlay_p2p_bind_exact_ipv6_not_wildcard(self):
        ip = "fca0:2328:77b8:6578:a55::1"
        self.assertEqual(m.port_bindings(ip, True), [
            f"[{ip}]:30404:30404/tcp", f"[{ip}]:30404:30404/udp",
            "127.0.0.1:28545:8545/tcp"])
        self.assertEqual(m.port_bindings(ip, False), [
            f"[{ip}]:9000:9000/tcp", f"[{ip}]:9000:9000/udp",
            f"[{ip}]:9001:9001/udp", "127.0.0.1:25052:5052/tcp"])

    def test_reject_arbitrary_or_wildcard_ipv6_port_publication(self):
        for addr in ("::", "::1", "2001:db8::1", "fe80::1"):
            with self.subTest(addr=addr), self.assertRaises(m.R59Refused):
                m.port_bindings(addr, True)

    def test_no_privileged_engine_port_exposed(self):
        all_bindings = m.port_bindings("fca0:2328:77b8:6578:a55::1", True) + m.port_bindings(
            "fca0:2328:77b8:6578:a55::1", False)
        self.assertFalse(any(":8551/" in x or ":8551:" in x for x in all_bindings))
        self.assertFalse(any("0.0.0.0:" in x or "[::]:" in x for x in all_bindings))

    def test_refuse_invalid_enr_or_mismatched_bootstrap(self):
        self.assertFalse(m.bootnodes(None, None))
        with self.assertRaises(m.R59Refused):
            m.bootnodes("enr:" + "A"*90, None)
        with self.assertRaises(m.R59Refused):
            m.bootnodes("enr:" + "A"*90, "enr:" + "A"*90)
        with self.assertRaises(m.R59Refused):
            m.bootnodes("enode://" + "A"*90, "enr:" + "B"*90)
        # Besu EL wants enode URL (not consensus ENR); Lighthouse wants ENR.
        enode6 = "enode://" + "a"*128 + "@[fca0:2328:776e:4750:395b::1]:30404"
        self.assertTrue(m.bootnodes(enode6, "enr:" + "B"*90))
        with self.assertRaises(m.R59Refused):
            m.bootnodes("enode://" + "a"*128 + "@[2001:db8::1]:30404", "enr:" + "B"*90)

    def test_besu_separate_ipv6_port_and_seed_protocol(self):
        src=(ROOT/"tools/sse_pos_r59_native_ipv6_observer.py").read_text("utf-8")
        self.assertIn('"--p2p-port-ipv6=30404"',src)
        self.assertIn('p.add_argument("--execution-seed-enode-v6")',src)
        self.assertNotIn('"--p2p-port-ipv6=30303"',src)
        self.assertNotIn('p.add_argument("--execution-seed-enr")',src)

    def test_verify_image_id_platform_does_not_accept_tag_only(self):
        with patch.object(m, "docker", side_effect=["sha256:"+"b"*64, "linux/amd64"]):
            with self.assertRaises(m.R59Refused):
                m.images()

    def test_refuse_existing_owner_signer_or_existing_r59_state(self):
        with patch.object(m.platform, "system", return_value="Linux"), \
             patch.object(m.platform, "machine", return_value="x86_64"), \
             patch.object(m.Path, "home", return_value=ROOT), \
             patch.object(m.Path, "exists", return_value=True):
            with self.assertRaises(m.R59Refused):
                m.guard_owner()

    def test_actual_membership_must_be_controllerless_and_host_bound(self):
        payload = [{
            "nwid": m.NETWORK, "status": "OK", "type": "PUBLIC",
            "portDeviceName": "ztrb6cq527",
            "assignedAddresses": ["fca0:2328:77b8:6578:a55::1/40"]
        }]
        with patch.object(m, "run", side_effect=[json.dumps(payload),
                 "inet6 fca0:2328:77b8:6578:a55::1/40 scope global"]):
            self.assertEqual(m.overlay_ip(), ("ztrb6cq527", "fca0:2328:77b8:6578:a55::1"))

    def test_wrong_controller_or_ip_fails_closed(self):
        payload = [{
            "nwid": m.NETWORK, "status": "OK", "type": "PRIVATE",
            "portDeviceName": "ztrb6cq527",
            "assignedAddresses": ["fca0:2328:77b8:6578:a55::1/40"]
        }]
        with patch.object(m, "run", return_value=json.dumps(payload)):
            with self.assertRaises(m.R59Refused):
                m.overlay_ip()

    def test_docker_host_port_postinspection_exact_match(self):
        ip = "fca0:2328:77b8:6578:a55::1"
        config = {
            "30404/tcp": [{"HostIp": ip, "HostPort": "30404"}],
            "30404/udp": [{"HostIp": ip, "HostPort": "30404"}],
            "8545/tcp": [{"HostIp": "127.0.0.1", "HostPort": "28545"}],
        }
        with patch.object(m, "docker", side_effect=[m.BESU_ID, json.dumps(config)]):
            m.inspect_published(m.EL, m.port_bindings(ip, True), m.BESU_ID)

    def test_refuse_unplanned_exposure_after_container_start(self):
        ip = "fca0:2328:77b8:6578:a55::1"
        config = {
            "30404/tcp": [{"HostIp": ip, "HostPort": "30404"}],
            "30404/udp": [{"HostIp": ip, "HostPort": "30404"}],
            "8545/tcp": [{"HostIp": "0.0.0.0", "HostPort": "28545"}],
        }
        with patch.object(m, "docker", side_effect=[m.BESU_ID, json.dumps(config)]):
            with self.assertRaises(m.R59Refused):
                m.inspect_published(m.EL, m.port_bindings(ip, True), m.BESU_ID)

    def test_p2p_only_bridge_publications_and_auto_restart(self):
        src = (ROOT / "tools/sse_pos_r59_native_ipv6_observer.py").read_text("utf-8")
        self.assertIn('"--driver", "bridge", "--ipv6"', src)
        self.assertIn('"--restart", "unless-stopped"', src)
        self.assertIn('"--network", BRIDGE', src)
        self.assertIn('"--read-only", "--cap-drop", "ALL"', src)
        self.assertNotIn('"--network", "host"', src)
        self.assertIn('"--p2p-host-ipv6=" + ip', src)
        self.assertIn('"--p2p-interface-ipv6=::"', src)
        self.assertIn('"--enable-private-discovery"', src)

    def test_https_engine_api_and_local_rpc_boundaries(self):
        src = (ROOT / "tools/sse_pos_r59_native_ipv6_observer.py").read_text("utf-8")
        self.assertIn('"--engine-jwt-secret=/jwt/engine.jwt"', src)
        self.assertIn('"--engine-host-allowlist=" + EL', src)
        self.assertIn('"--engine-rpc-port=8551"', src)
        self.assertIn('"127.0.0.1:28545:8545/tcp"', src)
        self.assertIn('"127.0.0.1:25052:5052/tcp"', src)
        self.assertIn('"--execution-jwt=/jwt/engine.jwt"', src)
        self.assertNotIn('"--validators-dir"', src)
        self.assertNotIn('"--secrets-dir"', src)

    def test_preflight_is_read_only(self):
        src = (ROOT / "tools/sse_pos_r59_native_ipv6_observer.py").read_text("utf-8")
        preflight = src[src.index("def preflight("):src.index("def create_file(")]
        for bad in ('docker(["run"', 'docker(["network", "create"', 'mkdir(', 'stage_genesis(',
                    'create_file(', 'secrets.token_hex', 'docker(["start"'):
            self.assertNotIn(bad, preflight)
        self.assertIn('"noServicesOrFilesCreatedByPreflight": True', preflight)

    def test_one_time_interactive_authorization_and_refuse_reuse(self):
        src = (ROOT / "tools/sse_pos_r59_native_ipv6_observer.py").read_text("utf-8")
        for token in ('"CREATE-REAL-R59-NONSIGNING-OBSERVER"', 'sys.stdin.isatty()',
                      'ROOT.exists() or ROOT.is_symlink()', 'os.O_EXCL',
                      '"--apply"', '"--plan"'):
            self.assertIn(token, src)

    def test_reality_limit_no_peer_or_consensus_claimed(self):
        src = (ROOT / "tools/sse_pos_r59_native_ipv6_observer.py").read_text("utf-8")
        for token in ('"actualNativeRemotePeerHandshakeStillNeedsIndependentEvidence": True',
                      '"actualOriginalChainHeadAndFinalityStillNeedIndependentObservation": True',
                      '"ipv6DockerPublishAndNativeClientHandshakeAlreadyVerified": False',
                      '"noNewConsensusFinalityOrSynchronizationClaimed": True'):
            self.assertIn(token, src)

if __name__ == "__main__":
    unittest.main()
