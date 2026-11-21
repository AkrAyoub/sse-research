"""R42 verify no synthetic chain metrics and strict private Docker health."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import sse_pos_g2_internal_health_r42 as m
import sse_pos_g2_resume_r41 as r41

class R42RealG2InsideDockerHealthTests(unittest.TestCase):
    def test_only_original_clients_observed(self):
        self.assertEqual(m.internal.EL, "sse31340-g2-el-r40")
        self.assertEqual(m.internal.BN, "sse31340-g2-bn")
        self.assertEqual(m.internal.VC, "sse31340-g2-vc")
        self.assertEqual(m.EXPECTED_CHAIN, hex(31340))

    def test_synthetic_positive_block_not_accepted_without_chain_identity(self):
        with patch.object(m, "require_actual_source"):
            with patch.object(m.internal, "state", side_effect=lambda name: {
                "Running": name != m.internal.ORIGINAL, "ExitCode": 0, "OOMKilled": False
            }):
                with patch.object(m, "rpc", side_effect=lambda method, params=None: {
                    "eth_chainId": "0x1", "eth_blockNumber": "0xff", "eth_getCode": "0x"
                }[method]):
                    with patch.object(m, "beacon", side_effect=lambda path: {
                        "/eth/v1/beacon/genesis": {"genesis_time": "1795219212"},
                        "/eth/v1/beacon/headers/head": {"header": {"message": {"slot": "1024"}}},
                        "/eth/v1/beacon/states/head/finality_checkpoints": {"finalized": {"epoch": "9"}},
                        "/eth/v1/node/syncing": {"is_syncing": False},
                    }[path]):
                        report = m.observe("a"*40)
        self.assertFalse(report["realExecutionPostGenesisBlockObserved"])
        self.assertFalse(report["realPositiveBeaconFinalityObserved"])

    def test_true_postgenesis_blocks_require_chain_id_and_nonzero_height(self):
        with patch.object(m, "require_actual_source"):
            with patch.object(m.internal, "state", side_effect=lambda name: {
                "Running": name != m.internal.ORIGINAL, "ExitCode": 0, "OOMKilled": False
            }):
                with patch.object(m, "rpc", side_effect=lambda method, params=None: {
                    "eth_chainId": hex(31340), "eth_blockNumber": "0x2", "eth_getCode": "0x"
                }[method]):
                    with patch.object(m, "beacon", side_effect=lambda path: {
                        "/eth/v1/beacon/genesis": {"genesis_time": "1795219212"},
                        "/eth/v1/beacon/headers/head": {"header": {"message": {"slot": "1024"}}},
                        "/eth/v1/beacon/states/head/finality_checkpoints": {"finalized": {"epoch": "9"}},
                        "/eth/v1/node/syncing": {"is_syncing": False},
                    }[path]):
                        report = m.observe("a"*40)
        self.assertTrue(report["realExecutionPostGenesisBlockObserved"])
        self.assertTrue(report["realPositiveBeaconFinalityObserved"])
        self.assertFalse(report["canonicalDepositRuntimeCodeVerified"])
        self.assertTrue(report["independentBLSPrivateKeyPossessionNotYetProven"])

    def test_no_signed_validator_claim_merely_because_client_runs(self):
        text = (ROOT / "tools/sse_pos_g2_internal_health_r42.py").read_text("utf-8")
        self.assertIn('"independentBLSPrivateKeyPossessionNotYetProven": True', text)
        self.assertIn('"publicInternetP2PNotYetVerified": True', text)

    def test_health_api_is_readonly_fixed_allowlist(self):
        for method, url, port in [
            ("GET", "/eth/v1/beacon/headers/head", 5052),
            ("GET", "/eth/v1/beacon/states/head/finality_checkpoints", 5052),
            ("GET", "/eth/v1/node/syncing", 5052),
        ]:
            self.assertIn(url, r41.wire(method, port, url, None))
        with self.assertRaises(r41.Refuse):
            r41.wire("POST", 8545, "/", {
                "jsonrpc": "2.0", "id": 1, "method": "eth_sendTransaction", "params": []
            })

    def test_exact_original_public_ssz_and_rendered_config_verified(self):
        source = (ROOT / "tools/sse_pos_g2_internal_health_r42.py").read_text("utf-8")
        self.assertIn("old.safe_public", source)
        self.assertIn("config.synthesize", source)
        self.assertIn("config.upstream_git_blob", source)

    def test_no_runtime_container_mutations_or_secret_printout(self):
        source = (ROOT / "tools/sse_pos_g2_internal_health_r42.py").read_text("utf-8")
        for forbidden in ('"start"', '"restart"', '"run"', '"stop"', '"kill"', '"rm"', "wallet create"):
            self.assertNotIn(forbidden, source)
        self.assertIn('"rawRpcResponseOrPrivateKeysEmitted": False', source)

if __name__ == "__main__":
    unittest.main()
