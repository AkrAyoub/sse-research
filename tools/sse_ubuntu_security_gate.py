#!/usr/bin/env python3
"""Manual Ubuntu-specific security regression gate.

Runs Linux-only tests without silently counting their skips as success.
No Foundry, Docker start, VM deletion, account unlocking, or chain transaction.
"""
from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
import re
import subprocess
import sys
import unittest

SHA=re.compile(r"[0-9a-f]{40}\Z")
REQUIRED=[
    "test_sse_qbft_validator_identity.py",
    "test_sse_vm_role_setup.py",
    "test_sse_ssh_identity_tunnel.py",
    "test_sse_lab_release_handoff.py",
    "test_sse_vm_bootstrap.py",
    "test_sse_experiment_evidence.py",
]
ROOT=Path(__file__).resolve().parents[1]


class UbuntuGateError(ValueError):
    pass


def environment_check(release_text:str, kernel_text:str, system:str) -> None:
    if system!="Linux" or not any(line.strip() in ("ID=ubuntu",'ID="ubuntu"')
                                      for line in release_text.splitlines()):
        raise UbuntuGateError("Ubuntu Linux is required for POSIX security gates")
    if "microsoft" in kernel_text.lower() or "wsl" in kernel_text.lower():
        raise UbuntuGateError("WSL is not an independent Ubuntu VM test host")


def _git(cmd):
    try:
        return subprocess.run(["git","-C",str(ROOT),*cmd],capture_output=True,
                              text=True,check=True,timeout=10).stdout.strip()
    except (OSError,subprocess.SubprocessError):
        raise UbuntuGateError("could not inspect exact Git revision") from None


def run_gate(revision:str, *, out=sys.stdout) -> dict:
    release=Path("/etc/os-release").read_text("utf-8")
    kernel=Path("/proc/sys/kernel/osrelease").read_text("utf-8")
    environment_check(release,kernel,platform.system())
    if type(revision) is not str or not SHA.fullmatch(revision):
        raise UbuntuGateError("full 40-character approved Git SHA is mandatory")
    if _git(["rev-parse","HEAD"])!=revision:
        raise UbuntuGateError("Ubuntu source checkout differs from approved commit")
    if _git(["status","--porcelain","--untracked-files=no"]):
        raise UbuntuGateError("tracked source modifications detected")
    loader=unittest.TestLoader()
    suite=unittest.TestSuite()
    for name in REQUIRED:
        file=ROOT/"tests"/name
        if not file.is_file():
            raise UbuntuGateError("required POSIX test module missing: "+name)
        discovered=loader.discover(str(ROOT/"tests"),pattern=name)
        count=discovered.countTestCases()
        if count<2:
            raise UbuntuGateError("unexpected empty POSIX test discovery: "+name)
        suite.addTests(discovered)
    count=suite.countTestCases()
    print("SSE_UBUNTU_SECURITY_TESTS_DISCOVERED="+str(count),file=out)
    result=unittest.TextTestRunner(stream=out,verbosity=2).run(suite)
    if not result.wasSuccessful() or result.skipped:
        raise UbuntuGateError(
            f"Ubuntu security gate failed: failures={len(result.failures)} "
            f"errors={len(result.errors)} skipped={len(result.skipped)}"
        )
    return {
        "kind":"SSE_UBUNTU_SECURITY_GATE_V1",
        "gitCommit":revision,
        "executed":count,
        "passed":result.testsRun,
        "failures":0,
        "skipped":0,
        "sourceOnly":True,
        "walletKeysTransferred":False,
        "ethereumTransactionsSent":False,
        "independentValidatorNetworkProved":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Require actual Ubuntu/POSIX tests to run, no skips")
    p.add_argument("--expected-commit",required=True)
    a=p.parse_args(argv)
    try:
        report=run_gate(a.expected_commit)
        print(json.dumps(report,indent=2,sort_keys=True))
        return 0
    except (UbuntuGateError,OSError,ValueError,ImportError) as exc:
        print("SSE_UBUNTU_SECURITY_GATE_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
