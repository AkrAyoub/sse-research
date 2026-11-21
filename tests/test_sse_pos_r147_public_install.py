"""R147 actual public installer logic tests (never calls apt/git/root)."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import sse_install as r

SHA="4aab40483b769fc0c8e11f72e3758ea3fcefd566"

class R147Tests(unittest.TestCase):
    def test_all_role_names_and_multi_role(self):
        self.assertEqual(r.check_roles(list(r.ROLES)),list(r.ROLES))
        for role in r.ROLES:
            self.assertEqual(r.check_roles([role]),[role])

    def test_only_one_interaction_for_role_choice(self):
        asked=[]
        def once(prompt):
            asked.append(prompt)
            return "1, 3, 6"
        self.assertEqual(r.select_roles(once,lambda _:None),
                         ["full_node","validator","monitor"])
        self.assertEqual(len(asked),1)

    def test_wrong_roles_never_join_or_install(self):
        for roles in ([],["miner"],["observer","observer"],
                      ["monitor","root"],["ADMIN"]):
            with self.subTest(roles=roles),self.assertRaises(r.Refused):
                r.check_roles(roles)

    def test_menu_bad_numbers_and_duplicates_refused(self):
        for choice in ("", "0", "7","1,1","2,abc","1,,6"):
            with self.subTest(choice=choice),self.assertRaises(r.Refused):
                r.select_roles(lambda _:choice,lambda _:None)

    def test_identity_requires_exact_immutable_sha_and_correct_host(self):
        with patch.object(r.platform,"system",return_value="Linux"), \
             patch.object(r.platform,"machine",return_value="x86_64"), \
             patch.object(r.Path,"exists",return_value=False):
            self.assertEqual(r.identity(SHA),SHA)
            for commit in ("HEAD","main","deadbeef","z"*40):
                with self.subTest(commit=commit),self.assertRaises(r.Refused):
                    r.identity(commit)

    def test_real_source_plan_does_not_claim_consensus_or_stake(self):
        plan=r.build_plan(SHA,["full_node","monitor"],"node-a")
        for field in ("publicSourceDownloaded","genesisVerified",
                      "executionAndBeaconClientsStarted",
                      "validatorKeyOrEoaCreated","nativePeersDiscovered",
                      "marketplaceRolesActivated"):
            self.assertFalse(plan[field])
        self.assertFalse(plan["chainGenesisRecreated"])

    def test_no_existing_state_is_safe(self):
        with tempfile.TemporaryDirectory() as home:
            base=Path(home)
            (base/"home/new-operator").mkdir(parents=True)
            r.guard_existing(base)
            signer=base/"home/new-operator/.local/share/sse-r27-bls-operator-private"
            signer.mkdir(parents=True)
            with self.assertRaises(r.Refused):
                r.guard_existing(base)

    def test_no_overwrite_of_old_node_state(self):
        with tempfile.TemporaryDirectory() as home:
            base=Path(home)
            (base/"var/lib/sse/chain31340").mkdir(parents=True)
            with self.assertRaises(r.Refused):
                r.guard_existing(base)

    def test_source_install_never_runs_unprivileged(self):
        with patch.object(r.os,"geteuid",return_value=1000), \
             patch.object(r,"command") as called:
            with self.assertRaises(r.Refused):
                r.install_source(SHA,r.build_plan(SHA,["observer"],"node-a"))
        called.assert_not_called()

    def test_public_https_repository_and_no_hardcoded_host_address(self):
        self.assertEqual(r.REPOSITORY,
                         "https://github.com/AkrAyoub/sse-research.git")
        self.assertNotIn("4706",r.REPOSITORY)
        self.assertNotIn("4707",r.REPOSITORY)

if __name__=="__main__":
    unittest.main()
