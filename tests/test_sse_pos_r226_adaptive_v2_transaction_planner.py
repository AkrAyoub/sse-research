"""R226 source-only exact ABI planner tests. No signer, HTTP, Docker, or chain."""
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_pos_r226_adaptive_v2_transaction_planner as mod

MARKET="0x"+"11"*20
LEDGER="0x"+"22"*20
HASH="0x"+"ab"*32
SIG="0x"+"01"*32+"02"*32+"1b"
SIG2="0x"+"03"*32+"04"*32+"1c"
TERMS={
    "endpointHash":HASH,
    "epochs":2,
    "monitorBudgetWei":8_000,
    "perMonitorEpochRewardWei":1_000,
    "requiredFaultTolerance":1,
    "gasBoundSeats":4,
    "confirmationSeconds":3600,
    "responseSeconds":30,
    "monitoringSeconds":30,
}

def plan(action,role,params):
    return mod.build(action,role,params,MARKET,LEDGER)

def payload_words(p):
    raw=bytes.fromhex(p.calldata[2:])
    return raw[:4],[int.from_bytes(raw[n:n+32],"big")
                     for n in range(4,len(raw),32)]

class TestR226V2UnsignedPlanner(unittest.TestCase):
    def test_every_canonical_action_has_unique_selector(self):
        selectors=[mod.keccak256(item[2].encode("ascii"))[:4]
                   for item in mod.METHODS.values()]
        self.assertEqual(len(selectors),21)
        self.assertEqual(len(set(selectors)),len(selectors))
        self.assertEqual(plan("market-withdraw","observer",{}).calldata,"0x3ccfd60b")
        self.assertEqual(plan("ledger-withdraw","monitor",{}).calldata,"0x3ccfd60b")

    def test_permissionless_idle_close_no_private_keys_or_value(self):
        p=plan("expire-idle","observer",{"leaseId":7})
        self.assertEqual(p.target,MARKET)
        self.assertEqual(p.value_wei,0)
        self.assertEqual(p.calldata,"0x"+mod.keccak256(
            b"forceCloseIdle(uint256)")[:4].hex()+(7).to_bytes(32,"big").hex())
        self.assertFalse(p.public()["transactionSignedOrSubmitted"])

    def test_role_scope_fail_closed(self):
        with self.assertRaises(mod.Refused):
            plan("monitor-register","provider",{"bondWei":1})
        with self.assertRaises(mod.Refused):
            plan("request","observer",{"profileHash":HASH,"policyHash":HASH,
                                        "maxEpochFeeWei":1,"biddingClose":77})
        with self.assertRaises(mod.Refused):
            plan("future-action","monitor",{})
        with self.assertRaises(mod.Refused):
            plan("bid","provider",{"requestId":1,"epochFeeWei":2,"extra":1})

    def test_register_ether_value_and_no_private_key(self):
        p=plan("monitor-register","monitor",{"bondWei":10**15})
        self.assertEqual(p.target,MARKET)
        self.assertEqual(p.value_wei,10**15)
        self.assertEqual(len(p.calldata),10)
        self.assertFalse(p.public()["transactionSignedOrSubmitted"])
        self.assertFalse(p.public()["finalizedDeploymentAndBindingsVerified"])
        self.assertFalse(p.public()["realSlaVerified"])

    def test_request_static_four_words(self):
        p=plan("request","consumer",{
            "profileHash":HASH,"policyHash":HASH,
            "maxEpochFeeWei":123,"biddingClose":987654321
        })
        raw=bytes.fromhex(p.calldata[2:])
        self.assertEqual(len(raw),4+4*32)
        self.assertEqual(raw[4:36],bytes.fromhex(HASH[2:]))
        self.assertEqual(raw[36:68],bytes.fromhex(HASH[2:]))
        self.assertEqual(int.from_bytes(raw[68:100],"big"),123)
        self.assertEqual(int.from_bytes(raw[100:132],"big"),987654321)
        self.assertEqual(p.value_wei,0)

    def test_funded_tuple_has_correct_selector_and_flat_abi(self):
        p=plan("fund","consumer",{"requestId":9,"bidIndex":2,
                                 "bidEpochFeeWei":11_000,"terms":TERMS})
        raw=bytes.fromhex(p.calldata[2:])
        self.assertEqual(len(raw),4+11*32)
        self.assertEqual(raw[:4],mod.keccak256(
            mod.METHODS["fund"][2].encode("ascii"))[:4])
        self.assertEqual(int.from_bytes(raw[4:36],"big"),9)
        self.assertEqual(int.from_bytes(raw[36:68],"big"),2)
        self.assertEqual(raw[68:100],bytes.fromhex(HASH[2:]))
        self.assertEqual(int.from_bytes(raw[100:132],"big"),2)
        self.assertEqual(int.from_bytes(raw[132:164],"big"),8_000)
        self.assertEqual(p.value_wei,30_000)

    def test_invalid_funding_assumptions_refused(self):
        base={"requestId":1,"bidIndex":0,"bidEpochFeeWei":100,"terms":dict(TERMS)}
        for key,value in [
            ("epochs",65),("requiredFaultTolerance",2),
            ("confirmationSeconds",3599),("responseSeconds",0),
            ("gasBoundSeats",65),("endpointHash","0x"+"00"*32)
        ]:
            candidate={**base,"terms":{**TERMS,key:value}}
            with self.subTest(key=key),self.assertRaises(mod.Refused):
                plan("fund","consumer",candidate)
        with self.assertRaises(mod.Refused):
            plan("fund","consumer",{**base,"bidEpochFeeWei":0})
        with self.assertRaises(mod.Refused):
            plan("fund","consumer",{**base,"terms":{**TERMS,"unknown":10}})

    def test_signed_vote_dynamic_offset_alignment(self):
        p=plan("signed-vote","monitor",{
            "leaseId":3,"epochId":0,"outcome":2,
            "evidenceHash":HASH,"signature":SIG
        })
        raw=bytes.fromhex(p.calldata[2:])
        self.assertEqual(len(raw),4+5*32+32+96)
        self.assertEqual(int.from_bytes(raw[4+4*32:4+5*32],"big"),160)
        self.assertEqual(int.from_bytes(raw[4+5*32:4+6*32],"big"),65)
        self.assertEqual(raw[4+6*32:4+6*32+65],bytes.fromhex(SIG[2:]))
        self.assertEqual(p.target,LEDGER)

    def test_bilateral_residual_two_dynamic_abi_tails(self):
        p=plan("resolve-inconclusive","observer",{
            "leaseId":5,"epochId":1,
            "consumerShareWei":700,"providerShareWei":300,
            "nonce":0,"expiry":987654321,
            "consumerSig":SIG,"providerSig":SIG2,
        })
        raw=bytes.fromhex(p.calldata[2:])
        self.assertEqual(len(raw),4+8*32+2*(32+96))
        self.assertEqual(int.from_bytes(raw[4+6*32:4+7*32],"big"),256)
        self.assertEqual(int.from_bytes(raw[4+7*32:4+8*32],"big"),384)
        self.assertEqual(int.from_bytes(raw[4+8*32:4+9*32],"big"),65)
        self.assertEqual(int.from_bytes(raw[4+12*32:4+13*32],"big"),65)
        self.assertEqual(p.value_wei,0)

    def test_reject_bad_signatures_and_boolean_uints(self):
        a={"leaseId":5,"epochId":0,"outcome":1,
           "evidenceHash":HASH,"signature":SIG}
        for signature in ("0x",SIG[:-2]+"00",SIG[:-2]+"01","0x"+"ff"*65):
            with self.subTest(signature=signature[-5:]),self.assertRaises(mod.Refused):
                plan("signed-vote","monitor",{**a,"signature":signature})
        with self.assertRaises(mod.Refused):
            plan("signed-vote","monitor",{**a,"epochId":True})
        with self.assertRaises(mod.Refused):
            plan("signed-vote","monitor",{**a,"outcome":3})

    def test_verified_bid_must_match_finalized_on_chain_fee(self):
        m={"market":{"address":MARKET},"ledger":{"address":LEDGER}}
        p=plan("fund","consumer",{"requestId":9,"bidIndex":2,
                                  "bidEpochFeeWei":11_000,"terms":TERMS})
        args={"requestId":9,"bidIndex":2,"bidEpochFeeWei":11_000}
        requests=[]
        def mock_rpc(url,method,parameters):
            requests.append((method,parameters))
            self.assertEqual(method,"eth_call")
            self.assertEqual(parameters[1],"0x7b")
            return "0x"+(int("33"*20,16)).to_bytes(32,"big").hex()+(11_000).to_bytes(32,"big").hex()
        with patch.object(mod,"verify_deployment",return_value={
                "finalizedExecutionHeight":123}):
            mod.verify_funded_bid(p,args,m,"http://127.0.0.1:28545",transport=mock_rpc)
        self.assertEqual(len(requests),1)
        def wrong_rpc(*_):
            return "0x"+(int("33"*20,16)).to_bytes(32,"big").hex()+(10_999).to_bytes(32,"big").hex()
        with patch.object(mod,"verify_deployment",return_value={
                "finalizedExecutionHeight":123}), self.assertRaises(mod.Refused):
            mod.verify_funded_bid(p,args,m,"http://127.0.0.1:28545",transport=wrong_rpc)

    def test_offline_cli_does_not_require_manifest_or_rpc(self):
        args=["--action","monitor-register","--role","monitor",
              "--params-json",'{"bondWei":1000000000000000}',
              "--market",MARKET,"--ledger",LEDGER]
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(mod.main(args),0)
        record=json.loads(out.getvalue())
        self.assertEqual(record["valueWei"],"1000000000000000")
        self.assertFalse(record["transactionSignedOrSubmitted"])
        self.assertFalse(record["finalizedDeploymentAndBindingsVerified"])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(mod.main(args+["--rpc","http://127.0.0.1:28545"]),2)

if __name__=="__main__":
    unittest.main()
