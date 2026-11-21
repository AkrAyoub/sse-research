#!/usr/bin/env python3
"""R65: preserve original chain31340 and signer when enabling PUBLIC-overlay P2P.

--plan: strictly read-only. --apply: explicit owner approval, *maintenance
restart* of EL, Beacon and existing VC (NO new VC or keystore), preserve old
containers stopped for rollback, reuse exact private data mounts + JWT and
pinned images. Host publication only actual ZeroTier 6plane IPv6 native P2P
and LOCALHOST RPC/REST; no Engine8551, no private-provider-LAN peer.
The original owner is one real validator; brief downtime affects liveness.
"""
from __future__ import annotations
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import sse_pos_r64_owner_native_public_p2p_migration_audit as r64
import sse_pos_r62_original_container_namespace_health as r62
import sse_pos_r59_native_ipv6_observer as r59

OWNER=r64.r63.r60
EL=OWNER.EL
BN=OWNER.BN
VC=OWNER.VC
TRUSTED=OWNER.NET
PUBLIC_BRIDGE="sse31340-g2-r65-public-p2p"
PRESERVED={EL:EL+"-r65-preserved",BN:BN+"-r65-preserved"}
BESU_ID=r59.BESU_ID
LIGHTHOUSE_ID=r59.LIGHTHOUSE_ID
BESU_REF=r59.BESU_REF
LIGHTHOUSE_REF=r59.LIGHTHOUSE_REF

class R65Refused(ValueError):
    pass

def docker(args:list[str],timeout:int=40)->str:
    try:
        p=subprocess.run(["sudo","-n","docker",*args],capture_output=True,
                         text=True,errors="replace",timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise R65Refused("reviewed Docker operation timed out/unavailable") from exc
    if p.returncode!=0 or len(p.stdout)>300_000:
        # Never show Docker stderr or raw inspect JSON. May include private paths.
        raise R65Refused("reviewed Docker operation failed; inspect original saved containers")
    return p.stdout.strip()

def get_json(args:list[str])->object:
    try:
        return json.loads(docker(args))
    except (ValueError,UnicodeError) as exc:
        raise R65Refused("Docker metadata invalid") from exc

def not_exists(kind:str,name:str)->None:
    try:
        p=subprocess.run(["sudo","-n","docker",kind,"inspect",name],
                         capture_output=True,timeout=12)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise R65Refused("Docker pre-existing resource check unavailable") from exc
    if p.returncode==0:
        raise R65Refused("existing migration resource; refuse to overwrite or rerun")
    if p.returncode!=1:
        raise R65Refused("cannot prove migration resource absent")

def normalized_entrypoint(value:object)->tuple[str,...]:
    """Normalize only Docker's absent/empty Entrypoint representation."""
    if value is None or value==[]:
        return ()
    if not isinstance(value,list) or any(
        not isinstance(item,str) or not item for item in value
    ):
        raise R65Refused("container/image entrypoint metadata invalid")
    return tuple(value)


def normalized_env(value:object)->dict[str,str]:
    """Compare exact environment keys AND values; print neither.

    Order is not semantically significant for Docker's environment entries.
    Reject duplicate variables rather than accidentally accepting ambiguity.
    """
    if value is None or value==[]:
        return {}
    if not isinstance(value,list):
        raise R65Refused("container/image environment metadata invalid")
    result:dict[str,str]={}
    for item in value:
        if not isinstance(item,str) or "=" not in item:
            raise R65Refused("container/image environment metadata malformed")
        key,val=item.split("=",1)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,100}",key) or key in result:
            raise R65Refused("container/image environment key invalid or duplicated")
        if len(val)>32768 or "\x00" in val:
            raise R65Refused("container/image environment value malformed")
        result[key]=val
    return result


def verify_unmodified_image_launch_config(
    container:dict,image:dict,name:str|None=None
)->str|None:
    """Preserve only the observed, strictly known Lighthouse entrypoint override.

    The immutable Lighthouse image has no ENTRYPOINT and defaults to /bin/bash;
    the running original Beacon container explicitly launches `lighthouse`.
    A replacement must pass `--entrypoint lighthouse` rather than inherit bash.
    Besu must retain its exact original image entrypoint. No arbitrary override.
    """
    a=normalized_entrypoint(container.get("Entrypoint"))
    b=normalized_entrypoint(image.get("Entrypoint"))
    override=None
    if a!=b:
        if name==BN and a==("lighthouse",) and b==():
            override="lighthouse"
        else:
            raise R65Refused(
                "original entrypoint differs from immutable image: "
                f"container_argv_count={len(a)} image_argv_count={len(b)}"
            )
    aenv=normalized_env(container.get("Env"))
    benv=normalized_env(image.get("Env"))
    added=set(aenv)-set(benv)
    missing=set(benv)-set(aenv)
    changed={key for key in set(aenv)&set(benv) if aenv[key]!=benv[key]}
    if added or missing or changed:
        raise R65Refused(
            "original environment differs from immutable image: "
            f"added_key_count={len(added)} missing_key_count={len(missing)} "
            f"changed_value_count={len(changed)}; no contents shown"
        )
    return override


