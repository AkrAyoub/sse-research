"""R158 open peer hint directory: bounded, expiring, no membership authority."""
from datetime import datetime,timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r158_open_directory_service as m
import sse_pos_r157_public_peer_directory as d
import sse_public_genesis as g

NOW=1810000000

def record(name="node-existing-a",key="a",ip="fca0:2328:7777:8888::1",
           now=NOW,expiry=None):
    return {
        "schema":d.SCHEMA,
        "capturedAtUtc":datetime.fromtimestamp(now,timezone.utc).isoformat(),
        "expiresAt":now+300 if expiry is None else expiry,
        "chainId":31340,
        "executionGenesisHash":g.EL_GENESIS,
        "beaconGenesisValidatorsRoot":g.CL_GENESIS,
        "overlayInterface":"ztabcdef12",
        "actualOverlayIpv6":ip,
        "publicPeerRecord":{
            "nodeId":name,
            "executionEnode":"enode://"+key*128+"@["+ip+"]:30404",
            "beaconEnr":"enr:"+key.upper()*100,
        },
        "publishedToAnyExternalDiscoveryService":False,
        "nativeRemoteHandshakeProven":False,
        "localSigningKeyRead":False,
        "independentOperatorProven":False,
    }

class DirectoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.clock=[NOW]
        self.store=m.PeerStore(clock=lambda:self.clock[0])

    def test_first_peer_can_register_without_whitelist_or_bond(self):
        status=self.store.announce(record())
        self.assertTrue(status["accepted"])
        self.assertFalse(status["membershipOrRoleGranted"])
        snap=self.store.snapshot()
        self.assertEqual(len(snap["peers"]),1)

    def test_dynamic_address_refresh_same_node_public_key(self):
        self.store.announce(record())
        new=record(ip="fca0:2328:7777:8888::3",now=NOW+10)
        self.clock[0]=NOW+10
        self.store.announce(new)
        self.assertIn("::3",self.store.snapshot()["peers"][0]["executionEnode"])

    def test_spoofed_node_id_with_different_public_key_refused(self):
        self.store.announce(record())
        with self.assertRaises(m.Refused):
            self.store.announce(record(key="b"))

    def test_expired_record_cannot_be_served(self):
        self.store.announce(record())
        self.clock[0]=NOW+301
        with self.assertRaises(m.Refused):
            self.store.snapshot()

    def test_stale_record_refused_before_store_mutation(self):
        obj=record(expiry=NOW-1)
        with self.assertRaises(m.Refused):
            self.store.announce(obj)
        self.assertEqual(self.store.records,{})

    def test_wrong_chain_and_secret_bearing_record_refused(self):
        for field,value in (("chainId",31339),("localSigningKeyRead",True)):
            item=record()
            item[field]=value
            with self.subTest(field=field),self.assertRaises(m.Refused):
                self.store.announce(item)

    def test_bounded_capacity_not_network_membership_cap(self):
        for i in range(64):
            self.store.announce(record(name="node-%03d"%i,
                                       key=format(i+1,"x")[-1],
                                       ip="fca0:2328:7777:8888::"+format(i+1,"x")))
        self.assertEqual(len(self.store.snapshot()["peers"]),64)
        with self.assertRaises(m.Refused):
            self.store.announce(record(name="node-overflow",ip="fca0:2328:7777:8888::70"))

    def test_no_remote_rpc_or_signer_action_exposed(self):
        self.assertEqual(m.PATH,"/peers.json")
        self.assertEqual(m.MAX_BODY,8192)
        self.assertNotIn("private",str(self.store.records))

if __name__=="__main__":
    unittest.main()
