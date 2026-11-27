#!/usr/bin/env python3
"""R285: VM4714 only, verify EXACT three old exited hello-world containers.

Read-only safety gate for one owner-authorized real compute worker. It never
deletes, starts, stops, restarts, renames, creates or edits existing Docker
containers. The three pre-existing IDs/names originated in the owner's
2026-11-24 actual nonmutating 'sudo docker ps -a --no-trunc' output.
No general 'all exited containers are safe' shortcut is permitted.
"""
from __future__ import annotations

import argparse
import json
import os
import pwd
import re
import subprocess
import sys

ROOTFUL="unix:///var/run/docker.sock"
OWNER="ayoubakrvm4714"
EXPECTED={
    "0736e142f5d925c8a63771d6ce08d02cc2723509e06f9d3b638f35d306f88084":"serene_sammet",
    "dc71dc02b5e4375535c2fc69e90c0dc62322e72a4550b46e0c7f6d90f6e9434c":"friendly_saha",
    "ff494d7657a18a7f0a6ecce74ceb9edf97250c8ae64cacaa23aa166d8524aade":"zealous_wilson",
}
HEX_ID=re.compile(r"[a-f0-9]{64}\Z")


class Refused(ValueError):
    pass


def _call(args, *, run):
    env=dict(os.environ)
    for key in ("DOCKER_CONTEXT","DOCKER_HOST","DOCKER_TLS_VERIFY","DOCKER_CERT_PATH"):
        env.pop(key,None)
    command=["sudo","-n","docker","--host",ROOTFUL]+args
    try:
        result=run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                   text=True,check=False,shell=False,timeout=10,env=env)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise Refused("read-only local Docker CLI unavailable") from exc
    if result.returncode!=0:
        raise Refused("read-only local Docker CLI access denied or query failed")
    # Inspect of three existing Docker objects includes long HostConfig,
    # labels and environment. Permit a bounded 192KiB read-only response;
    # no stdout fields are passed to shell commands or executed.
    if type(result.stdout) is not str or len(result.stdout)>196608:
        raise Refused("Docker read-only response exceeds safe response limit")
    return result.stdout


def audit(*,run=subprocess.run,uid_fn=os.geteuid,username_fn=None):
    uid=uid_fn()
    if username_fn is None:
        username_fn=lambda n:pwd.getpwuid(n).pw_name
    if uid==0 or username_fn(uid)!=OWNER:
        raise Refused("run only as dedicated VM4714 nonroot owner")

    def ids():
        raw=_call(["ps","-a","--no-trunc","--format","{{.ID}}"],run=run)
        found=raw.splitlines()
        if (len(found)!=len(EXPECTED) or
            len(set(found))!=len(EXPECTED) or
            any(not HEX_ID.fullmatch(item) for item in found) or
            set(found)!=set(EXPECTED)):
            raise Refused("container inventory DIFFERENT from three exact owner-observed harmless IDs")
        return found

    first=ids()
    # Inspect only IDs already seen; Docker CLI read-only inspect MUST show
    # exact names and benign old image and stopped exit0 statuses.
    raw=_call(["container","inspect"]+sorted(first),run=run)
    try:
        detail=json.loads(raw)
    except (TypeError,ValueError) as exc:
        raise Refused("Docker inspect not valid JSON") from exc
    if type(detail) is not list or len(detail)!=len(EXPECTED):
        raise Refused("Docker inspect has wrong number of containers")
    verified=[]
    for d in detail:
        if type(d) is not dict:
            raise Refused("invalid Docker inspect object")
        id_=d.get("Id")
        name=d.get("Name")
        config=d.get("Config")
        state=d.get("State")
        if (id_ not in EXPECTED or type(config) is not dict or
            type(state) is not dict or
            name!="/"+EXPECTED[id_] or
            config.get("Image") not in ("hello-world","hello-world:latest") or
            state.get("Status")!="exited" or
            state.get("Running") is not False or
            state.get("Paused") is not False or
            state.get("Restarting") is not False or
            type(state.get("ExitCode")) is not int or
            state.get("ExitCode")!=0):
            raise Refused("unexpected/mutable Docker container image/name/runtime state")
        verified.append(id_)
    if len(set(verified))!=len(EXPECTED) or set(verified)!=set(EXPECTED):
        raise Refused("Docker inspect IDs different from observed container IDs")
    if set(ids())!=set(EXPECTED):
        raise Refused("Docker container inventory changed during inspection")
    return {
        "schema":"SSE_R285_VM4714_EXACT_THREE_OLD_EXITED_HELLOWORLD_NONMUTATING_AUDIT_V1",
        "actualDedicatedHostUser":OWNER,
        "exactThreeExistingContainerIdsNamesAndImagesVerified":True,
        "onlyThreeExistingOldExitedExitZeroContainers":True,
        "actualRunningPreexistingContainers":0,
        "verifiedOldContainers":[
            {"id":id_,"name":EXPECTED[id_],"image":"hello-world","status":"exited","exitCode":0}
            for id_ in sorted(EXPECTED)
        ],
        "newWorkerCreated":False,
        "oldContainerChanged":False,
        "nativeChainOrValidatorChanged":False,
        "transactionSignedOrSent":False,
        "safeToAttemptSeparateOwnerApprovedIsolatedWorker":True,
        "productionSlaOrHardwareAttestationProven":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--audit",action="store_true",
                   help="only real existing container read-only audit; no Docker writes")
    a=p.parse_args(argv)
    try:
        if not a.audit:
            raise Refused("--audit required; no mutation mode exists")
        print(json.dumps(audit(),indent=2,sort_keys=True))
        print("R285_EXACT_THREE_EXITED_HELLOWORLD_CONTAINERS_PRESERVED_READONLY=true")
        return 0
    except (Refused,ValueError,OSError,TypeError,KeyError) as exc:
        print("R285_VM4714_EXISTING_CONTAINERS_REFUSED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
