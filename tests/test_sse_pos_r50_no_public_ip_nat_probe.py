"""R50 tests of correct, privacy-preserving real NAT/outbound STUN audit."""
import struct
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import sse_pos_r50_no_public_ip_nat_probe as m

class R50RealNatNoPublicIPTests(unittest.TestCase):
    def test_stun_rfc5389_magic_cookie_and_binding_nonce(self):
        self.assertEqual(m.MAGIC, 0x2112A442)
        self.assertEqual(len(bytes(range(12))), 12)

    def test_valid_ipv4_xor_mapped_global_address_not_emitted(self):
        nonce = bytes(range(12))
        ip = bytes((8, 8, 8, 8))
        obfuscation = m.MAGIC.to_bytes(4, "big")
        mapped = bytes(a ^ b for a, b in zip(ip, obfuscation))
        port = (19302 ^ (m.MAGIC >> 16)).to_bytes(2, "big")
        payload = b"\x00\x01" + port + mapped
        attr = struct.pack("!HH", 0x0020, len(payload)) + payload
        packet = struct.pack("!HHI", 0x0101, len(attr), m.MAGIC) + nonce + attr
        result = m.unpack_stun(packet, nonce)
        self.assertTrue(result["validStunBindingSuccess"])
        self.assertTrue(result["outboundMappedGlobalIPv4Observed"])
        self.assertNotIn("8.8.8.8", str(result))
        self.assertFalse(result["nativeP2pInboundReachabilityProven"])

    def test_transaction_spoof_mismatch_rejected(self):
        nonce = b"\x00" * 12
        packet = struct.pack("!HHI", 0x0101, 0, m.MAGIC) + b"\xff" * 12
        self.assertFalse(m.unpack_stun(packet, nonce)["validStunBindingSuccess"])

    def test_local_private_mapping_not_represented_as_public(self):
        nonce = bytes(range(12))
        ip = bytes((10, 0, 0, 8))
        obfuscation = m.MAGIC.to_bytes(4, "big")
        payload = b"\x00\x01\x00\x00" + bytes(a ^ b for a, b in zip(ip, obfuscation))
        attr = struct.pack("!HH", 0x0020, len(payload)) + payload
        packet = struct.pack("!HHI", 0x0101, len(attr), m.MAGIC) + nonce + attr
        self.assertFalse(m.unpack_stun(packet, nonce)["outboundMappedGlobalIPv4Observed"])

    def test_plan_is_readonly_and_has_no_external_probe(self):
        observed = {
            "privateDockerNetworkInternal": True,
            "hostInterfaces": {
                "hostHasDirectGlobalIpv4": False,
                "hostHasDirectGlobalIpv6": False,
                "privateOrCarrierNatIPv4Present": True,
            },
        }
        with patch.object(m.owner, "run", return_value=observed):
            with patch.object(m, "tcp_egress", side_effect=AssertionError("TCP forbidden")):
                with patch.object(m, "udp_stun_egress", side_effect=AssertionError("UDP forbidden")):
                    result = m.report("a"*40, False)
        self.assertEqual(result["probeStatus"], "NO_NETWORK_PROBES")
        self.assertFalse(result["ownerNativeP2pCurrentlyAccessibleOverPublicInternet"])
        self.assertTrue(result["dockerClientsContainersOrFilesModified"] is False)

    def test_probe_data_does_not_prove_inbound(self):
        observed = {
            "privateDockerNetworkInternal": True,
            "hostInterfaces": {
                "hostHasDirectGlobalIpv4": False,
                "hostHasDirectGlobalIpv6": False,
                "privateOrCarrierNatIPv4Present": True,
            },
        }
        with patch.object(m.owner, "run", return_value=observed):
            with patch.object(m, "tcp_egress", return_value={"tcpConnectionEstablished": True}):
                with patch.object(m, "udp_stun_egress", return_value={"bindingResponseReceivedAndMatchedNonce": True}):
                    result = m.report("a"*40, True)
        self.assertFalse(result["outboundTcpUdpProvenToCarryNativeEthereumP2p"])
        self.assertFalse(result["actualNativeExternalP2pPeerHandshakeObserved"])

    def test_source_never_modifies_docker_or_validator_files(self):
        src = (ROOT / "tools/sse_pos_r50_no_public_ip_nat_probe.py").read_text("utf-8")
        for forbidden in ('"start"', '"run"', '"restart"', '"rm"', '"stop"',
                          "validators-dir", "secrets-dir", "mnemonic"):
            self.assertNotIn(forbidden, src)
        self.assertIn('"rawPublicIpOrMappedPortPrinted": False', src)
        self.assertIn('mode.add_argument("--probe-outbound"', src)

    def test_source_distinguishes_provider_forwarding_from_stun(self):
        src = (ROOT / "tools/sse_pos_r50_no_public_ip_nat_probe.py").read_text("utf-8")
        self.assertIn('"providerIngressPortForwardingOrGlobalIpv6Capability": "UNKNOWN_NOT_PROBED"', src)
        self.assertIn('"natTypeOrInboundPortMappingDetermined": False', src)

if __name__ == "__main__":
    unittest.main()