def original_definition(name:str)->dict:
    if name not in (EL,BN):
        raise R65Refused("only original execution and beacon processes may be re-created")
    snap=get_json(["inspect","--format","{{json .}}",name])
    if not isinstance(snap,dict):
        raise R65Refused("original native container inspect unexpected")
    config=snap.get("Config")
    host=snap.get("HostConfig")
    state=snap.get("State")
    mounts=snap.get("Mounts")
    networks=(snap.get("NetworkSettings") or {}).get("Networks")
    if not all(isinstance(x,dict) for x in (config,host,state,networks)):
        raise R65Refused("native Docker config malformed")
    if not state.get("Running") or host.get("NetworkMode")!=TRUSTED or set(networks)!={TRUSTED}:
        raise R65Refused("original running native client bridge changed")
    expected_id=BESU_ID if name==EL else LIGHTHOUSE_ID
    if snap.get("Image")!=expected_id:
        raise R65Refused("native image not exact pinned immutable ID")
    ref=BESU_REF if name==EL else LIGHTHOUSE_REF
    image=get_json(["image","inspect","--format","{{json .Config}}",ref])
    if not isinstance(image,dict):
        raise R65Refused("pinned image config unreadable")
    entrypoint_override=verify_unmodified_image_launch_config(config,image,name)
    if config.get("WorkingDir")!=image.get("WorkingDir"):
        raise R65Refused("custom working directory requires separate review")
    if host.get("Privileged") or host.get("ReadonlyRootfs") is not True:
        raise R65Refused("original root filesystem security not preserved")
    if not host.get("Init") or "ALL" not in (host.get("CapDrop") or []):
        raise R65Refused("original capability/init restrictions not preserved")
    if not any(item in ("no-new-privileges", "no-new-privileges:true", "no-new-privileges=true") for item in (host.get("SecurityOpt") or [])):
        raise R65Refused("original no-new-privileges missing")
    user=config.get("User")
    if not isinstance(user,str) or not re.fullmatch(r"[0-9]{1,7}:[0-9]{1,7}",user):
        raise R65Refused("original native process uid/gid not numeric")
    if not isinstance(mounts,list) or len(mounts)!=3:
        raise R65Refused("original native mount count changed")
    targets={m.get("Destination") for m in mounts if isinstance(m,dict)}
    if targets!={"/testnet","/jwt/engine.jwt","/data"}:
        raise R65Refused("original data, genesis or JWT mount destinations differ")
    owner_root=OWNER.OWNER.resolve(strict=True)
    for m in mounts:
        if m.get("Type")!="bind" or not isinstance(m.get("Source"),str):
            raise R65Refused("only exact existing bind-mounted owner state supported")
        source=Path(m["Source"])
        if source.is_symlink() or not source.exists():
            raise R65Refused("original private mount does not exist or is symlink")
        # Never permit copying/reading arbitrary host locations in launch.
        if os.path.commonpath((str(owner_root),str(source.resolve(strict=True))))!=str(owner_root):
            raise R65Refused("mount lies outside unchanged original owner state")
        if m["Destination"] in ("/testnet","/jwt/engine.jwt") and m.get("RW") is not False:
            raise R65Refused("genesis and Engine JWT binds must be readonly")
        if m["Destination"]=="/data" and m.get("RW") is not True:
            raise R65Refused("original database must remain writable")
    tmpfs=host.get("Tmpfs") or {}
    if not isinstance(tmpfs,dict) or "/tmp" not in tmpfs:
        raise R65Refused("original temporary filesystem policy changed")
    cmd=config.get("Cmd")
    if not isinstance(cmd,list) or not cmd or not all(isinstance(x,str) for x in cmd):
        raise R65Refused("original native CLI command malformed")
    if name==EL and not any(x=="--p2p-enabled=false" for x in cmd):
        raise R65Refused("original Besu P2P-disable flag no longer exact")
    if name==BN and "bn" not in cmd:
        raise R65Refused("expected original Lighthouse Beacon subcommand")
    if int(host.get("Memory") or 0)<=0 or int(host.get("PidsLimit") or 0)<=0:
        raise R65Refused("original native memory/pid policy unexpected")
    port=host.get("PortBindings") or {}
    if not isinstance(port,dict):
        raise R65Refused("original host port bindings unreadable")
    # Preserve exact trusted chain process data; no validator keys touched.
    return {"name":name,"image":ref,"cmd":cmd,"mounts":mounts,"config":config,
            "host":host,"network":networks[TRUSTED],
            "entrypoint_override":entrypoint_override}

