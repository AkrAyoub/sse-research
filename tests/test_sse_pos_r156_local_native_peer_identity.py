"""R156 deterministic parser tests, no network, Docker or signer access."""
import base64
import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r156_local_native_peer_identity as m

ADDR="fca0:2328:7777:8888::99"
ID="node-independent-a"
ENODE="enode://"+"a"*128+"@127.0.0.1:30303"

def rlp(raw):
    if isinstance(raw,list):
        body=b"".join(rlp(item) for item in raw)
        return bytes([0xc0+len(body)])+body if len(body)<=55 else (
            bytes([0xf7+len(len(body).to_bytes((len(body).bit_length()+7)//8,"big"))])
            + len(body).to_bytes((len(body).bit_length()+7)//8,"big")+body)
    if len(raw)==1 and raw[0]<128:
        return raw
    if len(raw)<=55:
        return bytes([0x80+len(raw)])+raw
    digits=len(raw).to_bytes((len(raw).bit_length()+7)//8,"big")
    return bytes([0xb7+len(digits)])+digits+raw

def enr(ip=ADDR, key_order=None, port=9000):
    # Mock RLP body to verify parser rules only, not a real signed ENR.
    entries=[
        (b"id",b"v4"),
        (b"ip6",ipaddress.IPv6Address(ip).packed),
        (b"tcp6",port.to_bytes(2,"big")),
        (b"udp6",(9000).to_bytes(2,"big"))
    ]
    if key_order:
        entries=key_order
    stream=[b"\0"*64,b"\x01"]
    for key,val in entries:
        stream.extend((key,val))
    raw=rlp(stream)
    return "enr:"+base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

class R156Tests(unittest.TestCase):
    def test_real_identity_shape_pinned_to_local_ipv6_not_ipv4(self):
        result=m.make_record(ID,ADDR,ENODE,enr(),31340,m.genesis.CL_GENESIS)
        self.assertTrue(result["executionEnode"].endswith("@[fca0:2328:7777:8888::99]:30404"))
        self.assertIn("a"*128,result["executionEnode"])
        self.assertTrue(result["beaconEnr"].startswith("enr:"))

    def test_lighthouse_enr_ipv6_must_equal_actual_dynamic_address(self):
        with self.assertRaises(m.Refused):
            m.make_record(ID,ADDR,ENODE,enr("fca0:2328:7777:8888::98"),
                          31340,m.genesis.CL_GENESIS)

    def test_different_chain_or_beacon_genesis_refused(self):
        with self.assertRaises(m.Refused):
            m.make_record(ID,ADDR,ENODE,enr(),31339,m.genesis.CL_GENESIS)
        with self.assertRaises(m.Refused):
            m.make_record(ID,ADDR,ENODE,enr(),31340,"0x"+"ab"*32)

    def test_private_ipv4_or_nonoverlay_ipv6_not_published(self):
        for ip in ("::1","2001:db8::1","fd00::1"):
            with self.subTest(ip=ip),self.assertRaises(m.Refused):
                m.make_record(ID,ip,ENODE,enr(),31340,m.genesis.CL_GENESIS)

    def test_besu_enode_public_key_not_signer_material(self):
        for raw in ("enode://not-real@127.0.0.1:30303",
                    "enode://"+"g"*128+"@127.0.0.1:30303",
                    "",None):
            with self.subTest(enode=raw),self.assertRaises(m.Refused):
                m.make_record(ID,ADDR,raw,enr(),31340,m.genesis.CL_GENESIS)

    def test_bad_lighthouse_port_refused(self):
        with self.assertRaises(m.Refused):
            m.make_record(ID,ADDR,ENODE,enr(port=3000),31340,m.genesis.CL_GENESIS)

    def test_bad_enr_key_order_refused(self):
        vals=[(b"ip6",ipaddress.IPv6Address(ADDR).packed),
              (b"id",b"v4"),(b"tcp6",b"\x23\x28"),(b"udp6",b"\x23\x28")]
        with self.assertRaises(m.Refused):
            m.decode_enr(enr(key_order=vals))

    def test_invalid_rlp_or_fake_enr_rejected(self):
        for value in ("enr:"+"A"*90,"enr:"+"_"*100,
                      "enr:"+"a"*3000):
            with self.subTest(v=value[:10]),self.assertRaises(m.Refused):
                m.decode_enr(value)

    def test_capture_checks_actual_local_two_layer_genesis(self):
        calls=[]
        def fetch(url,method="GET",rpc_method=None):
            calls.append((url,method,rpc_method))
            if rpc_method=="eth_chainId":
                return "0x7a6c"
            if rpc_method=="eth_getBlockByNumber":
                return {"hash":m.genesis.EL_GENESIS}
            if rpc_method=="net_enode":
                return ENODE
            if url.endswith("/eth/v1/node/identity"):
                return {"enr":enr()}
            if url.endswith("/eth/v1/beacon/genesis"):
                return {"genesis_validators_root":m.genesis.CL_GENESIS}
            raise AssertionError(url)
        out=m.capture(ID,fetch=fetch,overlay_reader=lambda : ("ztabcdef123",ADDR))
        self.assertFalse(out["publishedToAnyExternalDiscoveryService"])
        self.assertFalse(out["nativeRemoteHandshakeProven"])
        self.assertFalse(out["localSigningKeyRead"])
        self.assertEqual(len(calls),5)

    def test_rotating_private_peer_record_is_valid_json_for_r157_and_r159(self):
        # Actual R156 local capture succeeded on VM4707, but --out was not
        # exercised by the prior command. A literal backslash-n corrupted
        # saved files and would prevent the announcer from reading them.
        from pathlib import Path
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/"public-peer.json"
            original={
                "schema":"SSE_R156_LOCAL_NODE_NATIVE_IDENTITY_V1",
                "publicPeerRecord":{"nodeId":ID},
            }
            m.write_atomic(target,original)
            self.assertEqual(json.loads(target.read_text()),original)
            self.assertEqual(target.stat().st_mode & 0o777,0o600)
            self.assertEqual(target.read_bytes()[-1:],bytes([10]))
            m.write_atomic(target,original)
            self.assertEqual(json.loads(target.read_text()),original)

    def test_full_local_capture_file_to_discovery_feed_and_announcement(self):
        # One actual read-only capture path, with simulated loopback
        # responses only; checks that all three real parsers interoperate.
        import json
        import tempfile
        from datetime import datetime, timezone
        from pathlib import Path
        import sse_pos_r157_public_peer_directory as feeds
        import sse_pos_r159_native_peer_announce as announce
        import sse_public_genesis as genesis
        def fetch(url,method="GET",rpc_method=None):
            if rpc_method=="eth_chainId":
                return hex(31340)
            if rpc_method=="eth_getBlockByNumber":
                return {"hash":genesis.EL_GENESIS}
            if rpc_method=="net_enode":
                return ENODE
            if url.endswith("/eth/v1/node/identity"):
                return {"enr":enr()}
            if url.endswith("/eth/v1/beacon/genesis"):
                return {"genesis_validators_root":genesis.CL_GENESIS}
            raise AssertionError(url)
        captured=m.capture(ID,fetch=fetch,
                           overlay_reader=lambda:("ztrb6cq527",ADDR))
        now=int(datetime.now(timezone.utc).timestamp())
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/"r156.json"
            output=Path(tmp)/"r157.json"
            m.write_atomic(source,captured)
            feed=feeds.build([feeds.load_public_record(source)],now=now)
            feeds.write_rotating(output,feed)
            self.assertEqual(len(json.loads(output.read_text())["peers"]),1)
            release={
                "schema":genesis.SCHEMA,"chainId":31340,
                "executionGenesisHash":genesis.EL_GENESIS,
                "beaconGenesisValidatorsRoot":genesis.CL_GENESIS,
                "originalGenesisArchiveSha256":genesis.ARCHIVE_SHA,
                "originalGenesisArchiveSources":[],
                "replaceablePeerDirectorySources":[],
                "currentPublicReleaseStatus":
                    "BLOCKED_UNPUBLISHED_ORIGINAL_GENESIS_AND_DISCOVERY",
                "noFixedBootstrapPeerOrIp":True,"noMemberAllowlist":True,
                "noAutomaticGenesisRecreation":True,
            }
            status=announce.announce(
                feeds.load_public_record(source),release,now=now)
            self.assertEqual(status["state"],
                             "AWAITING_REAL_PUBLIC_DIRECTORY_SOURCES")
            self.assertFalse(status["nativePeerHandshakeVerified"])

    def test_api_allowlist_disallows_remote_or_mutating_rpc(self):
        for url,method,rpc in (
            ("http://example.org:28545","POST","net_enode"),
            (m.LOOPBACK_EL,"POST","eth_sendRawTransaction"),
            (m.LOOPBACK_BN+"/eth/v1/node/identity","POST","net_enode")):
            with self.subTest(url=url),self.assertRaises(m.Refused):
                m.read_json(url,method=method,rpc_method=rpc)

if __name__=="__main__":
    unittest.main()
