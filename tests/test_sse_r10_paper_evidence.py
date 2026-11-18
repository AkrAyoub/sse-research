"""Reproducible paper evidence extraction fails closed on non-matching logs."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_r10_paper_evidence import EvidenceError,parse_windows,parse_ubuntu,bundle,CE

REV="a"*40

def windows_fixture():
    return "\n".join([
        "SSE_MANUAL_INTEGRATION_SHA="+REV,
        "Ran 3 tests in 0.01s\n\nOK",
        "Ran 910 tests in 95.0s\n\nOK (skipped=20)",
        "Ran 19 test suites in 700.1ms (4.4s CPU time): 144 tests passed, 0 failed, 0 skipped",
        *["[PASS] "+s+"() (gas: 750000)" for s in CE],
        *["WP09Q|batch_call_gas "+str(g) for g in (680497,613317,612008,613768,638445)],
        "WP09Q|pool_runtime_bytes 22670",
        "WP09Q|settlement_runtime_bytes 22533",
        "SSE_LOCAL_GATE_COMPLETED on "+REV,
    ])

def ubuntu_fixture():
    obj={
        "kind":"SSE_UBUNTU_SECURITY_GATE_V1",
        "gitCommit":REV,
        "executed":50,"passed":50,"failures":0,"skipped":0,
        "sourceOnly":True,
    }
    return "SSE_UBUNTU_SECURITY_TESTS_DISCOVERED=50\nRan 50 tests in 1s\n\nOK\n"+json.dumps(obj,indent=2)

class PaperEvidenceTests(unittest.TestCase):
    def test_exact_r9_local_evm_and_ubuntu_evidence(self):
        x=parse_windows(windows_fixture(),REV)
        y=parse_ubuntu(ubuntu_fixture(),REV)
        self.assertEqual(x["pythonTestsRun"],910)
        self.assertEqual(x["pythonTestsExecuted"],890)
        self.assertEqual(x["foundryEvmTestsPassed"],144)
        self.assertEqual(x["WP09QBatchGasUsedTotal"],3158035)
        self.assertEqual(x["EIP170HeadroomBytes"]["OpenMonitorCommittee"],1906)
        self.assertEqual(x["EIP170HeadroomBytes"]["SSESettlement"],2043)
        self.assertEqual(len(x["adversarialEvmCounterexamplesExecuted"]),4)
        self.assertEqual(y["ubuntuTestsPassed"],50)
        self.assertTrue(x["physicalWorldTruthNotObserved"])

    def test_missing_or_wrong_git_rev_and_false_evm_green_refused(self):
        for altered in (
            windows_fixture().replace("SSE_LOCAL_GATE_COMPLETED on "+REV,
                                      "SSE_LOCAL_GATE_COMPLETED on "+"b"*40),
            windows_fixture().replace("144 tests passed, 0 failed",
                                      "143 tests passed, 1 failed"),
            windows_fixture().replace("[PASS] "+CE[2],"[FAIL] "+CE[2]),
            windows_fixture().replace("WP09Q|pool_runtime_bytes 22670",
                                      "WP09Q|pool_runtime_bytes 26000"),
            windows_fixture().replace("SSE_LOCAL_GATE_COMPLETED","GATE_FAILED"),
        ):
            with self.subTest(input=altered[-80:]),self.assertRaises(EvidenceError):
                parse_windows(altered,REV)
        with self.assertRaises(EvidenceError):
            parse_windows(windows_fixture(),"main")

    def test_linux_skips_or_wrong_commit_refused(self):
        bad=json.loads(ubuntu_fixture().split("\nOK\n",1)[1])
        bad["skipped"]=1
        with self.assertRaises(EvidenceError):
            parse_ubuntu("SSE_UBUNTU_SECURITY_TESTS_DISCOVERED=50\n"+json.dumps(bad,indent=2),REV)
        with self.assertRaises(EvidenceError):
            parse_ubuntu(ubuntu_fixture(),"b"*40)

    def test_immutable_single_file_audit_does_not_copy_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            win=root/"windows.txt"
            linux=root/"ubuntu.txt"
            win.write_text(windows_fixture())
            linux.write_text(ubuntu_fixture())
            target=root/"evidence.json"
            report=bundle(win,linux,REV,target)
            self.assertFalse(report["originalLogsCopied"])
            self.assertFalse(report["independentValidatorsActuallyDeployed"])
            self.assertFalse(report["noveltyClaimProved"])
            self.assertEqual(report["sourceLogSha256"]["windows"],
                             hashlib.sha256(win.read_bytes()).hexdigest())
            self.assertTrue(target.exists())
            with self.assertRaises(EvidenceError):
                bundle(win,linux,REV,target)

if __name__=="__main__":
    unittest.main()
