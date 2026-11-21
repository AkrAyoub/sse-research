"""R143 pure tests: resource recommendations are not chain admission policy."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_pos_r143_new_vm_readiness as m

class R143Tests(unittest.TestCase):
    def mock_inventory(self, roles, *, cpus=4, memory=16, disk=80, which=lambda _: "/bin/tool"):
        with tempfile.TemporaryDirectory() as home:
            return m.inspect("fresh-host-a", roles, home=home,
                             get_cpus=lambda: cpus,
                             get_mem=lambda: memory*m.GIB,
                             get_disk=lambda: disk*m.GIB,
                             which=which, get_os=lambda: "Linux",
                             get_machine=lambda: "x86_64")

    def test_large_full_client_host_recommendation(self):
        result=self.mock_inventory(["full_node","validator"])
        self.assertTrue(result["initialSizingAdviceMet"])
        self.assertFalse(result["beaconValidatorActiveVerified"])
        self.assertFalse(result["signingKeysReadOrCreated"])
        self.assertFalse(result["containersStarted"])
        self.assertFalse(result["originalChain31340ArchiveVerified"])

    def test_small_app_host_no_full_client_requirement(self):
        result=self.mock_inventory(["monitor","consumer"],cpus=2,memory=4,disk=40)
        self.assertTrue(result["initialSizingAdviceMet"])
        self.assertFalse(result["fullClientRoleRequested"])
        self.assertEqual(result["initialPlanningTarget"]["vcpus"],1)

    def test_small_full_node_gaps_are_advisory_not_admission(self):
        result=self.mock_inventory(["full_node"],cpus=2,memory=4,disk=40)
        self.assertFalse(result["initialSizingAdviceMet"])
        self.assertGreaterEqual(len(result["sizingGaps"]),1)
        self.assertFalse(result["eligibleToJoinConsensusOrSseMarketplaceClaimed"])

    def test_provider_with_monitor_is_allowed_as_role_choice(self):
        result=self.mock_inventory(["provider","monitor"],cpus=2,memory=4,disk=40)
        self.assertEqual(result["requestedRoles"],["provider","monitor"])
        self.assertFalse(result["roleEconomicsVerifiedOnChain"])

    def test_no_fixed_total_role_or_node_population(self):
        for value in ("observer","full_node","validator","consumer","provider","monitor"):
            result=self.mock_inventory([value])
            self.assertEqual(result["requestedRoles"],[value])

    def test_missing_binaries_are_reported_not_installed(self):
        result=self.mock_inventory(["full_node"],which=lambda _: None)
        self.assertIn("docker",result["missingBinaries"])
        self.assertIn("zerotier-cli",result["missingBinaries"])
        self.assertFalse(result["hostPackagesInstalled"])

    def test_existing_signer_state_prevents_new_host_inventory(self):
        with tempfile.TemporaryDirectory() as home:
            root=Path(home)/".local/share/sse-r27-bls-operator-private"
            root.mkdir(parents=True)
            with self.assertRaises(m.Refused):
                m.inspect("fresh-host-a",["observer"],home=home,
                          get_cpus=lambda:4,get_mem=lambda:16*m.GIB,
                          get_disk=lambda:80*m.GIB,
                          which=lambda _:None,get_os=lambda:"Linux",
                          get_machine=lambda:"x86_64")

    def test_rejects_wrong_architecture(self):
        with self.assertRaises(m.Refused):
            m.inspect("fresh-host-a",["observer"],get_os=lambda:"Windows")

    def test_no_duplicate_or_unknown_roles(self):
        for roles in ([],["monitor","monitor"],["administrator"],["miner"],
                      ["consumer","admin"]):
            with self.subTest(roles=roles), self.assertRaises(m.Refused):
                m.check_roles("fresh-host-a", roles)

    def test_invalid_host_identity_or_resources_rejected(self):
        for host in ("VM 1","a","bad/name",""):
            with self.subTest(host=host), self.assertRaises(m.Refused):
                m.check_roles(host,["observer"])
        with self.assertRaises(m.Refused):
            m.recommend(["observer"],0,12*m.GIB,80*m.GIB)

    def test_exact_integer_memory_extraction(self):
        self.assertEqual(m.parse_meminfo("MemTotal: 4096000 kB\nMemFree: 1 kB\n"),
                         4096000*1024)
        for raw in ("", "MemTotal: no", "MemTotal: 200 MB"):
            with self.subTest(raw=raw), self.assertRaises(m.Refused):
                m.parse_meminfo(raw)

if __name__=="__main__":
    unittest.main()