def validated_host_ports(ip:str)->dict[str,list[str]]:
    try:
        address=ipaddress.IPv6Address(ip)
    except ValueError as exc:
        raise R65Refused("public P2P host endpoint is not real IPv6") from exc
    if address not in ipaddress.IPv6Network("fca0::/16"):
        raise R65Refused("public native ports require actual 6plane IPv6 host")
    return {
        EL:[f"[{ip}]:30404:30404/tcp",f"[{ip}]:30404:30404/udp",
            "127.0.0.1:18545:8545/tcp"],
        BN:[f"[{ip}]:9000:9000/tcp",f"[{ip}]:9000:9000/udp",
            f"[{ip}]:9001:9001/udp","127.0.0.1:15052:5052/tcp"],
    }

def revised_cmd(name:str,original:list[str],ipv6:str)->list[str]:
    if name not in (EL,BN):
        raise R65Refused("cannot modify validator signer startup")
    if name==EL:
        replacements={
            "--p2p-enabled=true","--discovery-enabled=true","--discovery-mode=BOTH",
            "--p2p-interface=0.0.0.0","--p2p-host=127.0.0.1",
            "--p2p-interface-ipv6=::","--p2p-host-ipv6="+ipv6,
            "--p2p-port=30303","--p2p-port-ipv6=30404",
            "--p2p-discovery-port-ipv6=30404",
            "--p2p-ipv6-outbound-enabled=true","--nat-method=NONE",
        }
        keys={x.split("=",1)[0] for x in replacements}
        result=[a for a in original if a.split("=",1)[0] not in keys]
        result.extend(sorted(replacements))
        return result
    replacements=[
        "--listen-address=::","--port6=9000","--discovery-port6=9000",
        "--quic-port6=9001","--enr-address="+ipv6,
        "--enr-tcp6-port=9000","--enr-udp6-port=9000",
        "--enr-quic6-port=9001","--enable-private-discovery","--disable-upnp",
    ]
    keys={x.split("=",1)[0] for x in replacements}
    result=[a for a in original if a.split("=",1)[0] not in keys]
    result.extend(replacements)
    return result

def clone_args(definition:dict,ipv6:str)->list[str]:
    name=definition["name"]
    host=definition["host"]
    config=definition["config"]
    args=["create","--pull","never","--platform","linux/amd64",
          "--name",name,"--hostname",name,"--init","--stop-timeout","90",
          "--network",TRUSTED,
          "--read-only","--cap-drop","ALL",
          "--security-opt","no-new-privileges",
          "--user",config["User"],"--memory",str(host["Memory"]),
          "--pids-limit",str(host["PidsLimit"])]
    if host.get("NanoCpus"):
        args.extend(["--cpus",str(host["NanoCpus"]/1_000_000_000)])
    elif host.get("CpuQuota") and host.get("CpuPeriod"):
        args.extend(["--cpu-quota",str(host["CpuQuota"]),"--cpu-period",str(host["CpuPeriod"])])
    for dest,opts in host["Tmpfs"].items():
        if dest!="/tmp" or not isinstance(opts,str) or len(opts)>150:
            raise R65Refused("only reviewed original tmpfs supported")
        args.extend(["--tmpfs",dest+":"+opts])
    if name==EL:
        if definition.get("entrypoint_override") is not None:
            raise R65Refused("Besu entrypoint must remain its pinned image default")
        args.extend(["--network-alias","sse31340-g2-el"])
    elif name==BN:
        if definition.get("entrypoint_override")!="lighthouse":
            raise R65Refused("original Lighthouse explicit executable not validated")
        args.extend(["--entrypoint","lighthouse"])
    else:
        raise R65Refused("original validator must never be recreated")
    for m in definition["mounts"]:
        source=m["Source"]
        target=m["Destination"]
        mount=f"type=bind,source={source},target={target}"
        if m["RW"] is False:
            mount+=",readonly"
        args.extend(["--mount",mount])
    for binding in validated_host_ports(ipv6)[name]:
        args.extend(["--publish",binding])
    args.extend(["--restart","unless-stopped",
                 definition["image"]])
    args.extend(revised_cmd(name,definition["cmd"],ipv6))
    return args

