"""R49 REAL public native devp2p+discv5 seed, no original signer."""
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r49_public_seed as m

class R49RealExternalNonsigningSeedTests(unittest.TestCase):
    def test_exact_real_original_chain31340_only(self):
        self.assertEqual(m.bundle.EXPECTED["genesis.ssz"],"8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82")
        self.assertEqual(m.EXTERNAL_BUNDLE_SHA if hasattr(m,"EXTERNAL_BUNDLE_SHA") else m.external.BUNDLE_SHA256,
                         "1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7")
    def test_refuse_private_loopback_linklocal_or_nonglobal_ipv4(self):
        for address in ("10.0.0.1","127.0.0.1","192.168.1.8","100.65.1.1","169.254.1.2","::1","example.com"):
            with self.subTest(addr=address), self.assertRaises(m.SeedRefused):
                m.ipv4(address)
    def test_actual_public_native_tcp_udp_ports_only(self):
        self.assertEqual(m.DOCKER_PUBLISH,(
            "0.0.0.0:30303:30303/tcp","0.0.0.0:30303:30303/udp",
            "0.0.0.0:9000:9000/tcp","0.0.0.0:9000:9000/udp",
            "0.0.0.0:9001:9001/udp",
        ))
    def test_never_publish_engine_rpc_or_signer_api(self):
        src=(ROOT/"tools/sse_pos_r49_public_seed.py").read_text("utf-8")
        for literal in ('0.0.0.0:8551', '0.0.0.0:8545', '0.0.0.0:5052',
                        '"--validators-dir"', '"--secrets-dir"'):
            self.assertNotIn(literal,src)
    def test_besu_manual_public_advertisement_and_real_discv5(self):
        src=(ROOT/"tools/sse_pos_r49_public_seed.py").read_text("utf-8")
        for literal in ('"--nat-method=NONE"','"--p2p-host=" + address',
                        '"--p2p-interface=0.0.0.0"','"--discovery-mode=BOTH"',
                        '"--p2p-discovery-port=30303"'):
            self.assertIn(literal,src)
    def test_beacon_real_native_discovery_quic_and_weak_subjectivity_caveat(self):
        src=(ROOT/"tools/sse_pos_r49_public_seed.py").read_text("utf-8")
        for literal in ('"--enr-address=" + address', '"--port=9000"',
                        '"--quic-port=9001"', '"--disable-upnp"',
                        '"--allow-insecure-genesis-sync"'):
            self.assertIn(literal,src)
    def test_real_host_operator_authorization_required_before_applying(self):
        src=(ROOT/"tools/sse_pos_r49_public_seed.py").read_text("utf-8")
        self.assertIn("CREATE-31340-NONSIGNING-PUBLIC-SEED",src)
        self.assertIn("sys.stdin.isatty()",src)
        self.assertIn("operator_verified is not True",src)
        self.assertIn("RUN.mkdir(mode=0o700)",src)
    def test_no_duplicate_owner_g2_or_r27_signing_state(self):
        src=(ROOT/"tools/sse_pos_r49_public_seed.py").read_text("utf-8")
        self.assertIn("owner.RUN.exists()",src)
        self.assertIn("sse-r27-bls-operator-private",src)
        self.assertNotIn("wallet create",src)
        self.assertNotIn("mnemonic",src)
    def test_readonly_plan_no_files_or_services_started(self):
        src=(ROOT/"tools/sse_pos_r49_public_seed.py").read_text("utf-8")
        preflight=src[src.index("def check("):src.index("def stage_public(")]
        self.assertNotIn("mkdir(",preflight)
        self.assertNotIn('"run"',preflight)
        self.assertNotIn('"network", "create"',preflight)
    def test_seed_must_not_claim_public_handshake_from_docker_bindings(self):
        src=(ROOT/"tools/sse_pos_r49_public_seed.py").read_text("utf-8")
        self.assertIn('"actualExternalTcpUdpReachabilityStillUnverified": True',src)
        self.assertIn('"publicInternetSeedReady": False',src)
        self.assertIn('"actualNativeExternalHandshakesVerified": False',src)
if __name__=="__main__":
    unittest.main()
