"""R257 dry-run/one-shot owner deployment policy. ALL RPC/signers mocked; NO SEND."""
from pathlib import Path
import contextlib
import hashlib
import io
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r257_vm4707_one_time_v2_deployment as m


def offer(**updates):
    d={
        "chainId":31340,
        "originalExecutionGenesisVerified":True,
        "marketCompilerAbiMatchedR249":True,
        "ledgerCompilerAbiMatchedR249":True,
        "deploymentSigner":m.APP,
        "quoteOnlyNoPrivateKeysNoTransactionNoDeployment":True,
        "minimumBondWeiQuoteScenarioOnly":str(m.BOND_WEI),
        "actualNodeEstimatedConstructorGas":6_670_081,
        "paddedGasLimitScenario":m.GAS_LIMIT,
        "actualNodeGasPriceWei":"1000",
        "actualNodeBaseFeeWeiPerGas":"7",
        "balanceWeiAtFinalized":str(10**18),
        "currentBalanceWeiAtLatest":str(10**18),
    }
    d.update(updates)
    return d


def funding(**updates):
    d={
        "fundingTxCanonicalAndFinalizedVerified":True,
        "recipientBalanceWeiAtFinalized":str(10**18),
        "sourceNonceAtFinalized":1,
        "transactionHash":"0x07e3ff069936936b3daf17efc5cb484c1712e93dc6bd6040c55a5fae1b8d2a90",
    }
    d.update(updates)
    return d


def transport(nonce="0x0",code="0x"):
    calls=[]
    def call(rpc,method,params):
        calls.append((rpc,method,params))
        if rpc!=m.RPC:
            raise AssertionError("wrong RPC")
        if method=="eth_getTransactionCount":
            return nonce
        if method=="eth_getCode":
            return code
        raise AssertionError("Unexpected potentially mutating RPC "+method)
    return call,calls


