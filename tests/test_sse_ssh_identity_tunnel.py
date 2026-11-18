"""Regression tests for private, fingerprint-pinned lab SSH discovery."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from sse_ssh_identity_tunnel import (
    DiscoveryError, allowed_network, discover, read_pin, ssh_command,
)

KEY = "AAAAC3NzaC1lZDI1NTE5AAAAIGRTM1gQHbWX1668bjIowKUGXI5FMyGduQ2HCadMfAov"


class TestPinnedDiscovery(unittest.TestCase):
    def test_bounded_private_network_only(self):
        self.assertEqual(allowed_network("10.50.56.0/24").num_addresses, 256)
        for bad in ("8.8.8.0/24", "10.50.0.0/16", "0.0.0.0/0",
                    "10.50.56.1/24", "::1/128"):
            with self.subTest(cidr=bad), self.assertRaises(DiscoveryError):
                allowed_network(bad)

    def test_discover_by_identity_not_memorized_ip(self):
        self.assertEqual(
            discover("10.50.56.12/30", KEY,
                     scan=lambda ip, key, seconds: ip == "10.50.56.14"),
            "10.50.56.14",
        )

    def test_missing_or_duplicate_identity_fails_closed(self):
        for matches in (set(), {"10.50.56.13", "10.50.56.14"}):
            with self.subTest(matches=matches), self.assertRaises(DiscoveryError):
                discover("10.50.56.12/30", KEY,
                         scan=lambda ip, key, seconds: ip in matches)

    def test_pin_exact_alias_and_user_private_file(self):
        with tempfile.TemporaryDirectory() as directory:
            f = Path(directory) / "known_hosts"
            f.write_text("sse-anvil ssh-ed25519 " + KEY + "\n")
            f.chmod(0o600)
            self.assertEqual(read_pin(str(f), "sse-anvil"), KEY)
            with self.assertRaises(DiscoveryError):
                read_pin(str(f), "other-peer")
            f.chmod(0o644)
            with self.assertRaises(DiscoveryError):
                read_pin(str(f), "sse-anvil")

    def test_ssh_uses_pinned_identity_and_loopback_forward(self):
        with tempfile.TemporaryDirectory() as directory:
            k = Path(directory) / "key"
            h = Path(directory) / "known_hosts"
            k.write_text("fixture"); k.chmod(0o600)
            h.write_text("sse-anvil ssh-ed25519 " + KEY + "\n"); h.chmod(0o600)
            cmd = ssh_command(
                ip="10.50.56.14", user="ayoubakrvm4695", identity=str(k),
                alias="sse-anvil", known_hosts=str(h),
                local_port=8545, target_port=8545,
            )
            self.assertIn("StrictHostKeyChecking=yes", cmd)
            self.assertIn("HostKeyAlias=sse-anvil", cmd)
            self.assertIn("127.0.0.1:8545:127.0.0.1:8545", cmd)
            self.assertEqual(cmd[-1], "ayoubakrvm4695@10.50.56.14")


if __name__ == "__main__":
    unittest.main()
