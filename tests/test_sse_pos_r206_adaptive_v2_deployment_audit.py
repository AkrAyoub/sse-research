import importlib.util
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sse_r206", ROOT / "tools" / "sse_pos_r206_adaptive_v2_deployment_audit.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

MARKET = "0x" + "a" * 40
LEDGER = "0x" + "b" * 40
SENDER = "0x" + "c" * 40
TX = "0x" + "d" * 64
BLOCK = "0x" + "e" * 64
CODE_MARKET = "0x6001600055"
CODE_LEDGER = "0x6002600055"


def _digest(code):
    return hashlib.sha256(bytes.fromhex(code[2:])).hexdigest()


def _pad_address(address):
    return "0x" + "0" * 24 + address[2:]


class TestR206FinalizedV2DeploymentAudit(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "schema": "SSE_R206_ADAPTIVE_MARKET_V2_DEPLOYMENT_V1",
            "chainId": 31340,
            "executionGenesisHash": m.GENESIS,
            "deployer": SENDER,
            "deploymentTxHash": TX,
            "minimumBondWei": "1000000000000000",
            "market": {"address": MARKET, "runtimeSha256":_digest(CODE_MARKET)},
            "ledger": {"address": LEDGER, "runtimeSha256":_digest(CODE_LEDGER)}
        }
        self.wrongGenesis = False
        self.missingCode = False
        self.wrongWiring = False
        self.unfinalized = False
        self.rpcMethods = []

    def transport(self, url, method, params):
        self.assertIn(url, m.RPC_URLS)
        self.rpcMethods.append(method)
        self.assertNotIn(method, ("eth_sendTransaction", "eth_sendRawTransaction"))
        if method == "eth_chainId":
            return "0x7a6c"
        if method == "eth_getBlockByNumber":
            if params[0] == "0x0":
                return {"hash":"0x"+"f"*64 if self.wrongGenesis else m.GENESIS}
            if params[0] == "finalized":
                return {"number":"0x5" if self.unfinalized else "0x20","hash":BLOCK}
            return {"number":"0x10","hash":BLOCK}
        if method == "eth_getTransactionByHash":
            return {"hash":TX,"from":SENDER,"to":None,"chainId":"0x7a6c"}
        if method == "eth_getTransactionReceipt":
            return {"transactionHash":TX,"status":"0x1","blockNumber":"0x10",
                    "blockHash":BLOCK,"contractAddress":MARKET}
        if method == "eth_getCode":
            if self.missingCode:
                return "0x"
            return CODE_MARKET if params[0] == MARKET else CODE_LEDGER
        if method == "eth_call":
            if params[0]["to"] == MARKET and params[0]["data"] == m.selector("votes()"):
                return _pad_address(SENDER if self.wrongWiring else LEDGER)
            if params[0]["to"] == LEDGER and params[0]["data"] == m.selector("settlement()"):
                return _pad_address(MARKET)
            return hex(int(self.manifest["minimumBondWei"])).replace(
                "0x", "0x" + "0" * (64 - len(hex(int(self.manifest["minimumBondWei"]))[2:])))
        raise AssertionError(method)

    def test_verified_finalized_runtime_receipt_wiring(self):
        out = m.verify(self.manifest,m.RPC_URLS.copy().pop(),self.transport)
        self.assertTrue(out["deploymentReceiptSuccessfulAndFinalized"])
        self.assertTrue(out["runtimeCodeSha256Verified"])
        self.assertFalse(out["signedTransactionsSubmittedByThisTool"])
        self.assertFalse(out["independentPhysicalSlaVerified"])

    def test_wrong_genesis_refused(self):
        self.wrongGenesis = True
        with self.assertRaises(m.Refused):
            m.verify(self.manifest,"http://127.0.0.1:28545",self.transport)

    def test_unfinalized_deploy_refused(self):
        self.unfinalized = True
        with self.assertRaises(m.Refused):
            m.verify(self.manifest,"http://127.0.0.1:28545",self.transport)

    def test_missing_runtime_refused(self):
        self.missingCode = True
        with self.assertRaises(m.Refused):
            m.verify(self.manifest,"http://127.0.0.1:28545",self.transport)

    def test_bad_wiring_refused(self):
        self.wrongWiring = True
        with self.assertRaises(m.Refused):
            m.verify(self.manifest,"http://127.0.0.1:28545",self.transport)

    def test_manifest_disallows_extra_secret_field(self):
        self.manifest["privateKey"] = "SECRET"
        with self.assertRaises(m.Refused):
            m.validate(self.manifest)


if __name__ == "__main__":
    unittest.main()
