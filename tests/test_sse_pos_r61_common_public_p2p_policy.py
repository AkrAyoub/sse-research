"""R61: regression gates for equal open-join Internet-native P2P topology.

These inspect executable source and architecture. They do NOT simulate a real
native peer handshake or attest underlay ISP/physical independence.
"""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import sse_pos_r59_native_ipv6_observer as observer
import sse_pos_r60_owner_native_p2p_readonly_audit as owner


class PublicP2pNoPrivateLanContract(unittest.TestCase):
    def test_every_native_full_node_must_share_the_same_open_overlay_contract(self):
        architecture=(ROOT/"docs/ARCHITECTURE.md").read_text("utf-8")
        self.assertIn("NO provider-private LAN",architecture)
        self.assertIn("ff2328775f000000",architecture)
        self.assertIn("FORBIDDEN as an Ethereum native execution/consensus bootstrap path",architecture)
        self.assertIn("same open Internet-accessible network mechanism",architecture)
        self.assertIn("ZeroTier 6plane address does NOT prove",architecture)

    def test_observer_uses_only_the_shared_6plane_network(self):
        self.assertEqual(observer.NETWORK,"ff2328775f000000")
        ipv6="fca0:2328:77b8:6578:a55::1"
        self.assertEqual(observer.port_bindings(ipv6,True),[
            f"[{ipv6}]:30404:30404/tcp",f"[{ipv6}]:30404:30404/udp",
            "127.0.0.1:28545:8545/tcp"])
        self.assertEqual(observer.port_bindings(ipv6,False),[
            f"[{ipv6}]:9000:9000/tcp",f"[{ipv6}]:9000:9000/udp",
            f"[{ipv6}]:9001:9001/udp","127.0.0.1:25052:5052/tcp"])

    def test_no_provider_private_ip_in_any_native_peer_endpoint_source(self):
        for path in (ROOT/"tools/sse_pos_r59_native_ipv6_observer.py",
                     ROOT/"tools/sse_pos_r60_owner_native_p2p_readonly_audit.py"):
            src=path.read_text("utf-8")
            # Test only native peering implementation, not historical journal/SCP.
            for block in ("10.50.56.","192.168.","10.0.0.","172.16.",
                          "scp ", "ssh ", "--enode=10.","--bootnodes=10."):
                self.assertNotIn(block,src, f"private provider transport dependency in {path.name}")
        self.assertIn('"--p2p-host-ipv6=" + ip',
                      (ROOT/"tools/sse_pos_r59_native_ipv6_observer.py").read_text("utf-8"))

    def test_no_bootstrap_admission_whitelist_or_single_owner_required(self):
        src=(ROOT/"tools/sse_pos_r59_native_ipv6_observer.py").read_text("utf-8")
        self.assertIn('el_enode: str | None',src)
        self.assertIn('bn_enr: str | None',src)
        self.assertNotIn("allowlist-operators",src)
        self.assertNotIn("genesis-owner-ip",src)
        self.assertIn('"actualBootnodesAuthenticatedOrReachableByPreflight": False',src)
        self.assertIn('"actualOriginalChainHeadAndFinalityStillNeedIndependentObservation": True',src)

    def test_same_native_el_cl_requires_real_two_layer_peer_evidence(self):
        architecture=(ROOT/"docs/ARCHITECTURE.md").read_text("utf-8")
        for phrase in ("Besu devp2p/discovery", "Lighthouse discv5+libp2p P2P",
                       "no private LAN used", "third-party root/discovery/relay"):
            self.assertIn(phrase,architecture)
        self.assertIn('"nativeSecondPeerOrIndependentFinalityProven": False',
                      (ROOT/"tools/sse_pos_r60_owner_native_p2p_readonly_audit.py").read_text("utf-8"))

    def test_r60_owner_audit_has_no_mutating_overlay_join_or_validator_restart(self):
        src=(ROOT/"tools/sse_pos_r60_owner_native_p2p_readonly_audit.py").read_text("utf-8")
        self.assertIn('ownerZeroTierCliInstalled',src)
        self.assertIn('ownerZeroTierOverlayActuallyJoinedByThisAudit',src)
        for banned in ('zerotier-cli", "join"', 'docker(["network", "connect"',
                       'docker(["start"', 'docker(["stop"', '"--apply"'):
            self.assertNotIn(banned,src)

if __name__=="__main__":
    unittest.main()
