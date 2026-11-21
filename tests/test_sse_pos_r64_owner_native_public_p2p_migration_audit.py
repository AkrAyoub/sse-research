"""R64 source-only tests; no real VM networking, chain or signing altered."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r64_owner_native_public_p2p_migration_audit as m

class R64OwnerReadOnlyNativeMigration(unittest.TestCase):
    def test_real_owner_overlay_ipv6_and_reject_private_lan(self):
        self.assertEqual(m.safe_overlay_address("fca0:2328:776e:4750:395b::1"),
                         "fca0:2328:776e:4750:395b::1")
        for addr in ("10.50.56.2","::1","fd00::1","2001:db8::1",None):
            with self.subTest(address=addr),self.assertRaises(m.R64Refused):
                m.safe_overlay_address(addr)

    def test_read_only_argv_redacts_jwt_key_and_host_paths(self):
        source=["--network-id=31340","--p2p-enabled=false","--p2p-port=30303",
                "--engine-jwt-secret=/jwt/engine.jwt","--password=/private/secret",
                "--execution-jwt=/private/secret","--engine-rpc-port=8551"]
        out=m.safe_runtime_flags(source)
        self.assertEqual(out["network-id"],["31340"])
        self.assertEqual(out["p2p-enabled"],["false"])
        self.assertEqual(out["engine-rpc-port"],["8551"])
        self.assertNotIn("jwt",json.dumps(out))
        self.assertNotIn("secret",json.dumps(out).lower())

    def test_no_unreviewed_network_flag_values(self):
        with self.assertRaises(m.R64Refused):
            m.safe_runtime_flags(["--p2p-interface-ipv6=token&secret"])
        with self.assertRaises(m.R64Refused):
            m.safe_runtime_flags(None)

    def test_mount_data_sources_never_printed(self):
        raw=json.dumps([{"Type":"bind","Destination":"/data","Source":"/host/secrets/eth"},
                        {"Type":"bind","Destination":"/jwt/engine.jwt","Source":"/host/jwt"},
                        {"Type":"bind","Destination":"/mystery-key-path","Source":"/host/validator/private"}])
        out=m.safe_mounts(raw)
        self.assertEqual(out["mountCount"],3)
        self.assertIn("<redacted_other_mount>",out["knownMountTargetsOnly"])
        self.assertNotIn("/host/",json.dumps(out))
        self.assertNotIn("validator/private",json.dumps(out))

    def test_owner_mounts_fail_on_bad_json(self):
        for raw in ("{}","null","[null]"):
            with self.subTest(raw=raw),self.assertRaises(m.R64Refused):
                m.safe_mounts(raw)

    def test_original_client_refuses_public_network_attachment(self):
        responses=[
            json.dumps({"Running":True}),m.r63.r60.NET,
            json.dumps({m.r63.r60.NET:{}, "external-unreviewed":{}})
        ]
        with patch.object(m.r63,"priv",side_effect=responses):
            with self.assertRaises(m.R64Refused):
                m.original_container(m.r63.r60.VC)

    def test_correct_original_client_readonly_inventory(self):
        responses=[
            json.dumps({"Running":True}),m.r63.r60.NET,
            json.dumps({m.r63.r60.NET:{}}),
            json.dumps(["--p2p-enabled=false","--engine-jwt-secret=/jwt/engine.jwt"]),
            json.dumps([{"Type":"bind","Destination":"/data","Source":"/private"}]),
            "sha256:"+"a"*64
        ]
        with patch.object(m.r63,"priv",side_effect=responses):
            o=m.original_container(m.r63.r60.EL)
        self.assertTrue(o["originalStillRunning"])
        self.assertTrue(o["noExtraAttachedNetworks"])
        self.assertEqual(o["reviewedNetworkRuntimeFlags"]["p2p-enabled"],["false"])
        self.assertTrue(o["originalPreservedMountLayout"]["hostMountSourcePathsNeverPrinted"])

    def test_actual_owner_health_must_match_original_chain(self):
        transport={"alreadyOnExactPublicControllerlessNetwork":True,
                   "actualHostOverlay6planeIpv6":"fca0:2328:776e:4750:395b::1",
                   "targetNetworkId":m.r63.NETWORK,
                   "targetZeroTierVersion":m.r63.VERSION}
        def original(name):
            return {"reviewedNetworkRuntimeFlags":{"p2p-enabled":["false"]}}
        health={"execution":{"insideExistingContainerNetnsApiReadings":{
                    "eth_chainId":{"value":hex(31340)},
                    "eth_blockNumber":{"value":"0xbd5"},
                    "net_peerCount":{"value":"0x0"}}},
                "beacon":{"insideExistingContainerNetnsApiReadings":{
                    "genesis":{"genesisTime":m.r63.r60.GENESIS_TIME},
                    "head":{"headSlot":"3247"},
                    "finality":{"finalizedEpoch":"97","finalizedRoot":"0x"+"a"*64}}},
                "originalValidatorContainerRunning":True}
        with patch.object(m.r63,"plan",return_value=transport),patch.object(
             m,"original_container",side_effect=original),patch.object(m.r62,"audit",return_value=health):
            out=m.current_owner_audit("a"*40)
        self.assertEqual(out["actualOwnerOverlayNetworkId"],m.r63.NETWORK)
        self.assertTrue(out["originalExecutionChainId31340Live"])
        self.assertEqual(out["originalBeaconFinalizedEpoch"],"97")
        self.assertTrue(out["originalELP2pExplicitlyDisabled"])
        self.assertFalse(out["ownerOverlayTransportModeOrUnderlayPathVerified"])
        self.assertTrue(out["noServicesOrNetworkConfigurationsChanged"])

    def test_mismatch_refuses_any_migration_claim(self):
        transport={"alreadyOnExactPublicControllerlessNetwork":False}
        with patch.object(m.r63,"plan",return_value=transport):
            with self.assertRaises(m.R64Refused):
                m.current_owner_audit("a"*40)

    def test_no_apply_or_docker_mutations_in_readonly_source(self):
        src=(ROOT/"tools/sse_pos_r64_owner_native_public_p2p_migration_audit.py").read_text("utf-8")
        for banned in ('"--apply"','"docker","stop"','"docker","start"',
                       '"docker","run"','"docker","network","connect"',
                       'zerotier-cli", "join"', "scp ", "ssh ", "--publish"):
            self.assertNotIn(banned,src)
        self.assertIn('mode":"readonly_migration_readiness_not_implementation"',src)
        self.assertIn('noPrivateLanEthereumBootstrapUsed":True',src)

if __name__=="__main__":
    unittest.main()
