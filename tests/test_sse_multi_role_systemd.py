"""Multi-role systemd planning checks: read-only monitor isolation, no apply."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))

from sse_multi_role_systemd import (
    SupervisorPlanError,render_monitor_discovery_unit,role_supervision_plan)

NODE={"schema":"sse-node-roles-v1","nodeId":"mixed-provider-monitor-1",
      "roles":["provider","monitor","observer"],
      "wallets":{"provider":"0x"+"11"*20,"monitor":"0x"+"22"*20}}
ARGS={
    "python":"/opt/sse/runtime/abcdef/bin/python",
    "checkout":"/opt/sse/releases/abcdef",
    "manifest":"/etc/sse/node-roles.json",
    "journal":"/var/lib/sse-monitor/events.sqlite",
    "rpc_url":"http://127.0.0.1:8545",
    "settlement":"0x"+"33"*20,
    "chain_id":31337,
    "start_block":12,
}


class RoleSystemdPlanTests(unittest.TestCase):
    def test_monitor_plan_is_separate_nonprivileged_unit(self):
        result=role_supervision_plan(NODE,**ARGS)
        self.assertEqual(result["configuredRoles"],["provider","monitor","observer"])
        self.assertEqual(set(result["units"]),{"sse-monitor-discovery.service"})
        unit=result["units"]["sse-monitor-discovery.service"]
        for item in ("User=ssemonitor","Group=ssemonitor","StateDirectoryMode=0700",
                     "ProtectSystem=strict","NoNewPrivileges=yes",
                     "ReadWritePaths=/var/lib/sse-monitor","--watch",
                     "ExecStart=","--confirmations 2"):
            self.assertIn(item,unit)
        self.assertNotIn("signer",unit.lower())
        self.assertNotIn("--capture",unit)
        self.assertNotIn("--execute",unit)
        self.assertFalse(result["ethereumTransactionsSent"])
        self.assertFalse(result["roleActivated"])
        self.assertFalse(result["providerAutostart"])

    def test_node_without_monitor_has_no_unauthorized_monitor_unit(self):
        node={**NODE,"roles":["provider","observer"],
              "wallets":{"provider":NODE["wallets"]["provider"]}}
        result=role_supervision_plan(node,**ARGS)
        self.assertEqual(result["units"],{})
        with self.assertRaises(SupervisorPlanError):
            render_monitor_discovery_unit(node,**ARGS)

    def test_unsafe_paths_and_remote_plain_http_refused(self):
        for kw in ({"checkout":"/opt/sse/../etc"},
                   {"journal":"/tmp/unprotected.sqlite"},
                   {"python":"python3"},
                   {"rpc_url":"http://example.org:8545"},
                   {"settlement":"0x"+"00"*20}):
            args={**ARGS,**kw}
            with self.subTest(kw=kw),self.assertRaises((SupervisorPlanError,ValueError)):
                render_monitor_discovery_unit(NODE,**args)

    def test_no_privileged_or_global_dashboard_role_started(self):
        both={**NODE,"roles":["provider","monitor","observer","consumer"],
              "wallets":{**NODE["wallets"],"consumer":"0x"+"44"*20}}
        plan=role_supervision_plan(both,**ARGS)
        self.assertEqual(len(plan["units"]),1)
        self.assertFalse(plan["monitorVotesSent"])
        self.assertFalse(plan["consumerAutostart"])
        self.assertFalse(plan["systemdUnitWritten"])


if __name__=="__main__":
    unittest.main()
