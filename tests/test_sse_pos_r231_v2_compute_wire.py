"""R231 bounded actual-compute hash commitment / EIP712 authentication unit tests."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r231_v2_compute_wire as mod
from compute_workload import compute_result

MARKET="0x"+"11"*20
LEDGER="0x"+"22"*20
CONSUMER="0x"+"33"*20
PROVIDER="0x"+"44"*20
HASH="0x"+"ab"*32
PROFILE="0x"+"cd"*32
POLICY="0x"+"ef"*32
SIGNATURE="0x"+"11"*32+"22"*32+"1b"


def original_snapshot():
    return {
        "schema":"SSE_R229_FINALIZED_V2_LEASE_READONLY_V1",
        "deploymentRuntimeAndWiringAttested":True,
        "chainId":31340,"market":MARKET,"ledger":LEDGER,
        "leaseId":1,"epochId":0,
        "lease":{
            "consumer":CONSUMER,"provider":PROVIDER,
            "profileHash":PROFILE,"policyHash":POLICY,
        },
        "epoch":{"market":{"exists":True,"requestHash":HASH}},
    }


def actual_payload():
    result=compute_result(1,0,HASH)
    return mod.payload_from_result(1,0,HASH,PROFILE,POLICY,result)


class TestR231RealComputeCommitment(unittest.TestCase):
    def test_cpu_reference_and_result_hash_bound_to_lease(self):
        payload=actual_payload()
        self.assertEqual(payload["workRounds"],8192)
        self.assertRegex(payload["workResultDigest"],r"^sha256:[0-9a-f]{64}$")
        digest=mod.response_hash(payload)
        self.assertRegex(digest,r"^0x[0-9a-f]{64}$")
        message=mod.provider_eip712_message(payload)
        self.assertEqual(message,{
            "leaseId":1,"epochId":0,"requestHash":HASH,"responseHash":digest})

    def test_signed_response_requires_actual_r229_attested_context(self):
        p=actual_payload()
        reply={**p,"responseHash":mod.response_hash(p),
               "providerSignature":SIGNATURE}
        with patch.object(mod,"verify_public_signer",return_value=True):
            out=mod.validate_signed_reply(reply,original_snapshot())
        self.assertTrue(out["providerPublicSignatureVerified"])
        self.assertFalse(out["remotePhysicalComputeProved"])
        self.assertFalse(out["onChainProviderResponseAuthenticated"])
        self.assertFalse(out["transactionSignedOrSubmitted"])
        with patch.object(mod,"verify_public_signer",return_value=False):
            with self.assertRaises(mod.Refused):
                mod.validate_signed_reply(reply,original_snapshot())

    def test_wrong_work_result_or_request_hash_refused(self):
        wrong={**compute_result(1,0,HASH),"rounds":8191}
        with self.assertRaises(mod.Refused):
            mod.payload_from_result(1,0,HASH,PROFILE,POLICY,wrong)
        p=actual_payload()
        tampered={**p,"requestHash":"0x"+"ff"*32}
        with self.assertRaises(mod.Refused):
            mod.validate_signed_reply({
                **tampered,"responseHash":mod.response_hash(tampered),
                "providerSignature":SIGNATURE
            },original_snapshot())

    def test_refuses_unauthenticated_lease_context(self):
        p=actual_payload()
        reply={**p,"responseHash":mod.response_hash(p),
               "providerSignature":SIGNATURE}
        with self.assertRaises(mod.Refused):
            mod.validate_signed_reply(reply,{
                **original_snapshot(),"deploymentRuntimeAndWiringAttested":False})
        with self.assertRaises(mod.Refused):
            mod.validate_signed_reply(reply,{
                **original_snapshot(),"epoch":{"market":{"exists":False}}})

    def test_refuse_signed_body_from_wrong_provider_or_bad_hash(self):
        p=actual_payload()
        reply={**p,"responseHash":mod.response_hash(p),
               "providerSignature":SIGNATURE}
        with self.assertRaises(mod.Refused):
            mod.validate_signed_reply({**reply,"responseHash":HASH},
                                       original_snapshot())
        with self.assertRaises(mod.Refused):
            mod.validate_signed_reply({**reply,"untrustedExtra":"yes"},
                                       original_snapshot())

if __name__=="__main__":
    unittest.main()
