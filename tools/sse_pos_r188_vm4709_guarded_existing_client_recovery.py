#!/usr/bin/env python3
"""R188: guarded recovery of EXACT existing VM4709 observer EL+CL.

--plan: read-only actual Docker inspection, SHA/checkpoint and DB checks.
--execute: explicit authorization; preserves old containers and old Beacon DB
under unique backup names; stages fresh Beacon DB with locally copied P2P key.
No validator, signer, genesis or Engine JWT modifications or WS bypass.
"""
from __future__ import annotations
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

NODE="node-8be265272c35f3d8c3a0"
PREFIX="sse31340-r137-"+NODE
NETWORK=PREFIX
OLD={"el":PREFIX+"-el","bn":PREFIX+"-bn"}
BACKUP={k:v+"-r188-preserved" for k,v in OLD.items()}
IDS={"el":"sha256:4fd2ba40f0d65917bcb3abd9af60673946f66dee2ecb1b87f7cdfa6a30fe458d",
     "bn":"sha256:53f9063d98c3d3a2d290207873f019ea2298cfc02f8cd58d87c33b04aab856d1"}
ROOT=Path("/root/.local/share/sse-r137-"+NODE)
ORIGINAL_BEACON=ROOT/"beacon"
FRESH_BEACON=ROOT/"beacon-r188-checkpoint-e565"
CHECKPOINT=Path("/home/ayoubakrvm4709/sse-chain31340-checkpoint-e565")
GENESIS="0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd"
BLOCK_ROOT="0x86fdc98df47d641a27fbc95eb3229dfc0e24553d1dc57bfbe2599e161b60a259"
PIN={
 "checkpoint-state.ssz":(2859760,"8c03cdec390bb9442d7ac8d98a01a1d6dc03861602bf085d95553554ea5a1d41"),
 "checkpoint-block.ssz":(1417,"9e2859ca4e57bf1228d010bd7958483ee111b4ec10d39c5d5aa82f691c702373"),
}
PORTS={"el":{"30404/tcp","30404/udp","8545/tcp"},
       "bn":{"9000/tcp","9000/udp","9001/udp","5052/tcp"}}
AUTH="RECOVER-VM4709-PRESERVING-OLD-CLIENTS"
class Refused(ValueError):pass

def docker(*args):
    r=subprocess.run(["docker",*args],text=True,capture_output=True,timeout=45,check=False)
    if r.returncode:
        raise Refused("R188_DOCKER_COMMAND_FAILED_"+args[0])
    return r.stdout.strip()

def exact_inspect(name):
    try:
        data=json.loads(docker("inspect",name))
    except (ValueError,TypeError) as exc:
        raise Refused("R188_INVALID_DOCKER_INSPECTION") from exc
    if type(data) is not list or len(data)!=1 or data[0].get("Name")!="/"+name:
        raise Refused("R188_UNEXPECTED_CONTAINER_IDENTITY")
    return data[0]

def verify_checkpoint():
    for filename,(size,expected) in PIN.items():
        path=CHECKPOINT/filename
        if path.is_symlink() or not path.is_file() or path.stat().st_size!=size:
            raise Refused("R188_CHECKPOINT_MISSING_OR_UNEXPECTED_SIZE_"+filename)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise Refused("R188_CHECKPOINT_HASH_MISMATCH_"+filename)
    mf=CHECKPOINT/"checkpoint-manifest.json"
    if mf.is_symlink() or not mf.is_file() or mf.stat().st_size>4096:
        raise Refused("R188_CHECKPOINT_MANIFEST_INVALID")
    m=json.loads(mf.read_text("utf-8"))
    if (m.get("genesisValidatorsRoot")!=GENESIS
        or m.get("finalizedBlockRoot")!=BLOCK_ROOT
        or m.get("chainId")!=31340 or m.get("finalizedEpoch")!=565
        or m.get("finalizedSlot")!=18080):
        raise Refused("R188_CHECKPOINT_IDENTITY_MISMATCH")
    return True