def binding_set(name:str)->set[str]:
    raw=get_json(["inspect","--format","{{json .NetworkSettings.Ports}}",name])
    if not isinstance(raw,dict):
        raise R65Refused("effective Docker host port bindings missing")
    observed=set()
    for key,items in raw.items():
        if items is None:
            continue
        if not isinstance(items,list):
            raise R65Refused("published Docker ports invalid")
        for item in items:
            ip=item.get("HostIp") if isinstance(item,dict) else None
            port=item.get("HostPort") if isinstance(item,dict) else None
            if not isinstance(ip,str) or not isinstance(port,str):
                raise R65Refused("published host endpoint invalid")
            observed.add((f"[{ip}]" if ":" in ip else ip)+":"+port+":"+key)
    return observed

def wait_client(name:str,kind:str,attempts:int=14)->bool:
    for _ in range(attempts):
        state=get_json(["inspect","--format","{{json .State}}",name])
        if not isinstance(state,dict) or state.get("Running") is not True:
            return False
        pid=state.get("Pid")
        if type(pid) is int and pid>1:
            try:
                values=r62.contained_net_probe(pid,kind)
                if kind=="execution":
                    if values["eth_chainId"].get("value")==hex(31340) and values["eth_blockNumber"].get("status")=="ok":
                        return True
                elif values["genesis"].get("genesisTime")==OWNER.GENESIS_TIME and values["head"].get("status")=="ok":
                    return True
            except (r62.R62Refused,OSError,ValueError):
                pass
        time.sleep(10)
    return False

def verify_old_absent_and_new_reachability(ipv6:str)->dict:
    expected=validated_host_ports(ipv6)
    for name in (EL,BN):
        if binding_set(name)!=set(expected[name]):
            raise R65Refused("actual effective port publications differ from review")
        net=get_json(["inspect","--format","{{json .NetworkSettings.Networks}}",name])
        if not isinstance(net,dict) or set(net)!={TRUSTED,PUBLIC_BRIDGE}:
            raise R65Refused("new native process not on exactly both reviewed bridges")
        if docker(["inspect","--format","{{.HostConfig.NetworkMode}}",name])!=TRUSTED:
            raise R65Refused("original internal trust path not primary")
    return {
        "actualNativeHostPublicationsVerified":True,
        "originalEngine8551PublishedToHost":False,
        "onlyRequiredP2pPublishedToActualOwner6plane":True,
        "hostJsonRpcAndBeaconApiPublishedOnlyToLocalhost":True,
    }

