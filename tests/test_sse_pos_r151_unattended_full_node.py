"""R151 read-only and authorization tests; no Docker, ZT, real keys or RPC."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r151_unattended_full_node as m
import sse_pos_r137_independent_observer_create_once as r137

SHA="0acee05d348fa823046f09217078ea5e9d04307c"

def selected(roles=None):
    return {
        "schema":"SSE_R147_PUBLIC_INSTALL_V1",
        "network":"chain31340","chainGenesisRecreated":False,
        "sourceCommit":SHA,"nodeId":"node-test-operator-a",
        "selectedRoles":["full_node"] if roles is None else roles,
        "publicSourceDownloaded":True,"roleSelectionRecorded":True,
    }

def release(peer_sources=None):
    return {"replaceablePeerDirectorySources":peer_sources or []}

class R151Tests(unittest.TestCase):
    def test_full_node_observer_and_validator_selectable(self):
        for role in ("full_node","observer","validator","full_node"):
            with self.subTest(role=role):
                self.assertIn(role,m.safe_selection(selected([role]))["selectedRoles"])

    def test_application_role_only_cannot_start_a_full_node(self):
        for role in ("provider","consumer","monitor"):
            with self.subTest(role=role),self.assertRaises(m.Refused):
                m.safe_selection(selected([role]))

    def test_unsigned_unfunded_role_is_not_live_validator(self):
        self.assertEqual(m.safe_selection(selected(["validator"]))["selectedRoles"],
                         ["validator"])

    def test_plan_does_not_create_or_inspect_live_client(self):
        with tempfile.TemporaryDirectory() as temp:
            archive=Path(temp)/"real-archive-file-name"
            archive.write_bytes(b"fixture only no claim of genesis verification")
            result=m.plan(selected(),release(),archive)
            self.assertEqual(result["discoveryMode"],
                             "ZERO_PUBLISHED_BOOTSTRAPS_WAIT_FOR_DISCOVERY")
            self.assertIsNone(result["actualPreflight"])
            self.assertFalse(result["nativePeerHandshakeVerified"])
            self.assertFalse(result["finalizedCheckpointVerified"])
            self.assertFalse(result["newValidatorSignerStarted"])

    def test_real_preflight_delegation_does_not_invent_peers(self):
        called=[]
        def observe(*args,**kwargs):
            called.append((args,kwargs))
            return {"actualR137Status":"checks mocked not live"}
        with tempfile.TemporaryDirectory() as temp:
            archive=Path(temp)/"existing-public-archive"
            archive.write_bytes(b"fixture")
            result=m.plan(selected(),release(),archive,observe=observe)
            self.assertEqual(len(called),1)
            self.assertIsNone(called[0][0][2])
            self.assertIsNone(called[0][0][3])
            self.assertTrue(called[0][1]["allow_no_peers"])
            self.assertFalse(result["nativePeerHandshakeVerified"])

    def test_dynamic_multiple_bootnodes_only_from_live_feed(self):
        el=["enode://"+str(i) for i in (1,2)]
        bn=["enr:"+str(i) for i in (1,2)]
        urls=["https://a.example.org/peers","https://b.example.org/peers"]
        def lookup(observed):
            self.assertEqual(observed,urls)
            return {"executionBootnodes":el,"beaconBootnodes":bn}
        x,y,status=m.peer_hints(release(urls),lookup=lookup)
        self.assertEqual(x,",".join(el))
        self.assertEqual(y,",".join(bn))
        self.assertEqual(status,"PUBLIC_MULTISOURCE_NATIVE_HINTS")

    def test_fewer_than_two_discovered_hints_fail_closed(self):
        urls=["https://a.example.org/peers","https://b.example.org/peers"]
        with self.assertRaises(m.Refused):
            m.peer_hints(release(urls),lookup=lambda _: {
                "executionBootnodes":["one"],"beaconBootnodes":["two"]})

    def test_bad_local_role_selection_or_fake_source_refused(self):
        for change in ({"publicSourceDownloaded":False},
                       {"roleSelectionRecorded":False},
                       {"chainGenesisRecreated":True},
                       {"network":"chain31339"},{"sourceCommit":"main"},
                       {"nodeId":"bad/id"}):
            with self.subTest(change=change),self.assertRaises((m.Refused,m.r136.Refused)):
                m.safe_selection({**selected(),**change})

    def test_private_local_selection_required(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"selection.json"
            path.write_text(json.dumps(selected()))
            path.chmod(0o644)
            with self.assertRaises(m.Refused):
                m.load_selection(path)
            path.chmod(0o600)
            self.assertEqual(m.load_selection(path)["nodeId"],selected()["nodeId"])

    def test_preexisting_archive_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/"source"
            source.write_bytes(b"not real")
            target=Path(temp)/"preexisting-original"
            target.write_bytes(b"original-must-not-change")
            with patch.object(m.r59,"ARCHIVE",target),self.assertRaises(m.Refused):
                m.prepare_original_archive(source)
            self.assertEqual(target.read_bytes(),b"original-must-not-change")

    def test_r137_legacy_manual_path_default_remains_interactive(self):
        # No implicit privileged installation without selection evidence.
        import inspect
        default=inspect.signature(r137.apply).parameters["unattended"].default
        self.assertIs(default,False)

    def test_r137_refuses_unsigned_empty_bootnodes_without_explicit_option(self):
        with self.assertRaises(r137.Refused):
            r137.validate_seeds(None,None)
        self.assertTrue(r137.validate_seeds(None,None,allow_no_peers=True))

    def test_no_report_calls_native_sync_success(self):
        with tempfile.TemporaryDirectory() as temp:
            archive=Path(temp)/"fixture"
            archive.write_bytes(b"fake")
            result=m.plan(selected(),release(),archive)
            self.assertFalse(result["nativePeerHandshakeVerified"])
            self.assertFalse(result["finalizedCheckpointVerified"])

if __name__=="__main__":
    unittest.main()
