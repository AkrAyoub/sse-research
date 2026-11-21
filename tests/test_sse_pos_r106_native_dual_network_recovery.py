"""R106 source safety tests; no real Docker, no VM mutations."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"r106_vm4706_restore_native_dual_network.sh"

class R106NativeRecoveryTests(unittest.TestCase):
    def test_shell_syntax(self):
        subprocess.run(["bash","-n",str(SCRIPT)],check=True)
    def test_never_modifies_validator_or_recreates_client(self):
        s=SCRIPT.read_text()
        self.assertIn('VC=sse31340-g2-vc',s)
        self.assertIn('validator running; no automatic client restart',s)
        self.assertIn('grep -Fq "$IP/40"',s)
        self.assertIn('do [[ "$payload" == *"$binding"* ]]',s)
        self.assertNotIn('docker run ',s)
        self.assertNotIn('docker rm ',s)
        self.assertNotIn('network create ',s)
        self.assertNotIn('docker rename ',s)
    def test_explicit_original_networks_and_ports(self):
        s=SCRIPT.read_text()
        for item in (
            'sse31340-g2-internal','sse31340-g2-r65-public-p2p',
            '172.18.0.2','172.18.0.3','30404','9000','9001',
            '18545','15052','"8551/tcp"','--plan','--apply',
        ):
            self.assertIn(item,s)
    def test_relay_retired_only_after_success(self):
        s=SCRIPT.read_text()
        self.assertLess(s.index('network connect "$PUBLIC"'),s.index('systemctl disable "$RELAY"'))
        self.assertIn('validator running; no automatic client restart',s)
        self.assertIn('check state before retry',s)
        self.assertIn('if [[ "$(attachment "$C")" == no ]]',s)
        self.assertIn('if ! effective "$C"; then',s)
    def test_private_network_restored_before_public_on_boot(self):
        orchestrator=(ROOT/"scripts"/"r110_owner_boot_reconcile_networks.sh").read_text()
        service=(ROOT/"systemd"/"sse31340-owner-native-network-recovery.service").read_text()
        installer=(ROOT/"scripts"/"r109_install_owner_native_network_recovery.sh").read_text()
        self.assertLess(orchestrator.index("sse_pos_r92_guarded_existing_node_recovery.py"),
                        orchestrator.index("sse31340-owner-native-network-recovery.sh"))
        self.assertIn("--role owner --apply",orchestrator)
        self.assertIn("sse31340-owner-native-network-orchestrator.sh",service)
        self.assertIn('install -m 0755 "$PRIVATE_RECOVERY"',installer)
        subprocess.run(["bash","-n",str(ROOT/"scripts"/"r110_owner_boot_reconcile_networks.sh")],check=True)

    def test_boot_service_and_timer_are_recurrent(self):
        root=ROOT/"systemd"
        service=(root/"sse31340-owner-native-network-recovery.service").read_text()
        timer=(root/"sse31340-owner-native-network-recovery.timer").read_text()
        install=(ROOT/"scripts"/"r109_install_owner_native_network_recovery.sh").read_text()
        self.assertIn("R106_BOOT_SERVICE=true",service)
        self.assertIn("Restart=on-failure",service)
        self.assertNotIn("RemainAfterExit=yes",service)
        self.assertIn("OnBootSec=45s",timer)
        self.assertIn("OnUnitInactiveSec=2min",timer)
        self.assertIn("enable --now sse31340-owner-native-network-recovery.timer",install)
        self.assertNotIn("sse31340-g2-vc start",service)

if __name__=="__main__":
    unittest.main()