def read_only_plan(commit:str)->tuple[dict,dict,dict]:
    print("R65_PLAN_STAGE=VERIFY_CURRENT_ORIGINAL_CHAIN_AND_OPEN_OVERLAY",file=sys.stderr,flush=True)
    owner=r64.current_owner_audit(commit)  # current genuine chain, both clients, VC
    if not owner["originalELP2pExplicitlyDisabled"]:
        raise R65Refused("owner Besu already migrated; never rerun")
    print("R65_PLAN_STAGE=VERIFY_NO_PREEXISTING_MIGRATION_RESOURCES",file=sys.stderr,flush=True)
    for old in PRESERVED.values():
        not_exists("container",old)
    not_exists("network",PUBLIC_BRIDGE)
    print("R65_PLAN_STAGE=VERIFY_EXISTING_DOCKER_METADATA_AND_MOUNTS",file=sys.stderr,flush=True)
    el=original_definition(EL)
    bn=original_definition(BN)
    ipv6=owner["actualOwnerOverlayIpv6"]
    print("R65_PLAN_STAGE=VALIDATE_OVERLAY_ONLY_NATIVE_PORT_PUBLICATION",file=sys.stderr,flush=True)
    ports=validated_host_ports(ipv6)
    # Check original requested APIs were loopback-only, no Engine publication.
    for name,definition in ((EL,el),(BN,bn)):
        current=definition["host"]["PortBindings"] or {}
        for key,binds in current.items():
            if key=="8551/tcp" and binds:
                raise R65Refused("original Engine API must not be host published")
            if binds:
                for bind in binds:
                    if bind.get("HostIp") not in ("127.0.0.1","::1"):
                        raise R65Refused("original container unexpectedly exposes host port")
        cmd=revised_cmd(name,definition["cmd"],ipv6)
        if len(cmd)>200 or any("\x00" in a for a in cmd):
            raise R65Refused("updated native CLI unexpectedly large")
        if name==EL and not any(a=="--p2p-port-ipv6=30404" for a in cmd):
            raise R65Refused("EL native IPv6 port missing")
    return ({
        "schema":"SSE_R65_PRESERVE_ORIGINAL_POS_CHAIN31340_OWNER_PUBLIC_NATIVE_P2P_MIGRATION_V1",
        "mode":"read_only",
        "sourceGitExactSha":commit,
        "actualOpenOverlayIPv6":ipv6,
        "realOriginalExecutionBlockHex":owner["originalExecutionBlockHex"],
        "realOriginalBeaconFinalizedEpoch":owner["originalBeaconFinalizedEpoch"],
        "originalValidatorRunning":True,
        "originalThreeClientsMustBeStoppedForControlledMaintenance":True,
        "originalELAndBeaconDataAndJWTReusedWithoutCopy":True,
        "originalValidatorSigningDataAndKeystoreNeverCloned":True,
        "separatePublicDockerIPv6BridgePlanned":PUBLIC_BRIDGE,
        "existingTrustedEngineBridgeRemains":TRUSTED,
        "newExecutionP2pHostPublications":ports[EL],
        "newBeaconP2pHostPublications":ports[BN],
        "engine8551HostPublicationPlanned":False,
        "oldELAndBNContainersPreservedStoppedForRollback":list(PRESERVED.values()),
        "nativeOutsideProviderP2pPeerAndContinuedFinalityStillUnverified":True,
        "ownerBackupAndMaintenanceConsentRequiredBeforeApply":True,
        "nothingModifiedByPlan":True,
    },el,bn)

def start_if_stopped(name:str)->None:
    state=get_json(["inspect","--format","{{json .State}}",name])
    if not isinstance(state,dict):
        raise R65Refused("original rollback container state unavailable")
    if state.get("Running") is not True:
        docker(["start",name],timeout=35)

def rollback(renamed:set[str],created:set[str])->None:
    print("R65_MAINTENANCE_ROLLBACK_ATTEMPTED=true",file=sys.stderr,flush=True)
    # Only remove NEW containers created by this migration. NEVER remove
    # original containers if the failure happened before docker rename.
    try:
        docker(["stop","--time","35",VC],timeout=50)
    except R65Refused:
        pass
    failed=False
    for name in (BN,EL):
        if name in created:
            try:
                docker(["stop","--time","35",name],timeout=50)
            except R65Refused:
                pass
            try:
                docker(["rm",name],timeout=25)
            except R65Refused:
                failed=True
    for name in (EL,BN):
        if name in renamed:
            try:
                docker(["rename",PRESERVED[name],name])
            except R65Refused:
                failed=True
    if failed:
        print("R65_ROLLBACK_PARTIAL_ORIGINAL_VALIDATOR_LEFT_STOPPED=true",file=sys.stderr,flush=True)
        return
    try:
        start_if_stopped(EL)
        if not wait_client(EL,"execution",8):
            raise R65Refused("original EL health not recovered")
        start_if_stopped(BN)
        if not wait_client(BN,"beacon",8):
            raise R65Refused("original BN health not recovered")
        start_if_stopped(VC)
        print("R65_ROLLBACK_EXISTING_ORIGINAL_EL_BN_VC_RESTARTED=true",file=sys.stderr,flush=True)
    except R65Refused:
        print("R65_ROLLBACK_HEALTH_UNVERIFIED_ORIGINAL_SIGNER_LEFT_STOPPED=true",file=sys.stderr,flush=True)

