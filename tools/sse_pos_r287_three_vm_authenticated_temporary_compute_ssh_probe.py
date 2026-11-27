#!/usr/bin/env python3
"""R287 real remote pre-lease compute observation over temporary pinned SSH.

On VM4714 --provider-hostkey reads ONLY ssh_host_ed25519_key.pub and
prints its SHA256 fingerprint for owner to carry OUT OF BAND.
On VM4711/12/13 --preflight uses ssh-keyscan ONLY to get an UNTRUSTED
SSH public key, then independently compares its SHA256 fingerprint to
the explicit provider-console fingerprint. A verified ephemeral
known_hosts file is used by a strict noninteractive SSH publickey check.
--probe additionally opens ONE ephemeral local-only SSH TCP tunnel to
the existing VM4714 127.0.0.1:8877 Docker worker, performs ONE real
OS-random HTTP CPU SHA256 challenge and independent digest check, then
terminates the SSH process and removes its temporary known_hosts file.

No new SSH accounts/keys/authorized_keys, firewall/ingress, Docker,
native chain, public HTTPS, wallets, signing or onchain SLA votes.
SSH TCP reachability alone is NOT SSH host authenticity or user auth.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import socket
import stat
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPRedirectHandler, ProxyHandler, Request, build_opener,
)

from compute_workload import compute_result

OWNER_PROVIDER="ayoubakrvm4714"
MONITORS=frozenset(("ayoubakrvm4711","ayoubakrvm4712","ayoubakrvm4713"))
HOST="10.50.56.22"
TARGET=OWNER_PROVIDER+"@"+HOST
PORT=22
WORKER_PORT=8877
FINGERPRINT=re.compile(r"SHA256:[A-Za-z0-9+/]{43}\Z")
PUBLIC_PATH=Path("/etc/ssh/ssh_host_ed25519_key.pub")


class Refused(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def owner(*,uid_fn=os.geteuid,name_fn=None):
    uid=uid_fn()
    if name_fn is None:
        name_fn=lambda n:pwd.getpwuid(n).pw_name
    if uid==0:
        raise Refused("nonroot VM owner required")
    user=name_fn(uid)
    if user not in MONITORS and user!=OWNER_PROVIDER:
        raise Refused("R287 limited to four actually observed VM accounts")
    return user


def parse_public(line):
    """Fingerprints PUBLIC SSH ED25519 key data, not a signing key."""
    fields=line.split()
    if len(fields)<2 or fields[0]!="ssh-ed25519":
        raise Refused("expected public ED25519 SSH host key")
    encoded=fields[1]
    if not 50<=len(encoded)<=4096:
        raise Refused("invalid bounded SSH host public key bytes")
    try:
        raw=base64.b64decode(encoded+"="*((-len(encoded))%4),validate=True)
    except (binascii.Error,ValueError) as exc:
        raise Refused("invalid public SSH key base64") from exc
    if not 32<=len(raw)<=4096:
        raise Refused("invalid SSH public key body")
    fingerprint="SHA256:"+base64.b64encode(hashlib.sha256(raw).digest()).decode(
        "ascii").rstrip("=")
    return fingerprint,encoded


def provider_public_hostkey(*,read=None,path=PUBLIC_PATH):
    if read is None:
        if path.is_symlink() or not path.is_file() or path.stat().st_size>2048:
            raise Refused("only small regular public SSH host key file allowed")
        read=lambda: path.read_text(encoding="ascii")
    fingerprint,key=parse_public(read().strip())
    return {
        "schema":"SSE_R287_PROVIDER_VM4714_PUBLIC_SSH_HOST_KEY_ONLY_V1",
        "providerUser":OWNER_PROVIDER,
        "providerPrivateIpv4":HOST,
        "ed25519HostPublicKeyFingerprint":fingerprint,
        "publicHostKeyOnlyRead":True,
        "sshHostOrAuthorizedKeysChanged":False,
        "privateSshSigningKeyRead":False,
    }


def scanned_public_hostkey(expected,*,run=subprocess.run):
    if type(expected) is not str or not FINGERPRINT.fullmatch(expected):
        raise Refused("operator must supply EXACT provider-console SHA256 host fingerprint")
    command=["ssh-keyscan","-T","4","-p","22","-t","ed25519",HOST]
    try:
        p=run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
              text=True,shell=False,check=False,timeout=7)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise Refused("SSH public key scan unavailable") from exc
    if p.returncode!=0 or type(p.stdout) is not str or len(p.stdout)>8192:
        raise Refused("SSH public key scan failed")
    keys=set()
    for line in p.stdout.splitlines():
        if not line or line.startswith("#"):
            continue
        parts=line.split()
        if len(parts)!=3 or parts[0]!=HOST or parts[1]!="ssh-ed25519":
            raise Refused("unknown SSH public host key entry")
        observed,encoded=parse_public(parts[1]+" "+parts[2])
        if observed!=expected:
            raise Refused("REMOTE SSH HOST KEY DOES NOT MATCH PROVIDER-CONSOLE PIN")
        keys.add(encoded)
    if len(keys)!=1:
        raise Refused("expected exactly one pinned SSH ED25519 host public key")
    return next(iter(keys))


def _identity(path,user_uid):
    if path is None:
        return None
    p=Path(path)
    if not p.is_absolute() or p.is_symlink() or not p.is_file():
        raise Refused("optional SSH identity must be existing absolute regular non-symlink file")
    st=p.stat()
    if st.st_uid!=user_uid or stat.S_IMODE(st.st_mode) not in (0o400,0o600):
        raise Refused("SSH private identity must be owner-controlled 0400/0600")
    return str(p)


def strict_ssh_args(known_hosts,*,identity=None):
    # -F /dev/null prevents unexpected ProxyJump, LocalCommand, dynamic
    # forwarding, insecure known-host overrides, host alias or remote context.
    args=[
        "ssh","-F","/dev/null","-p","22",
        "-o","BatchMode=yes",
        "-o","PreferredAuthentications=publickey",
        "-o","PasswordAuthentication=no",
        "-o","KbdInteractiveAuthentication=no",
        "-o","StrictHostKeyChecking=yes",
        "-o","VerifyHostKeyDNS=no",
        "-o","UpdateHostKeys=no",
        "-o","UserKnownHostsFile="+str(known_hosts),
        "-o","GlobalKnownHostsFile=/dev/null",
        "-o","ProxyCommand=none",
        "-o","ForwardAgent=no",
        "-o","ForwardX11=no",
        "-o","PermitLocalCommand=no",
        "-o","ControlMaster=no",
        "-o","ConnectionAttempts=1",
        "-o","ConnectTimeout=4",
        "-o","ExitOnForwardFailure=yes",
        "-o","ServerAliveInterval=2",
        "-o","ServerAliveCountMax=2",
    ]
    if identity is not None:
        args+=["-o","IdentitiesOnly=yes","-i",identity]
    return args


def authorize_known_host(temporary_dir,key):
    file=Path(temporary_dir)/"vm4714_host_ed25519_known_hosts"
    fd=os.open(file,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w",encoding="ascii") as out:
        out.write(HOST+" ssh-ed25519 "+key+"\n")
    return file


def ssh_auth(ssh_base,*,run=subprocess.run):
    command=ssh_base+[TARGET,"true"]
    try:
        p=run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
              text=True,shell=False,check=False,timeout=10,
              stdin=subprocess.DEVNULL)
    except (OSError,subprocess.TimeoutExpired):
        return False
    return p.returncode==0


def _port(*,socket_factory=socket.socket):
    with socket_factory(socket.AF_INET,socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1",0))
        return listener.getsockname()[1]


def _unique_pairs(pairs):
    doc={}
    for k,v in pairs:
        if k in doc:
            raise Refused("duplicate JSON compute response field")
        doc[k]=v
    return doc


def _bounded_json(opener,url,*,payload=None):
    if payload is None:
        request=Request(url,method="GET")
    else:
        raw=json.dumps(payload,separators=(",",":"),sort_keys=True).encode("ascii")
        if len(raw)>1024:
            raise Refused("remote CPU challenge larger than expected")
        request=Request(url,method="POST",data=raw,
                        headers={"Content-Type":"application/json"})
    try:
        with opener.open(request,timeout=5) as response:
            if response.status!=200:
                raise Refused("remote CPU worker returned non-200 HTTP")
            if int(response.headers.get("Content-Length","0"))>4096:
                raise Refused("remote CPU worker response too large")
            body=response.read(4097)
    except (OSError,TimeoutError,HTTPError,URLError) as exc:
        raise Refused("short-lived authenticated SSH worker HTTP unavailable") from exc
    if len(body)>4096:
        raise Refused("remote CPU body exceeds 4096 bytes")
    try:
        return json.loads(body.decode("utf-8"),object_pairs_hook=_unique_pairs)
    except (ValueError,UnicodeDecodeError,TypeError) as exc:
        raise Refused("invalid remote CPU response JSON") from exc


def worker_probe(local_port,*,opener=None,random_hex=secrets.token_hex):
    if type(local_port) is not int or not 1<=local_port<=65535:
        raise Refused("invalid own temporary loopback port")
    if opener is None:
        opener=build_opener(ProxyHandler({}),NoRedirect())
    base="http://127.0.0.1:"+str(local_port)
    health=_bounded_json(opener,base+"/healthz")
    if (type(health) is not dict or health.get("localComputeWorker") is not True
        or health.get("ok") is not True or
        health.get("onChainAuthenticated") is not False):
        raise Refused("SSH tunnel did not reach expected unauthenticated local worker")
    request_hash="0x"+random_hex(32)
    if (len(request_hash)!=66 or
        any(c not in "0123456789abcdef" for c in request_hash[2:])):
        raise Refused("fresh OS challenge invalid")
    payload={"leaseId":1,"epochId":0,"requestHash":request_hash}
    expected=compute_result(1,0,request_hash)
    started=time.perf_counter()
    result=_bounded_json(opener,base+"/v1/compute",payload=payload)
    elapsed=round(time.perf_counter()-started,6)
    if result!=expected:
        raise Refused("SSH remote REAL CPU result differs from independent digest")
    return {
        "realRemoteCpuResultVerified":True,
        "preLeaseTestChallengeOnly":True,
        "leaseId":1,"epochId":0,"requestHash":request_hash,
        "resultDigest":expected["resultDigest"],
        "rounds":8192,
        "remoteSshTunneledHttpRoundtripSeconds":elapsed,
        "providerResponseEip712SignatureVerified":False,
        "onChainLeaseOrSlaVerified":False,
        "trustedHardwareAttestation":False,
    }


def temporary_tunnel(ssh_base,*,popen=subprocess.Popen,
                     connect=socket.create_connection,
                     port_picker=_port,probe=worker_probe,
                     sleep=time.sleep):
    port=port_picker()
    # The forwarded listener is bound to *monitor host* loopback only,
    # while its remote endpoint is *provider host* loopback only.
    command=ssh_base+[
        "-N","-L",f"127.0.0.1:{port}:127.0.0.1:{WORKER_PORT}",TARGET
    ]
    proc=None
    try:
        proc=popen(command,stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                   close_fds=True)
        for _ in range(24):
            if proc.poll() is not None:
                raise Refused("authenticated SSH forwarding process exited")
            try:
                with connect(("127.0.0.1",port),timeout=.25):
                    break
            except (OSError,TimeoutError):
                sleep(.125)
        else:
            raise Refused("authenticated local-only SSH forwarding did not bind")
        if proc.poll() is not None:
            raise Refused("SSH tunnel exited before the real CPU challenge")
        out=probe(port)
        return {
            **out,
            "temporarySshForwardListenerBoundOnlyMonitorLoopback":True,
            "targetProviderLoopbackWorkerPort":WORKER_PORT,
            "providerDirectTcp8877OpenedToLan":False,
        }
    finally:
        # Always attempt to terminate the exact process created here.
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.terminate()
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)


def observe(*,user,mode,fingerprint=None,identity=None,
            scan_run=subprocess.run,ssh_run=subprocess.run,
            tunnel=temporary_tunnel):
    if mode=="--provider-hostkey":
        if user!=OWNER_PROVIDER:
            raise Refused("only provider VM4714 can attest its local public SSH host key")
        return provider_public_hostkey()
    if mode not in ("--preflight","--probe") or user not in MONITORS:
        raise Refused("only VM4711–4713 monitors may initiate host-pinned SSH probe")
    identity_path=_identity(identity,os.geteuid())
    key=scanned_public_hostkey(fingerprint,run=scan_run)
    with tempfile.TemporaryDirectory(prefix="sse-r287-pinned-host-") as td:
        pinned=authorize_known_host(td,key)
        args=strict_ssh_args(pinned,identity=identity_path)
        ssh_ok=ssh_auth(args,run=ssh_run)
        result={
            "schema":"SSE_R287_VM4711_4713_PINNED_TEMPORARY_SSH_COMPUTE_V1",
            "observedMonitorOwner":user,
            "providerPrivateIpv4":HOST,
            "providerSshEd25519FingerprintMatchedConsole":True,
            "sshNoninteractivePublicKeyLoginVerified":ssh_ok,
            "fullSshTunnelAndRealRemoteCpuTestRequested":mode=="--probe",
            "nativeChainOrDockerChanged":False,
            "privateSshOrEvmSigningKeyReadByScript":False,
            "walletOrValidatorKeysPrinted":False,
            "newAuthorizedKeysOrKnownHostsPersisted":False,
            "publicWorkerPortExposed":False,
            "monitorEip712VoteSignedOrBroadcast":False,
            "publicInternetProviderReachabilityVerified":False,
            "paidFinalizedV2LeaseOrSlaVerified":False,
        }
        if not ssh_ok:
            result["nextAction"]="REVIEW_PUBLIC_KEY_LOGIN_WITHOUT_CHANGING_FIREWALL_OR_KEYS"
            return result
        if mode=="--probe":
            result.update(tunnel(args))
            result["temporarySshTunnelProcessStoppedAfterProbe"]=True
        return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--provider-hostkey",action="store_true",
                       help="VM4714 read ONLY /etc/ssh/ssh_host_ed25519_key.pub")
    group.add_argument("--preflight",action="store_true",
                       help="VM4711–13 scan+verify out-of-band host fingerprint; noninteractive SSH true")
    group.add_argument("--probe",action="store_true",
                       help="VM4711–13 plus temporary SSH port-forward+one real CPU challenge")
    parser.add_argument("--expected-host-fingerprint",
                        help="EXACT SHA256 fingerprint from VM4714 console, never ssh-keyscan alone")
    parser.add_argument("--identity-file",
                        help="optional existing owner-private 0400/0600 SSH identity; SSH reads it, script does not")
    args=parser.parse_args(argv)
    try:
        user=owner()
        mode=("--provider-hostkey" if args.provider_hostkey else
              "--preflight" if args.preflight else "--probe")
        if mode=="--provider-hostkey" and (
            args.expected_host_fingerprint or args.identity_file):
            raise Refused("provider public hostkey audit accepts no client identity")
        result=observe(user=user,mode=mode,
                       fingerprint=args.expected_host_fingerprint,
                       identity=args.identity_file)
        print(json.dumps(result,indent=2,sort_keys=True))
        print("R287_REAL_VM_SSH_PIN_AND_SINGLE_PRELEASE_CPU_PROBE_NO_NATIVE_TX=true")
        return 0
    except (Refused,ValueError,OSError,TypeError,KeyError) as exc:
        print("R287_SSH_PINNED_PRIVATE_WORKER_PROBE_REFUSED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
