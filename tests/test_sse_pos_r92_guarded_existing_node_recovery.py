"""R92 guard-only tests: mock Docker and ZeroTier, never create containers."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import sse_pos_r92_guarded_existing_node_recovery as m

class R92RecoveryTests(unittest.TestCase):
    def test_role_isolation_and_fixed_addresses(self):
        self.assertEqual(set(m.ROLES), {"owner", "observer"})
        self.assertTrue(m.ROLES["owner"]["internal"])
        self.assertFalse(m.ROLES["observer"]["internal"])
        self.assertEqual(len(m.ROLES["owner"]["containers"]), 2)
        self.assertEqual(len(m.ROLES["observer"]["containers"]), 2)
        for role, config in m.ROLES.items():
            for cname, _, _ in config["containers"]:
                self.assertNotIn("vc", cname)
                self.assertNotIn("preserved", cname)
                self.assertNotIn("8551/tcp", config["bindings"][cname])
    def test_fail_closed_unexpected_binding(self):
        config = m.ROLES["owner"]
        name = "sse31340-g2-bn"
        bad = {"HostConfig": {"NetworkMode": config["network"],
                "PortBindings": {**{
                  k: [{"HostIp": host, "HostPort": port}]
                  for k, (host, port) in config["bindings"][name].items()},
                  "8551/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8551"}]}},
               "State": {"Running": True}}
        with patch.object(m, "inspect", return_value=bad), self.assertRaises(m.Refused):
            m.verify_container(name, config)
    def test_refuse_wrong_bridge_alias(self):
        cfg = m.ROLES["owner"]
        obj = {"NetworkSettings": {"Networks": {cfg["network"]: {
            "IPAddress": "172.18.0.2", "Aliases": [], "DNSNames": ["other"]}}}}
        with self.assertRaises(m.Refused):
            m.verify_attachment(obj, cfg, "172.18.0.2", "sse31340-g2-el")
    def test_missing_endpoint_and_port_are_not_success(self):
        cfg = m.ROLES["observer"]
        self.assertFalse(m.verify_attachment({"NetworkSettings":{"Networks":{}}}, cfg,
                                             "172.18.0.2", None))
        self.assertFalse(m.published({"NetworkSettings":{"Ports":{}}},
                                     cfg["bindings"]["sse31340-r59-nonsigning-el"]))
    def test_observer_periodic_recovery_installed_and_not_latched(self):
        service = (ROOT / "systemd" / "sse31340-existing-node-recover@.service").read_text()
        timer = (ROOT / "systemd" / "sse31340-observer-network-recovery.timer").read_text()
        installer = (ROOT / "scripts" / "r92_install_existing_node_recovery.sh").read_text()
        self.assertIn("Type=oneshot", service)
        self.assertNotIn("RemainAfterExit=yes", service)
        self.assertIn("Restart=on-failure", service)
        self.assertIn("OnBootSec=45s", timer)
        self.assertIn("OnUnitInactiveSec=2min", timer)
        self.assertIn("Unit=sse31340-existing-node-recover@observer.service", timer)
        self.assertIn("enable --now sse31340-observer-network-recovery.timer", installer)
        self.assertLess(installer.index("enable --now sse31340-observer-network-recovery.timer"),
                        installer.index('systemctl disable "sse31340-existing-node-recover@$ROLE.service"'))
    def test_plan_does_not_modify_docker(self):
        cfg = m.ROLES["observer"]
        with patch.object(m, "verify_environment", return_value=cfg), patch.object(
            m, "verify_container", return_value=({}, True)), patch.object(
            m, "verify_attachment", return_value=False), patch.object(
            m, "published", return_value=False), patch.object(m, "docker"
        ) as docker:
            self.assertEqual(m.perform("observer", apply=False), 0)
        docker.assert_not_called()

if __name__ == "__main__":
    unittest.main()