def get_port_bindings(role,data):
    bindings=(data.get("HostConfig") or {}).get("PortBindings")
    if type(bindings) is not dict or set(bindings)!=PORTS[role]:
        raise Refused("R188_UNEXPECTED_PUBLISHED_PORTS_"+role)
    formatted=[]
    expected_host_ip=None
    for port,items in sorted(bindings.items()):
        if type(items) is not list or len(items)!=1:
            raise Refused("R188_AMBIGUOUS_PORT_BINDINGS")
        item=items[0]
        host_ip=item.get("HostIp")
        host_port=item.get("HostPort")
        internal_port,proto=port.split("/")
        if not str(host_port).isdecimal():
            raise Refused("R188_INVALID_DOCKER_HOST_PORT")
        if internal_port in ("8545","5052"):
            if (host_ip!="127.0.0.1" or
                    host_port!=("28545" if role=="el" else "25052")):
                raise Refused("R188_PRIVILEGED_RPC_NOT_LOOPBACK")
            formatted.append(f"127.0.0.1:{host_port}:{port}")
        else:
            try:
                ip=ipaddress.ip_address(host_ip)
            except ValueError as exc:
                raise Refused("R188_INVALID_PEER_IPV6") from exc
            if ip.version!=6 or not str(ip).lower().startswith("fca0:2328:"):
                raise Refused("R188_UNEXPECTED_P2P_INTERFACE")
            if expected_host_ip is None:
                expected_host_ip=host_ip
            elif expected_host_ip!=host_ip:
                raise Refused("R188_MIXED_P2P_INTERFACES")
            if host_port!=internal_port:
                raise Refused("R188_UNEXPECTED_P2P_PORT_TRANSLATION")
            formatted.append(f"[{host_ip}]:{host_port}:{port}")
    return formatted

def verify_container(role):
    data=exact_inspect(OLD[role])
    if data.get("Image")!=IDS[role]:
        raise Refused("R188_PINNED_IMAGE_MISMATCH_"+role)
    cfg=data.get("Config") or {}
    host=data.get("HostConfig") or {}
    if (not host.get("ReadonlyRootfs") or
        set(host.get("CapDrop") or [])!={"ALL"} or
        "no-new-privileges" not in (host.get("SecurityOpt") or []) or
        cfg.get("User") not in ("0:0","0")):
        raise Refused("R188_SECURITY_CONFIGURATION_MISMATCH_"+role)
    if (host.get("NetworkMode")!=NETWORK or
        (host.get("RestartPolicy") or {}).get("Name")!="unless-stopped"):
        raise Refused("R188_NETWORK_OR_RESTART_POLICY_MISMATCH_"+role)
    mounts=data.get("Mounts")
    if type(mounts) is not list or len(mounts)!=3:
        raise Refused("R188_UNEXPECTED_MOUNTS_"+role)
    expected={"/testnet":(ROOT/"testnet",False),
              "/jwt/engine.jwt":(ROOT/"engine.jwt",False),
              "/data":(ROOT/("el" if role=="el" else "beacon"),True)}
    for mount in mounts:
        destination=mount.get("Destination")
        if destination not in expected or mount.get("Type")!="bind":
            raise Refused("R188_UNEXPECTED_MOUNT_"+role)
        source,writable=expected[destination]
        if mount.get("Source")!=str(source) or bool(mount.get("RW"))!=writable:
            raise Refused("R188_ORIGINAL_DATA_BINDING_MISMATCH_"+role)
    cmd=cfg.get("Cmd")
    if type(cmd) is not list or not cmd or any(type(x) is not str for x in cmd):
        raise Refused("R188_BAD_ORIGINAL_CLIENT_CMD")
    if role=="el":
        if cfg.get("Entrypoint")!=["besu-entry.sh"]:
            raise Refused("R188_UNEXPECTED_EL_ENTRYPOINT")
        if not any(x=="--network-id=31340" for x in cmd):
            raise Refused("R188_WRONG_EL_CHAIN")
    else:
        if cfg.get("Entrypoint")!=["lighthouse"]:
            raise Refused("R188_UNEXPECTED_CL_ENTRYPOINT")
        if "bn" not in cmd or not any(x=="--testnet-dir=/testnet" for x in cmd):
            raise Refused("R188_WRONG_CL_NETWORK")
        if any(x.startswith("--checkpoint") or x=="--ignore-ws-check" for x in cmd):
            raise Refused("R188_EXISTING_CL_UNEXPECTED_CHECKPOINT")
    return data,cmd,get_port_bindings(role,data)

def plan():
    if os.geteuid()!=0:
        raise Refused("R188_REQUIRES_ROOT")
    verify_checkpoint()
    if any((ROOT/x).is_symlink() for x in ("testnet","beacon","el","engine.jwt")):
        raise Refused("R188_ORIGINAL_PATH_SYMLINK")
    if not ORIGINAL_BEACON.is_dir() or not (ORIGINAL_BEACON/"beacon/chain_db").is_dir():
        raise Refused("R188_ORIGINAL_BEACON_DB_NOT_PRESENT")
    network_key=ORIGINAL_BEACON/"beacon/network/key"
    if network_key.is_symlink() or not network_key.is_file() or network_key.stat().st_size!=64:
        raise Refused("R188_MISSING_OR_UNEXPECTED_ORIGINAL_P2P_KEY")
    if FRESH_BEACON.exists() or FRESH_BEACON.is_symlink():
        raise Refused("R188_FRESH_DATA_DIR_ALREADY_EXISTS")
    if any(docker("ps","-aq","--filter","name=^/"+BACKUP[k]+"$") for k in BACKUP):
        raise Refused("R188_BACKUP_CONTAINERS_ALREADY_EXIST")
    info={role:verify_container(role) for role in OLD}
    return {"schema":"SSE_R188_GUARDED_EXISTING_VM4709_RECOVERY_PLAN_V1",
            "nodeId":NODE,"originalContainerNames":[OLD[k] for k in ("el","bn")],
            "backupContainerNames":[BACKUP[k] for k in ("el","bn")],
            "pinnedImageIdsVerified":True,"originalP2pIdentityWillBeCopiedLocally":True,
            "originalBeaconDatabaseWillBePreserved":True,
            "originalJwtAndGenesisWillBeReusedWithoutEditing":True,
            "checkpointSha256AndIdentityVerified":True,
            "checkpointConsensusAcceptanceVerified":False,
            "networkP2pBindingsWillBePreserved":True,
            "nativePeerAndFinalityVerified":False},info

