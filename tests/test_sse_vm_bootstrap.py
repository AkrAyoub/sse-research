"""Offline tests for R6 bootstrap plan and systemd posture; never run --apply."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_vm_bootstrap as b

SHA = "c2fe632f8899fbf8cf29cad1de0d56c9a2e49c5e"
ADDRESS = "0x" + "12" * 20


def spec(**changes):
    options = dict(revision=SHA, node_id="compute-vm-a",
                   role_names="provider,monitor",
                   rpc_url="https://sepolia.example.org",
                   chain_id=11155111, settlement=ADDRESS,
                   install_root=Path("/opt/sse"))
    options.update(changes)
    return b.make_spec(**options)


class BootstrapPlanTests(unittest.TestCase):
    def test_good_plan_is_read_only_and_lists_selected_roles(self):
        plan = b.describe(spec())
        self.assertEqual(plan["mode"], "DRY_RUN")
        self.assertEqual(plan["rolesConfigured"], ["provider", "monitor"])
        self.assertFalse(plan["roleActivated"])
        self.assertFalse(plan["ethereumTransactionsSent"])
        self.assertNotIn("privateKey", json.dumps(plan))

    def test_service_unit_is_loopback_nonprivileged_and_has_no_rpc_secret(self):
        unit = b.systemd_unit(spec())
        for required in ("User=sseagent", "Environment=SSE_AGENT_HOST=127.0.0.1",
                         "ProtectSystem=strict", "NoNewPrivileges=yes",
                         "ExecStart=/usr/bin/python3 /opt/sse/releases/"):
            self.assertIn(required, unit)
        self.assertNotIn("https://sepolia.example.org", unit)
        self.assertNotIn("PrivateKey", unit)
        self.assertNotIn("SSE_MONITOR_PRIVATE_KEY", unit)

    def test_pinned_revision_not_head_or_short_sha(self):
        for bad in ("HEAD", "main", "c2fe632", "g" * 40, "0x" + "a" * 40):
            with self.subTest(bad=bad), self.assertRaises(b.BootstrapError):
                spec(revision=bad)

    def test_unrecognized_or_duplicate_roles_fail_closed(self):
        for bad in ("provider,provider", "validator", "", "provider,",
                    "executor", "monitor,wrong"):
            with self.subTest(bad=bad), self.assertRaises(b.BootstrapError):
                spec(role_names=bad)

    def test_no_unsafe_names_or_boolean_chain_ids(self):
        for bad in ("-delete", "compute vm", "a/../b", ""):
            with self.subTest(node=bad), self.assertRaises(b.BootstrapError):
                spec(node_id=bad)
        with self.assertRaises(b.BootstrapError):
            spec(chain_id=True)

    def test_no_unknown_or_empty_settlement_or_wallet(self):
        for key, bad in (("settlement", "0x0"),
                         ("settlement", "0x" + "00" * 20),
                         ("wallet", "0x0")):
            with self.subTest(key=key, bad=bad), self.assertRaises(b.BootstrapError):
                spec(**{key: bad})

    def test_remote_http_and_url_secrets_rejected(self):
        for bad in ("http://remote.example.org", "https://u:p@example.org",
                    "https://rpc.example.org/token-123",
                    "https://rpc.example.org?apikey=x", "file:///etc/passwd"):
            with self.subTest(url=bad), self.assertRaises(b.BootstrapError):
                spec(rpc_url=bad)

    def test_loopback_http_and_testnet_https_supported(self):
        self.assertEqual(spec(rpc_url="http://127.0.0.1:8545").chain_id, 11155111)
        self.assertEqual(spec(rpc_url="https://rpc.example.org").node_id, "compute-vm-a")

    def test_install_root_must_be_absolute_and_not_system_root(self):
        for bad in ("/", ".", "../opt/sse", "/opt/../etc"):
            with self.subTest(root=bad), self.assertRaises(b.BootstrapError):
                spec(install_root=Path(bad))

    @unittest.skipUnless(os.name == "posix", "filesystem symlink test is POSIX only")
    def test_symlink_install_path_rejected(self):
        with patch("pathlib.Path.is_symlink", return_value=True):
            with self.assertRaises(b.BootstrapError):
                spec(install_root=Path("/opt/sse"))

    def test_rejects_unit_injection_or_system_directories(self):
        for unsafe in ("/etc/sse", "/opt/sse\\nExecStart=/bin/sh", "/tmp/sse"):
            with self.subTest(root=unsafe), self.assertRaises(b.BootstrapError):
                spec(install_root=Path(unsafe))

    @unittest.skipUnless(sys.platform.startswith("linux"), "Ubuntu account test is Linux only")
    def test_rejects_unsafe_existing_service_account(self):
        from types import SimpleNamespace
        with patch("pwd.getpwnam", return_value=SimpleNamespace(pw_uid=0, pw_shell="/bin/bash")):
            with self.assertRaises(b.BootstrapError):
                b.ensure_agent_user()

    @unittest.skipUnless(sys.platform.startswith("linux"), "Ubuntu account test is Linux only")
    def test_creates_service_account_only_when_missing(self):
        from types import SimpleNamespace
        good = SimpleNamespace(pw_uid=1001, pw_shell="/usr/sbin/nologin")
        with patch("pwd.getpwnam", side_effect=[KeyError(), good]) as user, patch.object(b, "_run") as run:
            b.ensure_agent_user()
            self.assertEqual(user.call_count, 2)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][0], "useradd")

    def test_no_wallet_does_not_imply_funding(self):
        self.assertIsNone(b.describe(spec())["publicWallet"])

    def test_wallet_public_address_can_be_supplied(self):
        wallet = "0x" + "34" * 20
        self.assertEqual(b.describe(spec(wallet=wallet))["publicWallet"], wallet)

    def test_repo_host_is_fixed_and_not_user_controlled(self):
        self.assertEqual(b.REPOSITORY, "https://github.com/AkrAyoub/sse-research.git")

    def test_main_default_dry_run_does_not_invoke_apply(self):
        args = ["--revision", SHA, "--node-id", "compute-vm-a",
                "--roles", "observer", "--rpc-url", "https://rpc.example.org",
                "--chain-id", "11155111", "--settlement", ADDRESS]
        with patch.object(b, "apply", side_effect=AssertionError("unexpected apply")):
            self.assertEqual(b.main(args), 0)

    def test_main_explicit_apply_changes_only_if_requested(self):
        args = ["--revision", SHA, "--node-id", "compute-vm-a",
                "--roles", "observer", "--rpc-url", "https://rpc.example.org",
                "--chain-id", "11155111", "--settlement", ADDRESS, "--apply"]
        with patch.object(b, "apply", return_value={"result": "mock"}) as mocked:
            self.assertEqual(b.main(args), 0)
            self.assertEqual(mocked.call_count, 1)

    def test_nonubuntu_or_nonroot_install_gate_does_not_change_system(self):
        # Never actually installs; enforces prerequisite only in apply mode.
        with patch.object(b, "_assert_ubuntu", side_effect=b.BootstrapError("not Ubuntu")):
            with self.assertRaises(b.BootstrapError):
                b.apply(spec())

if __name__ == "__main__":
    unittest.main()
