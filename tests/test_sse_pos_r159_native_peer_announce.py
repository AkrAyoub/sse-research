"""R159 announce tests: never calls external networking, funding or signing."""
from datetime import datetime,timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r159_native_peer_announce as a
import sse_pos_r157_public_peer_directory as d
import sse_public_genesis as g

NOW=1810000000

def record():
    return {
        "schema":d.SCHEMA,
        "capturedAtUtc":datetime.fromtimestamp(NOW,timezone.utc).isoformat(),
        "expiresAt":NOW+300,
        "chainId":31340,
        "executionGenesisHash":g.EL_GENESIS,
        "beaconGenesisValidatorsRoot":g.CL_GENESIS,
        "overlayInterface":"ztabcdef12",
        "actualOverlayIpv6":"fca0:2328:7777:8888::1",
        "publicPeerRecord":{
            "nodeId":"node-first-a",
            "executionEnode":"enode://"+"a"*128+"@[fca0:2328:7777:8888::1]:30404",
            "beaconEnr":"enr:"+"A"*100,
        },
        "publishedToAnyExternalDiscoveryService":False,
        "nativeRemoteHandshakeProven":False,
        "localSigningKeyRead":False,
        "independentOperatorProven":False,
    }

def manifest(urls=None):
    return {
        "schema":g.SCHEMA,"chainId":31340,
        "executionGenesisHash":g.EL_GENESIS,
        "beaconGenesisValidatorsRoot":g.CL_GENESIS,
        "originalGenesisArchiveSha256":g.ARCHIVE_SHA,
        "originalGenesisArchiveSources":[],
        "replaceablePeerDirectorySources":urls or [],
        "currentPublicReleaseStatus":"BLOCKED_UNPUBLISHED_ORIGINAL_GENESIS_AND_DISCOVERY",
        "noFixedBootstrapPeerOrIp":True,
        "noMemberAllowlist":True,
        "noAutomaticGenesisRecreation":True,
    }

class R159Tests(unittest.TestCase):
    def test_no_configured_mirrors_is_explicit_pending_not_faked(self):
        outcome=a.announce(record(),manifest(),now=NOW,
                           sender=lambda *x: (_ for _ in ()).throw(AssertionError()))
        self.assertEqual(outcome["state"],"AWAITING_REAL_PUBLIC_DIRECTORY_SOURCES")
        self.assertFalse(outcome["nativePeerHandshakeVerified"])

    def test_first_peer_mirrored_to_two_distinct_urls_without_manual_enode(self):
        urls=["https://first.example.org/peers.json",
              "https://second.example.net/peers.json"]
        sent=[]
        def ack(url,obj):
            sent.append(url)
            return {"accepted":True,"nodeId":obj["publicPeerRecord"]["nodeId"],
                    "expiresAt":obj["expiresAt"],
                    "membershipOrRoleGranted":False}
        result=a.announce(record(),manifest(urls),now=NOW,sender=ack)
        self.assertEqual(result["acknowledgedSources"],2)
        self.assertEqual(sent,urls)
        self.assertFalse(result["redundantlyPublishedByIndependentSourcesProven"])
        self.assertFalse(result["nativePeerHandshakeVerified"])

    def test_one_mirror_down_reports_partial_not_false_success(self):
        urls=["https://first.example.org/peers.json",
              "https://second.example.net/peers.json"]
        def ack(url,obj):
            if url==urls[1]:
                raise a.Refused("offline")
            return {"accepted":True,"nodeId":obj["publicPeerRecord"]["nodeId"],
                    "expiresAt":obj["expiresAt"],
                    "membershipOrRoleGranted":False}
        result=a.announce(record(),manifest(urls),now=NOW,sender=ack)
        self.assertEqual(result["acknowledgedSources"],1)
        self.assertEqual(result["state"],"PARTIAL_OR_UNAVAILABLE_PUBLIC_MIRRORS")

    def test_inconsistent_acknowledgement_not_accepted(self):
        urls=["https://one.example.org/peers.json",
              "https://two.example.net/peers.json"]
        result=a.announce(record(),manifest(urls),now=NOW,
                          sender=lambda u,x:{"accepted":True,"nodeId":"wrong",
                                              "expiresAt":x["expiresAt"],
                                              "membershipOrRoleGranted":False})
        self.assertEqual(result["acknowledgedSources"],0)

    def test_expired_local_record_refused_before_network(self):
        called=[]
        with self.assertRaises(a.Refused):
            a.announce(record(),manifest(),now=NOW+301,
                       sender=lambda *x:called.append(x))
        self.assertEqual(called,[])

    def test_wrong_chain_id_refused_before_network(self):
        item=record()
        item["chainId"]=31339
        with self.assertRaises(a.Refused):
            a.announce(item,manifest(),now=NOW)

    def test_local_or_private_untrusted_url_disallowed(self):
        for url in ("http://localhost/peers.json",
                    "https://127.0.0.1/peers.json",
                    "https://u:p@example.org/peers.json"):
            with self.subTest(url=url),self.assertRaises(a.Refused):
                a.send_https(url,record())

    def test_no_identity_or_secret_fields_added_by_publisher(self):
        result=a.announce(record(),manifest(),now=NOW)
        self.assertNotIn("validatorKey",result)
        self.assertNotIn("wallet",result)
        self.assertNotIn("privateKey",result)

if __name__=="__main__":
    unittest.main()
