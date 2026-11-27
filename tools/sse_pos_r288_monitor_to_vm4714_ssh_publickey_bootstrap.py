#!/usr/bin/env python3
"""R288 owner-interactive *dedicated lab* monitor -> VM4714 SSH trust bootstrap.

--client-preview / --client-public: read ONLY local metadata/public key.
--client-create: one expressly authorized SSH ED25519 identity, no passphrase,
                 owner-private 0600; never overwrite an existing identity.
--provider-preview: read ONLY existing .ssh/authorized_keys metadata.
--provider-authorize: one expressly authorized EXACT PUBLIC key, append only
                      to existing authorized_keys, preserving all old entries.

Each provider authorized_keys line is source-IP restricted, shell denied by a
fixed forced command, no PTY/agent/X11, only one TCP forward target allowed.
These are APP TEST SSH identities, NOT original chain31340 Ethereum EOAs,
not validator keys, not the rootful Docker daemon. This setup neither tests
public Internet connectivity nor changes sshd_config or service state.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys

MONITORS={
    "ayoubakrvm4711":("vm4711","10.50.56.14"),
    "ayoubakrvm4712":("vm4712","10.50.56.19"),
    "ayoubakrvm4713":("vm4713","10.50.56.21"),
}
PROVIDER="ayoubakrvm4714"
PRIVATE_FILENAME="r288_vm4714_cpu_tunnel_ed25519"
MAX_KEYS_FILE=65536
B64=re.compile(r"[A-Za-z0-9+/]+={0,2}\Z")


class Refused(ValueError):
    pass


def owner(*,uid_fn=os.geteuid,by_uid=pwd.getpwuid):
    uid=uid_fn()
    if uid==0:
        raise Refused("nonroot VM owner required")
    record=by_uid(uid)
    if record.pw_name not in MONITORS and record.pw_name!=PROVIDER:
        raise Refused("not an inventoried VM4711-14 lab owner")
    return record.pw_name,uid,Path(record.pw_dir)


def ssh_private_paths(home):
    directory=home/".local"/"share"/"sse-v2-app-only"/"ssh"
    return directory,directory/PRIVATE_FILENAME, directory/(PRIVATE_FILENAME+".pub")


def _require_regular_owner(path,uid,modes):
    if path.is_symlink() or not path.is_file():
        raise Refused("identity/authorized_keys path must be an existing regular file")
    st=path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid!=uid or stat.S_IMODE(st.st_mode) not in modes:
        raise Refused("file not owned by current VM user or mode is too permissive")
    return st


def _private_dir(path,uid):
    if path.is_symlink() or not path.is_dir():
        raise Refused("private SSH directory missing, symlinked or not a directory")
    st=path.stat()
    if st.st_uid!=uid or stat.S_IMODE(st.st_mode)!=0o700:
        raise Refused("private SSH directory must be owner-only mode0700")


def _valid_public_key(pub):
    if type(pub) is not str or "\n" in pub or "\r" in pub or len(pub)>500:
        raise Refused("public SSH ED25519 key must be one bounded line")
    fields=pub.strip().split()
    if len(fields) not in (2,3) or fields[0]!="ssh-ed25519" or not B64.fullmatch(fields[1]):
        raise Refused("only exact one-line SSH ED25519 public keys supported")
    encoded=fields[1]
    try:
        raw=base64.b64decode(encoded,validate=True)
    except (binascii.Error,ValueError) as exc:
        raise Refused("invalid SSH ED25519 public key encoding") from exc
    # SSH ED25519 public key blob: uint32 len(11), 'ssh-ed25519',
    # uint32 len(32), exactly 32 raw public-key bytes.
    if raw[:4]!=b"\0\0\0\x0b" or raw[4:15]!=b"ssh-ed25519" or raw[15:19]!=b"\0\0\0\x20" or len(raw)!=51:
        raise Refused("SSH public key does not contain one authentic-format ED25519 key blob")
    canonical=base64.b64encode(raw).decode("ascii")
    fp="SHA256:"+base64.b64encode(hashlib.sha256(raw).digest()).decode("ascii").rstrip("=")
    return canonical,fp


def client_public(*,name,uid,home):
    if name not in MONITORS:
        raise Refused("only an actual monitor owner may reveal own PUBLIC SSH key")
    directory,private,public=ssh_private_paths(home)
    _private_dir(directory,uid)
    _require_regular_owner(private,uid,{0o600,0o400})
    _require_regular_owner(public,uid,{0o600,0o400,0o644})
    if public.stat().st_size>500:
        raise Refused("public SSH identity too long")
    # OpenSSH ssh-keygen writes exactly one terminal LF in its normal
    # public .pub file. Strip only that one file terminator; never accept
    # embedded/newline-separated keys or relax direct CLI-key validation.
    # Read exact PUBLIC bytes: Path.read_text() does universal-newline
    # conversion and can silently turn CRLF into LF. Only a single normal
    # ssh-keygen terminal LF is permitted, not CRLF or embedded newlines.
    # Never open/read the corresponding private key contents.
    public_line=public.read_bytes().decode("ascii")
    if public_line.endswith("\n"):
        public_line=public_line[:-1]
    key,fp=_valid_public_key(public_line)
    return {
        "schema":"SSE_R288_OWNER_ONLY_MONITOR_SSH_PUBLIC_IDENTITY_V1",
        "sourceVm":MONITORS[name][0],
        "sourcePrivateIPv4":MONITORS[name][1],
        "destinationVm":"vm4714",
        "publicKey":"ssh-ed25519 "+key,
        "publicKeyFingerprint":fp,
        "sshPrivateKeyPrintedOrUploaded":False,
        "ethereumOrValidatorKeyRead":False,
        "chainTransactionSignedOrSent":False,
    }


def client_preview(*,name,uid,home):
    if name not in MONITORS:
        raise Refused("client preview only on three monitor owner accounts")
    directory,private,public=ssh_private_paths(home)
    return {
        "schema":"SSE_R288_MONITOR_SSH_KEY_CREATION_PREVIEW_ONLY_V1",
        "sourceVm":MONITORS[name][0],
        "destinationVm":"vm4714",
        "privateIdentityExists":private.exists() or private.is_symlink(),
        "publicIdentityExists":public.exists() or public.is_symlink(),
        "dedicatedIdentityDirectoryExists":directory.exists() or directory.is_symlink(),
        "sshIdentityGenerated":False,
        "nativeEoaOrValidatorKeyRead":False,
        "dockerOrNetworkSettingsModified":False,
    }


def client_create(*,name,uid,home,confirm,run=subprocess.run):
    if name not in MONITORS:
        raise Refused("only monitor owners may create dedicated SSH identities")
    directory,private,public=ssh_private_paths(home)
    if private.exists() or private.is_symlink() or public.exists() or public.is_symlink():
        raise Refused("dedicated SSH identity already exists; NEVER overwrite")
    # Existing app-only path created by R279; require every ancestor to be
    # owner-private and never chmod existing directories.
    for ancestor in (home/".local",home/".local"/"share",home/".local"/"share"/"sse-v2-app-only"):
        if ancestor.is_symlink() or not ancestor.is_dir() or ancestor.stat().st_uid!=uid:
            raise Refused("existing owner application parent directory unsafe or missing")
    _private_dir(home/".local"/"share"/"sse-v2-app-only",uid)
    phrase="CREATE-ONE-R288-"+MONITORS[name][0].upper()+"-VM4714-SSH-ED25519"
    if confirm!=phrase:
        raise Refused("exact interactive one-owner SSH key authorization missing")
    directory.mkdir(mode=0o700,exist_ok=False)
    _private_dir(directory,uid)
    command=[
        "ssh-keygen","-q","-t","ed25519","-a","16","-N","",
        "-f",str(private),"-C","sse-r288-"+MONITORS[name][0]+"-to-vm4714"
    ]
    try:
        proc=run(command,check=False,shell=False,stdin=subprocess.DEVNULL,
                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise Refused("local ssh-keygen unavailable; no key output shown") from exc
    if proc.returncode!=0:
        raise Refused("ssh-keygen failed; preserve private path for manual owner review")
    _require_regular_owner(private,uid,{0o600,0o400})
    _require_regular_owner(public,uid,{0o644,0o600,0o400})
    return client_public(name=name,uid=uid,home=home)


def provider_preview(*,name,uid,home):
    if name!=PROVIDER:
        raise Refused("only provider VM4714 owner may inspect authorized_keys metadata")
    directory=home/".ssh"
    authorized=directory/"authorized_keys"
    if directory.exists() or directory.is_symlink():
        _private_dir(directory,uid)
    if authorized.exists() or authorized.is_symlink():
        _require_regular_owner(authorized,uid,{0o600})
        size=authorized.stat().st_size
        if size>MAX_KEYS_FILE:
            raise Refused("existing authorized_keys file unexpectedly large")
    else:
        size=0
    return {
        "schema":"SSE_R288_VM4714_EXISTING_AUTHORIZED_KEYS_METADATA_ONLY_V1",
        "providerVm":"vm4714",
        "sshDirectoryExists":directory.is_dir(),
        "authorizedKeysExists":authorized.is_file(),
        "authorizedKeysBytes":size,
        "existingAuthorizedKeysContentsPrinted":False,
        "existingAuthorizedKeysModified":False,
        "sshdOrFirewallModified":False,
    }


def restricted_entry(vm,key):
    if vm not in ("vm4711","vm4712","vm4713"):
        raise Refused("only three exact monitor VM public keys may be authorized")
    ip=next(p for _,(role,p) in MONITORS.items() if role==vm)
    canonical,fp=_valid_public_key(key)
    options=(
        'from="'+ip+'",restrict,port-forwarding,'
        'permitopen="127.0.0.1:8877",command="/usr/bin/true"'
    )
    return options+" ssh-ed25519 "+canonical+" sse-r288-"+vm,canonical,fp


def provider_authorize(*,name,uid,home,vm,pub,confirm):
    if name!=PROVIDER:
        raise Refused("only provider VM4714 can authorize monitor PUBLIC keys")
    entry,key,fp=restricted_entry(vm,pub)
    phrase="AUTHORIZE-ONE-R288-"+vm.upper()+"-LOOPBACK-8877"
    if confirm!=phrase:
        raise Refused("exact one-key server authorization missing")
    directory=home/".ssh"
    if directory.is_symlink():
        raise Refused("owner SSH directory symlink forbidden")
    if directory.exists():
        _private_dir(directory,uid)
    else:
        directory.mkdir(mode=0o700)
        _private_dir(directory,uid)
    path=directory/"authorized_keys"
    if path.is_symlink():
        raise Refused("authorized_keys symlink forbidden")
    # O_NOFOLLOW, owner-only permission, advisory lock, and append-only.
    flags=os.O_RDWR|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC
    fd=os.open(path,flags,0o600)
    changed=False
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=uid or stat.S_IMODE(st.st_mode)!=0o600:
            raise Refused("existing authorized_keys must be user owned mode0600")
        if st.st_size>MAX_KEYS_FILE:
            raise Refused("existing authorized_keys too large; preserve without append")
        with os.fdopen(os.dup(fd),"rb") as f:
            existing=f.read(MAX_KEYS_FILE+1)
        if len(existing)>MAX_KEYS_FILE:
            raise Refused("existing authorized_keys too large")
        if existing and not existing.endswith(b"\n"):
            raise Refused("existing authorized_keys lacks newline; preserve without append")
        lines=existing.decode("utf-8").splitlines()
        for line in lines:
            if "sse-r288-"+vm in line or ("ssh-ed25519 "+key) in line:
                if line==entry:
                    return {
                        "schema":"SSE_R288_ONE_RESTRICTED_VM4714_MONITOR_SSH_PUBLIC_KEY_AUTHORIZATION_V1",
                        "providerVm":"vm4714","sourceVm":vm,
                        "publicKeyFingerprint":fp,
                        "restrictedToProviderLoopback8877":True,
                        "sourcePrivateIpRestricted":True,
                        "forcedNoShellCommand":True,
                        "alreadyPresentIdentical":True,
                        "addedAuthorizedKeysLine":False,
                        "existingOtherAuthorizedKeysPreserved":True,
                        "sshPrivateKeyRead":False,
                        "nativeChainOrDockerChanged":False,
                    }
                raise Refused("existing key/marker conflicts; preserve original authorized_keys")
        encoded=(entry+"\n").encode("ascii")
        if len(existing)+len(encoded)>MAX_KEYS_FILE:
            raise Refused("new authorized_keys entry would exceed limit")
        os.write(fd,encoded)
        os.fsync(fd)
        changed=True
    finally:
        os.close(fd)
    return {
        "schema":"SSE_R288_ONE_RESTRICTED_VM4714_MONITOR_SSH_PUBLIC_KEY_AUTHORIZATION_V1",
        "providerVm":"vm4714","sourceVm":vm,
        "publicKeyFingerprint":fp,
        "restrictedToProviderLoopback8877":True,
        "sourcePrivateIpRestricted":True,
        "forcedNoShellCommand":True,
        "alreadyPresentIdentical":False,
        "addedAuthorizedKeysLine":changed,
        "existingOtherAuthorizedKeysPreserved":True,
        "sshPrivateKeyRead":False,
        "nativeChainOrDockerChanged":False,
    }


def _tty_approval(phrase):
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        raise Refused("interactive owner TTY required to change SSH trust")
    received=input("Type "+phrase+" to authorize exactly one SSH change: ")
    return received


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group(required=True)
    for mode in ("client-preview","client-public","client-create",
                 "provider-preview","provider-authorize"):
        modes.add_argument("--"+mode,action="store_true")
    parser.add_argument("--source-vm",choices=("vm4711","vm4712","vm4713"))
    parser.add_argument("--public-key",help="one exact PUBLIC ssh-ed25519 monitor key, never private")
    args=parser.parse_args(argv)
    try:
        name,uid,home=owner()
        if args.client_preview:
            result=client_preview(name=name,uid=uid,home=home)
        elif args.client_public:
            result=client_public(name=name,uid=uid,home=home)
        elif args.client_create:
            if name not in MONITORS:
                raise Refused("client-create limited to the three monitors")
            phrase="CREATE-ONE-R288-"+MONITORS[name][0].upper()+"-VM4714-SSH-ED25519"
            result=client_create(name=name,uid=uid,home=home,
                                 confirm=_tty_approval(phrase))
        elif args.provider_preview:
            result=provider_preview(name=name,uid=uid,home=home)
        else:
            if args.source_vm is None or args.public_key is None:
                raise Refused("--source-vm and --public-key required to authorize")
            phrase="AUTHORIZE-ONE-R288-"+args.source_vm.upper()+"-LOOPBACK-8877"
            result=provider_authorize(
                name=name,uid=uid,home=home,vm=args.source_vm,
                pub=args.public_key,confirm=_tty_approval(phrase))
        print(json.dumps(result,indent=2,sort_keys=True))
        print("R288_DEDICATED_OWNER_APPROVED_MONITOR_SSH_TRUST_NO_CHAIN_NO_DOCKER=true")
        return 0
    except (Refused,OSError,ValueError,TypeError,UnicodeError,KeyError,subprocess.SubprocessError) as exc:
        print("R288_MONITOR_TO_PROVIDER_SSH_BOOTSTRAP_REFUSED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
