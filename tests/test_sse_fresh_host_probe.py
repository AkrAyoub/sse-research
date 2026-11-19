"""Regression tests for read-only R19 fresh-VM / external-PC inventory."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sse_fresh_host_probe import (
    FreshHostError, ROLES, TOOLS, SCHEMA, parse_roles,
    _read_os_release, _read_mem_mib, gather_facts, build_report, main,
)


def host_facts(cpus=4, memory=11264, disk_free=93):
    return {
        "system": "Linux",
        "architecture": "x86_64",
        "distribution": "ubuntu",
        "distributionVersion": "24.04",
        "logicalCPUs": cpus,
        "memoryMiB": memory,
        "rootDiskFreeGiB": disk_free,
        "rootDiskTotalGiB": 120.0,
        "pythonVersion": "3.12.3",
        "executablesPresent": {x: False for x in TOOLS},
    }


class FreshHostProbeTests(unittest.TestCase):
    def test_roles_can_coexist(self):
        self.assertEqual(parse_roles("validator,provider,monitor"),
                         ("validator", "provider", "monitor"))

    def test_each_public_role_accepted(self):
        for role in ROLES:
            with self.subTest(role=role):
                self.assertEqual(parse_roles(role), (role,))

    def test_invalid_unknown_duplicate_or_empty_roles(self):
        for roles in ("", "admin", "full-node", "validator,validator",
                      ",validator", "validator,", " validator",
                      "validator, monitor", "monitor, "):
            with self.subTest(roles=roles), self.assertRaises(FreshHostError):
                parse_roles(roles)
        with self.assertRaises(FreshHostError):
            parse_roles(None)

    def test_small_historical_vm_is_reported_without_fake_capacity_claim(self):
        r = build_report(("observer", "monitor"), host_facts(2, 3891, 37))
        self.assertEqual(r["host"]["logicalCPUs"], 2)
        self.assertEqual(r["host"]["memoryMiB"], 3891)
        self.assertEqual(r["host"]["rootDiskFreeGiB"], 37)
        self.assertEqual(r["activatedRoles"], [])
        self.assertFalse(r["acceptance"]["realCrossHostSLAObserved"])
        self.assertFalse(r["acceptance"]["publicHTTPSNodeUIVerified"])

    def test_larger_historical_vm_still_not_a_public_validator(self):
        r = build_report(("validator",), host_facts())
        self.assertEqual(r["schema"], SCHEMA)
        self.assertTrue(r["bootstrapUbuntu2404Detected"])
        self.assertFalse(r["acceptance"]["freshPoS31340Joined"])
        self.assertFalse(r["acceptance"]["validatorDepositAndActivationVerified"])
        self.assertTrue(any("EL+CL" in n for n in r["roleRuntimeRequirementsNotVerified"]))

    def test_no_static_ip_invitation_or_infrastructure_assumption(self):
        r = build_report(("full_node", "consumer"), host_facts())
        self.assertFalse(r["network"]["staticPublicIPRequired"])
        self.assertFalse(r["network"]["publicTCPIngressVerified"])
        self.assertFalse(r["network"]["publicUDPIngressVerified"])
        self.assertFalse(r["network"]["externalPeerConnected"])
        self.assertFalse(r["network"]["natOrCGNATDetermined"])
        self.assertFalse(r["roleSelectionIsAdmission"])
        self.assertEqual(r["funding"]["nativeCurrency"], "valueless_test_eth")
        self.assertTrue(r["funding"]["sseAdministratorApprovalForbidden"])
        self.assertFalse(r["funding"]["onchainGrantFinalized"])
        self.assertFalse(r["funding"]["independentGasSponsorAvailable"])

    def test_no_signer_file_private_keys_or_network_touch_claimed(self):
        r = build_report(("provider", "monitor"), host_facts())
        self.assertFalse(r["readsPrivateKeys"])
        self.assertFalse(r["writesHostConfiguration"])
        self.assertFalse(r["sendsNetworkRequests"])
        self.assertEqual(r["status"], "HOST_INVENTORY_ONLY_NOT_AN_ONBOARDED_NODE")

    def test_non_ubuntu_host_is_inventory_only_not_rejected_from_network(self):
        facts = host_facts()
        facts.update(system="Windows", distribution="unknown", distributionVersion="unknown",
                     memoryMiB=None)
        r = build_report(("observer",), facts)
        self.assertFalse(r["bootstrapUbuntu2404Detected"])
        self.assertEqual(r["host"]["system"], "Windows")
        self.assertEqual(r["requestedRoles"], ["observer"])

    def test_invalid_hardware_observations_rejected_not_fabricated(self):
        for key, bad in (("logicalCPUs", 0), ("logicalCPUs", True),
                         ("memoryMiB", -1), ("rootDiskFreeGiB", -1.0),
                         ("rootDiskTotalGiB", float("inf"))):
            facts = host_facts()
            facts[key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(FreshHostError):
                build_report(("observer",), facts)
        facts = host_facts()
        facts["rootDiskFreeGiB"] = 300.0
        with self.assertRaises(FreshHostError):
            build_report(("observer",), facts)

    def test_reject_missing_tools_inventory_or_invalid_flag(self):
        facts = host_facts()
        facts["executablesPresent"].pop("docker")
        with self.assertRaises(FreshHostError):
            build_report(("monitor",), facts)
        facts = host_facts()
        facts["executablesPresent"]["besu"] = "installed"
        with self.assertRaises(FreshHostError):
            build_report(("monitor",), facts)

    def test_actual_memory_and_os_release_parser(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "os-release"
            p.write_text('NAME="Ubuntu"\nID=ubuntu\nVERSION_ID="24.04"\n')
            self.assertEqual(_read_os_release(p), ("ubuntu", "24.04"))
            p.write_text("ID=debian\nVERSION_ID=12\n")
            self.assertEqual(_read_os_release(p), ("debian", "12"))
            mem = Path(temp) / "meminfo"
            mem.write_text("MemTotal:       11534336 kB\nMemFree: 999 kB\n")
            self.assertEqual(_read_mem_mib(mem), 11264)
            mem.write_text("MemTotal: corrupted kB\n")
            self.assertIsNone(_read_mem_mib(mem))

    def test_main_json_only_and_zero_network_side_effects(self):
        out = io.StringIO()
        with patch("sse_fresh_host_probe.gather_facts", return_value=host_facts()), contextlib.redirect_stdout(out):
            self.assertEqual(main(["--roles", "full_node,monitor"]), 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["requestedRoles"], ["full_node", "monitor"])
        self.assertFalse(payload["acceptance"]["publicSignedReleaseVerified"])

    def test_live_machine_probe_is_only_local_inventory(self):
        facts = gather_facts()
        self.assertIn(facts["system"], ("Linux", "Windows", "Darwin"))
        self.assertEqual(set(facts["executablesPresent"]), set(TOOLS))
        report = build_report(("observer",), facts)
        self.assertEqual(report["activatedRoles"], [])
        self.assertFalse(report["network"]["externalPeerConnected"])


if __name__ == "__main__":
    unittest.main()
