import unittest
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "r201", ROOT / "tools" / "sse_pos_r201_v2_readonly_live_chain_gate.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class TestR201ReadOnlyFundingGate(unittest.TestCase):
    def fake(self, url, method, params):
        self.assertEqual(url, m.RPC)
        self.assertNotIn(method, ("eth_sendRawTransaction", "eth_sendTransaction"))
        if method == "eth_chainId":
            return m.CHAIN
        if method == "eth_getBlockByNumber":
            number = params[0]
            if number == "0x0":
                return {"hash": m.GENESIS}
            return {"number": "0x41b6", "hash": "0x" + "f" * 64,
                    "gasLimit": "0x1c9c380", "baseFeePerGas": "0x7"}
        if method == "eth_getBalance":
            self.assertEqual(params, [m.FUNDED_ACCOUNT, "finalized"])
            return hex(1_000_000 * 10 ** 18)
        if method == "eth_getTransactionCount":
            self.assertEqual(params, [m.FUNDED_ACCOUNT, "finalized"])
            return "0x0"
        raise AssertionError(method)

    def test_read_only_evidence_and_no_deployment_claim(self):
        evidence = m.observe(transport=self.fake)
        self.assertEqual(evidence["chainId"], 31340)
        self.assertEqual(evidence["genesisAccountBalanceWeiAtFinalized"],
                         str(1_000_000 * 10 ** 18))
        self.assertFalse(evidence["marketV2Deployed"])
        self.assertFalse(evidence["accountPrivateKeyAccessVerified"])
        self.assertFalse(evidence["transactionSignedOrSubmittedByThisTool"])

    def test_wrong_genesis_fails_closed(self):
        def altered(url, method, params):
            if method == "eth_getBlockByNumber" and params[0] == "0x0":
                return {"hash": "0x" + "a" * 64}
            return self.fake(url, method, params)
        with self.assertRaises(m.Refused):
            m.observe(transport=altered)

    def test_wrong_chain_fails_closed(self):
        def altered(url, method, params):
            return "0x1" if method == "eth_chainId" else self.fake(url, method, params)
        with self.assertRaises(m.Refused):
            m.observe(transport=altered)

    def test_nonlocal_rpc_rejected(self):
        with self.assertRaises(m.Refused):
            m.observe("https://example.com", transport=self.fake)

    def test_invalid_balance_rejected(self):
        def altered(url, method, params):
            if method == "eth_getBalance":
                return "99999"
            return self.fake(url, method, params)
        with self.assertRaises(m.Refused):
            m.observe(transport=altered)


if __name__ == "__main__":
    unittest.main()
