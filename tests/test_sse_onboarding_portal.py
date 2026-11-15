"""Offline structural checks for the static R6 onboarding website.

These do NOT execute JavaScript or prove that GitHub Pages is actually live.
"""
from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / "docs" / "index.html"
PIN = "97bd3d434af1bb20ce08b763b90b58cce7e4c036"


class PortalParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tag_attrs = []
    def handle_starttag(self, tag, attrs):
        self.tag_attrs.append((tag, dict(attrs)))


class OnboardingPortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = HTML.read_text(encoding="utf-8")
        cls.tags = PortalParser()
        cls.tags.feed(cls.source)

    def test_immutable_installer_pin_not_moving_branch(self):
        self.assertIn('const SHA = "' + PIN + '"', self.source)
        self.assertIn('"/tools/sse_vm_bootstrap.py"', self.source)
        self.assertNotIn("raw.githubusercontent.com/AkrAyoub/sse-research/main/", self.source)

    def test_can_render_offline_without_external_js_css_dependencies(self):
        scripts = [d for t, d in self.tags.tag_attrs if t == "script"]
        links = [d for t, d in self.tags.tag_attrs if t == "link"]
        self.assertEqual(len(scripts), 1)
        self.assertFalse(any("src" in d for d in scripts))
        self.assertFalse(any(d.get("rel") == "stylesheet" for d in links))
        self.assertIn("<style>", self.source)

    def test_preinstalled_ubuntu_workflow_and_manual_privilege(self):
        self.assertIn("No custom VM image", self.source)
        self.assertIn("sudo apt-get install", self.source)
        self.assertIn('commands.dryrun = command(fields, false)', self.source)
        self.assertIn('commands.apply = "sudo " + command(fields, true)', self.source)
        self.assertIn("Review the dry-run", self.source)

    def test_only_public_configuration_inputs_collected(self):
        inputs = {d.get("id") for tag, d in self.tags.tag_attrs if tag == "input"}
        self.assertEqual(inputs, {"nodeId", "rpc", "settlement", "wallet"})
        self.assertNotIn('<input type="password"', self.source)
        self.assertNotIn("<form", self.source)
        self.assertNotIn("localStorage", self.source)
        self.assertNotIn("fetch(", self.source)

    def test_supported_roles_and_native_test_eth_named(self):
        self.assertIn('value="provider"', self.source)
        self.assertIn('value="monitor"', self.source)
        self.assertIn('value="consumer"', self.source)
        self.assertIn('value="observer"', self.source)
        self.assertIn("11155111", self.source)
        self.assertIn("31337", self.source)
        self.assertIn("test ETH", self.source)

    def test_fail_closed_before_generating_apply_and_escape_dynamic_values(self):
        self.assertIn("safeAddress(settlement)", self.source)
        self.assertIn("supportedUrl(rpc)", self.source)
        self.assertIn("!selected.length", self.source)
        self.assertIn("el(\"dryrun\").textContent", self.source)
        self.assertIn("el(\"apply\").textContent", self.source)
        self.assertNotIn("innerHTML", self.source)

    def test_no_false_claim_of_actual_role_activation(self):
        self.assertIn("does not yet activate provider/monitor transactions", self.source)
        self.assertIn("not active until", self.source)
        self.assertIn("role heartbeat only", self.source)

    def test_complete_static_publishing_source_exists(self):
        self.assertTrue((HTML.parent / ".nojekyll").exists())
        self.assertTrue((HTML.parent / "research" / "R6_ONBOARDING_PORTAL.md").is_file())


if __name__ == "__main__":
    unittest.main()
