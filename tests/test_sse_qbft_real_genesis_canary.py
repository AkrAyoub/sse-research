"""Actual four-key genesis block0 canary never uses synthetic validators."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_qbft_real_genesis_canary import validate_input,RealGenesisError
from sse_qbft_lab_config import genesis
from sse_qbft_validator_identity import node_key_record
from sse_qbft_vm_preflight import PreflightError
from sse_qbft_network_assembly import AssemblyError

SHA="a"*40
IMG="hyperledger/besu:26.11.1@sha256:"+"4"*64

class ActualGenesisTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.records=[node_key_record(i.to_bytes(32,"big"),f"validator-{i}",
                     f"100.100.101.{20+i}") for i in range(1,5)]
        self.file=self.base/"genesis.json"
        self.file.write_text(json.dumps(genesis(
            [r["validatorAddress"] for r in self.records],reward_wei=0)))
        self.sha=hashlib.sha256(self.file.read_bytes()).hexdigest()
        self.kw={"public":self.records,"genesis_path":self.file,
                 "genesis_sha256":self.sha,"image":IMG,
                 "revision":SHA,"run_id":"genesis-vm4704-1"}

    def test_four_actual_public_keys_match_genesis(self):
        plan=validate_input(**self.kw)
        self.assertEqual(plan["kind"],"SSE_QBFT_REAL_GENESIS_CANARY_PLAN_V1")
        self.assertEqual(plan["validatorAddresses"],
                         [r["validatorAddress"] for r in self.records])
        self.assertTrue(plan["p2pDisabled"])
        self.assertFalse(plan["startedValidator"])
        self.assertFalse(plan["consensusQuorumObserved"])
        self.assertFalse(plan["permissionlessMembershipClaimed"])
        self.assertFalse(plan["validatorPrivateKeysAccessed"])

    def test_reject_genesis_mismatching_signed_records(self):
        replaced=self.records.copy()
        replaced[0]=node_key_record((88).to_bytes(32,"big"),"validator-1",
                                    "100.100.101.21")
        with self.assertRaises(RealGenesisError):
            validate_input(**{**self.kw,"public":replaced})
        with self.assertRaises((AssemblyError,RealGenesisError)):
            validate_input(**{**self.kw,"public":self.records[:3]})

    def test_never_treat_previous_synthetic_canary_hash_as_real(self):
        bad=self.base/"synthetic.json"
        bad.write_text(json.dumps(genesis(["0x"+f"{i:02x}"*20
                       for i in range(1,5)],reward_wei=0)))
        digest=hashlib.sha256(bad.read_bytes()).hexdigest()
        with self.assertRaises(RealGenesisError):
            validate_input(**{**self.kw,"genesis_path":bad,
                              "genesis_sha256":digest})

    def test_wrong_chain_digest_and_source_refused(self):
        with self.assertRaises((PreflightError,RealGenesisError)):
            validate_input(**{**self.kw,"image":"hyperledger/besu:26.8.0@sha256:"+"4"*64})
        with self.assertRaises((PreflightError,RealGenesisError)):
            validate_input(**{**self.kw,"genesis_sha256":"0"*64})
        with self.assertRaises(RealGenesisError):
            validate_input(**{**self.kw,"revision":"main"})

    def test_runtime_does_not_launch_without_apply(self):
        source=(ROOT/"tools"/"sse_qbft_real_genesis_canary.py").read_text()
        self.assertIn('if a.apply:',source)
        self.assertIn('"up","-d","--pull","never"',source)
        self.assertIn('"down","--remove-orphans"',source)
        self.assertIn('["sudo","-n","docker","info"',source)
        self.assertIn("result.json",source)
        self.assertIn("docker.log",source)

if __name__=="__main__":
    unittest.main()
