#!/usr/bin/env python3
"""R358h: inspect local validator installation conflicts without exposing secrets.
No container start/stop/removal, key access, database writes or staking.
Docker inspect is processed locally; raw environment, arguments and logs
are never emitted. Names and bounded public filesystem metadata only.
"""
import json
import os
from pathlib import Path
import re
import stat
import subprocess

def docker(*args):
    return subprocess.check_output(["sudo","-n","docker",*args],text=True,timeout=20)

def info(p):
    if p.is_symlink():
        return {"kind":"symlink"}
    try:
        s=p.stat()
    except FileNotFoundError:
        return {"kind":"absent"}
    return {"kind":"directory" if stat.S_ISDIR(s.st_mode) else "regular" if stat.S_ISREG(s.st_mode) else "other",
            "ownerUid":s.st_uid,"mode":oct(stat.S_IMODE(s.st_mode)),"bytes":s.st_size}

def inspect():
    root=Path.home()/".local/share/sse31340-validator"
    vc=root/"lighthouse"
    ids=docker("ps","-aq").split()
    rows=[]
    for ident in ids:
        c=json.loads(docker("inspect",ident))[0]
        name=c["Name"].lstrip("/")
        args=[str(x) for x in c.get("Args",[])]
        tokens={x.lower() for x in args}
        signing=bool(tokens & {"vc","validator_client","validator-client"}) or any(
            x.startswith(("--validators-dir","--secrets-dir","--beacon-nodes")) for x in tokens)
        image=str(c.get("Config",{}).get("Image","")).lower()
        path=str(c.get("Path","")).lower()
        old_name_match=bool(re.search(r"validator|[-_]vc([_-]|$)",name,re.I))
        overlaps=[]
        for m in c.get("Mounts",[]):
            source=str(m.get("Source",""))
            if not source.startswith("/"):
                continue
            if source==str(root) or source.startswith(str(root)+"/") or str(root).startswith(source.rstrip("/")+"/"):
                overlaps.append(str(m.get("Destination","")))
        if old_name_match or signing or overlaps or "lighthouse" in image or "lighthouse" in path:
            rows.append({"name":name,"state":c["State"]["Status"],
                         "matchedOldNameGuard":old_name_match,
                         "signingCliIndicator":signing,
                         "lighthouseImageOrExecutable":"lighthouse" in image or "lighthouse" in path,
                         "validatorRootMountDestinations":overlaps,
                         "restartPolicy":c.get("HostConfig",{}).get("RestartPolicy",{}).get("Name")})
    paths={str(p.relative_to(root)):info(p) for p in (vc,vc/"validators",vc/"secrets",vc/"validators/slashing_protection.sqlite",vc/"validators/validator_definitions.yml")}
    # Do not traverse symlink directories or read any validator definitions.
    counts={}
    for parent in (vc,vc/"validators",vc/"secrets"):
        if parent.is_dir() and not parent.is_symlink() and not any(x.is_symlink() for x in (root,vc)):
            entries=list(parent.iterdir())
            counts[str(parent.relative_to(root))]={"entries":len(entries),"directories":sum(x.is_dir() and not x.is_symlink() for x in entries),"symlinks":sum(x.is_symlink() for x in entries)}
    return {"ownerUid":os.geteuid(),"validatorRoot":info(root),"paths":paths,"directoryCounts":counts,"relevantContainers":rows,"privateContentsRead":False,"stateChanged":False}

if __name__=="__main__":
    print(json.dumps(inspect(),indent=2,sort_keys=True))