class TestR257ActualOwnerOneCreatePolicy(unittest.TestCase):
    def run_preflight(self,*,quote_data=None,funding_data=None,nonce="0x0",code="0x"):
        t,calls=transport(nonce=nonce,code=code)
        fake_initcode="0xaabb"
        fake_digest=hashlib.sha256(bytes.fromhex(fake_initcode[2:])).hexdigest()
        with patch.object(m,"create_address",return_value=m.APPROVED_MARKET_ADDRESS),patch.object(
            m,"pin_artifacts",return_value=fake_initcode),patch.object(
            m,"APPROVED_INITCODE_SHA256",fake_digest):
            d=m.preflight({}, {}, transport=t,
                 quote_fn=lambda *a,**k: quote_data if quote_data is not None else offer(),
                 funding_fn=lambda *a,**k: funding_data if funding_data is not None else funding())
        return d,calls

    def test_successful_readonly_preflight_has_exact_no_send_intent(self):
        d,calls=self.run_preflight()
        self.assertTrue(d["r255FundingCanonicalAndFinalized"])
        self.assertFalse(d["signedOrBroadcast"])
        self.assertTrue(d["separateOwnerApprovalStillRequired"])
        self.assertEqual(d["gasLimit"],8_342_601)
        self.assertEqual(d["gasPriceWei"],1000)
        self.assertEqual(d["constructorBondWei"],str(10**15))
        self.assertEqual(d["deployerPendingNonce"],0)
        self.assertEqual(d["maximumTransactionGasFeeWei"],"8342601000")
        self.assertNotIn("initcode",m.public_intent(d))
        self.assertTrue(all(x[1] in ("eth_getCode","eth_getTransactionCount") for x in calls))

    def test_finalized_funding_is_required_before_quoting(self):
        calls=[]
        def reject(*args,**kwargs):
            calls.append("QUOTE_CALLED")
            raise AssertionError("cannot quote without funding")
        with self.assertRaises(m.Refused):
            m.preflight({}, {}, quote_fn=reject,
                funding_fn=lambda *a,**k: funding(fundingTxCanonicalAndFinalizedVerified=False))
        self.assertEqual(calls,[])
        with self.assertRaises(m.Refused):
            m.preflight({}, {}, quote_fn=reject,
                funding_fn=lambda *a,**k: funding(recipientBalanceWeiAtFinalized="0"))

    def test_refuse_extra_gas_limit_price_base_fee_and_unfunded_finalized(self):
        for changes in (
            {"paddedGasLimitScenario":m.GAS_LIMIT+1},
            {"actualNodeEstimatedConstructorGas":m.GAS_LIMIT+1},
            {"actualNodeGasPriceWei":"1001"},
            {"actualNodeBaseFeeWeiPerGas":"1001"},
            {"balanceWeiAtFinalized":"0"},
            {"currentBalanceWeiAtLatest":"0"},
            {"marketCompilerAbiMatchedR249":False},
            {"ledgerCompilerAbiMatchedR249":False},
            {"chainId":1},
            {"deploymentSigner":m.ORIGINAL_GENESIS_EOA} if hasattr(m,"ORIGINAL_GENESIS_EOA") else
                {"deploymentSigner":"0x"+"12"*20},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(m.Refused):
                    self.run_preflight(quote_data=offer(**changes))

    def test_refuse_pending_or_latest_app_nonce(self):
        for value in ("0x1","0x2"):
            with self.subTest(nonce=value),self.assertRaises(m.Refused):
                self.run_preflight(nonce=value)

    def test_refuse_predicted_create_address_already_has_code(self):
        with self.assertRaises(m.Refused):
            self.run_preflight(code="0x6000")

    def test_refuse_send_without_vm4707_owner_identity_before_password(self):
        with patch.object(m,"getuser",return_value="unknown"),patch.object(
            m,"safe_keystore",side_effect=AssertionError("MUST NOT READ KEY")):
            with self.assertRaises(m.Refused):
                m.send_once({}, {}, Path("/tmp/bad"), Path("/tmp/bad.marker"),
                    tty=False,confirm=lambda _:m.CONFIRM,
                    password_prompt=lambda _: "never")

    def test_no_approval_does_not_access_keystore_or_marker_or_broadcast(self):
        # Important: send_once's preflight_fn default was bound when the
        # function was defined. Patching m.preflight alone does NOT change
        # that default and accidentally calls the real R256 quote on {}.
        # Inject an explicit synthetic preview, with no access to live RPC.
        key=Path("/safe/app.keystore.json")
        marker=Path("/safe/no-attempt")
        preview={"initcode":"0xaabb","deployer":m.APP,"signedOrBroadcast":False}
        prompts=[]
        def declined(prompt):
            prompts.append(prompt)
            return "DECLINE"
        def never_password(_):
            raise AssertionError("PASSWORD MUST NOT BE REQUESTED")
        def never_rpc(*_):
            raise AssertionError("RPC MUST NOT BE CALLED ON DECLINED SEND")
        with patch.object(m,"owner_private_paths",return_value=(key,marker)),patch.object(
             m,"getuser",return_value="ayoubakrvm4707"),patch.object(
             m.os,"geteuid",return_value=1000),patch.object(
             m,"safe_keystore",side_effect=AssertionError("KEY MUST STAY UNREAD")),patch.object(
             m,"consume_one_shot_marker",side_effect=AssertionError("NO SEND MARKER")):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(m.Refused,"did not authorize"):
                    m.send_once({}, {}, key,marker,tty=False,confirm=declined,
                        password_prompt=never_password,transport=never_rpc,
                        preflight_fn=lambda *a,**k: preview)
        self.assertEqual(len(prompts),1)

    def test_marker_created_exclusively_and_prevents_duplicate_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker=Path(tmp)/"one-shot"
            m.consume_one_shot_marker(marker)
            self.assertEqual(marker.stat().st_mode & 0o777,0o600)
            with self.assertRaises(m.Refused):
                m.consume_one_shot_marker(marker)

    def test_pinned_source_mismatch_fails_before_any_wallet_access(self):
        with self.assertRaises(m.Refused):
            m.check_git("not-a-sha")
        with patch.object(m.subprocess,"check_output",side_effect=[
            "f"*40+"\n",""]):
            with self.assertRaises(m.Refused):
                m.check_git("0"*40)

    def test_predicted_nonce_zero_rlp_create_address_differs_from_source(self):
        # Independent hash implementation is provided by eth_utils on
        # actual owner venv, not a hardcoded untrusted user address.
        with patch.dict(sys.modules,{"eth_utils":__import__("types").SimpleNamespace(
            keccak=lambda raw: b"\x00"*12+b"\x11"*20,
            to_checksum_address=lambda raw: "0x"+raw.hex())}):
            addr=m.create_address(m.APP)
            self.assertEqual(addr,"0x"+"11"*20)

    def test_owner_approved_full_compiled_initcode_digest_rejects_drift(self):
        # Even identical ABI and byte lengths cannot approve different
        # executable deployment bytes; exact full SHA256 is mandatory.
        t,_=transport()
        with patch.object(m,"create_address",return_value=m.APPROVED_MARKET_ADDRESS),patch.object(
            m,"pin_artifacts",return_value="0xaabb"):
            with self.assertRaisesRegex(m.Refused,"SHA256 differs"):
                m.preflight({}, {}, transport=t,
                    quote_fn=lambda *a,**k: offer(),
                    funding_fn=lambda *a,**k: funding())
        self.assertEqual(m.APPROVED_INITCODE_SHA256,
            "22d5b3310ec9a9efc66015762ea3d78d152f0a52eb9d67a257f18e3470c171ec")

    def test_owner_approved_market_create_address_refuses_change(self):
        t,_=transport()
        with patch.object(m,"create_address",return_value="0x"+"ab"*20),patch.object(
            m,"pin_artifacts",side_effect=AssertionError("NO INITCODE READ")):
            with self.assertRaisesRegex(m.Refused,"owner-approved R257"):
                m.preflight({}, {}, transport=t,
                    quote_fn=lambda *a,**k: offer(),
                    funding_fn=lambda *a,**k: funding())

    def test_ephemeral_fake_key_signs_legacy_contract_create_offline(self):
        # No real key, no key file, no ETH, no RPC; validates the exact
        # contract CREATE transaction encoding before accessing app wallet.
        try:
            from eth_account import Account
        except ImportError:
            self.skipTest("local test venv missing eth-account")
        fake_key=bytes([7])*32
        signer=Account.from_key(fake_key)
        unsigned={
            "chainId":m.CHAIN,"nonce":m.EXPECTED_NONCE,
            "gas":m.GAS_LIMIT,"gasPrice":m.GAS_PRICE_WEI,
            "to":"","value":0,"data":bytes.fromhex("60006000"),
        }
        signed=Account.sign_transaction(unsigned,fake_key)
        self.assertEqual(Account.recover_transaction(
            "0x"+bytes(signed.raw_transaction).hex()).lower(),
            signer.address.lower())
        self.assertTrue(bytes(signed.raw_transaction).startswith(b"\xf8") or
                        bytes(signed.raw_transaction).startswith(b"\xf9"))

    def test_r257_has_strict_immutable_pending_only_funding_parameters(self):
        self.assertEqual(m.BOND_WEI,10**15)
        self.assertEqual(m.GAS_LIMIT,8_342_601)
        self.assertEqual(m.GAS_PRICE_WEI,1000)
        self.assertEqual(m.APPROVED_MARKET_ADDRESS.lower(),
                         "0x6c01dbd7aa336a96d8ab09ea631e209612224080")
        self.assertEqual(m.EXPECTED_NONCE,0)
        self.assertEqual(m.CONFIRM,"DEPLOY-ONE-V2-CHAIN31340-BOND-0.001-TEST-ETH")
        self.assertNotEqual(m.APP.lower(),"0x13fb73aace8a11be2899d047635a757a224ce00b")


if __name__=="__main__":
    unittest.main()
