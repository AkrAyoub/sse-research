"""R9 new-host coordinator: logged-out Tailscale, dirty Git, identity safety."""
import json
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_r9_host_setup import (
    HostSetupError, base_check, parse_tailnet, prepare_identity,
    NODE_IDS, run_readonly
)

REV="0"*40


class HostSetupTests(unittest.TestCase):
    def test_logged_out_tailnet_blocks_validator_identity(self):
        status='{"BackendState":"NeedsLogin"}'
        report=base_check(expected_commit=REV,observed_commit=REV,
                          tracked_dirty="",status=status,linux=True,
                          docker_access=False)
        self.assertFalse(report["readyForValidatorIdentity"])
        self.assertFalse(report["readyForContainerCanary"])
        self.assertIn("AUTHORIZE_TAILSCALE_TAILNET_INTERACTIVELY_OR_WITH_ONE_TIME_BROKER",
                      report["blockers"])
        self.assertIn("DOCKER_SOCKET_REQUIRES_REVIEWED_OPERATOR_ACCESS",
                      report["blockers"])
        self.assertFalse(report["ethereumTransactionsSent"])

    def test_connected_tailnet_with_real_overlay_address(self):
        status=json.dumps({"BackendState":"Running","Self":{
            "Online":True,"ID":"n-example","TailscaleIPs":["100.101.102.103","fd7a:115c:a1e0::7"],
        }})
        self.assertEqual(parse_tailnet(status)["ip"],"100.101.102.103")
        report=base_check(expected_commit=REV,observed_commit=REV,
                          tracked_dirty="",status=status,linux=True,
                          docker_access=True)
        self.assertTrue(report["readyForContainerCanary"])
        self.assertEqual(report["blockers"],[])

    def test_mutated_source_wrong_commit_and_platform_fail_closed(self):
        for current,dirty,linux in [
            ("1"*40,"",True),
            (REV," M contracts/OpenMonitorCommittee.sol",True),
            (REV,"",False),
        ]:
            with self.subTest(current=current,dirty=dirty,linux=linux):
                with self.assertRaises(HostSetupError):
                    base_check(expected_commit=REV,observed_commit=current,
                               tracked_dirty=dirty,status='{"BackendState":"Running"}',
                               linux=linux)

    def test_missing_or_ambiguous_tailnet_id_fails_closed(self):
        for state in [
            "not json",
            "[]",
            json.dumps({"BackendState":"Running","Self":{"Online":True,
                       "TailscaleIPs":["10.50.56.20"],"ID":"n1"}}),
            json.dumps({"BackendState":"Running","Self":{"Online":True,
                       "TailscaleIPs":["100.101.102.103","100.101.102.104"],"ID":"n1"}}),
        ]:
            with self.subTest(state=state):
                self.assertFalse(parse_tailnet(state)["online"])

    def test_forbids_validator_role_escalation(self):
        self.assertEqual(NODE_IDS,
                         {"validator-1","validator-2","validator-3","validator-4"})
        with self.assertRaises(HostSetupError):
            prepare_identity(node_id="provider",
                             private_dir=Path("/tmp/untrusted"),
                             public_file=Path("/tmp/untrusted/provider.public.json"),
                             approved_revision=REV)

    def test_doctor_disallows_commands_other_than_read_only(self):
        for unsafe in [
            ["tailscale","up"],
            ["sudo","docker","compose","up"],
            ["git","switch","main"],
            ["cast","send"],
        ]:
            with self.subTest(cmd=unsafe),self.assertRaises(HostSetupError):
                run_readonly(unsafe)


if __name__=="__main__":
    unittest.main()
