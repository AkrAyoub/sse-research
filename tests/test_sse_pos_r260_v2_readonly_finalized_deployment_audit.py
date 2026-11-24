"""R260 exact live V2 creation evidence verifier; mocks ONLY, never sends."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r260_v2_readonly_finalized_deployment_audit as m


def fixtures():
    ledger="0x"+"bb"*20
    def artifact(length,offsets):
        raw=bytearray(b"\x60"*length)
        refs={str(i):[{"start":start,"length":32}]
              for i,start in enumerate(offsets)}
        return {"deployedBytecode":{"object":"0x"+raw.hex(),
                                    "immutableReferences":refs}}
    market=artifact(m.EXPECTED_MARKET_RUNTIME_BYTES,[100,200])
    ledger_art=artifact(m.EXPECTED_LEDGER_RUNTIME_BYTES,[100])
    market_actual=bytearray(b"\x60"*m.EXPECTED_MARKET_RUNTIME_BYTES)
    ledger_actual=bytearray(b"\x60"*m.EXPECTED_LEDGER_RUNTIME_BYTES)
    market_actual[100:132]=int(ledger,16).to_bytes(32,"big")
    market_actual[200:232]=m.BOND_WEI.to_bytes(32,"big")
    ledger_actual[100:132]=int(m.APPROVED_MARKET_ADDRESS,16).to_bytes(32,"big")
    return market,ledger_art,"0x"+market_actual.hex(),"0x"+ledger_actual.hex(),ledger


def fake_api(*,finalized=True,tx=True,receipt=True,status="0x1",
             wrong_input=False,gas_used=6_670_081):
    market,ledger_art,market_hex,ledger_hex,ledger=fixtures()
    INCLUDED=25100
    FINAL=25110 if finalized else 25050
    B_HASH="0x"+"1a"*32
    tx_obj={
        "hash":m.TX_HASH,"from":m.APP,"to":None,"nonce":"0x0",
        "value":"0x0","gas":hex(m.GAS_LIMIT),"gasPrice":hex(m.GAS_PRICE_WEI),
        "input":"0xaabb" if not wrong_input else "0xaabc",
        "chainId":hex(m.CHAIN),"type":"0x0","blockHash":B_HASH,
    }
    receipt_obj={
        "transactionHash":m.TX_HASH,"from":m.APP,"to":None,
        "contractAddress":m.APPROVED_MARKET_ADDRESS,"status":status,
        "gasUsed":hex(gas_used),"effectiveGasPrice":hex(m.GAS_PRICE_WEI),
        "blockNumber":hex(INCLUDED),"blockHash":B_HASH,
    }
    calls=[]
    def transport(rpc,method,params):
        if rpc!=m.RPC:
            raise AssertionError("unexpected remote endpoint")
        if method in ("eth_sendTransaction","eth_sendRawTransaction"):
            raise AssertionError("NO BROADCAST EVER ALLOWED")
        calls.append((method,params))
        if method=="eth_chainId":return hex(m.CHAIN)
        if method=="eth_getBlockByNumber":
            if params[0]=="0x0":return {"hash":m.GENESIS}
            if params[0]==hex(INCLUDED):return {"hash":B_HASH}
            if params[0]=="finalized":
                return {"number":hex(FINAL),"hash":"0x"+"3c"*32}
        if method=="eth_getTransactionByHash":return tx_obj if tx else None
        if method=="eth_getTransactionReceipt":return receipt_obj if receipt else None
        if method=="eth_call":
            addr=params[0]["to"].lower()
            code=params[0]["data"]
            if addr==m.APPROVED_MARKET_ADDRESS.lower():
                if code==m.selector("votes()"):
                    return "0x"+int(ledger,16).to_bytes(32,"big").hex()
                if code==m.selector("minimumBond()"):
                    return "0x"+m.BOND_WEI.to_bytes(32,"big").hex()
            if addr==ledger and code==m.selector("settlement()"):
                return "0x"+int(m.APPROVED_MARKET_ADDRESS,16).to_bytes(32,"big").hex()
        if method=="eth_getCode":
            if params[0].lower()==m.APPROVED_MARKET_ADDRESS.lower():
                return market_hex
            if params[0].lower()==ledger.lower():
                return ledger_hex
        raise AssertionError("unexpected RPC call "+repr((method,params)))
    return market,ledger_art,transport,calls


def positive_funding(_url,*,transport):
    return {"fundingTxCanonicalAndFinalizedVerified":True,"destination":m.APP}


def full_r206(_manifest,_url,*,transport):
    return {"deploymentReceiptSuccessfulAndFinalized":True}


class TestR260FinalizedExactCreationEvidence(unittest.TestCase):
    def verify_fixture(self,*,finalized=True,tx=True,receipt=True,
                       status="0x1",wrong_input=False,gas_used=6_670_081):
        market,ledger,api,calls=fake_api(finalized=finalized,tx=tx,
                                        receipt=receipt,status=status,
                                        wrong_input=wrong_input,
                                        gas_used=gas_used)
        data=b"\xaa\xbb"
        with patch.object(m,"pin_artifacts",return_value="0xaabb"),patch.object(
             m,"APPROVED_INITCODE_SHA256",hashlib.sha256(data).hexdigest()),patch.object(
             m,"create_address",return_value=m.APPROVED_MARKET_ADDRESS):
            result=m.verify(m.RPC,market,ledger,transport=api,
                            r206_fn=full_r206,funding_fn=positive_funding)
        return result,calls

    def test_actual_complete_chain_finality_runtime_proof_yields_manifest(self):
        result,calls=self.verify_fixture()
        self.assertEqual(result["status"],"REAL_MARKET_AND_VOTE_LEDGER_CONTRACTS_FINALIZED")
        self.assertTrue(result["SolcNonImmutableRuntimeBytesVerifiedForBothContracts"])
        self.assertTrue(result["r206FinalizedAuditPassed"])
        self.assertEqual(result["manifest"]["ledger"]["address"],"0x"+"bb"*20)
        self.assertEqual(result["actualGasUsed"],6_670_081)
        self.assertEqual(result["actualFeePaidWei"],str(6_670_081*1000))
        self.assertTrue(result["immutableMarketLedgerMutualLinksAndMonitorBondVerified"])
        self.assertFalse(result["keysReadOrTransactionsSent"])
        self.assertNotIn("eth_sendRawTransaction",[x[0] for x in calls])

    def test_known_tx_without_receipt_is_pending_never_fake_success(self):
        with self.assertRaises(m.Pending) as ctx:
            self.verify_fixture(receipt=False)
        self.assertIn("DO_NOT_RESEND",ctx.exception.stage)

    def test_canonical_receipt_below_finalized_is_pending(self):
        with self.assertRaises(m.Pending) as ctx:
            self.verify_fixture(finalized=False)
        self.assertEqual(ctx.exception.numbers["includedBlock"],25100)
        self.assertEqual(ctx.exception.numbers["finalizedExecutionBlock"],25050)

    def test_unknown_hash_is_pending_no_resend(self):
        with self.assertRaises(m.Pending):
            self.verify_fixture(tx=False)

    def test_reverted_or_wrong_initcode_or_overpaid_receipt_refuses(self):
        for kw in ({"status":"0x0"},{"wrong_input":True},
                   {"gas_used":m.GAS_LIMIT+1}):
            with self.subTest(kw=kw),self.assertRaises(m.Refused):
                self.verify_fixture(**kw)

    def test_runtime_must_match_every_nonimmutable_byte(self):
        market,ledger,market_hex,ledger_hex,_=fixtures()
        out=m.verify_compiler_runtime(
            market,market_hex,m.EXPECTED_MARKET_RUNTIME_BYTES,"market")
        self.assertTrue(out["unmodifiedCompiledNonImmutableBytesVerified"])
        self.assertEqual(out["solcImmutablePatchSlots"],2)
        altered=bytearray(bytes.fromhex(market_hex[2:]))
        altered[400]^=1
        with self.assertRaisesRegex(m.Refused,"OUTSIDE IMMUTABLE"):
            m.verify_compiler_runtime(
                market,"0x"+altered.hex(),m.EXPECTED_MARKET_RUNTIME_BYTES,"market")

    def test_missing_immutable_bond_or_link_rejected(self):
        market,ledger,market_hex,ledger_hex,_=fixtures()
        out=m.verify_compiler_runtime(
            market,market_hex,m.EXPECTED_MARKET_RUNTIME_BYTES,"market")
        with self.assertRaises(m.Refused):
            m.require_slot_value(out,999999,"minimumBond")
        out=m.verify_compiler_runtime(
            ledger,ledger_hex,m.EXPECTED_LEDGER_RUNTIME_BYTES,"ledger")
        with self.assertRaises(m.Refused):
            m.require_slot_value(out,int(m.APP,16),"wrong settlement")

    def test_bad_overlapping_or_oob_solc_immutable_layout_rejected(self):
        market,_,market_hex,_,_=fixtures()
        for refs in (
            {"1":[{"start":1,"length":32}],"2":[{"start":10,"length":32}]},
            {"1":[{"start":m.EXPECTED_MARKET_RUNTIME_BYTES-1,"length":32}]},
            {"1":[{"start":100,"length":1}]},
        ):
            corrupt={"deployedBytecode":{**market["deployedBytecode"],
                                       "immutableReferences":refs}}
            with self.subTest(refs=refs),self.assertRaises(m.Refused):
                m.verify_compiler_runtime(corrupt,market_hex,
                                          m.EXPECTED_MARKET_RUNTIME_BYTES,"market")

    def test_manifest_only_creates_new_small_public_file_never_overwrites(self):
        manifest={"schema":"SSE_R206_ADAPTIVE_MARKET_V2_DEPLOYMENT_V1",
                  "chainId":m.CHAIN,"executionGenesisHash":m.GENESIS}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"manifest.json"
            m.write_manifest(path,manifest)
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertEqual(path.read_text().count("SSE_R206_"),1)
            with self.assertRaises(m.Refused):
                m.write_manifest(path,manifest)


if __name__=="__main__":
    unittest.main()
