#!/usr/bin/env python3
"""Turn ACTUAL operator console logs into a traceable, conservative SSE paper pack.

Does not invent test runs, physical events or consensus rewards; rejects
mismatched Git revisions, missing Foundry gate or incomplete Ubuntu security
tests. It records original file SHA256 but does not copy or sanitize operator
logs. Keep logs out of GitHub and preserve them in protected storage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

SHA=re.compile(r"[0-9a-f]{40}\Z")
EIP170=24576
CE=(
    "testCE01_ThreeAuthenticatedFailureVotesOverrefundStipulatedSuccess",
    "testCE02_SignedAckPlusThreeFailuresCreditsFullConsumer",
    "testCE03_AuthenticatedSuccessCanCreditProviderWithoutDeliveryProof",
    "testCE04_GracePeriodResponseAndSuccessVotesStillSettleSuccess",
)
BATCH=re.compile(r"WP09Q\|batch_call_gas\s+([0-9]+)")
SIZEPOOL=re.compile(r"WP09Q\|pool_runtime_bytes\s+([0-9]+)")
SIZESETTLE=re.compile(r"WP09Q\|settlement_runtime_bytes\s+([0-9]+)")
DONE=re.compile(r"SSE_LOCAL_GATE_COMPLETED on ([0-9a-f]{40})")
FOUNDRY=re.compile(
    r"Ran [0-9]+ test suites in [^\n]+:\s+([0-9]+) tests passed,"
    r"\s+([0-9]+) failed,\s+([0-9]+) skipped"
)
PYTHON=re.compile(r"Ran ([0-9]+) tests in [0-9.]+s\s+OK \(skipped=([0-9]+)\)")
UBUNTU=re.compile(r"SSE_UBUNTU_SECURITY_TESTS_DISCOVERED=([0-9]+)")
MAX_LOG=20_000_000


class EvidenceError(ValueError):
    pass


def read_log(path:Path):
    if (path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_LOG
            or path.stat().st_size==0):
        raise EvidenceError("missing/oversized/symlink source log")
    raw=path.read_bytes()
    return raw.decode("utf-8",errors="replace"),hashlib.sha256(raw).hexdigest()


def parse_windows(text:str,revision:str)->dict:
    if type(revision) is not str or not SHA.fullmatch(revision):
        raise EvidenceError("exact Git SHA required")
    done=DONE.findall(text)
    if done!=[revision]:
        raise EvidenceError("manual gate is missing, duplicated, or wrong Git revision")
    tests=PYTHON.findall(text)
    if not tests:
        raise EvidenceError("no successful complete Python suite detected")
    # Short targeted suites occur earlier: the last successful full suite
    # is the one with the maximum test count, but reject ambiguity.
    most=max(int(n) for n,_ in tests)
    matches=[(int(n),int(skips)) for n,skips in tests if int(n)==most]
    if len(matches)!=1 or most<100:
        raise EvidenceError("ambiguous or incomplete Python gate")
    py,skip=matches[0]
    if skip>py:
        raise EvidenceError("invalid Python skipped count")
    all_foundry=FOUNDRY.findall(text)
    if len(all_foundry)!=1:
        raise EvidenceError("Foundry suite summary absent or ambiguous")
    passing,failed,foundry_skips=tuple(int(x) for x in all_foundry[0])
    if passing<100 or failed!=0 or foundry_skips!=0:
        raise EvidenceError("Foundry EVM baseline failed")
    for case in CE:
        if not re.search(r"\[PASS\]\s+"+re.escape(case)+r"\(",text):
            raise EvidenceError("required EVM physical-observability counterexample not found: "+case)
    batch=[int(x) for x in BATCH.findall(text)]
    if len(batch)!=5 or any(x<=0 for x in batch):
        raise EvidenceError("require five actual measured WP09Q batch gas values")
    p=SIZEPOOL.findall(text)
    s=SIZESETTLE.findall(text)
    if len(p)!=1 or len(s)!=1:
        raise EvidenceError("require actual EIP170 runtime code size lines")
    pool,settlement=int(p[0]),int(s[0])
    if not 0<pool<EIP170 or not 0<settlement<EIP170:
        raise EvidenceError("runtime bytecode exceeds EIP170 or is empty")
    return {
        "sourceGitSha":revision,
        "pythonTestsRun":py,
        "pythonTestsSkipped":skip,
        "pythonTestsExecuted":py-skip,
        "foundryEvmTestsPassed":passing,
        "foundryEvmTestsFailed":0,
        "physicalWorldTruthNotObserved":True,
        "adversarialEvmCounterexamplesExecuted":list(CE),
        "WP09QFiveBatchGasUsed":batch,
        "WP09QBatchGasUsedTotal":sum(batch),
        "runtimeBytes":{
            "OpenMonitorCommittee":pool,
            "SSESettlement":settlement,
        },
        "EIP170HeadroomBytes":{
            "OpenMonitorCommittee":EIP170-pool,
            "SSESettlement":EIP170-settlement,
        },
        "liveBesuConsensusMeasured":False,
        "testOnlyEVM":True,
    }


def parse_ubuntu(text:str,revision:str)->dict:
    discovered=UBUNTU.findall(text)
    if len(discovered)!=1:
        raise EvidenceError("exactly one Ubuntu zero-skip gate required")
    n=int(discovered[0])
    # Python runner emits JSON; extract only the final well-known key-value
    # *isolated lines*, not an arbitrary test fixture printed earlier.
    import re as _re
    records=list(_re.finditer(r'^\s*"kind"\s*:\s*"SSE_UBUNTU_SECURITY_GATE_V1"',text,_re.MULTILINE))
    if len(records)!=1:
        raise EvidenceError("Ubuntu security gate report missing")
    # Find final JSON object by its 'kind' field; reject duplicate or stale.
    # In the operator log the report is the last top-level JSON payload,
    # and tests sometimes print nested unrelated fixture JSON.
    try:
        mark=records[0].start()
        left=text.rfind("{",0,mark)
        right=text.find("}",mark)
        if left<0 or right<0:
            raise ValueError("cannot find object boundaries")
        obj=json.loads(text[left:right+1])
    except (ValueError,UnicodeError):
        raise EvidenceError("Ubuntu gate JSON report invalid") from None
    if (obj.get("gitCommit")!=revision
            or obj.get("executed")!=n or obj.get("passed")!=n
            or obj.get("failures")!=0 or obj.get("skipped")!=0
            or obj.get("sourceOnly") is not True):
        raise EvidenceError("Ubuntu security test report is incomplete/wrong revision")
    return {
        "sourceGitSha":revision,"ubuntuTestsExecuted":n,
        "ubuntuTestsPassed":n,"ubuntuSecuritySkips":0,
        "notEvidenceOfIndependentHosts":True,
    }


def bundle(windows:Path,ubuntu:Path,revision:str,output:Path)->dict:
    if (not output.is_absolute() or not output.parent.is_dir()
            or output.parent.is_symlink() or output.exists() or output.is_symlink()):
        raise EvidenceError("output must be new absolute file under existing directory")
    win,wh=read_log(windows)
    ub,uh=read_log(ubuntu)
    report={
        "schema":"SSE_R10_LOCAL_EVM_UBUNTU_PAPER_EVIDENCE_V1",
        "scientificScope":"LOCAL_EVM_PLUS_UBUNTU_SECURITY_ONLY",
        "sourceGitSha":revision,
        "sourceLogSha256":{"windows":wh,"ubuntu":uh},
        "windows":parse_windows(win,revision),
        "ubuntu":parse_ubuntu(ub,revision),
        "originalLogsCopied":False,
        "originalLogContentsSanitized":False,
        "independentValidatorsActuallyDeployed":False,
        "physicalServiceOutcomeVerified":False,
        "contractsActuallyDeployedToBesu31338":False,
        "noveltyClaimProved":False,
    }
    payload=json.dumps(report,sort_keys=True,indent=2)+"\n"
    flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY
    if hasattr(os,"O_NOFOLLOW"):flags|=os.O_NOFOLLOW
    fd=os.open(output,flags,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        f.write(payload)
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description="Audit Windows Foundry and Ubuntu gate, emit verifiable local paper evidence")
    p.add_argument("--windows-log",type=Path,required=True)
    p.add_argument("--ubuntu-log",type=Path,required=True)
    p.add_argument("--source-commit",required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args(argv)
    try:
        result=bundle(a.windows_log,a.ubuntu_log,a.source_commit,a.output)
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (EvidenceError,OSError,ValueError,TypeError) as exc:
        print("SSE_R10_PAPER_EVIDENCE_REFUSED: "+str(exc),file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
