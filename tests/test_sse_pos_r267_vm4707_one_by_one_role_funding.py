"""R267 fake-only owner role funding; unit checks NEVER send to real RPC."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r267_vm4707_one_by_one_role_funding as m


AUDIT={
    "chainId":m.CHAIN,
    "deploymentReceiptSuccessfulAndFinalized":True,
    "runtimeCodeSha256Verified":True,
    "mutualMarketLedgerBindingsVerified":True,
    "finalizedExecutionHeight":25364,
}
MANIFEST={
    "deployer":m.APP,"market":{"address":m.MARKET},
    "minimumBondWei":str(m.BOND),
}


class TestR267ExactRoleSingleNonceFunding(unittest.TestCase):
    def make_api(self,*,source_nonce=1,recipient_balance=0,recipient_nonce=0,
                 estimate=21000,price=1000,source_balance=10**18):
        calls=[]
        def rpc(url,method,params):
            self.assertEqual(url,m.RPC)
            self.assertNotIn(method,("eth_sendRawTransaction","eth_sendTransaction"))
            calls.append(method)
            if method=="eth_getTransactionCount":
                if params[0].lower()==m.APP.lower():return hex(source_nonce)
                return hex(recipient_nonce)
            if method=="eth_getCode":return "0x"
            if method=="eth_getBalance":
                if params[0].lower()==m.APP.lower():return hex(source_balance)
                return hex(recipient_balance)
            if method=="eth_estimateGas":
                self.assertEqual(params[0]["from"],m.APP)
                self.assertEqual(params[0]["data"],"0x")
                return hex(estimate)
            if method=="eth_gasPrice":return hex(price)
            if method=="eth_getBlockByNumber":
                return {"baseFeePerGas":"0x7","gasLimit":hex(30000000)}
            raise AssertionError("unexpected read-only RPC "+repr((method,params)))
        return rpc,calls

    def quote(self,role="consumer",**kw):
        api,calls=self.make_api(**kw)
        with tempfile.TemporaryDirectory() as root:
            k=Path(root)/"adaptive-v2-deployer.keystore.json"
            marker=Path(root)/(".r267-one-time-"+role+"-funding-attempted.json")
            deploy=Path(root)/".r257-one-time-v2-contract-deployment-attempted"
            with patch.object(m,"private_paths",return_value=(k,deploy,marker)),patch.object(
                 m,"load_manifest",return_value=MANIFEST):
                result=m.preflight(role,transport=api,
                    verify_fn=lambda *a,**kw:AUDIT)
        return result,calls

    def test_exact_consumer_real_native_quote_fails_closed_no_rpc_send(self):
        report,calls=self.quote()
        self.assertEqual(report["role"],"consumer")
        self.assertEqual(report["sourceNonce"],1)
        self.assertEqual(report["valueWei"],"10000000000000000")
        self.assertTrue(report["finalizedDeploymentR206Verified"])
        self.assertEqual(report["maximumFeeWei"],"21000000")
        self.assertFalse(report["transactionAuthorized"])
        self.assertFalse(report["transactionSignedOrSubmitted"])
        self.assertNotIn("eth_sendRawTransaction",calls)

    def test_funder_nonce_drift_and_existing_balance_rejected(self):
        for kw in ({"source_nonce":2},{"recipient_balance":1},
                   {"recipient_nonce":1},{"estimate":22000},
                   {"price":2000},{"source_balance":5}):
            with self.subTest(kw=kw),self.assertRaises(m.Refused):
                self.quote(**kw)

    def test_wrong_finalized_deployment_proof_refused(self):
        api,_=self.make_api()
        fake={**AUDIT,"deploymentReceiptSuccessfulAndFinalized":False}
        with patch.object(m,"private_paths",return_value=(
            Path("/tmp/fake/key"),Path("/tmp/fake/deploy"),
            Path("/tmp/fake/not-created-marker"))),patch.object(
            m,"load_manifest",return_value=MANIFEST):
            with self.assertRaises(m.Refused):
                m.preflight("consumer",transport=api,verify_fn=lambda *a,**kw:fake)

    def test_roles_must_be_strictly_ordered_after_predecessor_finality(self):
        api,_=self.make_api(source_nonce=2)
        with patch.object(m,"private_paths",return_value=(
            Path("/tmp/fake/key"),Path("/tmp/fake/deploy"),
            Path("/tmp/fake/not-created-marker"))),patch.object(
            m,"load_manifest",return_value=MANIFEST):
            with self.assertRaises(m.Pending):
                m.preflight("monitor-1",transport=api,
                            verify_fn=lambda *a,**kw:AUDIT,
                            prior_fn=lambda *a,**kw:(_ for _ in ()).throw(
                                m.Pending("earlier tx not finalized")))

    def test_consumed_marker_refuses_automated_retry(self):
        api,_=self.make_api()
        with tempfile.TemporaryDirectory() as temp:
            marker=Path(temp)/"used"
            marker.write_text("attempted")
            with patch.object(m,"private_paths",return_value=(
                Path(temp)/"key",Path(temp)/"deploy",marker)):
                with self.assertRaisesRegex(m.Refused,"NEVER RETRY"):
                    m.preflight("consumer",transport=api)

    def test_owner_decline_does_not_open_keystore_or_broadcast(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            marker=path/"marker"
            deploy=path/"deploy"
            deploy.write_text("R257 one-time deployment attempt consumed")
            deploy.chmod(0o600)
            key=path/"adaptive-v2-deployer.keystore.json"
            # No key material needed; owner declines before safe_keystore.
            fake_intent={
                "role":"consumer","chainId":m.CHAIN,"source":m.APP,
                "recipient":m.RECIPIENTS[0][1],"sourceNonce":1,
                "valueWei":str(m.RECIPIENTS[0][2]),
            }
            with patch.object(m,"private_paths",return_value=(key,deploy,marker)),patch.object(
                m.pwd,"getpwuid",return_value=Mock(pw_name=m.OWNER)),patch.object(
                m.os,"geteuid",return_value=12345),patch.object(
                m,"safe_keystore",side_effect=AssertionError("key read")):
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaisesRegex(m.Refused,"consent"):
                        m.send_once("consumer",preview_fn=lambda *a,**k:fake_intent,
                            confirm=lambda prompt:"DECLINE",
                            password_prompt=lambda prompt: (_ for _ in ()).throw(
                                AssertionError("secret requested")),
                            transport=lambda *a:(_ for _ in ()).throw(
                                AssertionError("broadcast")),
                            tty=False)
            self.assertFalse(marker.exists())

    def test_actual_signed_eip155_rlp_transfer_exact_public_fields(self):
        from eth_account import Account
        from eth_utils import to_checksum_address
        fake_key=b"\x37"*32  # local fake-only test key; never deployed/funded.
        i=0
        tx={"chainId":m.CHAIN,"nonce":i+1,"gas":m.GAS_LIMIT,
            "gasPrice":m.GAS_PRICE,
            "to":to_checksum_address(m.RECIPIENTS[i][1]),
            "value":m.RECIPIENTS[i][2],"data":b""}
        signed=Account.sign_transaction(tx,fake_key)
        raw="0x"+bytes(signed.raw_transaction).hex()
        self.assertTrue(m.verify_signed_legacy_transfer(raw,"consumer"))
        with self.assertRaises(m.Refused):
            m.verify_signed_legacy_transfer(raw,"monitor-1")
        tx["value"]-=1
        bad=Account.sign_transaction(tx,fake_key)
        with self.assertRaises(m.Refused):
            m.verify_signed_legacy_transfer(
                "0x"+bytes(bad.raw_transaction).hex(),"consumer")

    def test_marker_atomic_create_private_and_never_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            marker=root/"consumer-marker"
            k=root/"adaptive-v2-deployer.keystore.json"
            d=root/"deploy-marker"
            with patch.object(m,"private_paths",return_value=(k,d,marker)):
                data=m.record_marker(marker,"consumer","0x"+"ab"*32)
                self.assertEqual(marker.stat().st_mode & 0o777,0o600)
                self.assertEqual(json.loads(marker.read_text()),data)
                with self.assertRaisesRegex(m.Refused,"exists"):
                    m.record_marker(marker,"consumer","0x"+"cd"*32)

    def test_predecessor_genuine_successful_canonical_finalized(self):
        txhash="0x"+"ab"*32
        blockhash="0x"+"cd"*32
        role="consumer"
        doc={
            "schema":"SSE_R267_SINGLE_ROLE_FUNDING_ATTEMPT_V1",
            "role":role,"source":m.APP,"recipient":m.RECIPIENTS[0][1],
            "valueWei":str(m.RECIPIENTS[0][2]),"nonce":1,
            "gasLimit":m.GAS_LIMIT,"gasPriceWei":m.GAS_PRICE,
            "txHash":txhash,
        }
        tx={
            "hash":txhash,"from":m.APP,"to":m.RECIPIENTS[0][1],
            "value":hex(m.RECIPIENTS[0][2]),"nonce":"0x1",
            "gas":hex(m.GAS_LIMIT),"gasPrice":hex(m.GAS_PRICE),
            "input":"0x","chainId":hex(m.CHAIN),
        }
        receipt={
            "transactionHash":txhash,"status":"0x1","from":m.APP,
            "to":m.RECIPIENTS[0][1],"contractAddress":None,
            "gasUsed":hex(m.GAS_LIMIT),"blockNumber":hex(25400),
            "blockHash":blockhash,
        }
        def transport(_url,method,params):
            if method=="eth_getTransactionByHash":return tx
            if method=="eth_getTransactionReceipt":return receipt
            if method=="eth_getBlockByNumber":return {"hash":blockhash}
            if method=="eth_getBalance":return hex(m.RECIPIENTS[0][2])
            raise AssertionError("unexpected read")
        actual=m.check_previous_role_finalized(
            m.RPC,role,25410,transport=transport,
            read_marker_fn=lambda x:doc)
        self.assertEqual(actual,doc)
        with self.assertRaises(m.Pending):
            m.check_previous_role_finalized(
                m.RPC,role,25399,transport=transport,
                read_marker_fn=lambda x:doc)
        receipt["status"]="0x0"
        with self.assertRaises(m.Refused):
            m.check_previous_role_finalized(
                m.RPC,role,25410,transport=transport,
                read_marker_fn=lambda x:doc)


if __name__=="__main__":
    unittest.main()
