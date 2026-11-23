#!/usr/bin/env python3
"""R147 public single-repository Ubuntu 24.04 bootstrap.

This release implements authenticated public SOURCE acquisition + one-time
role selection. Client launch is deliberately blocked until actual original
genesis archive and native dynamic discovery are publicly available. Never
claims source installation is a joined chain or activated role.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

REPOSITORY = "https://github.com/AkrAyoub/sse-research.git"
ROLES = ("full_node", "observer", "validator", "provider", "consumer", "monitor")
TARGET_ROOT = Path("/opt/sse/releases")
STATE = Path("/var/lib/sse/selection.json")
SCHEMA = "SSE_R147_PUBLIC_INSTALL_V1"
HEX_COMMIT = re.compile(r"[0-9a-f]{40}\Z")

class Refused(ValueError):
    pass

def select_roles(input_fn=input, output=print):
    output("SSE chain31340: select roles (the only installer prompt).")
    for i, role in enumerate(ROLES, 1):
        output(f" {i}. {role}")
    raw = input_fn("Enter role numbers separated by commas: ")
    if type(raw) is not str:
        raise Refused("invalid selection")
    choices = [s.strip() for s in raw.split(",")]
    if not choices or any(not s.isdigit() or not 1 <= int(s) <= 6
                          for s in choices):
        raise Refused("invalid role choices")
    selected = [ROLES[int(n)-1] for n in choices]
    return check_roles(selected)

def check_roles(roles):
    if type(roles) is not list or not roles or len(roles) != len(set(roles)):
        raise Refused("invalid or duplicate roles")
    if any(type(r) is not str or r not in ROLES for r in roles):
        raise Refused("unsupported roles")
    return roles

def identity(value):
    if not HEX_COMMIT.fullmatch(value):
        raise Refused("full immutable 40-character release SHA required")
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise Refused("reviewed Linux x86_64 machine required")
    if Path("/etc/os-release").exists():
        data = Path("/etc/os-release").read_text()
        if not (re.search(r'^ID=ubuntu$', data, flags=re.M)
                and re.search(r'^VERSION_ID="?24\.04"?$', data, flags=re.M)):
            raise Refused("Ubuntu 24.04 required for unattended package installation")
    return value

def guard_existing(root=Path("/")):
    # Observe only: existing genesis/validator data must never be modified.
    paths = [root / "var/lib/sse/selection.json",
             root / "var/lib/sse/validator",
             root / "var/lib/sse/chain31340"]
    home = root / "home"
    if home.exists():
        for candidate in home.iterdir():
            state = candidate / ".local/share"
            paths.extend(state / name for name in (
                "sse-r35-chain31340-g2-private",
                "sse-r27-bls-operator-private",
                "sse-r59-chain31340-observer"))
            paths.extend(state.glob("sse-r137-*"))
    if any(p.exists() or p.is_symlink() for p in paths):
        raise Refused("existing SSE state; refuse overwrite and duplicate signer")

def build_plan(commit, roles, node_id):
    return {
        "schema": SCHEMA, "network": "chain31340",
        "sourceCommit": commit, "nodeId": node_id,
        "selectedRoles": check_roles(roles),
        "roleSelectionRecorded": False,
        "publicSourceDownloaded": False,
        "genesisVerified": False, "nativePeersDiscovered": False,
        "executionAndBeaconClientsStarted": False,
        "validatorKeyOrEoaCreated": False, "stakeOrBondFunded": False,
        "marketplaceRolesActivated": False,
        "chainGenesisRecreated": False,
        "installerPhase": "PUBLIC_SOURCE_ONLY_PENDING_REAL_NETWORK_ARTIFACTS",
    }

def command(args, timeout=120):
    try:
        result = subprocess.run(args, check=False, text=True,
                                capture_output=True, timeout=timeout,
                                env={**os.environ,"DEBIAN_FRONTEND":"noninteractive",
                                     "NEEDRESTART_MODE":"a",
                                     "GIT_TERMINAL_PROMPT":"0"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Refused("host command unavailable") from exc
    if result.returncode:
        raise Refused("host prerequisite or GitHub command failed")
    return result.stdout.strip()

def install_source(commit, plan, root=TARGET_ROOT, state=STATE):
    if os.geteuid() != 0:
        raise Refused("run with sudo/root; no repeated privilege prompts")
    guard_existing()
    release = root / commit
    if release.exists() or release.is_symlink():
        raise Refused("release checkout already exists; never overwrite")
    command(["apt-get","update","-qq"], timeout=180)
    command(["apt-get","install","-y","-qq","--no-install-recommends",
             "git","python3","ca-certificates","curl","iproute2"],timeout=180)
    root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".r147-",dir=root) as tmp:
        checkout = Path(tmp) / "repo"
        command(["git","-c","credential.helper=","clone","--no-checkout",
                 REPOSITORY,str(checkout)], timeout=180)
        command(["git","-C",str(checkout),"cat-file","-e",commit+"^{commit}"])
        command(["git","-C",str(checkout),"switch","--detach",commit])
        if command(["git","-C",str(checkout),"rev-parse","HEAD"]) != commit:
            raise Refused("source SHA mismatch")
        # Release descriptor carries exact public genesis identity and
        # replaceable artifact sources; never a hardcoded bootstrap host/IP.
        sys.path.insert(0,str(checkout/"tools"))
        import sse_public_genesis as public_genesis
        release_data=public_genesis.read_manifest(
            checkout/"release/chain31340-public-release.json")
        if release_data["originalGenesisArchiveSources"]:
            result_archive=public_genesis.acquire(
                release_data,Path(tmp)/"original-chain31340.tar.gz")
            if not result_archive["sha256Verified"]:
                raise Refused("unverified original genesis archive")
            # Do not pretend archived data are a live synchronized node.
            plan["originalGenesisArchiveAcquired"]=True
        else:
            # Do not leave a fresh VM with a permanent, misleading
            # /var/lib/sse/selection.json and a release checkout that
            # refuses all retries. This state happened before R163 publication.
            # Retry of the same immutable release remains possible when the
            # public original archive is genuinely distributed.
            raise Refused("PUBLIC_ORIGINAL_GENESIS_NOT_YET_AVAILABLE: no source-only pseudo-install")
        # The existing local role engine is reused; it is only a plan, never
        # silently advertised as on-chain authority.
        node_id=plan["nodeId"]
        result=command(["python3","-B",str(checkout/"tools/sse_join.py"),
                        "--node-id",node_id,
                        "--roles",",".join(plan["selectedRoles"]),"--plan"])
        report=json.loads(result)
        expected = list(plan["selectedRoles"])
        if ("validator" in expected and
                not set(expected).intersection({"full_node", "observer"})):
            expected.insert(0, "full_node")
        if report.get("nodeId") != node_id or report.get("selectedRoles") != expected:
            raise Refused("unified role configuration disagrees")
        plan["selectedRoles"] = expected
        shutil.move(str(checkout),str(release))
        # Public archive source, when real and verified, is kept with exact
        # pinned release, never injected into an existing signer data dir.
        verified_archive=Path(tmp)/"original-chain31340.tar.gz"
        if verified_archive.exists():
            shutil.move(str(verified_archive),str(release/"original-chain31340.tar.gz"))
    state.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    data={**plan,"publicSourceDownloaded":True,"roleSelectionRecorded":True}
    fd=os.open(str(state),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as dest:
        json.dump(data,dest,indent=2,sort_keys=True)
        dest.write("\n")
    # After the only role-choice prompt, continue automatically into
    # the genuine reviewed R137 Docker/Besu/Lighthouse installation.
    # Never do this unless the exact original PUBLIC genesis was acquired
    # and verified. No new genesis or validator key is ever generated.
    full_roles = {"full_node", "observer", "validator"}
    if not full_roles.intersection(data["selectedRoles"]):
        # Application agents are not implemented in this entry point.
        # Never write installed success for consumer/provider/monitor.
        raise Refused("MARKETPLACE_ROLE_INSTALLER_NOT_YET_IMPLEMENTED")
    if (full_roles.intersection(data["selectedRoles"])
            and (release/"original-chain31340.tar.gz").is_file()):
        command(["python3","-B",str(release/"tools/sse_pos_r151_unattended_full_node.py"),
                 "--execute"],timeout=900)
        data["realNonsigningClientsSubmitted"] = True
        data["nativeP2pAndFinalityVerified"] = False
    else:
        data["realNonsigningClientsSubmitted"] = False
        data["nativeP2pAndFinalityVerified"] = False
    return data

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--commit",required=True)
    p.add_argument("--roles",help="comma-separated roles; omit for one menu")
    p.add_argument("--plan",action="store_true",help="zero mutation")
    args=p.parse_args(argv)
    try:
        commit=identity(args.commit)
        selected=check_roles(args.roles.split(",")) if args.roles is not None else select_roles()
        machine=Path("/etc/machine-id")
        if not machine.exists():
            raise Refused("machine-id unavailable")
        mid=machine.read_text().strip()
        if not re.fullmatch(r"[0-9a-f]{32}",mid):
            raise Refused("invalid independent host machine-id")
        node_id="node-"+hashlib.sha256(mid.encode("ascii")).hexdigest()[:20]
        plan=build_plan(commit,selected,node_id)
        if args.plan:
            print(json.dumps(plan,sort_keys=True,indent=2))
            return 0
        result=install_source(commit,plan)
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (Refused,ValueError,TypeError,OSError,KeyError) as exc:
        print("R147_PUBLIC_INSTALL_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
