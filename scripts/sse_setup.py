#!/usr/bin/env python3
"""Single role-selection and preparation entry point for original chain31340.

Plan is default; --apply approves the displayed preparation plan once.
Fresh lightweight hosts use a pinned optional RPC adapter, not a forced full
node. Native fresh install is intentionally gated until verified checkpoint
onboarding is implemented. Existing native nodes are never reinstalled.
Wallets, gas permissions, validator keys and deposits remain owner-local
choices. Preparation is not activation or proof of synchronization.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
CHAIN_ROLES=("full_node","observer","validator")
APP_ROLES=("consumer","provider","monitor","keeper")
ROLES=CHAIN_ROLES+APP_ROLES
SHA=re.compile(r"^[0-9a-f]{40}$")

class Refused(ValueError):
    pass

def plan(roles,commit,publish_console=False,transport="auto",existing_native=False,existing_app=False):
    roles=list(dict.fromkeys(roles))
    if not roles or any(r not in ROLES for r in roles):
        raise Refused("invalid roles")
    if not SHA.fullmatch(commit or ""):
        raise Refused("exact reviewed commit required")
    chain=any(r in CHAIN_ROLES for r in roles)
    app=[r for r in roles if r in APP_ROLES]
    if transport=="auto":
        transport="local" if chain or existing_native else "relay"
    if transport not in ("local","relay"):
        raise Refused("invalid transport")
    if (chain or existing_native) and transport!="local":
        raise Refused("native roles require local EL/CL, not relay")
    if chain and not existing_native:
        return [{"id":"native-checkpoint-gate","blocked":True,"argv":[],
                 "note":"Fresh native onboarding blocked until verified recent original-chain checkpoint support; never bypass weak subjectivity."}]
    steps=[]
    def add(id,argv,note):
        steps.append(dict(id=id,argv=argv,note=note))
    if existing_native:
        add("verify-existing-native",[sys.executable,"-B","tools/sse_setup_verify_local_native.py"],"Verify actual local original EL/CL finality; preserve containers and keys.")
    if existing_app and not app:
        raise Refused("existing application transport needs application roles")
    if app and transport=="relay" and existing_app:
        add("app-python",["bash","scripts/sse_v4_prepare_python.sh",commit],"Owner-local Python environment.")
        add("verify-existing-rpc",["bash","scripts/sse_v4_verify_existing_rpc.sh",commit],"Check and update existing pinned adapter if needed; no native changes.")
    if app and transport=="relay" and not existing_app:
        add("app-host-prerequisites",["bash","scripts/sse_v4_prepare_app_host.sh",commit],"Fresh lightweight host only: Python and pinned optional TLS RPC adapter.")
    if app and transport=="local":
        add("app-python",["bash","scripts/sse_v4_prepare_python.sh",commit],"Owner-local application environment; no native changes.")
    if "validator" in roles:
        steps.append({"id":"validator-authorization-gate","blocked":True,"argv":[],
                      "note":"Validator enrollment/upgrade requires unique owner-generated BLS key, canonical deposit and signer/slashing protection reconciliation. Existing signer must never be duplicated."})
        return steps
    if app:
        python=str(Path.home()/".venvs/sse-v4/bin/python")
        argv=[python,"-B","scripts/sse_v4_app_install.py","--roles",",".join(app),"--prepare-only"]
        if publish_console:
            argv.append("--publish-readonly-console")
        add("v4-app-roles",argv,"Prepare wallet/policy/console; do not start signing or provider-output service.")
        add("linger",["sudo","-n","loginctl","enable-linger",str(os.getuid())],"Persist user console/adapter across logout.")
    return steps

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--roles",required=True)
    p.add_argument("--commit",required=True)
    p.add_argument("--transport",choices=("auto","local","relay"),default="auto")
    p.add_argument("--existing-native",action="store_true")
    p.add_argument("--existing-app",action="store_true",help="preserve existing application transport and wallets")
    p.add_argument("--publish-readonly-console",action="store_true")
    p.add_argument("--apply",action="store_true")
    a=p.parse_args(argv)
    try:
        if os.geteuid()==0:
            raise Refused("unprivileged owner required")
        steps=plan(a.roles.split(","),a.commit,a.publish_readonly_console,a.transport,a.existing_native,a.existing_app)
        print(json.dumps(dict(schema="SSE_SETUP_PLAN_V2",steps=steps,activationClaimed=False),indent=2),flush=True)
        if not a.apply:
            return 0
        if any(s.get("blocked") for s in steps):
            raise Refused("plan contains unresolved safety gate; no changes applied")
        actual=subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO,text=True).strip()
        dirty=subprocess.check_output(["git","status","--porcelain"],cwd=REPO,text=True)
        if actual!=a.commit or dirty:
            raise Refused("pinned clean source required")
        if input("Type PREPARE-SSE-ROLES to approve this preparation plan: ")!="PREPARE-SSE-ROLES":
            raise Refused("not authorized")
        for step in steps:
            print("== "+step["id"]+" ==",flush=True)
            rc=subprocess.call(step["argv"],cwd=REPO)
            if rc:
                print("Stopped at "+step["id"]+"; inspect before retry.")
                return rc
        print("SSE_ROLE_PREPARATION_COMPLETE=true; signing, funding and workload admission not claimed")
        return 0
    except Refused as exc:
        print("SSE_SETUP_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
