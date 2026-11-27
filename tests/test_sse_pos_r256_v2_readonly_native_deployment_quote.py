"""R256 live deployment quoting policy: synthetic JSON-RPC only, no network."""
import sys
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_pos_r256_v2_readonly_native_deployment_quote as x


def compiled():
    return (
        {
            "abi": [{"type":"constructor",
                     "inputs":[{"name":"bondWei","type":"uint256"}],
                     "stateMutability":"nonpayable"}],
            "bytecode": {"object": "0x"+"ab"*x.EXPECTED_MARKET_INITCODE_BYTES},
            "deployedBytecode": {"object": "0x"+"cd"*x.EXPECTED_MARKET_RUNTIME_BYTES},
        },
        {"abi": [], "deployedBytecode":
            {"object": "0x"+"ef"*x.EXPECTED_LEDGER_RUNTIME_BYTES}},
    )


def checked_report():
    return {"market":{"compiledAbiSha256":x.EXPECTED_MARKET_ABI},
            "ledger":{"compiledAbiSha256":x.EXPECTED_LEDGER_ABI}}


def rpc_with(**changes):
    state = {
        "chain":"0x7a6c", "genesis":x.GENESIS,
        "head":"0x6200", "final":"0x61f0",
        "blockgas":hex(30_000_000),
        "latest_balance":hex(10**18),
        "final_balance":"0x0", "app_code":"0x",
        "price":"0x3e8", "estimate":hex(5_000_000),
    }
    state.update(changes)
    calls = []

    def transport(url, method, params):
        if url != x.RPC:
            raise AssertionError("unexpected RPC URL")
        calls.append(method)
        if method == "eth_chainId":
            return state["chain"]
        if method == "eth_getBlockByNumber":
            if params[0] == "0x0":
                return {"hash":state["genesis"]}
            if params[0] == "latest":
                return {"number":state["head"],"gasLimit":state["blockgas"],
                        "baseFeePerGas":"0x7"}
            if params[0] == "finalized":
                return {"number":state["final"],"hash":"0x"+"12"*32}
        if method == "eth_getBalance":
            return state["latest_balance"] if params[1]=="latest" else state["final_balance"]
        if method == "eth_getCode":
            return state["app_code"]
        if method == "eth_gasPrice":
            return state["price"]
        if method == "eth_estimateGas":
            tx=params[0]
            if (set(tx)!={"from","data","value"} or
                tx["from"]!=x.APP or tx["value"]!="0x0" or
                not tx["data"].startswith("0x"+"ab"*32) or
                tx["data"][-64:]!=f"{10**15:064x}"):
                raise AssertionError("wrong exact constructor estimation")
            return state["estimate"]
        raise AssertionError("unexpected RPC method "+method)

    return transport,calls


class TestR256ExactCompiledNativeCreationEstimate(TestCase):
    def test_positive_bond_encodes_one_exact_solidity_uint256_constructor_arg(self):
        m,l=compiled()
        with patch.object(x,"audit_abi",return_value=checked_report()):
            actual=x.pin_artifacts(m,l,10**15)
        self.assertEqual(len(actual[2:])//2,x.EXPECTED_MARKET_INITCODE_BYTES+32)
        self.assertEqual(actual[-64:],f"{10**15:064x}")

    def test_estimate_from_actual_chain_scenario_not_permission(self):
        m,l=compiled()
        transport,calls=rpc_with()
        with patch.object(x,"audit_abi",return_value=checked_report()):
            result=x.quote(x.RPC,m,l,10**15,transport=transport)
        self.assertEqual(result["actualNodeEstimatedConstructorGas"],5_000_000)
        self.assertEqual(result["actualNodeGasPriceWei"],"1000")
        self.assertTrue(result["estimatedPaddedFeeCoveredByCurrentLatestBalance"])
        self.assertFalse(result["estimatedPaddedFeeCoveredByFinalizedBalance"])
        self.assertFalse(result["immutableMonitorBondPolicyChosenOrApproved"])
        self.assertTrue(result["quoteOnlyNoPrivateKeysNoTransactionNoDeployment"])
        self.assertIn("eth_estimateGas",calls)
        self.assertNotIn("eth_sendRawTransaction",calls)

    def test_refuse_wrong_chain_genesis_and_read_only_wallet_changed(self):
        m,l=compiled()
        for change in ({"chain":"0x1"}, {"genesis":"0x"+"11"*32},
                       {"app_code":"0x60"}, {"blockgas":"0x0"},
                       {"final":"0x6201"}, {"price":"0x0"}):
            with self.subTest(change=change), patch.object(x,"audit_abi",return_value=checked_report()):
                transport,_=rpc_with(**change)
                with self.assertRaises(x.Refused):
                    x.quote(x.RPC,m,l,10**15,transport=transport)

    def test_refuse_legacy_or_modified_constructor_or_bytecode_or_abi(self):
        m,l=compiled()
        with patch.object(x,"audit_abi",return_value=checked_report()):
            for bond in (0, -1, 2**256, "10000", True):
                with self.subTest(bond=bond), self.assertRaises(x.Refused):
                    x.pin_artifacts(m,l,bond)
            m2={**m,"bytecode":{"object":"0x"+"ab"*12345}}
            with self.assertRaises(x.Refused):
                x.pin_artifacts(m2,l,10**15)
            m2={**m,"abi":[]}
            with self.assertRaises(x.Refused):
                x.pin_artifacts(m2,l,10**15)
        with patch.object(x,"audit_abi",return_value={
            "market":{"compiledAbiSha256":"wrong"},
            "ledger":{"compiledAbiSha256":x.EXPECTED_LEDGER_ABI}}):
            with self.assertRaises(x.Refused):
                x.pin_artifacts(m,l,10**15)

    def test_refuse_gas_estimate_above_block_cap(self):
        m,l=compiled()
        transport,_=rpc_with(estimate=hex(30_000_001))
        with patch.object(x,"audit_abi",return_value=checked_report()):
            with self.assertRaises(x.Refused):
                x.quote(x.RPC,m,l,10**15,transport=transport)

    def test_refuse_wrong_rpc_endpoint_even_with_local_compiled_artifacts(self):
        m,l=compiled()
        with patch.object(x,"audit_abi",return_value=checked_report()):
            with self.assertRaises(x.Refused):
                x.quote("https://public-rpc.invalid",m,l,10**15)


if __name__=="__main__":
    main()
