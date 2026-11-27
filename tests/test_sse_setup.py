"""Pure orchestration plan checks; no live host mutations."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import sse_setup as setup
SHA="a"*40
class SetupPlanTest(unittest.TestCase):
    def test_fresh_app_only(self):
        s=setup.plan(["consumer","monitor","keeper"],SHA)
        self.assertEqual([x["id"] for x in s],["app-host-prerequisites","v4-app-roles","linger"])
        self.assertIn("--prepare-only",s[1]["argv"])
    def test_existing_app(self):
        s=setup.plan(["monitor","keeper"],SHA,existing_app=True)
        self.assertEqual([x["id"] for x in s],["app-python","verify-existing-rpc","v4-app-roles","linger"])
    def test_fresh_native_blocked(self):
        self.assertTrue(setup.plan(["validator","provider"],SHA)[0]["blocked"])
    def test_existing_native_preserved(self):
        s=setup.plan(["full_node","monitor"],SHA,existing_native=True)
        self.assertEqual([x["id"] for x in s],["verify-existing-native","app-python","v4-app-roles","linger"])
    def test_validator_gate(self):
        self.assertTrue(setup.plan(["validator"],SHA,existing_native=True)[-1]["blocked"])
    def test_invalid(self):
        for roles,sha in ((["miner"],SHA),([],SHA),(["monitor"],"HEAD")):
            with self.assertRaises(setup.Refused): setup.plan(roles,sha)
        with self.assertRaises(setup.Refused): setup.plan(["full_node"],SHA,transport="relay")
if __name__=="__main__": unittest.main()
