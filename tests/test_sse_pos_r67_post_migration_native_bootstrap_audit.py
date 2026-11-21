"""R67 tests use fake public ENR/NodeID and mocked localhost APIs only.

NO real client, chain, validator, native P2P, RPC, file or Docker mutation in tests.
"""
from __future__ import annotations
import base64
import ipaddress
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r67_post_migration_native_bootstrap_audit as m

IP="fca0:2328:776e:4750:395b::1"
NODEID="a"*128

def rlp_string(s:bytes)->bytes:
    if len(s)==1 and s[0]<128:return s
    if len(s)<56:return bytes([128+len(s)])+s
    n=len(s).to_bytes((len(s).bit_length()+7)//8,"big")
    return bytes([183+len(n)])+n+s

def rlp_list(vals:list[bytes])->bytes:
    raw=b"".join(rlp_string(v) for v in vals)
    if len(raw)<56:return bytes([192+len(raw)])+raw
    n=len(raw).to_bytes((len(raw).bit_length()+7)//8,"big")
    return bytes([247+len(n)])+n+raw

def fake_enr(ip=IP,port=9000,extra=None)->str:
    fields={
        b"id":b"v4",b"ip6":ipaddress.IPv6Address(ip).packed,
        b"secp256k1":b"\x02"+b"\x03"*32,
        b"tcp6":port.to_bytes(2,"big"),
        b"udp6":port.to_bytes(2,"big")
    }
    if extra:fields.update(extra)
    values=[b"\x01"*64,b"\x01"]
    for k,v in sorted(fields.items()):
        values.extend([k,v])
    return "enr:"+base64.urlsafe_b64encode(rlp_list(values)).decode().rstrip("=")

class R67RealPostMigrationSafetyTests(unittest.TestCase):
    def test_true_source_besu_public_nodeid_to_owner_ipv6_candidate(self):
        original="enode://"+NODEID+"@127.0.0.1:30303"
        v6=m.enode_bootstrap_from_rpc(original,IP)
        self.assertEqual(v6,"enode://"+NODEID+"@["+IP+"]:30404")
        self.assertTrue(m.r59.ENODE6.fullmatch(v6))

    def test_refuse_fake_or_private_lan_besu_identity(self):
        for value in ("enode://bad@[10.50.56.8]:30404",
                      "enr:"+NODEID,
                      "enode://"+NODEID+"@127.0.0.1:0",
                      "enode://"+NODEID+"@127.0.0.1:30303?password=abc",
                      None):
            with self.subTest(v=value),self.assertRaises(m.R67Refused):
                m.enode_bootstrap_from_rpc(value,IP)
        with self.assertRaises(m.R67Refused):
            m.enode_bootstrap_from_rpc("enode://"+NODEID+"@127.0.0.1:30303",
                                       "10.50.56.8")

    def test_beacon_public_enr_rlp_has_original_real_overlay_ip6_tcp_udp(self):
        fields=m.parse_enr_fields(fake_enr())
        data=m.validate_enr_host(fields,IP)
        self.assertTrue(data["beaconEnrIp6VerifiedAsActualOwnerOpenOverlay"])
        self.assertEqual(data["beaconEnrUdp6"],9000)

    def test_beacon_enr_refuses_incorrect_ipv6_or_ports(self):
        for enr in (fake_enr(ip="fca0:2328:77b8:6578:a55::1"),
                    fake_enr(port=9008)):
            with self.subTest(enr=enr[:10]),self.assertRaises(m.R67Refused):
                m.validate_enr_host(m.parse_enr_fields(enr),IP)

    def test_beacon_enr_refuses_private_ipv4_advertisement(self):
        fields=m.parse_enr_fields(fake_enr(extra={b"ip":ipaddress.IPv4Address("10.50.56.8").packed}))
        with self.assertRaises(m.R67Refused):
            m.validate_enr_host(fields,IP)

    def test_enr_rejects_invalid_b64_and_truncated_rlp(self):
        for value in ("enr:"+"*"*90,"enr:"+"A"*100,
                      "enr:"+base64.urlsafe_b64encode(b"not-an-enr"*20).decode()):
            with self.subTest(enr=value[:10]),self.assertRaises(m.R67Refused):
                m.parse_enr_fields(value)

    def test_safe_eth_rpc_hex_quantities(self):
        self.assertEqual(m.safe_hex_quantity("0x7a6c"),31340)
        for v in ("31340","0x", "0xz", -1, None, "0x"+"1"*100):
            with self.subTest(v=v),self.assertRaises(m.R67Refused):
                m.safe_hex_quantity(v)

    def test_only_exact_localhost_http_endpoints_and_reviewed_rpc_methods(self):
        with self.assertRaises(m.R67Refused):
            m.endpoint_json("http://10.50.56.8:8545")
        with self.assertRaises(m.R67Refused):
            m.rpc("admin_removePeer")
        with self.assertRaises(m.R67Refused):
            m.rpc("eth_sendRawTransaction")

    def test_post_migration_original_owner_bootstrap_and_progress_with_mock_source(self):
        enode="enode://"+NODEID+"@127.0.0.1:30303"
        rpc_data={"eth_chainId":"0x7a6c","eth_blockNumber":"0xf10",
                  "net_peerCount":"0x0","net_listening":True,
                  "net_enode":enode}
        REST={
            "/eth/v1/beacon/genesis":{"genesis_time":str(m.r65.OWNER.GENESIS_TIME)},
            "/eth/v1/node/identity":{"enr":fake_enr(),"peer_id":"test-peer-only"},
            "/eth/v1/beacon/headers/head":{"header":{"message":{"slot":"4000"}}},
            "/eth/v1/beacon/states/head/finality_checkpoints":{
                "finalized":{"epoch":"121","root":"0x"+"b"*64}},
            "/eth/v1/node/peer_count":{"connected":"0"},
            "/eth/v1/node/syncing":{"is_syncing":False}
        }
        def get_json(args):
            field=args[2]
            if field=="{{json .State}}":
                return {"Running":not args[-1].endswith("-r65-preserved")}
            if field=="{{json .NetworkSettings.Networks}}":
                return {m.r65.TRUSTED:{},m.r65.PUBLIC_BRIDGE:{}}
            if field=="{{json .Config.Cmd}}":
                if args[-1]==m.r65.EL:
                    return ["--network-id=31340","--p2p-enabled=true",
                            "--p2p-port-ipv6=30404","--p2p-host-ipv6="+IP]
                return ["--enr-address="+IP,"--port6=9000",
                        "--discovery-port6=9000","--disable-enr-auto-update"]
            raise AssertionError(args)
        with patch.object(m.r59,"overlay_ip",return_value=("ztfake",IP)),patch.object(
             m.r65,"get_json",side_effect=get_json),patch.object(
             m.r65,"binding_set",side_effect=lambda n:set(m.r65.validated_host_ports(IP)[n])),patch.object(
             m,"rpc",side_effect=lambda method:rpc_data[method]),patch.object(
             m,"rest",side_effect=lambda path:REST[path]):
            out=m.post_migration_audit()
        self.assertEqual(out["originalExecutionChainId"],31340)
        self.assertEqual(out["originalExecutionNativePeerCount"],0)
        self.assertTrue(out["originalBeaconFinalizedBeyondR65Epoch120"])
        self.assertEqual(out["sourceLighthouseBeaconEnrFromLiveNodeIdentity"],fake_enr())
        self.assertTrue(out["noContainerOrOverlayModification"])
        self.assertFalse(out["outsideProviderExecutionAndConsensusSyncProved"])

    def test_source_has_no_native_mutations_or_private_key_access(self):
        src=(ROOT/"tools/sse_pos_r67_post_migration_native_bootstrap_audit.py").read_text()
        for forbidden in ('"docker","stop"', '"docker","run"',
                          '"docker","create"', '"docker","start"',
                          '"docker","network","connect"', "public-key export",
                          "node-private-key", "slashing_protection", ".pem",
                          "zerotier-cli\",\"join", "tf.extract", "read_bytes("):
            self.assertNotIn(forbidden,src)
        self.assertIn('net_enode',src)
        self.assertIn('/eth/v1/node/identity',src)
        self.assertIn('"noSecretsReadOrFilesChanged":True',src)
        self.assertIn('"executionEnodeV6RemoteAdvertiseOrReachabilityNotYetProved":True',src)

if __name__=="__main__":
    unittest.main()
