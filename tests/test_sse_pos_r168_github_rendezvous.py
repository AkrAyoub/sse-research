"""R168 provisional public GitHub issue rendezvous: no live GitHub calls."""
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r168_github_rendezvous as m
import sse_pos_r157_public_peer_directory as d
import sse_public_genesis as g

NOW=1795426000

def record(node="node-observer-a",key="a",expiry=NOW+300,now=NOW):
    return {
        "schema":d.SCHEMA,
        "capturedAtUtc":datetime.fromtimestamp(now,timezone.utc).isoformat(),
        "expiresAt":expiry,"chainId":31340,
        "executionGenesisHash":g.EL_GENESIS,
        "beaconGenesisValidatorsRoot":g.CL_GENESIS,
        "overlayInterface":"ztrb6cq527",
        "actualOverlayIpv6":"fca0:2328:7777:8888::99",
        "publicPeerRecord":{
            "nodeId":node,
            "executionEnode":"enode://"+key*128+
                              "@[fca0:2328:7777:8888::99]:30404",
            "beaconEnr":"enr:"+"A"*100,
        },
        "publishedToAnyExternalDiscoveryService":False,
        "nativeRemoteHandshakeProven":False,
        "localSigningKeyRead":False,
        "independentOperatorProven":False,
    }

def comment(obj=None,*,user="contributor",comment_id=11):
    return {"id":comment_id,"user":{"login":user},
            "body":m.MARKER+json.dumps(obj or record())}

class R168Tests(unittest.TestCase):
    def test_public_api_only_no_fixed_vm_ip(self):
        self.assertEqual(
            m.API,"https://api.github.com/repos/AkrAyoub/sse-research/"
                  "issues/42/comments?per_page=100")
        self.assertNotIn("10.50.",m.API)
        self.assertNotIn("fca0:",m.API)

    def test_first_real_peer_one_comment_is_enough_for_second(self):
        result=m.discover(getter=lambda:[comment()],now=NOW)
        self.assertEqual(result["candidateNodeCount"],1)
        self.assertEqual(result["validSourceCount"],1)
        self.assertTrue(result["temporaryCentralizedRendezvous"])
        self.assertFalse(result["independentDiscoveryInfrastructureVerified"])
        self.assertFalse(result["actualNativePeersAuthenticated"])

    def test_stale_and_unmarked_comments_are_ignored(self):
        expired=record(expiry=NOW-2)
        with self.assertRaises(m.Refused):
            m.compile_comments([
                {"body":"general GitHub discussion","user":{"login":"anyone"}},
                comment(expired)],now=NOW)

    def test_no_wallet_secret_or_wrong_genesis_is_accepted(self):
        for key,value in (
            ("validatorSigningKey","PRIVATE"),
            ("executionGenesisHash","0x"+"aa"*32),
            ("localSigningKeyRead",True),
        ):
            data=record()
            data[key]=value
            with self.subTest(key=key),self.assertRaises(m.Refused):
                m.compile_comments([comment(data)],now=NOW)

    def test_newer_same_public_key_address_can_replace_old(self):
        old=record(expiry=NOW+100)
        newer=record(expiry=NOW+350,now=NOW+20)
        result=m.compile_comments([comment(old),comment(newer,comment_id=12)],
                                  now=NOW+30)
        self.assertEqual(result["expiresAt"],NOW+350)
        self.assertEqual(len(result["peers"]),1)

    def test_native_key_conflict_is_not_resolved_by_administrator_privilege(self):
        alice=comment(record(key="a"),user="admin")
        bob=comment(record(key="b"),user="other",comment_id=15)
        with self.assertRaises(m.Refused):
            m.compile_comments([alice,bob],now=NOW)

    def test_absence_of_comments_does_not_fabricate_a_peer(self):
        with self.assertRaises(m.Refused):
            m.discover(getter=lambda:[],now=NOW)

    def test_publisher_first_post_and_ack_no_role_grant(self):
        calls=[]
        def client(args):
            calls.append(args)
            if args==["user"]:
                return {"login":"first-operator"}
            return {"id":99,"body":m.MARKER+
                    json.dumps(record(),sort_keys=True,separators=(",",":"))}
        result=m.publish(record(),now=NOW,read=lambda:[],client=client)
        self.assertEqual(calls[-1][:3],[
            "repos/AkrAyoub/sse-research/issues/42/comments","--method","POST"])
        self.assertFalse(result["refreshedExistingComment"])
        self.assertFalse(result["nativePeerHandshakeVerified"])
        self.assertFalse(result["githubAccountRequiredForJoining"])

    def test_publisher_refreshes_only_own_existing_comment(self):
        calls=[]
        previous=comment(user="first-operator",comment_id=345)
        other=comment(user="other-user",comment_id=20)
        def client(args):
            calls.append(args)
            if args==["user"]:
                return {"login":"first-operator"}
            return {"id":345,"body":m.MARKER+
                    json.dumps(record(),sort_keys=True,separators=(",",":"))}
        result=m.publish(record(),now=NOW,read=lambda:[other,previous],
                         client=client)
        self.assertEqual(calls[-1][:3],[
            "repos/AkrAyoub/sse-research/issues/comments/345",
            "--method","PATCH"])
        self.assertTrue(result["refreshedExistingComment"])

    def test_refuses_duplicate_own_records_instead_of_comment_flood(self):
        comments=[comment(user="first-operator",comment_id=n) for n in (5,6)]
        with self.assertRaises(m.Refused):
            m.publish(record(),now=NOW,read=lambda:comments,
                      client=lambda args:{"login":"first-operator"})

    def test_no_remote_secrets_or_cli_when_local_record_expired(self):
        events=[]
        with self.assertRaises(m.Refused):
            m.publish(record(expiry=NOW-1),now=NOW,
                      read=lambda:events.append("read"),
                      client=lambda _:events.append("gh"))
        self.assertEqual(events,[])

    def test_bad_public_api_source_refused_before_network(self):
        with self.assertRaises(m.Refused):
            m.fetch_public("http://127.0.0.1/evil")

    def test_partial_untrusted_records_never_count_as_finality(self):
        result=m.discover(getter=lambda:[comment()],now=NOW)
        for key in ("actualNativePeersAuthenticated","peerReachabilityVerified",
                    "publisherIdentityOrIndependenceVerified"):
            self.assertIs(result[key],False)

    def test_oversized_marked_comment_refused_not_processed(self):
        with self.assertRaises(m.Refused):
            m.marker_record(m.MARKER+"a"*10000,now=NOW)

if __name__=="__main__":
    unittest.main()
