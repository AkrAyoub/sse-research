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
        self.assertIn('validator running: no automatic EL BN maintenance',s)
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
        self.assertIn('DO NOT RETRY BLINDLY',s)
if __name__=="__main__":
    unittest.main()
