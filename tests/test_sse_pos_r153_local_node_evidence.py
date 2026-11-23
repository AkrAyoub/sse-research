"""R153 pure evidence safety: no fake network or finality, no host mutation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r153_local_node_evidence as m
import sse_pos_r141_independent_fleet_audit as r141

SHA="8a983dd6f72933fb87711b760d6718b426712d9d"

class R153Tests(unittest.TestCase):
    def test_unavailable_clients_are_pending_not_fake_finality(self):
        def unavailable(*args):
            raise r141.Refused("local client not synchronized")
        outcome=m.observe("node-third-operator",collector=unavailable)
        self.assertEqual(outcome["state"],"WAITING_FOR_ACTUAL_EL_CL_FINALITY")
        self.assertIsNone(outcome["evidence"])
        self.assertFalse(outcome["permissionlessExternalP2pReachabilityVerified"])

    def test_invalid_node_identity_refused(self):
        for name in ("", "VM 7", "a", "../node", "node/owner"):
            with self.subTest(name=name),self.assertRaises(m.Refused):
                m.observe(name,collector=lambda *args:None)

    def test_mocked_valid_report_not_a_physical_independence_proof(self):
        # Build a schema-complete R141 fixture, no test code calls a host.
        report={
            "schema":r141.SCHEMA,"nodeId":"node-third-operator","chainId":31340,
            "capturedAtUtc":"2026-11-21T23:00:00+00:00",
            "executionGenesisHash":m.original_chain.EL_GENESIS,
            "beaconGenesisValidatorsRoot":m.original_chain.CL_GENESIS,
            "executionBlockNumber":50,"beaconHeadSlot":1024,
            "executionNativePeers":2,"beaconNativePeers":2,
            "finalizedEpoch":30,"finalizedRoot":"0x"+"cc"*32,
            "executionSyncing":False,"beaconSyncing":False,
            "executionOffline":False,"optimistic":False,
            "localClientApisRead":True,"validatorKeyRead":False,
            "transactionSubmitted":False,"dockerChanged":False,
            "independentOperatorVerified":False,
            "publicInternetNativeP2pVerified":False,
            "remotePhysicalResourceVerified":False,
        }
        outcome=m.observe("node-third-operator",collector=lambda *args:report)
        self.assertEqual(outcome["state"],"ACTUAL_LOCAL_CHAIN_FINALITY_VERIFIED")
        self.assertFalse(outcome["externalOperatorIndependenceVerified"])
        self.assertFalse(outcome["validatorKeyOrMarketLeaseVerified"])

    def test_wrong_original_genesis_rejected_even_with_chainid(self):
        # Validator check is made *after* schema validation. A structurally
        # valid unrelated chain with chainId 31340 cannot pass.
        from datetime import datetime, timezone
        report={
            "schema":r141.SCHEMA,"nodeId":"node-third-operator","chainId":31340,
            "capturedAtUtc":datetime.now(timezone.utc).isoformat(),
            "executionGenesisHash":"0x"+"aa"*32,
            "beaconGenesisValidatorsRoot":m.original_chain.CL_GENESIS,
            "executionBlockNumber":12,"beaconHeadSlot":96,
            "executionNativePeers":1,"beaconNativePeers":1,
            "finalizedEpoch":2,"finalizedRoot":"0x"+"cc"*32,
            "executionSyncing":False,"beaconSyncing":False,
            "executionOffline":False,"optimistic":False,
            "localClientApisRead":True,"validatorKeyRead":False,
            "transactionSubmitted":False,"dockerChanged":False,
            "independentOperatorVerified":False,
            "publicInternetNativeP2pVerified":False,
            "remotePhysicalResourceVerified":False,
        }
        outcome=m.observe("node-third-operator",collector=lambda *a:report)
        self.assertEqual(outcome["state"],"WAITING_FOR_ACTUAL_EL_CL_FINALITY")

    def test_no_native_el_or_cl_peers_does_not_count_as_joined(self):
        from datetime import datetime, timezone
        report={
            "schema":r141.SCHEMA,"nodeId":"node-third-operator","chainId":31340,
            "capturedAtUtc":datetime.now(timezone.utc).isoformat(),
            "executionGenesisHash":m.original_chain.EL_GENESIS,
            "beaconGenesisValidatorsRoot":m.original_chain.CL_GENESIS,
            "executionBlockNumber":12,"beaconHeadSlot":96,
            "executionNativePeers":0,"beaconNativePeers":1,
            "finalizedEpoch":2,"finalizedRoot":"0x"+"cc"*32,
            "executionSyncing":False,"beaconSyncing":False,
            "executionOffline":False,"optimistic":False,
            "localClientApisRead":True,"validatorKeyRead":False,
            "transactionSubmitted":False,"dockerChanged":False,
            "independentOperatorVerified":False,
            "publicInternetNativeP2pVerified":False,
            "remotePhysicalResourceVerified":False,
        }
        self.assertEqual(
            m.observe("node-third-operator",collector=lambda *a:report)["state"],
            "WAITING_FOR_ACTUAL_EL_CL_FINALITY")

    def test_bad_r141_report_does_not_fool_observer(self):
        outcome=m.observe("node-third-operator",collector=lambda *args:{
            "schema":r141.SCHEMA,"nodeId":"node-third-operator",
            "fakeFinality":True})
        self.assertEqual(outcome["state"],"WAITING_FOR_ACTUAL_EL_CL_FINALITY")

    def test_nonsecret_evidence_replacement_and_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/"evidence/latest.json"
            first=m.observe("node-third-operator",collector=lambda *a:
                            (_ for _ in ()).throw(r141.Refused("not synced")))
            m.write_atomic(target,first)
            self.assertEqual(json.loads(target.read_text())["state"],
                             "WAITING_FOR_ACTUAL_EL_CL_FINALITY")
            self.assertEqual(target.stat().st_mode & 0o777,0o600)
            m.write_atomic(target,first)
            self.assertTrue(target.is_file())

    def test_symlink_report_target_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            original=Path(temp)/"protected"
            original.write_text("secret untouched")
            link=Path(temp)/"report.json"
            link.symlink_to(original)
            with self.assertRaises(m.Refused):
                m.write_atomic(link,{"state":"fake"})
            self.assertEqual(original.read_text(),"secret untouched")

    def test_systemd_unit_is_pinned_readonly_and_no_validator(self):
        unit,timer=m.unit_contents(Path("/opt/sse/releases")/SHA,
                                    "node-third-operator")
        self.assertIn("--node-id node-third-operator",unit)
        self.assertIn("ProtectSystem=strict",unit)
        self.assertIn("OnUnitActiveSec=2min",timer)
        self.assertIn("sse_pos_r156_local_native_peer_identity.py",unit)
        self.assertIn("public-peer.json",unit)
        self.assertIn("sse_pos_r159_native_peer_announce.py",unit)
        self.assertIn("chain31340-public-release.json",unit)
        self.assertNotIn("validator",unit)
        self.assertNotIn("docker run",unit)
        self.assertNotIn("Engine",unit)

    def test_disallow_custom_or_mutable_runtime_path(self):
        for release in (Path("/tmp")/SHA,
                        Path("/opt/sse/releases/main"),
                        Path("/root")/SHA):
            with self.subTest(path=str(release)),self.assertRaises(m.Refused):
                m.unit_contents(release,"node-third-operator")

    def test_systemd_timer_requires_root_and_never_calls_automatically(self):
        commands=[]
        with patch.object(m.os,"geteuid",return_value=1000),self.assertRaises(m.Refused):
            m.install_timer(Path("/opt/sse/releases")/SHA,"node-third-operator",
                            run=lambda *a,**k:commands.append(a))
        self.assertEqual(commands,[])

if __name__=="__main__":
    unittest.main()