def apply(commit:str, backup_attested:bool)->dict:
    plan,el,bn=read_only_plan(commit)
    if not backup_attested:
        raise R65Refused("owner has not attested recoverable signing/chain backup")
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        raise R65Refused("local owner terminal required")
    print("R65 WILL STOP the sole original VC, Beacon and EL and recreate ONLY the "
          "EL/Beacon processes with existing original data and JWT. Original "
          "stopped containers are preserved for rollback. This creates native "
          "public P2P on your actual ZeroTier IPv6, NOT on provider-private LAN. "
          "This may interrupt solo-validator finality. Existing recoverable "
          "backup is your responsibility. Do not rerun after partial failure.",
          file=sys.stderr,flush=True)
    token=input("Type MIGRATE-EXISTING-CHAIN31340-NATIVE-P2P: ")
    if token!="MIGRATE-EXISTING-CHAIN31340-NATIVE-P2P":
        raise R65Refused("explicit owner maintenance approval absent")
    # Preconditions must remain true immediately before any mutation.
    latest,_,_=read_only_plan(commit)
    if latest["actualOpenOverlayIPv6"]!=plan["actualOpenOverlayIPv6"]:
        raise R65Refused("owner dynamic overlay IPv6 changed during review")
    ipv6=plan["actualOpenOverlayIPv6"]
    print("R65_STAGE=CREATE_SEPARATE_PUBLIC_IPV6_DOCKER_BRIDGE",flush=True)
    docker(["network","create","--driver","bridge","--ipv6",PUBLIC_BRIDGE],timeout=45)
    destructive_started=False
    renamed:set[str]=set()
    created:set[str]=set()
    try:
        print("R65_STAGE=STOP_ORIGINAL_SIGNER_BEFORE_CLIENT_MAINTENANCE",flush=True)
        destructive_started=True
        for name in (VC,BN,EL):
            docker(["stop","--time","90",name],timeout=110)
        for name in (EL,BN):
            docker(["rename",name,PRESERVED[name]],timeout=30)
            renamed.add(name)
        print("R65_ORIGINAL_EL_AND_BEACON_CONTAINERS_SAFELY_PRESERVED=true",flush=True)
        for name,definition,kind in ((EL,el,"execution"),(BN,bn,"beacon")):
            print("R65_STAGE=CREATE_EXISTING_DATA_NATIVE_"+kind.upper(),flush=True)
            docker(clone_args(definition,ipv6),timeout=50)
            created.add(name)
            docker(["network","connect",PUBLIC_BRIDGE,name],timeout=35)
            docker(["start",name],timeout=35)
            if not wait_client(name,kind):
                raise R65Refused("new original-data native client not healthy")
            print("R65_"+kind.upper()+"_REAL_ORIGINAL_CHAIN_API_HEALTHY=true",flush=True)
        ports=verify_old_absent_and_new_reachability(ipv6)
        print("R65_NATIVE_P2P_ONLY_HOST_PUBLICATIONS_VERIFIED=true",flush=True)
        docker(["start",VC],timeout=35)
        if docker(["inspect","--format","{{.State.Running}}",VC])!="true":
            raise R65Refused("original VC failed to restart")
        # Original validator is resumed only after authentic EL/BN chain API.
        print("R65_ORIGINAL_SINGLE_VALIDATOR_RESTARTED=true",flush=True)
        return {**plan,**ports,"mode":"owner_approved_original_state_native_p2p_migrated",
                "nothingModifiedByPlan":False,
                "originalSingleSignerRunningAfterMaintenance":True,
                "originalOldELAndBeaconContainersStoppedPreserved":True,
                "externalNativeEthereumP2pSyncAndFinalizedRootMatchObserved":False}
    except (R65Refused,KeyboardInterrupt,ValueError,OSError,TypeError,KeyError):
        if destructive_started:
            rollback(renamed,created)
        raise R65Refused("owner migration failed; recovery attempted, inspect state before any retry")

def main()->int:
    p=argparse.ArgumentParser(description="Original PoS chain31340 same-state public native overlay EL+BN migration")
    x=p.add_mutually_exclusive_group(required=True)
    x.add_argument("--plan",action="store_true")
    x.add_argument("--apply",action="store_true")
    p.add_argument("--expected-commit",required=True)
    p.add_argument("--backup-attested",action="store_true")
    args=p.parse_args()
    try:
        if args.plan:
            result,_,_=read_only_plan(args.expected_commit)
        else:
            result=apply(args.expected_commit,args.backup_attested)
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except R65Refused as exc:
        # The reason is a controlled static message, never raw Docker stderr
        # or untrusted private data, and makes failed plans diagnosable.
        print("R65_NATIVE_MIGRATION_REFUSED: "+str(exc),file=sys.stderr)
        return 2
    except (r64.R64Refused,r64.r63.R63Refused,
            r62.R62Refused,OWNER.R60Refused,OSError,ValueError,TypeError,KeyError) as exc:
        print("R65_OWNER_DEPENDENCY_REFUSED: "+type(exc).__name__,file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
