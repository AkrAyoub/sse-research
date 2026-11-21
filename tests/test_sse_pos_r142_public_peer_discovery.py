"""R142 pure public discovery and multi-peer installer tests, no Internet or Docker."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_pos_r142_public_peer_discovery as d
import sse_pos_r137_independent_observer_create_once as r137

NOW = 1800000000
SOURCES = ["https://mirror-one.example.org/peers.json",
           "https://mirror-two.example.net/peers.json",
           "https://mirror-three.example.com/peers.json"]

def peer(i):
    return {
        "nodeId": f"peer-{i}",
        "executionEnode": "enode://" + f"{i:0128x}" + "@[fca0:2328:7777:8888::" + str(i) + "]:30404",
        "beaconEnr": "enr:" + chr(65 + i) * 100,
    }

def directory(peers=None):
    return {
        "schema": d.SCHEMA, "chainId": 31340,
        "executionGenesisHash": d.EL_GENESIS,
        "beaconGenesisValidatorsRoot": d.BEACON_GENESIS,
        "networkId": d.NETWORK, "expiresAt": NOW + 1200,
        "peers": peers if peers is not None else [peer(1), peer(2)],
    }

def body(obj):
    return json.dumps(obj).encode()

class R142Tests(unittest.TestCase):
    def test_two_mirrors_return_multiple_dynamic_discovery_hints(self):
        result = d.discover(SOURCES[:2], lambda _: body(directory()), NOW)
        self.assertEqual(result["candidateNodeCount"], 2)
        self.assertEqual(result["validSourceCount"], 2)
        self.assertEqual(len(result["executionBootnodes"]), 2)
        self.assertFalse(result["actualNativePeersAuthenticated"])
        self.assertFalse(result["fullZeroTouchHostInstallationImplemented"])

    def test_wrong_genesis_or_beacon_root_refused(self):
        for field in ("executionGenesisHash", "beaconGenesisValidatorsRoot",
                      "networkId", "chainId"):
            obj = directory()
            obj[field] = "wrong"
            with self.subTest(field=field), self.assertRaises(d.Refused):
                d.parse(body(obj), NOW)

    def test_expiry_replay_refused(self):
        for expires in (NOW, NOW - 1, NOW + 86401, "bad"):
            obj = directory()
            obj["expiresAt"] = expires
            with self.subTest(expires=expires), self.assertRaises(d.Refused):
                d.parse(body(obj), NOW)

    def test_duplicate_json_keys_and_unknown_fields_refused(self):
        obj = directory()
        obj["ownerPrivateKey"] = "never"
        with self.assertRaises(d.Refused):
            d.parse(body(obj), NOW)
        bad = body(directory()).replace(b'"chainId": 31340',
                                         b'"chainId": 31340, "chainId": 31340')
        with self.assertRaises(d.Refused):
            d.parse(bad, NOW)

    def test_duplicate_peer_node_and_bad_enode_rejected(self):
        with self.assertRaises(d.Refused):
            d.parse(body(directory([peer(1), peer(1)])), NOW)
        obj = directory()
        obj["peers"][0]["executionEnode"] = "enode://wrong@10.0.0.1:30303"
        with self.assertRaises(d.Refused):
            d.parse(body(obj), NOW)

    def test_one_unavailable_mirror_with_two_good_mirrors(self):
        def get(url):
            if url == SOURCES[0]:
                raise d.Refused("mirror offline")
            return body(directory())
        result = d.discover(SOURCES, get, NOW)
        self.assertEqual(result["validSourceCount"], 2)

    def test_fail_closed_if_only_one_live_feed(self):
        with self.assertRaises(d.Refused):
            d.discover(SOURCES[:2], lambda url: (
                body(directory()) if url == SOURCES[0] else b'{}'), NOW)

    def test_conflicting_same_node_hint_not_silently_trusted(self):
        first = directory([peer(1), peer(2)])
        second = directory([peer(1), peer(2)])
        second["peers"][0]["beaconEnr"] = "enr:" + "Z" * 100
        with self.assertRaises(d.Refused):
            d.discover(SOURCES[:2], lambda url: body(
                first if url == SOURCES[0] else second), NOW)

    def test_no_local_network_urls_or_credentials(self):
        for url in ("http://public.example.org/peers",
                    "https://127.0.0.1/peers", "https://localhost/peers",
                    "https://u:p@public.example.org/peers",
                    "https://public.example.org/peers#fragment"):
            with self.subTest(url=url), self.assertRaises(d.Refused):
                d.check_source(url)

    def test_r137_multiple_bootnodes_supported_without_fixed_peer(self):
        entries = [peer(1), peer(2)]
        self.assertTrue(r137.validate_seeds(
            ",".join(p["executionEnode"] for p in entries),
            ",".join(p["beaconEnr"] for p in entries)))
        with self.assertRaises((r137.Refused, r137.r59.R59Refused)):
            r137.validate_seeds(
                ",".join(p["executionEnode"] for p in entries),
                entries[0]["beaconEnr"])

    def test_r137_directory_plan_has_no_mutation(self):
        results = d.discover(SOURCES[:2], lambda _: body(directory()), NOW)
        plan = {"manifest": {"nodeId": "new-peer"},
                "ip": "fca0:2328:7777:8888::3",
                "resources": r137.names("new-peer"),
                "root": Path("/tmp/new-peer")}
        with patch.object(r137.r142, "discover", return_value=results), \
             patch.object(r137, "preflight", return_value=plan) as preflight, \
             patch.object(r137, "apply") as apply:
            with patch("builtins.print"):
                rc = r137.main(["--plan", "--manifest", "/tmp/unused.json",
                     "--archive", "/tmp/archive",
                     "--discovery-source", SOURCES[0],
                     "--discovery-source", SOURCES[1]])
        self.assertEqual(rc, 0)
        apply.assert_not_called()
        self.assertEqual(len(preflight.call_args.args[2].split(",")), 2)

if __name__ == "__main__":
    unittest.main()
