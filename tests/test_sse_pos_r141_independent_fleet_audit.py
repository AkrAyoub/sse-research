"""R141 pure regressions: multiple nodes, no real network, keys or service control."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_pos_r141_independent_fleet_audit as m

EL = "http://127.0.0.1:18545"
BN = "http://127.0.0.1:15052"
GEN = "0x" + "12" * 32
VAL = "0x" + "34" * 32
FINAL = "0x" + "56" * 32

def fake_transport(url, method, rpc_method):
    if method == "POST":
        return {"eth_chainId": "0x7a6c",
                "eth_getBlockByNumber": {"hash": GEN},
                "eth_blockNumber": "0x240",
                "net_peerCount": "0x2", "eth_syncing": False}[rpc_method]
    if url.endswith("/eth/v1/beacon/genesis"):
        return {"genesis_validators_root": VAL}
    if url.endswith("/eth/v1/beacon/headers/head"):
        return {"header": {"message": {"slot": "6550"}}}
    if url.endswith("/eth/v1/beacon/states/head/finality_checkpoints"):
        return {"finalized": {"epoch": "200", "root": FINAL}}
    if url.endswith("/eth/v1/node/syncing"):
        return {"is_syncing": False, "is_optimistic": False,
                "el_offline": False, "sync_distance": "0", "head_slot": "6550"}
    if url.endswith("/eth/v1/node/peer_count"):
        return {"connected": "2"}
    raise AssertionError(url)

def report(n):
    return m.capture("operator-node-" + str(n), EL, BN, fake_transport)

class R141Tests(unittest.TestCase):
    def test_capture_uses_only_real_readonly_local_client_reads(self):
        obj = report(1)
        self.assertEqual(obj["chainId"], 31340)
        self.assertEqual(obj["finalizedEpoch"], 200)
        self.assertEqual(obj["finalizedRoot"], FINAL)
        self.assertFalse(obj["independentOperatorVerified"])
        self.assertFalse(obj["remotePhysicalResourceVerified"])
        self.assertFalse(obj["transactionSubmitted"])

    def test_two_thirty_two_and_large_fleet_no_architecture_quota(self):
        for n in (2, 8, 32, 65):
            with self.subTest(n=n):
                reports = [report(i) for i in range(n)]
                result = m.compare(reports)
                self.assertEqual(result["observedReportCount"], n)
                self.assertEqual(result["result"], "OBSERVED_CONSISTENT_CHECKPOINTS")
                self.assertFalse(result["independentOperatorsOrIspsVerified"])

    def test_differing_finality_epoch_not_false_fork_or_agreement(self):
        records = [report(1), report(2)]
        records[1]["finalizedEpoch"] = 199
        value = m.compare(records)
        self.assertFalse(value["sameFinalizedEpoch"])
        self.assertEqual(value["result"], "INCONCLUSIVE_OR_DIVERGENT_REQUIRES_REVIEW")

    def test_conflicting_root_and_genesis_refused_as_agreement(self):
        for field in ("finalizedRoot", "executionGenesisHash",
                      "beaconGenesisValidatorsRoot"):
            records = [report(1), report(2)]
            records[1][field] = "0x" + "bb" * 32
            with self.subTest(field=field):
                self.assertNotEqual(m.compare(records)["result"],
                                    "OBSERVED_CONSISTENT_CHECKPOINTS")

    def test_duplicate_identifiers_refused(self):
        with self.assertRaises(m.Refused):
            m.compare([report(1), report(1)])

    def test_no_native_peers_cannot_count_as_network_verification(self):
        records = [report(1), report(2)]
        records[1]["beaconNativePeers"] = 0
        self.assertFalse(m.compare(records)["allObservedNodesHaveNativeElAndClPeers"])
        self.assertNotEqual(m.compare(records)["result"],
                            "OBSERVED_CONSISTENT_CHECKPOINTS")

    def test_capture_skew_refuses_agreement_not_result_fabrication(self):
        records = [report(1), report(2)]
        now = datetime.now(timezone.utc)
        records[0]["capturedAtUtc"] = now.isoformat()
        records[1]["capturedAtUtc"] = (now - timedelta(minutes=10)).isoformat()
        self.assertNotEqual(m.compare(records)["result"],
                            "OBSERVED_CONSISTENT_CHECKPOINTS")

    def test_wrong_chain_or_sync_state_refused(self):
        def wrong_chain(url, method, rpc_method):
            if rpc_method == "eth_chainId":
                return "0x7a6b"
            return fake_transport(url, method, rpc_method)
        with self.assertRaises(m.Refused):
            m.capture("operator-node-1", EL, BN, wrong_chain)
        def optimistic(url, method, rpc_method):
            result = fake_transport(url, method, rpc_method)
            if url.endswith("/eth/v1/node/syncing"):
                return {**result, "is_optimistic": True}
            return result
        with self.assertRaises(m.Refused):
            m.capture("operator-node-1", EL, BN, optimistic)

    def test_no_remote_rpc_or_outbound_private_lan(self):
        for url in ("http://10.50.56.8:18545", "https://example.com",
                    "http://127.0.0.1:18545/path", "http://localhost:18545"):
            with self.subTest(url=url), self.assertRaises(m.Refused):
                m.local_url(url)

    def test_tampered_safety_claims_refused(self):
        for field in ("independentOperatorVerified",
                      "publicInternetNativeP2pVerified",
                      "validatorKeyRead", "transactionSubmitted", "dockerChanged"):
            obj = report(1)
            obj[field] = True
            with self.subTest(field=field), self.assertRaises(m.Refused):
                m.validate_report(obj)

    def test_no_signature_or_physical_independence_claim(self):
        result = m.compare([report(1), report(2)])
        self.assertFalse(result["operatorSignedReportsVerified"])
        self.assertFalse(result["independentOperatorsOrIspsVerified"])
        self.assertFalse(result["permissionlessExternalAdmissionVerified"])

if __name__ == "__main__":
    unittest.main()
