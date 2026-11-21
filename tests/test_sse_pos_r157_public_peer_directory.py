"""R157 peer-feed builder tests. Fake hints here are parser fixtures ONLY."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime,timezone
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r157_public_peer_directory as m
import sse_pos_r142_public_peer_discovery as d

NOW=1810000000

def fixture(name="node-existing-a", now=NOW):
    return {
        "schema":m.SCHEMA,
        "capturedAtUtc":datetime.fromtimestamp(now,timezone.utc).isoformat(),
        "expiresAt":now+300,
        "chainId":31340,
        "executionGenesisHash":m.genesis.EL_GENESIS,
        "beaconGenesisValidatorsRoot":m.genesis.CL_GENESIS,
        "overlayInterface":"ztabcdef12",
        "actualOverlayIpv6":"fca0:2328:7777:8888::1",
        "publicPeerRecord":{
            "nodeId":name,
            "executionEnode":"enode://"+"a"*128+"@[fca0:2328:7777:8888::1]:30404",
            "beaconEnr":"enr:"+"A"*100,
        },
        "publishedToAnyExternalDiscoveryService":False,
        "nativeRemoteHandshakeProven":False,
        "localSigningKeyRead":False,
        "independentOperatorProven":False,
    }

class R157Tests(unittest.TestCase):
    def test_first_node_record_produces_single_peer_directory(self):
        result=m.build([fixture()],now=NOW)
        self.assertEqual(len(result["peers"]),1)
        self.assertEqual(result["expiresAt"],NOW+300)
        self.assertEqual(result["chainId"],31340)
        self.assertEqual(len(d.parse(json.dumps(result).encode(),NOW)),1)

    def test_second_node_discovers_only_first_peer_using_two_mirrors(self):
        report=m.build([fixture()],now=NOW)
        urls=["https://independent-one.example.org/peers.json",
              "https://independent-two.example.net/peers.json"]
        found=d.discover(urls,lambda _:json.dumps(report).encode(),NOW)
        self.assertEqual(found["candidateNodeCount"],1)
        self.assertEqual(found["validSourceCount"],2)

    def test_multiple_real_records_require_unique_node_id(self):
        a=fixture()
        b=fixture(name="node-existing-b")
        b["publicPeerRecord"]["executionEnode"]="enode://"+"b"*128+"@[fca0:2328:7777:8888::2]:30404"
        b["actualOverlayIpv6"]="fca0:2328:7777:8888::2"
        b["publicPeerRecord"]["beaconEnr"]="enr:"+"B"*100
        result=m.build([b,a],now=NOW)
        self.assertEqual(len(result["peers"]),2)
        self.assertEqual(result["peers"][0]["nodeId"],"node-existing-a")

    def test_expired_first_online_peer_cannot_be_published(self):
        item=fixture()
        item["expiresAt"]=NOW-1
        with self.assertRaises(m.Refused):
            m.build([item],now=NOW)

    def test_wrong_original_execution_or_beacon_genesis_refused(self):
        for field in ("executionGenesisHash","beaconGenesisValidatorsRoot","chainId"):
            item=fixture()
            item[field]="bad"
            with self.subTest(field=field),self.assertRaises(m.Refused):
                m.build([item],now=NOW)

    def test_claim_of_actual_remote_reachability_or_secret_read_refused(self):
        for field in ("nativeRemoteHandshakeProven",
                      "localSigningKeyRead","independentOperatorProven"):
            item=fixture()
            item[field]=True
            with self.subTest(field=field),self.assertRaises(m.Refused):
                m.build([item],now=NOW)

    def test_equivocating_same_identity_refused(self):
        a=fixture()
        b=fixture()
        b["publicPeerRecord"]["beaconEnr"]="enr:"+"B"*100
        with self.assertRaises(m.Refused):
            m.build([a,b],now=NOW)

    def test_missing_or_unknown_signing_fields_refused(self):
        for change in ({"walletPrivateKey":"secret"},
                       {"schema":"unknown"}):
            obj={**fixture(),**change}
            with self.assertRaises(m.Refused):
                m.build([obj],now=NOW)

    def test_incorrect_enode_or_ipv4_lan_address_refused(self):
        item=fixture()
        item["publicPeerRecord"]["executionEnode"]="enode://"+"a"*128+"@10.50.56.8:30404"
        with self.assertRaises(m.Refused):
            m.build([item],now=NOW)

    def test_public_file_is_create_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"public/peers.json"
            report=m.build([fixture()],now=NOW)
            m.write_new(path,report)
            self.assertTrue(path.is_file())
            with self.assertRaises(m.Refused):
                m.write_new(path,report)

    def test_public_file_duplicate_json_fields_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"record.json"
            path.write_text('{"schema":"x","schema":"y"}')
            with self.assertRaises(m.Refused):
                m.load_public_record(path)

    def test_source_list_not_a_validator_or_membership_allowlist(self):
        report=m.build([fixture()],now=NOW)
        self.assertEqual(set(report),d.FIELDS)
        self.assertNotIn("allowedWallets",report)
        self.assertNotIn("authorizedValidators",report)

if __name__=="__main__":
    unittest.main()