def runner_args(role, cmd, bindings):
    name=OLD[role]
    base=["run","-d","--pull","never","--platform","linux/amd64",
          "--name",name,"--hostname",name,
          "--restart","unless-stopped","--stop-timeout","60","--init",
          "--network",NETWORK,"--user","0:0","--read-only","--cap-drop","ALL",
          "--security-opt","no-new-privileges",
          "--cpus","1.5" if role=="bn" else "2",
          "--memory","4g","--pids-limit","384",
          "--tmpfs","/tmp:rw,nosuid,"+("noexec" if role=="bn" else "exec")+",size=256m"]
    base+=["--mount",f"type=bind,source={ROOT/'testnet'},target=/testnet,readonly"]
    base+=["--mount",f"type=bind,source={ROOT/'engine.jwt'},target=/jwt/engine.jwt,readonly"]
    path=FRESH_BEACON if role=="bn" else ROOT/"el"
    base+=["--mount",f"type=bind,source={path},target=/data"]
    if role=="bn":
        base+=["--mount",f"type=bind,source={CHECKPOINT},target=/checkpoint,readonly"]
    for port in bindings:base+=["--publish",port]
    base+=["--entrypoint","lighthouse" if role=="bn" else "/opt/besu/bin/besu",IDS[role]]
    if role=="bn":
        cmd=[x for x in cmd if x!="--allow-insecure-genesis-sync"]
        cmd=cmd+["--checkpoint-state=/checkpoint/checkpoint-state.ssz",
                 "--checkpoint-block=/checkpoint/checkpoint-block.ssz"]
    return base+cmd

def execute(info):
    # Non-destructive stage first. Original identity remains in original DB.
    # Only a private local copy of original peer identity is created.
    FRESH_BEACON.mkdir(mode=0o700)
    path=FRESH_BEACON/"beacon/network"
    path.mkdir(parents=True,mode=0o700)
    source=ORIGINAL_BEACON/"beacon/network/key"
    destination=path/"key"
    fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(source.read_bytes())
        f.flush()
        os.fsync(f.fileno())
    print("R188_FRESH_BEACON_DATA_STAGED_OLD_DB_PRESERVED=true",flush=True)
    # No --rm, no container deletion, no data-root deletion.
    # Stop and rename original objects for rollback.
    for role in ("bn","el"):
        docker("stop","--time","60",OLD[role])
        docker("rename",OLD[role],BACKUP[role])
        print("R188_OLD_"+role.upper()+"_CONTAINER_RENAMED_PRESERVED=true",flush=True)
    for role in ("el","bn"):
        _,cmd,ports=info[role]
        docker(*runner_args(role,cmd,ports))
        print("R188_NEW_"+role.upper()+"_CONTAINER_SUBMITTED=true",flush=True)
    return {"status":"NEW_CLIENT_CONTAINERS_SUBMITTED_AWAITING_NATIVE_EVIDENCE",
            "oldContainersPreserved":True,
            "newClientsNativePeersVerified":False,
            "finalizedCheckpointVerified":False}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan",action="store_true")
    group.add_argument("--execute",action="store_true")
    p.add_argument("--authorize",default="")
    args=p.parse_args(argv)
    try:
        report,info=plan()
        if args.execute:
            if args.authorize!=AUTH:
                raise Refused("R188_EXPLICIT_AUTHORIZATION_REQUIRED")
            report.update(execute(info))
        else:
            report["status"]="READ_ONLY_SAFE_PLAN"
        print(json.dumps(report,indent=2,sort_keys=True))
        return 0
    except (Refused,OSError,ValueError,TypeError,KeyError,subprocess.TimeoutExpired) as exc:
        print("R188_GUARDED_RECOVERY_REFUSED: "+str(exc),file=sys.stderr)
        return 2
if __name__=="__main__":
    raise SystemExit(main())
