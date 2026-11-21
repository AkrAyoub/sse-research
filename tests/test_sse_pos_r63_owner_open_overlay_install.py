"""R63: source-only tests for one-time original-owner official ZeroTier overlay join.

These tests mock all Docker, GPG, APT and ZeroTier responses. They DO NOT
install software, establish a network or prove native ETH P2P/finality.
"""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r63_owner_open_overlay_install as m

class R63OpenOverlayOwnerInstallerTests(unittest.TestCase):
    def test_same_public_network_and_original_client_names(self):
        self.assertEqual(m.NETWORK,"ff2328775f000000")
        self.assertEqual(m.VERSION,"1.16.2")
        self.assertEqual(m.G2_CONTAINERS,("sse31340-g2-el-r40","sse31340-g2-bn","sse31340-g2-vc"))
    def test_official_vendor_apt_source_and_pinned_key(self):
        self.assertIn("https://download.zerotier.com/debian/noble noble main",m.APT_REPO)
        self.assertIn("signed-by=/usr/share/keyrings/zerotier-debian-package-key.gpg",m.APT_REPO)
        self.assertEqual(m.KEY_FINGERPRINT,"74A5E9C458E1A431F1DA57A71657198823E52A61")
        self.assertIn("githubusercontent.com/zerotier/ZeroTierOne/",m.KEY_URL)
    def test_key_fingerprint_happy_and_wrong_signature(self):
        correct="pub:-:4096:1:1657198823E52A61:0::::\nfpr:::::::::"+m.KEY_FINGERPRINT+":"
        with patch.object(m,"call",return_value=correct):
            m.verify_key(Path("/tmp/not-opened"))
        with patch.object(m,"call",return_value=correct.replace(m.KEY_FINGERPRINT,"0"*40)):
            with self.assertRaises(m.R63Refused):
                m.verify_key(Path("/tmp/not-opened"))
    def test_private_original_owner_guard_before_any_network_work(self):
        with patch.object(m.r60,"owner_guard") as original,patch.object(m,"os_guard"),             patch.object(m,"priv",side_effect=["true",m.r60.NET]*3+["true"]):
            m.original_state_guard("a"*40)
        original.assert_called_once_with("a"*40)
    def test_original_signer_must_be_running_and_internal(self):
        with patch.object(m.r60,"owner_guard"),patch.object(m,"os_guard"),             patch.object(m,"priv",return_value="false"):
            with self.assertRaises(m.R63Refused):
                m.original_state_guard("a"*40)
    def test_existing_zerotier_membership_is_public_not_private(self):
        payload=[{"nwid":m.NETWORK,"status":"OK","type":"PUBLIC","assignedAddresses":["fca0:2328:77b8:6578:a55::1/40"]}]
        with patch.object(m.shutil,"which",return_value="/usr/sbin/zerotier-cli"),             patch.object(m,"priv",return_value=json.dumps(payload)):
            self.assertEqual(m.membership(),(True,"fca0:2328:77b8:6578:a55::1"))
        payload[0]["type"]="PRIVATE"
        with patch.object(m.shutil,"which",return_value="/usr/sbin/zerotier-cli"),             patch.object(m,"priv",return_value=json.dumps(payload)):
            with self.assertRaises(m.R63Refused):
                m.membership()
    def test_plan_no_privileged_network_or_package_modification(self):
        src=(ROOT/"tools/sse_pos_r63_owner_open_overlay_install.py").read_text("utf-8")
        before=src[src.index("def plan("):src.index("def fetch_official_key(")]
        for bad in ("apt-get","zerotier-cli\",\"join", "install_and_join(", "network create", "docker run"):
            self.assertNotIn(bad,before)
        self.assertIn('"noNativeEthereumP2pStarted":True',before)
        self.assertIn('"noPrivateLanNativePeerBootstrap":True',before)
    def test_install_requires_local_operator_tty(self):
        src=(ROOT/"tools/sse_pos_r63_owner_open_overlay_install.py").read_text("utf-8")
        self.assertIn("sys.stdin.isatty() and sys.stderr.isatty()",src)
        self.assertIn("INSTALL-OWNER-OPEN-P2P-TRANSPORT",src)
        self.assertIn('"--install-and-join"',src)
    def test_no_curl_pipe_bash_and_only_immutable_version(self):
        src=(ROOT/"tools/sse_pos_r63_owner_open_overlay_install.py").read_text("utf-8")
        self.assertNotIn("curl -s",src)
        self.assertNotIn("| bash",src)
        self.assertNotIn('"apt-get","upgrade"',src)
        self.assertIn('"zerotier-one="+VERSION',src)
        self.assertIn('"gpg","--batch","--dearmor"',src)
    def test_join_same_public_id_and_prevent_default_route_dns(self):
        src=(ROOT/"tools/sse_pos_r63_owner_open_overlay_install.py").read_text("utf-8")
        self.assertIn('priv(["zerotier-cli","join",NETWORK]',src)
        self.assertIn('"allowDefault=0","allowDNS=0","allowGlobal=0"',src)
        self.assertIn('if default_route()!=oldroute:',src)
    def test_original_blockchain_clients_must_not_be_modified(self):
        src=(ROOT/"tools/sse_pos_r63_owner_open_overlay_install.py").read_text("utf-8")
        for bad in ('"docker","stop"', '"docker","start"', '"docker","run"', '"docker","network","connect"',
                    '"engine.jwt","read"', '"--p2p-enabled=true"','--publish', 'wallet create', 'ssh ', 'scp '):
            self.assertNotIn(bad,src)
        self.assertIn('"actualNativeEthereumPeerHandshakeObserved":False',src)
    def test_only_existing_unchanged_initial_host_route(self):
        routes=[{"dst":"default","gateway":"10.50.56.1","dev":"eth0","metric":100}]
        with patch.object(m,"call",return_value=json.dumps(routes)):
            self.assertIn('"dev":"eth0"',m.default_route())
        with patch.object(m,"call",return_value="{}"):
            with self.assertRaises(m.R63Refused):
                m.default_route()

if __name__=="__main__":
    unittest.main()
