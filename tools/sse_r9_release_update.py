#!/usr/bin/env python3
"""GitHub-first R9 source release updater for *stopped* dedicated Ubuntu hosts.

Unprivileged, manual, operator-approved. No GitHub Actions or --force/reset,
Docker start/stop, Tailscale changes, wallet imports, chain transactions or
service restarts. Never invoke against original Anvil host. Before new SHA is
activated, run Ubuntu security gate and full Python regression; roll the Git
checkout back if either fails. This changes only source checkout, NOT the
running chain's state, containers or Python environment.

Approval is on an exact SHA, never mutable 'main' or 'latest'.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import socket
import subprocess
import sys
import time

BRANCH="integration/r7-wp09q-wan-multivm-no-actions"
REMOTE="git@github.com:AkrAyoub/sse-research.git"
SHA=re.compile(r"[0-9a-f]{40}\Z")
MAX_LOG=4*1024*1024


class UpdateError(ValueError):
    pass


def _exec(argv, repo:Path, *, timeout=35):
    try:
        p=subprocess.run(argv,cwd=repo,capture_output=True,
                         text=True,check=True,timeout=timeout)
        if len(p.stdout)+len(p.stderr)>MAX_LOG:
            raise UpdateError("inspection output too large")
        return p.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise UpdateError("local Git or test operation failed; inspect private logs") from None


def _port_busy(port):
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
        sock.settimeout(.3)
        return sock.connect_ex(("127.0.0.1",port))==0


def validate_plan(*, current, expected_current, target, git_origin,
                  source_dirty, live_rpc=False, os_native=True, is_root=False):
    if any(type(s) is not str or not SHA.fullmatch(s)
           for s in (current,expected_current,target)):
        raise UpdateError("two full approved source SHAs are required")
    if current!=expected_current:
        raise UpdateError("checkout drifted from operator-approved current commit")
    if git_origin!=REMOTE:
        raise UpdateError("Git origin is not the reviewed private SSE repository")
    if source_dirty:
        raise UpdateError("tracked local source changes; preserve before checkout")
    if live_rpc:
        raise UpdateError("RPC already active; cannot update while a chain may be running")
    if not os_native or is_root:
        raise UpdateError("only nonroot native Ubuntu host source update allowed")
    return {
        "kind":"SSE_R9_PINNED_SOURCE_UPDATE_V1",
        "mode":"DRY_RUN", "current":current, "target":target,
        "remote":REMOTE, "branch":BRANCH,
        "requiresManualApproval":True,
        "willRunUbuntuSecurityGate":True,
        "willRunFullPythonSuite":True,
        "willNotTouchBesuProcess":True,
        "willNotInstallPackages":True,
        "willNotModifyChainState":True,
        "ethereumTransactionsSent":False,
    }


def _ubuntu():
    if platform.system()!="Linux" or "microsoft" in platform.release().lower():
        return False
    try:
        return any(s.strip() in ("ID=ubuntu",'ID="ubuntu"')
                   for s in Path("/etc/os-release").read_text("utf-8").splitlines())
    except OSError:
        return False


def plan(repo:Path, *, current, target, run=_exec, port_busy=None):
    root=repo.resolve(strict=True)
    if port_busy is None:
        port_busy=_port_busy
    if not (root/".git").exists():
        raise UpdateError("expected a dedicated Git checkout, not a source archive")
    actual=run(["git","rev-parse","HEAD"],root)
    origin=run(["git","remote","get-url","origin"],root)
    dirty=run(["git","status","--porcelain","--untracked-files=no"],root)
    return validate_plan(
        current=actual,expected_current=current,target=target,
        git_origin=origin,source_dirty=bool(dirty),
        live_rpc=any(port_busy(p) for p in (8545,18545,18559)),
        os_native=_ubuntu(),is_root=(os.geteuid()==0),
    )


def _new_log(folder:Path, name:str, raw:str):
    if not folder.is_absolute() or not folder.is_dir() or folder.is_symlink():
        raise UpdateError("logs require pre-existing protected absolute directory")
    st=folder.stat()
    if st.st_uid!=os.geteuid() or st.st_mode&0o077:
        raise UpdateError("log directory must be user-owned and mode 0700")
    file=folder/name
    if file.exists() or file.is_symlink():
        raise UpdateError("refusing to overwrite an earlier test log")
    data=raw.encode("utf-8",errors="replace")
    if len(data)>MAX_LOG:
        data=data[:MAX_LOG]
    fd=os.open(file,os.O_CREAT|os.O_EXCL|os.O_WRONLY|
               (os.O_NOFOLLOW if hasattr(os,"O_NOFOLLOW") else 0),0o600)
    with os.fdopen(fd,"wb") as out:
        out.write(data)
    return str(file)


def _run_test(args, repo:Path, folder:Path, label:str):
    try:
        p=subprocess.run(args,cwd=repo,capture_output=True,
                         text=True,timeout=600)
        output=p.stdout+"\n"+p.stderr
    except (OSError,subprocess.SubprocessError):
        output="EXCEPTION: test command unavailable or timed out"
        p=None
    fname=label+"-"+str(int(time.time()))+".log"
    path=_new_log(folder,fname,output)
    if p is None or p.returncode!=0:
        raise UpdateError("test gate failed, local log: "+path)
    return path


def apply(repo:Path, approved:dict, *, log_dir:Path,
          run=_exec, test=_run_test):
    root=repo.resolve(strict=True)
    expected=plan(root,current=approved["current"],target=approved["target"],run=run)
    if approved!=expected:
        raise UpdateError("update plan changed after approval")
    # The destination is tied to exactly the GitHub branch HEAD returned now.
    # This intentionally rejects a moving latest branch, even if SHA supplied
    # by an operator is an ancestor.
    run(["git","fetch","--no-tags","origin","refs/heads/"+BRANCH],root)
    fetched=run(["git","rev-parse","FETCH_HEAD"],root)
    if fetched!=approved["target"]:
        raise UpdateError("GitHub branch head differs from approved target SHA")
    old=approved["current"]
    switched=False
    try:
        run(["git","switch","--detach",approved["target"]],root)
        switched=True
        if run(["git","rev-parse","HEAD"],root)!=approved["target"]:
            raise UpdateError("post-checkout revision mismatch")
        # Security gate tests *must* actually run on Ubuntu, 0 skips.
        logs=[
            test([sys.executable,"tools/sse_ubuntu_security_gate.py",
                  "--expected-commit",approved["target"]],
                 root,log_dir,"ubuntu-security"),
            test([sys.executable,"-m","unittest","discover","-s","tests","-v"],
                 root,log_dir,"full-python"),
        ]
    except BaseException:
        if switched:
            try:
                run(["git","switch","--detach",old],root)
            except UpdateError:
                # Never force/reset; operator should examine the failed tree.
                raise UpdateError("new gate failed AND checkout rollback failed; manual recovery required") from None
        raise
    return {
        "kind":"SSE_R9_PINNED_SOURCE_UPDATED_V1",
        "gitCommit":approved["target"],
        "ubuntuAndPythonGatesPassed":True,
        "privateLogPaths":logs,
        "validatorsRestarted":False,
        "dockerContainersChanged":False,
        "dependenciesInstalled":False,
        "chainStateChanged":False,
        "ethereumTransactionsSent":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Explicit, exact-SHA GitHub update for STOPPED Ubuntu R9 source checkout")
    p.add_argument("--repo",type=Path,default=Path.cwd())
    p.add_argument("--approved-current",required=True)
    p.add_argument("--approved-target",required=True)
    p.add_argument("--private-log-dir",type=Path)
    p.add_argument("--apply",action="store_true")
    a=p.parse_args(argv)
    try:
        prepared=plan(a.repo,current=a.approved_current,target=a.approved_target)
        if a.apply:
            if not a.private_log_dir:
                raise UpdateError("--apply requires a protected existing private-log-dir")
            result=apply(a.repo,prepared,log_dir=a.private_log_dir)
        else:
            result=prepared
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (UpdateError,OSError,KeyError,ValueError,TypeError) as exc:
        print("SSE_R9_UPDATE_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
