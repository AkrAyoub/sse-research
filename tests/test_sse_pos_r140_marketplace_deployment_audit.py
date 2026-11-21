"""R140 pure tests: finalized 31340 deployment attestation, never transactions."""
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_pos_r140_marketplace_deployment_audit as m

GENESIS = "0x" + "ab" * 32
ADDR = {"committee": "0x" + "11" * 20, "settlement": "0x" + "22" * 20,
        "board": "0x" + "33" * 20}
CODE = {"committee": "6001600055", "settlement": "6002600055",
        "board": "6003600055"}
URL = "http://127.0.0.1:28545"

def manifest():
    return {"schema": "SSE_R140_CHAIN31340_DEPLOYMENT_V1",
            "chainId": 31340, "executionGenesisHash": GENESIS,
            "contracts": {name: {"address": ADDR[name],
                       "runtimeSha256": hashlib.sha256(bytes.fromhex(CODE[name])).hexdigest()}
                          for name in ADDR}}

def mock(url, method, params):
    if method == "eth_chainId":
        return "0x7a6c"
    if method == "eth_getBlockByNumber":
        if params[0] == "0x0":
            return {"hash": GENESIS}
        if params[0] == "finalized":
            return {"hash": "0x" + "cd" * 32, "number": "0x20"}
    if method == "eth_getCode":
        return "0x" + CODE[next(n for n in ADDR if params[0] == ADDR[n])]
    if method == "eth_call":
        binding = {"committee": "settlement", "settlement": "board",
                   "board": "settlement"}
        name = next(n for n in ADDR if params[0]["to"] == ADDR[n])
        return "0x" + "00" * 12 + ADDR[binding[name]][2:]
    raise AssertionError((method, params))

class R140Tests(unittest.TestCase):
    def test_pinned_genesis_code_and_bindings(self):
        report = m.verify(manifest(), URL, mock)
        self.assertEqual(report["finalizedExecutionHeight"], 32)
        self.assertTrue(report["mutualBindingsVerified"])
        self.assertTrue(report["runtimeCodePinnedAndVerified"])
        self.assertFalse(report["fundedLeaseExecuted"])
        self.assertFalse(report["walletsOrTransactionsUsed"])

    def test_no_known_contract_address_or_runtime_can_be_omitted(self):
        for key in ("committee", "settlement", "board"):
            obj = manifest()
            obj["contracts"][key]["runtimeSha256"] = "0" * 64
            with self.subTest(key=key), self.assertRaises(m.Refused):
                m.validate(obj)

    def test_old_chain_and_unexpected_admission_fields_refused(self):
        obj = manifest()
        obj["chainId"] = 31339
        with self.assertRaises(m.Refused):
            m.validate(obj)
        obj = manifest()
        obj["privateKey"] = "never"
        with self.assertRaises(m.Refused):
            m.validate(obj)

    def test_wrong_chain_and_wrong_genesis_refused(self):
        with self.assertRaises(m.Refused):
            m.verify(manifest(), URL, lambda url, method, params: "0x7a6b")
        def wrong_genesis(url, method, params):
            if method == "eth_getBlockByNumber" and params == ["0x0", False]:
                return {"hash": "0x" + "ee" * 32}
            return mock(url, method, params)
        with self.assertRaises(m.Refused):
            m.verify(manifest(), URL, wrong_genesis)

    def test_runtime_tampering_refused(self):
        def bad_code(url, method, params):
            if method == "eth_getCode" and params[0] == ADDR["committee"]:
                return "0x6000"
            return mock(url, method, params)
        with self.assertRaises(m.Refused):
            m.verify(manifest(), URL, bad_code)

    def test_wrong_contract_binding_refused(self):
        def wrong_wire(url, method, params):
            if method == "eth_call" and params[0]["to"] == ADDR["settlement"]:
                return "0x" + "00" * 12 + ADDR["committee"][2:]
            return mock(url, method, params)
        with self.assertRaises(m.Refused):
            m.verify(manifest(), URL, wrong_wire)

    def test_no_finalized_execution_refused(self):
        def no_finality(url, method, params):
            if method == "eth_getBlockByNumber" and params == ["finalized", False]:
                return None
            return mock(url, method, params)
        with self.assertRaises(m.Refused):
            m.verify(manifest(), URL, no_finality)

    def test_refuse_unreviewed_rpc_not_lan_or_public(self):
        with self.assertRaises(m.Refused):
            m.verify(manifest(), "http://0.0.0.0:8545", mock)

    def test_malformed_abi_response_refused(self):
        for value in ("0x", "0x" + "01" * 32, "0x" + "00" * 32):
            with self.subTest(value=value), self.assertRaises(m.Refused):
                m.decoded_address(value)

if __name__ == "__main__":
    unittest.main()
