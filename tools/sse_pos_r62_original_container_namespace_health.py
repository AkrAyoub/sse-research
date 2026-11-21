#!/usr/bin/env python3
"""R62: read-only local API checks *inside existing original Docker netns*.

No Docker networking modifications, process restarts, new containers, port
publication, sysctl, firewall, ZeroTier, keys/JWT or signing changes.
Host Python is run in only the target container NETWORK namespace, not its
mount or filesystem namespace; requests target 127.0.0.1 only.
Untrusted HTTP body is parsed inside the namespace and summarized by allowlist.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import sse_pos_r60_owner_native_p2p_readonly_audit as r60

ALLOWED_PORTS = ("8545/tcp", "5052/tcp", "8551/tcp",
                 "30303/tcp", "30303/udp", "9000/tcp",
                 "9000/udp", "9001/udp")
OWNER_CLIENTS = ((r60.EL, "execution"), (r60.BN, "beacon"))
NS_PROBE = r'''
import json, socket, sys, urllib.request, urllib.error

kind = sys.argv[1]
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def call(url, method=None):
    body = None if method is None else json.dumps({
        "jsonrpc":"2.0","id":1,"method":method,"params":[]}).encode()
    request = urllib.request.Request(url,data=body,headers={"Content-Type":"application/json"})
    try:
        with opener.open(request,timeout=3) as res:
            status=res.status
            raw=res.read(150001)
        if len(raw)>150000:
            return {"status":"response_oversize","http":status}
        try:
            result=json.loads(raw)
        except (ValueError, UnicodeError):
            return {"status":"invalid_json","http":status}
        if not isinstance(result,dict):
            return {"status":"unexpected_schema","http":status}
        if method:
            value=result.get("result")
            if (not isinstance(value,str) or len(value)>70 or
                not value.startswith("0x") or
                not all(c in "0123456789abcdefABCDEF" for c in value[2:])):
                return {"status":"missing_hex_result","http":status}
            return {"status":"ok","http":status,"value":value}
        data=result.get("data")
        if not isinstance(data,dict):
            return {"status":"missing_data","http":status}
        if "genesis_time" in data:
            v=data.get("genesis_time")
            return {"status":"ok" if isinstance(v,str) and v.isdecimal() else "missing_genesis_time",
                    "http":status, "genesisTime":v if isinstance(v,str) and v.isdecimal() else None}
        if "finalized" in data:
            final=data.get("finalized")
            epoch=final.get("epoch") if isinstance(final,dict) else None
            root=final.get("root") if isinstance(final,dict) else None
            if not isinstance(epoch,str) or not epoch.isdecimal():epoch=None
            if not isinstance(root,str) or len(root)!=66 or not root.startswith("0x") or not all(c in "0123456789abcdefABCDEF" for c in root[2:]):root=None
            return {"status":"ok" if epoch is not None and root is not None else "incomplete_finality",
                    "http":status,"finalizedEpoch":epoch,"finalizedRoot":root}
        header=data.get("header")
        msg=header.get("message") if isinstance(header,dict) else None
        slot=msg.get("slot") if isinstance(msg,dict) else None
        root=data.get("root")
        if not isinstance(slot,str) or not slot.isdecimal():slot=None
        if not isinstance(root,str) or len(root)!=66 or not root.startswith("0x") or not all(c in "0123456789abcdefABCDEF" for c in root[2:]):root=None
        return {"status":"ok" if slot is not None and root is not None else "incomplete_head",
                "http":status,"headSlot":slot,"headRoot":root}
    except urllib.error.HTTPError as e:
        return {"status":"http_error","http":e.code}
    except urllib.error.URLError as e:
        return {"status":"connection_error","reasonType":type(e.reason).__name__}
    except (socket.timeout, TimeoutError):
        return {"status":"timeout"}
    except (OSError, ValueError, TypeError, OverflowError) as e:
        return {"status":"request_error","reasonType":type(e).__name__}

if kind=="execution":
    address="http://127.0.0.1:8545"
    out={
        "eth_chainId":call(address,"eth_chainId"),
        "eth_blockNumber":call(address,"eth_blockNumber"),
        "net_peerCount":call(address,"net_peerCount"),
    }
elif kind=="beacon":
    address="http://127.0.0.1:5052"
    out={
        "genesis":call(address+"/eth/v1/beacon/genesis"),
        "head":call(address+"/eth/v1/beacon/headers/head"),
        "finality":call(address+"/eth/v1/beacon/states/head/finality_checkpoints"),
    }
else:
    raise SystemExit(2)
print(json.dumps(out,sort_keys=True))
'''

class R62Refused(ValueError):
    pass


def host_ports(raw: str) -> dict:
    try:
        obj=json.loads(raw)
    except (ValueError,UnicodeError) as exc:
        raise R62Refused("Docker port binding JSON not readable") from exc
    if obj is None:
        return {}
    if not isinstance(obj,dict):
        raise R62Refused("Docker port binding JSON format invalid")
    out={}
    for port in ALLOWED_PORTS:
        if port not in obj:
            continue
        entries=obj[port]
        if entries is None:
            out[port]=None
            continue
        if not isinstance(entries,list) or len(entries)>5:
            raise R62Refused("Docker port bindings not bounded")
        records=[]
        for entry in entries:
            if not isinstance(entry,dict):
                raise R62Refused("invalid port binding entry")
            ip=entry.get("HostIp")
            hostport=entry.get("HostPort")
            if not isinstance(ip,str) or len(ip)>45 or not re.fullmatch(r"[A-Fa-f0-9:.]*",ip):
                raise R62Refused("port binding address invalid")
            if not isinstance(hostport,str) or not hostport.isdecimal() or not 0<int(hostport)<=65535:
                raise R62Refused("port binding number invalid")
            records.append({"hostIp":ip,"hostPort":int(hostport)})
        out[port]=records
    return out


def inspect_owner(name: str) -> dict:
    state=json.loads(r60.docker(["inspect","--format","{{json .State}}",name]))
    if not isinstance(state,dict) or state.get("Running") is not True:
        raise R62Refused("original native client not running")
    pid=state.get("Pid")
    if type(pid) is not int or pid<2:
        raise R62Refused("original running client PID unavailable")
    network=r60.docker(["inspect","--format","{{.HostConfig.NetworkMode}}",name])
    if network != r60.NET:
        raise R62Refused("original client moved away from isolated network")
    requested=host_ports(r60.docker(["inspect","--format","{{json .HostConfig.PortBindings}}",name]))
    effective=host_ports(r60.docker(["inspect","--format","{{json .NetworkSettings.Ports}}",name]))
    return {
        "pid":pid,
        "status":"running",
        "networkModeIsOriginalInternal":True,
        "requestedHostBindings":requested,
        "effectiveHostBindings":effective,
        "noSecretsOrContainerEnvInspected":True,
    }


def contained_net_probe(pid: int, kind: str) -> dict:
    if type(pid) is not int or pid<2 or kind not in ("execution","beacon"):
        raise R62Refused("invalid preverified namespace target")
    if shutil.which("nsenter") is None:
        raise R62Refused("nsenter utility unavailable; do not install blindly")
    argv=["sudo","-n","nsenter","--target",str(pid),"--net",
          sys.executable,"-B","-c",NS_PROBE,kind]
    try:
        p=subprocess.run(argv,capture_output=True,text=True,
                         errors="replace",timeout=24,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise R62Refused("network namespace audit timed out or is unavailable") from exc
    if p.returncode!=0 or len(p.stdout)>10000:
        raise R62Refused("network namespace read-only probe failed")
    try:
        value=json.loads(p.stdout)
    except (ValueError,UnicodeError) as exc:
        raise R62Refused("network namespace probe did not return JSON") from exc
    expected={"eth_chainId","eth_blockNumber","net_peerCount"} if kind=="execution" else {"genesis","head","finality"}
    if not isinstance(value,dict) or set(value)!=expected:
        raise R62Refused("network namespace probe returned invalid result keys")
    if not all(isinstance(v,dict) and v.get("status") in
               ("ok","http_error","connection_error","timeout","request_error",
                "response_oversize","invalid_json","unexpected_schema",
                "missing_hex_result","missing_data","missing_genesis_time",
                "incomplete_finality","incomplete_head") for v in value.values()):
        raise R62Refused("network namespace probe returned unexpected status")
    return value


def audit(commit: str) -> dict:
    r60.owner_guard(commit)
    if shutil.which("nsenter") is None:
        raise R62Refused("no host nsenter utility installed")
    # First establish unchanged original clients and requested/effective binds.
    info={kind:inspect_owner(name) for name,kind in OWNER_CLIENTS}
    if r60.docker(["inspect","--format","{{.State.Running}}",r60.VC])!="true":
        raise R62Refused("original VC is unexpectedly not running")
    probes={kind:contained_net_probe(info[kind]["pid"],kind) for _,kind in OWNER_CLIENTS}
    for kind in info:
        info[kind].pop("pid")  # PID used only internally; do not publish it.
        info[kind]["insideExistingContainerNetnsApiReadings"]=probes[kind]
    return {
        "schema":"SSE_R62_ORIGINAL_CHAIN31340_EXISTING_NAMESPACE_READONLY_HEALTH_V1",
        "sourceGitExactSha":commit,
        "originalGenesisAndJwtMetadataVerified":True,
        "originalValidatorContainerRunning":True,
        "containerStatusDoesNotProveChainLiveness":True,
        "DockerHostPortPublicationComparedAgainstInternalNetnsApi":True,
        "execution":info["execution"],
        "beacon":info["beacon"],
        "requestsTargetOnlyContainerLoopback":True,
        "networkNamespaceEntryDoesNotJoinOrChangeOverlay":True,
        "noExistingDockerContainerOrBlockchainFilesChanged":True,
        "actualExternalEthereumP2pPeersVerified":False,
        "sameOpenJoinOverlayNativeConnectivityStillUnverified":True,
    }


def main() -> int:
    p=argparse.ArgumentParser(description="Read-only owner original G2 network namespace health")
    p.add_argument("--audit",action="store_true")
    p.add_argument("--expected-commit",required=True)
    a=p.parse_args()
    if not a.audit:
        print("R62_REFUSED: use only --audit",file=sys.stderr)
        return 2
    try:
        print(json.dumps(audit(a.expected_commit),sort_keys=True,indent=2))
        return 0
    except (R62Refused,r60.R60Refused,OSError,ValueError,TypeError,KeyError) as exc:
        print("R62_ORIGINAL_READONLY_HEALTH_REFUSED: "+type(exc).__name__,file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
