#!/usr/bin/env python3
"""R117 owner-only recovery for Docker 29 stale *stopped* primary bridge records.
Exact observed 2026-11-21 condition: both EL/BN exited, primary bridge record
has empty EndpointID/IP and network inspect Containers={}, public bridge empty.
Never recreate clients, networks, keys or signer. Never touch a live client.
"""
import argparse
import json
import subprocess
import sys

EL="sse31340-g2-el-r40"
BN="sse31340-g2-bn"
VC="sse31340-g2-vc"
PRIVATE="sse31340-g2-internal"
PUBLIC="sse31340-g2-r65-public-p2p"
OWNER_IP="fca0:2328:776e:4750:395b::1"
EXPECTED={EL:("172.18.0.2","sse31340-g2-el"),BN:("172.18.0.3",None)}
PORTS={
 EL:{"8545/tcp":("127.0.0.1","18545"),"30404/tcp":(OWNER_IP,"30404"),"30404/udp":(OWNER_IP,"30404")},
 BN:{"5052/tcp":("127.0.0.1","15052"),"9000/tcp":(OWNER_IP,"9000"),"9000/udp":(OWNER_IP,"9000"),"9001/udp":(OWNER_IP,"9001")},
}

class Refused(Exception):
    pass

def cmd(*args):
    p=subprocess.run(args,capture_output=True,text=True,timeout=90,check=False)
    if p.returncode:
        raise Refused("command failed: "+" ".join(args[:3])+" (no automatic retry after mutation)")
    return p.stdout.strip()

def docker(*args):
    return cmd("docker",*args)

def inspect(name):
    return json.loads(docker("inspect","--format","{{json .}}",name))

def network(name):
    return json.loads(docker("network","inspect",name,"--format","{{json .}}"))

def validate():
    if OWNER_IP+"/40" not in cmd("ip","-6","addr","show","dev","ztrb6cq527"):
        raise Refused("owner ZeroTier IPv6 not ready")
    private,public=network(PRIVATE),network(PUBLIC)
    if not (private["Driver"]=="bridge" and private["Internal"] is True
            and public["Driver"]=="bridge" and public["Internal"] is False
            and public["EnableIPv6"] is True):
        raise Refused("existing bridge identity/isolation changed")
    if inspect(VC)["State"]["Running"]:
        raise Refused("validator running")
    records={}
    for name,(ip,alias) in EXPECTED.items():
        c=inspect(name)
        if c["State"]["Running"] or c["State"]["Status"]!="exited":
            raise Refused("clients must be stopped for stale-endpoint repair")
        if c["HostConfig"]["NetworkMode"]!=PRIVATE:
            raise Refused("primary private bridge changed")
        actual=c["HostConfig"].get("PortBindings") or {}
        if set(actual)!=set(PORTS[name]) or any(
           not isinstance(actual[k],list) or len(actual[k])!=1 or
           (actual[k][0].get("HostIp"),actual[k][0].get("HostPort"))!=v
           for k,v in PORTS[name].items()
        ):
            raise Refused("host binding mismatch")
        nets=c.get("NetworkSettings",{}).get("Networks") or {}
        if set(nets)!={PRIVATE}:
            raise Refused("expected ONLY original stale private endpoint")
        n=nets[PRIVATE]
        if n.get("NetworkID")!=private["Id"] or n.get("EndpointID") not in ("",None) or n.get("IPAddress") not in ("",None):
            raise Refused("private record not the observed empty-endpoint state")
        if alias and alias not in (n.get("Aliases") or []):
            raise Refused("private Engine DNS alias missing")
        if name==BN and (n.get("IPAMConfig") or {}).get("IPv4Address")!=ip:
            raise Refused("original BN static IP config changed")
        records[name]=c
    for n in (private,public):
        if n.get("Containers"):
            raise Refused("existing network already has attached containers")
    return records

def main():
    ap=argparse.ArgumentParser()
    x=ap.add_mutually_exclusive_group(required=True)
    x.add_argument("--plan",action="store_true")
    x.add_argument("--apply",action="store_true")
    args=ap.parse_args()
    try:
        validate()
        print("R117_EXACT_STALE_STOPPED_OWNER_NETWORK_STATE_VERIFIED=true",flush=True)
        if args.plan:
            return 0
        # Recreate ONLY Docker endpoint attachments, never the stopped containers.
        # If interrupted, fail closed and inspect state before any retry.
        for name,(ip,alias) in EXPECTED.items():
            print("R117_STAGE=DISCONNECT_STALE_PRIVATE "+name,flush=True)
            docker("network","disconnect","--force",PRIVATE,name)
            print("R117_STAGE=CONNECT_ORIGINAL_PRIVATE "+name,flush=True)
            argv=["network","connect","--ip",ip]
            if alias:
                argv+=["--alias",alias]
            docker(*argv,PRIVATE,name)
        for name in EXPECTED:
            print("R117_STAGE=CONNECT_EXISTING_PUBLIC "+name,flush=True)
            docker("network","connect",PUBLIC,name)
        for name in EXPECTED:
            print("R117_STAGE=START_ORIGINAL_CLIENT "+name,flush=True)
            docker("start",name)
        for name,(ip,alias) in EXPECTED.items():
            c=inspect(name)
            nets=c["NetworkSettings"]["Networks"]
            if c["State"]["Running"] is not True or set(nets)!={PRIVATE,PUBLIC}:
                raise Refused("post-repair topology or client state invalid")
            if nets[PRIVATE]["IPAddress"]!=ip:
                raise Refused("private IP not restored")
            if alias and alias not in ((nets[PRIVATE].get("Aliases") or [])+(nets[PRIVATE].get("DNSNames") or [])):
                raise Refused("EL Engine alias not restored")
            published=c["NetworkSettings"].get("Ports") or {}
            for port,(host,number) in PORTS[name].items():
                if not any(v.get("HostIp")==host and v.get("HostPort")==number for v in (published.get(port) or [])):
                    raise Refused("effective native host publication absent")
        print("R117_EXISTING_OWNER_NATIVE_DUAL_NETWORK_RECOVERED=true",flush=True)
        print("R117_VALIDATOR_REMAINS_STOPPED=true",flush=True)
        return 0
    except (Refused,KeyError,ValueError,TypeError,subprocess.TimeoutExpired,OSError) as exc:
        print("R117_REFUSED_OR_PARTIAL: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    sys.exit(main())
