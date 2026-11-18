"""Simulated multi-node RPC responses, rejecting mismatched genesis and forks."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sse_qbft_readiness import inspect_many, safe_rpc, QBFTReadinessError, rpc

GENESIS = "0x" + "11" * 32
COMMON = "0x" + "22" * 32
RPCS = [f"http://127.0.0.1:{18545+i}" for i in range(4)]
VALIDATORS = ["0x" + f"{i:02x}" * 20 for i in range(1, 5)]


def fake(url, method, params):
    if method == "eth_chainId": return "0x7a6a"
    if method == "eth_blockNumber": return "0xa"
    if method == "net_peerCount": return "0x3"
    if method == "qbft_getValidatorsByBlockNumber": return VALIDATORS
    if method == "eth_getBlockByNumber":
        if params[0] == "0x0": return {"hash": GENESIS}
        if params[0] == "0xa": return {"hash": COMMON}
    raise AssertionError("unexpected RPC call")


class ReadinessTests(unittest.TestCase):
    def test_four_nodes_agree(self):
        result = inspect_many(RPCS, chain_id=31338,
                              genesis_hash=GENESIS,
                              expected_validators=4, require_four=True, call=fake)
        self.assertEqual(result["rpcNodes"], 4)
        self.assertEqual(result["commonBlockNumber"], 10)
        self.assertFalse(result["transactionsSent"])
        self.assertFalse(result["provedPhysicalIndependence"])

    def test_disallow_remote_unencrypted_rpc(self):
        for bad in ("http://10.50.56.14:8545", "http://public.example.org",
                    "https://me:password@rpc.example.org", "https://rpc.example.org?q=a"):
            with self.assertRaises(QBFTReadinessError):
                safe_rpc(bad)

    def test_bad_chain_fails_closed(self):
        def changed(url, method, params):
            if method == "eth_chainId" and url == RPCS[2]: return "0x7a69"
            return fake(url, method, params)
        with self.assertRaises(QBFTReadinessError):
            inspect_many(RPCS, chain_id=31338, genesis_hash=GENESIS,
                         expected_validators=4, require_four=True, call=changed)

    def test_fork_at_common_height_fails(self):
        def fork(url, method, params):
            if (url == RPCS[3] and method == "eth_getBlockByNumber"
                    and params[0] == "0xa"):
                return {"hash": "0x" + "ff" * 32}
            return fake(url, method, params)
        with self.assertRaises(QBFTReadinessError):
            inspect_many(RPCS, chain_id=31338, genesis_hash=GENESIS,
                         expected_validators=4, call=fork)

    def test_insufficient_peering_fails_strict(self):
        def isolated(url, method, params):
            if url == RPCS[1] and method == "net_peerCount": return "0x1"
            return fake(url, method, params)
        with self.assertRaises(QBFTReadinessError):
            inspect_many(RPCS, chain_id=31338, genesis_hash=GENESIS,
                         expected_validators=4, require_four=True, call=isolated)

    def test_mutating_rpc_never_allowed(self):
        with self.assertRaises(QBFTReadinessError):
            rpc(RPCS[0], "eth_sendTransaction", [{}])


if __name__ == "__main__":
    unittest.main()
