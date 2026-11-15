"""Offline, no-network SSE overlay enrollment checks."""
from __future__ import annotations

import importlib.util
import json
import stat
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sse_overlay", ROOT / "tools" / "sse_vm_overlay.py")
overlay = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = overlay
spec.loader.exec_module(overlay)


class OverlayTests(unittest.TestCase):
    def make_plan(self):
        return overlay.validate("provider-vm-01", "provider,observer",
                                "/run/sse/one-time.key")

    def test_dry_run_records_no_join_and_no_chain_action(self):
        plan = self.make_plan()
        self.assertEqual(plan["mode"], "DRY_RUN")
        self.assertEqual(plan["rolesConfigured"], ["provider", "observer"])
        self.assertFalse(plan["tailnetJoined"])
        self.assertFalse(plan["ethereumRoleActivated"])

    def test_rejects_node_id_injection(self):
        for node in ("", "../escape", "a b", "a;rm", "-dash"):
            with self.subTest(node=node), self.assertRaises(overlay.MeshJoinError):
                overlay.validate(node, "provider", "/run/sse/token")

    def test_rejects_role_injection_and_duplicates(self):
        for roles in ("", "provider,provider", "provider,root", "provider,", "monitor\nroot"):
            with self.subTest(roles=roles), self.assertRaises(overlay.MeshJoinError):
                overlay.validate("node-a", roles, "/run/sse/token")

    def test_rejects_untrusted_token_paths(self):
        for path in ("", "token.txt", "/tmp/key", "/etc/passwd", "/run/sse/../escape",
                     "/etc/sse/../../bad"):
            with self.subTest(path=path), self.assertRaises(overlay.MeshJoinError):
                overlay.validate("node-a", "monitor", path)

    def test_rejects_tag_injection(self):
        for tag in ("tag:admin", "tag:sse-x --reset", "", "tag:sse-x\n"):
            with self.subTest(tag=tag), self.assertRaises(overlay.MeshJoinError):
                overlay.validate("node-a", "monitor", "/etc/sse/key", tag)

    def test_dry_run_main_does_not_touch_system(self):
        with patch.object(overlay, "apply", side_effect=AssertionError("unsafe apply")):
            self.assertEqual(overlay.main(["--node-id", "node-a", "--roles", "monitor",
                                           "--auth-key-file", "/run/sse/key"]), 0)

    def test_apply_requires_ubuntu_root(self):
        with patch.object(overlay.os, "geteuid", return_value=1000):
            with self.assertRaises(overlay.MeshJoinError):
                overlay.apply(self.make_plan())

    def test_secure_file_uses_nonsecret_cli_argument_and_erases_key(self):
        class FakeCredential:
            def __init__(self): self.erased = False
            def unlink(self): self.erased = True
        cred = FakeCredential()
        commands = []
        def run(args):
            commands.append(args)
            if args[1] == "status":
                return json.dumps({"BackendState": "Running",
                                   "Self": {"Online": True, "TailscaleIPs": ["100.101.2.3"],
                                            "DNSName": "provider-vm-01.example.ts.net."}})
            return ""
        with patch.object(overlay, "_require_ubuntu_root"), \
             patch.object(overlay, "_check_auth_file"), \
             patch.object(overlay.shutil, "which", return_value="/usr/bin/tailscale"), \
             patch.object(overlay, "Path", side_effect=lambda x: cred):
            out = overlay.apply(self.make_plan(), command=run)
        self.assertEqual(out["result"], "OVERLAY_ONLINE")
        self.assertTrue(cred.erased)
        self.assertIn("--auth-key=file:/run/sse/one-time.key", commands[0])
        self.assertFalse(any("tskey-" in a for c in commands for a in c))

    def test_offline_status_refuses_and_preserves_key_for_diagnostics(self):
        class FakeCredential:
            def unlink(self): raise AssertionError("should not erase after offline response")
        def run(args):
            if args[1] == "status":
                return json.dumps({"BackendState": "NeedsLogin", "Self": {"Online": False,
                                  "TailscaleIPs": []}})
            return ""
        with patch.object(overlay, "_require_ubuntu_root"), \
             patch.object(overlay, "_check_auth_file"), \
             patch.object(overlay.shutil, "which", return_value="/usr/bin/tailscale"), \
             patch.object(overlay, "Path", side_effect=lambda x: FakeCredential()):
            with self.assertRaises(overlay.MeshJoinError):
                overlay.apply(self.make_plan(), command=run)

if __name__ == "__main__":
    unittest.main()
