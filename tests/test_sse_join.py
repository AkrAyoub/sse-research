"""R144 unified role-selection tests; no real Docker, wallet or network."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_join as join

def inventory(node, roles):
    return {
        "schema": "SSE_R143_NEW_HOST_READINESS_V1",
        "nodeId": node,
        "requestedRoles": list(roles),
        "initialSizingAdviceMet": True,
        "missingBinaries": [],
        "hostPackagesInstalled": False,
        "containersStarted": False
    }

class UnifiedJoinTests(unittest.TestCase):
    def test_every_single_public_role_selectable(self):
        for role in join.ROLE_NAMES:
            with self.subTest(role=role):
                obj=join.plan("new-node-a", [role], inventory)
                self.assertIn(role, obj["selectedRoles"])
                self.assertEqual(obj["rolesActivatedByThisPlan"], [])
                self.assertFalse(obj["allSelectedRolesInstalled"])

    def test_validator_implicitly_requires_full_client_not_staking_authorization(self):
        obj=join.plan("new-node-a",["validator"],inventory)
        self.assertEqual(obj["selectedRoles"],["full_node","validator"])
        self.assertTrue(obj["automaticallyIncludedDependencies"])
        self.assertFalse(obj["walletsOrValidatorKeysGenerated"])
        self.assertFalse(obj["transactionsBroadcast"])

    def test_validator_and_observer_does_not_add_extra_full_node(self):
        obj=join.plan("new-node-a",["observer","validator"],inventory)
        self.assertEqual(obj["selectedRoles"],["observer","validator"])
        self.assertEqual(obj["automaticallyIncludedDependencies"],[])

    def test_consumer_provider_and_monitor_can_coexist_as_preferences(self):
        obj=join.plan("new-node-a",["consumer","provider","monitor"],inventory)
        self.assertEqual(len(obj["components"]),3)
        self.assertFalse(obj["operatorOrValidatorIndependenceCertified"])

    def test_interactive_menu_handles_several_unique_roles(self):
        selected=join.choose(lambda _: "1, 4, 6",lambda _:None)
        self.assertEqual(selected,["full_node","provider","monitor"])

    def test_menu_rejects_duplicates_and_invalid_choice(self):
        for choices in ("1,1","0","7","1,three","",",","1,,2"):
            with self.subTest(choices=choices),self.assertRaises(join.Refused):
                join.choose(lambda _:choices,lambda _:None)

    def test_command_plan_does_not_touch_live_resources(self):
        out=[]
        rc=join.main(["--node-id","new-node-a","--roles","monitor,consumer",
                      "--plan"],inventory=inventory,output=out.append)
        self.assertEqual(rc,0)
        payload=json.loads(out[-1])
        self.assertEqual(payload["selectedRoles"],["monitor","consumer"])
        self.assertFalse(payload["networkJoined"])
        self.assertFalse(payload["nativeClientsStarted"])

    def test_observer_plan_only_delegates_readonly_r137(self):
        with patch.object(join.observer,"main",return_value=0) as delegated:
            rc=join.main(["--node-id","new-node-a","--roles","full_node",
                          "--observer-plan","--manifest","/tmp/manifest.json",
                          "--archive","/tmp/chain.tar.gz",
                          "--discovery-source","https://one.example.org/peers.json",
                          "--discovery-source","https://two.example.net/peers.json"],
                         inventory=inventory)
        self.assertEqual(rc,0)
        self.assertIn("--plan",delegated.call_args.args[0])
        self.assertNotIn("--apply",delegated.call_args.args[0])

    def test_observer_plan_does_not_accept_app_only_roles(self):
        with patch.object(join.observer,"main") as delegated:
            with redirect_stderr(io.StringIO()):
                rc=join.main(["--node-id","new-node-a","--roles","monitor",
                              "--observer-plan","--manifest","/tmp/m",
                              "--archive","/tmp/a",
                              "--discovery-source","https://one.example.org/p",
                              "--discovery-source","https://two.example.org/p"],
                             inventory=inventory)
        self.assertEqual(rc,2)
        delegated.assert_not_called()

    def test_observer_plan_refuses_missing_public_sources(self):
        with redirect_stderr(io.StringIO()):
            rc=join.main(["--node-id","new-node-a","--roles","full_node",
                          "--observer-plan","--manifest","/tmp/m",
                          "--archive","/tmp/a",
                          "--discovery-source","https://one.example.org/p"],
                         inventory=inventory)
        self.assertEqual(rc,2)

    def test_unrecognized_roles_and_duplicate_rejected(self):
        for roles in (["root"],["validator","validator"],[],["miner"]):
            with self.subTest(roles=roles),self.assertRaises(join.Refused):
                join.normalize_roles(roles)

    def test_cannot_mix_plan_and_observer_only_args(self):
        with redirect_stderr(io.StringIO()):
            rc=join.main(["--node-id","new-node-a","--roles","monitor",
                          "--manifest","/tmp/m"],inventory=inventory)
        self.assertEqual(rc,2)

if __name__=="__main__":
    unittest.main()
