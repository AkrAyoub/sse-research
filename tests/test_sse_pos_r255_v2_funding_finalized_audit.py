"""R255 exact native-chain one-transaction finality audit; mocked RPC only."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_pos_r255_v2_funding_finalized_audit as a

INCLUDED=24901
FINALIZED=24903
BH="0x" + "ab"*32
F_H="0x" + "cd"*32


def fixture():
    tx = {
        "hash": a.TX_HASH, "from": a.SOURCE, "to": a.DESTINATION,
        "value": hex(a.VALUE_WEI), "gas": hex(a.GAS_LIMIT),
        "gasPrice": hex(a.GAS_PRICE_CAP_WEI), "nonce": "0x0",
        "chainId": hex(a.CHAIN), "type": "0x0", "input": "0x",
        "blockHash": BH,
    }
    receipt = {
        "transactionHash": a.TX_HASH, "status": "0x1",
        "from": a.SOURCE, "to": a.DESTINATION,
        "contractAddress": None, "gasUsed": hex(a.GAS_LIMIT),
        "effectiveGasPrice": hex(a.GAS_PRICE_CAP_WEI),
        "blockNumber": hex(INCLUDED), "blockHash": BH,
    }
    return {
        ("eth_chainId", ()): hex(a.CHAIN),
        ("eth_getBlockByNumber", ("0x0", False)): {"hash": a.GENESIS},
        ("eth_getBlockByNumber", (hex(INCLUDED), False)): {"hash": BH},
        ("eth_getBlockByNumber", ("finalized", False)): {
            "number": hex(FINALIZED), "hash": F_H,
        },
        ("eth_getTransactionByHash", (a.TX_HASH,)): tx,
        ("eth_getTransactionReceipt", (a.TX_HASH,)): receipt,
        ("eth_getBalance", (a.DESTINATION, hex(FINALIZED))): hex(a.VALUE_WEI),
        ("eth_getTransactionCount", (a.SOURCE, hex(FINALIZED))): "0x1",
    }


def mocked(data):
    def transport(url, method, params):
        if url != a.RPC_CHOICES[0]:
            raise AssertionError("unexpected RPC endpoint")
        key=(method, tuple(params))
        if key not in data:
            raise AssertionError("unexpected RPC call: "+repr(key))
        return data[key]
    return transport


class TestR255NativeFundingFinalizedAudit(unittest.TestCase):
    def verify(self, data):
        return a.verify(a.RPC_CHOICES[0], transport=mocked(data))

    def test_exact_owner_approved_funded_finalized_transaction(self):
        out=self.verify(fixture())
        self.assertTrue(out["fundingTxCanonicalAndFinalizedVerified"])
        self.assertTrue(out["originalGenesisVerified"])
        self.assertEqual(out["exactValueWei"], str(10**18))
        self.assertEqual(out["totalActualCostWei"], "1000000000021000000")
        self.assertEqual(out["sourceNonceAtFinalized"], 1)
        self.assertFalse(out["newV2ContractsDeployedOrVerified"])
        self.assertFalse(out["privateKeysReadOrTransactionsSentByAudit"])

    def test_chain_and_genesis_mismatch_fail_closed(self):
        d=fixture()
        d[("eth_chainId", ())]="0x1"
        with self.assertRaises(a.Refused):
            self.verify(d)
        d=fixture()
        d[("eth_getBlockByNumber", ("0x0", False))]={"hash":"0x"+"99"*32}
        with self.assertRaises(a.Refused):
            self.verify(d)

    def test_mempool_unseen_and_included_unfinalized_never_claim_finality(self):
        d=fixture()
        d[("eth_getTransactionByHash", (a.TX_HASH,))]=None
        with self.assertRaises(a.Pending) as ctx:
            self.verify(d)
        self.assertIn("DO_NOT_RESEND",ctx.exception.stage)
        d=fixture()
        d[("eth_getTransactionReceipt", (a.TX_HASH,))]=None
        with self.assertRaises(a.Pending):
            self.verify(d)
        d=fixture()
        d[("eth_getBlockByNumber", ("finalized", False))]={
            "number": hex(INCLUDED-1), "hash": F_H}
        with self.assertRaises(a.Pending):
            self.verify(d)

    def test_wrong_sender_recipient_value_nonce_or_calldata_rejected(self):
        for field,value in (
            ("from", "0x"+"11"*20),("to", "0x"+"22"*20),
            ("value",hex(a.VALUE_WEI+1)),("nonce","0x1"),
            ("input","0x1234"),("gas",hex(a.GAS_LIMIT+1)),
            ("gasPrice","0x3e9"),("type","0x2"),("chainId","0x1"),
        ):
            d=fixture()
            d[("eth_getTransactionByHash", (a.TX_HASH,))][field]=value
            with self.subTest(field=field), self.assertRaises(a.Refused):
                self.verify(d)

    def test_failed_receipt_or_overpriced_actual_gas_rejected(self):
        for field,value in (
            ("status","0x0"),("gasUsed",hex(a.GAS_LIMIT+1)),
            ("effectiveGasPrice","0x3e9"),
            ("from","0x"+"33"*20),
            ("to","0x"+"44"*20),
            ("contractAddress","0x"+"55"*20),
        ):
            d=fixture()
            d[("eth_getTransactionReceipt", (a.TX_HASH,))][field]=value
            with self.subTest(field=field), self.assertRaises(a.Refused):
                self.verify(d)

    def test_forged_noncanonical_receipt_rejected(self):
        d=fixture()
        d[("eth_getBlockByNumber", (hex(INCLUDED), False))]={"hash":"0x"+"11"*32}
        with self.assertRaises(a.Refused):
            self.verify(d)
        d=fixture()
        d[("eth_getTransactionByHash", (a.TX_HASH,))]["blockHash"]="0x"+"22"*32
        with self.assertRaises(a.Refused):
            self.verify(d)

    def test_finalized_balance_and_sender_nonce_required(self):
        d=fixture()
        d[("eth_getBalance", (a.DESTINATION, hex(FINALIZED)))]=hex(a.VALUE_WEI-1)
        with self.assertRaises(a.Refused):
            self.verify(d)
        d=fixture()
        d[("eth_getTransactionCount", (a.SOURCE, hex(FINALIZED)))]="0x0"
        with self.assertRaises(a.Refused):
            self.verify(d)

    def test_refuse_any_external_rpc_and_malformed_quantities(self):
        with self.assertRaises(a.Refused):
            a.verify("https://example.com")
        with self.assertRaises(a.Refused):
            a.quantity("21000","gas")
        with self.assertRaises(a.Refused):
            a.quantity("0xgg","gas")


if __name__=="__main__":
    unittest.main()
