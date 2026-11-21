"""R69 read-only VM4707 live peer/status audit unit regressions; fake sources ONLY."""
from __future__ import annotations
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r69_vm4707_real_two_layer_peer_health as m

class R69ReadOnlyObserverTests(unittest.TestCase):
    def test_only_explicit_localhost_endpoints_allowed(self):
        for url,method in [
            ("http://10.50.56.8:28545/","POST"),
            ("http://127.0.0.1:28545/","GET"),
            ("http://127.0.0.1:25052/eth/v1/node/identity","GET"),
            ("http://127.0.0.1:25052/eth/v1/node/peer_count","POST"),
            ("http://127.0.0.1:25052/eth/v1/node/peer_count","PUT")
        ]:
            with self.subTest(url=url,method=method),self.assertRaises(m.R69Refused):
                m.get_local_json(url,method)

    def test_rpc_mutations_refused_without_network_call(self):
        with self.assertRaises(m.R69Refused):
            m.rpc("eth_sendRawTransaction")
        with self.assertRaises(m.R69Refused):
            m.rpc("admin_addPeer")

    def test_no_unreviewed_docker_container_ever_inspected(self):
        with self.assertRaises(m.R69Refused):
            m.docker_state("sse31340-g2-vc")

    def test_true_mock_local_peer_and_finality_values_distinguished_from_source(self):
        ip="fca0:2328:77b8:6578:a55::1"
        values={"eth_chainId":"0x7a6c","eth_blockNumber":"0x1234",
                "net_peerCount":"0x1","eth_syncing":False}
        beacon={
            "/eth/v1/beacon/genesis":{"genesis_time":"1"},
            "/eth/v1/node/peer_count":{"connected":"1"},
            "/eth/v1/node/syncing":{"is_syncing":False},
            "/eth/v1/beacon/headers/head":{"header":{"message":{"slot":"4096"}}},
            "/eth/v1/beacon/states/head/finality_checkpoints":{
                "finalized":{"epoch":"122","root":m.r68.SOURCE_OBSERVED_FINALIZED_ROOT}}
        }
        with patch.object(m.r59,"overlay_ip",return_value=("ztmock",ip)),patch.object(
            m,"docker_state",return_value={"running":True,"exitCode":0,
                                            "oomKilled":False,"restarting":False}),patch.object(
            m,"rpc",side_effect=lambda key:values[key]),patch.object(
            m,"beacon",side_effect=lambda path:beacon[path]):
            report=m.observed()
        self.assertTrue(report["bothClientsRunning"])
        self.assertTrue(report["bothNativePeerCountsPositive"])
        self.assertTrue(report["beacon"]["epoch122SameCheckpointIfAtEpoch122"])
        self.assertEqual(report["execution"]["nativePeerCount"],1)
        self.assertTrue(report["noDockerOrBlockchainMutations"])

    def test_unhealthy_initial_clients_report_unavailable_not_fake_sync(self):
        with patch.object(m.r59,"overlay_ip",return_value=("ztmock","fca0:2328:77b8:6578:a55::1")),patch.object(
             m,"docker_state",return_value={"running":False,"exitCode":1,
                                            "oomKilled":False,"restarting":False}),patch.object(
             m,"rpc",side_effect=m.R69Refused("not ready")),patch.object(
             m,"beacon",side_effect=m.R69Refused("not ready")):
            result=m.observed()
        self.assertFalse(result["bothClientsRunning"])
        self.assertFalse(result["bothNativePeerCountsPositive"])
        self.assertEqual(result["execution"]["apiStatus"],"unavailable_or_unexpected_schema")
        self.assertEqual(result["beacon"]["apiStatus"],"unavailable_or_unexpected_schema")

    def test_readonly_source_has_no_docker_mutation_or_privileged_rpc(self):
        source=(ROOT/"tools/sse_pos_r69_vm4707_real_two_layer_peer_health.py").read_text()
        for term in ('"run","-d"','"docker","start"','"docker","stop"',
                     '"docker","network","create"','"eth_sendRawTransaction"',
                     '"admin_addPeer"','"validator","create"','"wallet"','"engine.jwt"'):
            self.assertNotIn(term,source)
        self.assertIn('"noDockerOrBlockchainMutations":True',source)
        self.assertIn('"realIndependentSameEpochFinalizedRootAgreementStillNeedsOwnerComparison":True',source)

if __name__=="__main__":
    unittest.main()
