"""R60 source-only tests: owner read-only P2P/isolation and actual API snapshot.

All fixture subprocess and API results are mocks; no live Docker/service claims.
"""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import sse_pos_r60_owner_native_p2p_readonly_audit as r


class R60OwnerP2pAuditTests(unittest.TestCase):
    def test_owner_genesis_exact_real_original_sha(self):
        self.assertEqual(r.GENESIS["genesis.json"],
                         "22eb6c58288113b9c3671970967151012665137b345237b5c24060dc988b1ee8")
        self.assertEqual(r.GENESIS["genesis.ssz"],
                         "8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82")
        self.assertEqual(r.NET, "sse31340-g2-internal")

    def test_only_real_original_container_names(self):
        self.assertEqual((r.EL, r.BN, r.VC), ("sse31340-g2-el-r40", "sse31340-g2-bn", "sse31340-g2-vc"))

    def test_p2p_disabled_flag_parsed_without_other_secrets(self):
        opts = ["--p2p-enabled=false", "--rpc-http-port=8545",
                "--engine-jwt-secret=/jwt/engine.jwt",
                "--secret-key=NEVER_OUTPUT", "--listen-address=::"]
        self.assertEqual(r.safe_flags(opts),
                         {"p2p-enabled": ["false"], "listen-address": ["::"]})

    def test_refuse_unexpected_network_flag_content(self):
        with self.assertRaises(r.R60Refused):
            r.safe_flags(["--p2p-host=secret&token"])
        with self.assertRaises(r.R60Refused):
            r.safe_flags("not a list")
        with self.assertRaises(r.R60Refused):
            r.safe_flags([None])

    def test_p2p_host_is_allowed_and_validated_without_exposing_private_data(self):
        self.assertEqual(r.safe_flags(["--p2p-host=127.0.0.1"]),
                         {"p2p-host": ["127.0.0.1"]})
        with self.assertRaises(r.R60Refused):
            r.safe_flags(["--p2p-host=secret&token"])

    def test_sanitize_cmd_preserves_no_nonallowlisted_args(self):
        opts = r.safe_flags(["--password=abc", "--engine-host-allowlist=secret",
                             "--execution-jwt=/run/secret", "--port6=9000"])
        self.assertEqual(opts, {"port6": ["9000"]})

    def test_client_inspection_keeps_only_public_ports(self):
        state = json.dumps({"Running": True, "Status": "running"})
        cmd = json.dumps(["--p2p-enabled=false", "--engine-jwt-secret=/jwt/engine.jwt"])
        binding = json.dumps({
            "8545/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18545"}],
            "30303/udp": [{"HostIp": "fca0::1", "HostPort": "30303"}],
            "8551/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8551"}]
        })
        with patch.object(r, "docker", side_effect=[
            state, cmd, r.NET, "sha256:" + "a"*64, binding]):
            outcome = r.client(r.EL)
        self.assertTrue(outcome["running"])
        self.assertTrue(outcome["networkModeIsOriginalInternal"])
        self.assertEqual(outcome["explicitNetworkFlags"], {"p2p-enabled": ["false"]})
        self.assertEqual(len(outcome["publishedNativeP2pHostBindings"]), 1)
        self.assertNotIn("8545", json.dumps(outcome))
        self.assertNotIn("8551", json.dumps(outcome))

    def test_owner_gate_reject_wrong_git_commit(self):
        with patch.object(r, "run", return_value="b"*40):
            with self.assertRaises(r.R60Refused):
                r.owner_guard("a"*40)

    def test_owner_gate_reject_unpinned_or_malformed_commit(self):
        with self.assertRaises(r.R60Refused):
            r.owner_guard("main")
        with self.assertRaises(r.R60Refused):
            r.owner_guard("abc")

    def test_beacon_finality_reads_only_public_headers(self):
        data = iter([
            {"data": {"genesis_time": r.GENESIS_TIME}},
            {"data": {"root": "0x" + "a"*64, "header": {"message": {"slot": "550"}}}},
            {"data": {"finalized": {"epoch": "13", "root": "0x" + "b"*64}}},
        ])
        with patch.object(r, "api_json", side_effect=lambda *args, **kwargs: next(data)):
            report = r.beacon_reading()
        self.assertTrue(report["genesisTimeMatchesOriginal"])
        self.assertEqual(report["headSlot"], 550)
        self.assertEqual(report["finalizedEpoch"], 13)
        self.assertTrue(report["beaconRestGaveBothHeadAndFinalizedCheckpoint"])

    def test_missing_beacon_api_not_falsely_claimed(self):
        with patch.object(r, "api_json", return_value=None):
            report = r.beacon_reading()
        self.assertIsNone(report["headSlot"])
        self.assertIsNone(report["finalizedEpoch"])
        self.assertFalse(report["beaconRestGaveBothHeadAndFinalizedCheckpoint"])

    def test_source_enforces_readonly_and_secret_nonexposure(self):
        source = (ROOT/"tools/sse_pos_r60_owner_native_p2p_readonly_audit.py").read_text("utf-8")
        for forbidden in ('docker(["run"', 'docker(["start"', 'docker(["stop"',
                          'docker(["network", "connect"', 'docker(["network", "create"',
                          'docker(["container", "restart"', 'zerotier-cli", "join"',
                          '"--apply"', 'wallet create', 'mnemonic',
                          'read_text()'):
            self.assertNotIn(forbidden, source)
        self.assertIn("jwt.stat().st_size != 64", source)
        self.assertIn("noSignerSecretOrSlashingDbReadByTool", source)
        self.assertIn('"nativeP2pHostExposurePerformed": False', source)

    def test_owner_observational_output_cannot_prove_remote_sync(self):
        source = (ROOT/"tools/sse_pos_r60_owner_native_p2p_readonly_audit.py").read_text("utf-8")
        self.assertIn('"nativeSecondPeerOrIndependentFinalityProven": False', source)
        self.assertIn('"needsReviewedExistingStatePreservingP2pMaintenance": True', source)
        self.assertIn('"ownerZeroTierOverlayActuallyJoinedByThisAudit": False', source)


if __name__ == "__main__":
    unittest.main()
