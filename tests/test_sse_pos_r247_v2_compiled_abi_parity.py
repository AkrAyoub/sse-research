"""R247 expected compiled-Solidity ABI type/index parity; no network or wallet."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r247_v2_compiled_abi_parity as a

def param(kind,name="",indexed=None):
    p={"name":name,"type":kind}
    if indexed is not None:
        p["indexed"]=indexed
    return p

def event(signature,indexed,data):
    name=signature.split("(")[0]
    return {"type":"event","name":name,"anonymous":False,
            "inputs":[param(kind,key,True) for key,kind in indexed]+
                     [param(kind,key,False) for key,kind in data]}

def method(name,outputs):
    return {"type":"function","name":name,
            "inputs":[param("uint256","id")],
            "outputs":outputs}

def tupleoutput(schema):
    return {"name":"","type":"tuple","components":[
        param(t,name) for name,t in schema]}

class TestR247CompiledV2ABIParity(unittest.TestCase):
    def test_canonical_tuple_and_struct_signature(self):
        abi_param={"type":"tuple","components":[
            param("address","owner"),param("uint64","deadline")]}
        self.assertEqual(a.canonical_type(abi_param),"(address,uint64)")
        self.assertEqual(a.canonical_type({**abi_param,"type":"tuple[]"}),
                         "(address,uint64)[]")
        with self.assertRaises(a.Refused):
            a.canonical_type({"type":"tuple"})
        with self.assertRaises(a.Refused):
            a.canonical_type({"type":"string"})
        self.assertEqual(a.signature({"name":"fund","inputs":[
            param("uint256","id"),abi_param]}),
            "fund(uint256,(address,uint64))")

    def test_reject_unmatched_market_event_index_or_schema(self):
        template=a.MARKET_EVENTS[0]
        exact=event(*template)
        a.check_events([exact],[template],"market")
        changed=json.loads(json.dumps(exact))
        changed["inputs"][0]["indexed"]=False
        with self.assertRaises(a.Refused):
            a.check_events([changed],[template],"market")
        changed=json.loads(json.dumps(exact))
        changed["inputs"][1]["type"]="address"
        with self.assertRaises(a.Refused):
            a.check_events([changed],[template],"market")
        with self.assertRaises(a.Refused):
            a.check_events([], [template],"market")

    def test_solidity_enum_uint8_event_exact(self):
        v=next(x for x in a.LEDGER_EVENTS if x[0].startswith("VoteRecorded("))
        a.check_events([event(*v)],[v],"ledger")
        wrong=json.loads(json.dumps(event(*v)))
        for p in wrong["inputs"]:
            if p["name"]=="outcome":
                p["type"]="uint256"
        with self.assertRaises(a.Refused):
            a.check_events([wrong],[v],"ledger")

    def test_compiled_lease_layout_requires_last_progress_field(self):
        lease=method("lease",[tupleoutput(a.MARKET_LEASE)])
        a.check_function([lease],"lease(uint256)",[a.MARKET_LEASE])
        damaged=json.loads(json.dumps(lease))
        damaged["outputs"][0]["components"].pop()
        with self.assertRaises(a.Refused):
            a.check_function([damaged],"lease(uint256)",[a.MARKET_LEASE])

    def test_check_dynamic_selected_addresses_and_escrow_abi(self):
        selected=method("selected",[param("address[]","")])
        a.check_function([selected],"selected(uint256)",[("monitors","address[]")])
        with self.assertRaises(a.Refused):
            a.check_function([method("selected",[param("address","")])],
                             "selected(uint256)",[("monitors","address[]")])
        with self.assertRaises(a.Refused):
            a.check_function([],"escrowAccounting()",[("x","uint256")])

    def test_load_real_compiled_envelope_reject_bad_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"Artifact.json"
            path.write_text(json.dumps({
                "abi":[],"deployedBytecode":{"object":"0x6000"},
                "metadata":"source-only mock, not Foundry"
            }))
            self.assertEqual(a.load_artifact(path)["abi"],[])
            path.write_text(json.dumps({
                "abi":[],"deployedBytecode":{"object":"0x"}
            }))
            with self.assertRaises(a.Refused):
                a.load_artifact(path)
            path.unlink()
            with self.assertRaises(a.Refused):
                a.load_artifact(path)

    def test_missing_runtime_functions_never_silently_count_as_verified(self):
        with self.assertRaises(a.Refused):
            a.audit({"abi":[],"deployedBytecode":{"object":"0x6000"}},
                    {"abi":[],"deployedBytecode":{"object":"0x6000"}})

if __name__=="__main__":
    unittest.main()
