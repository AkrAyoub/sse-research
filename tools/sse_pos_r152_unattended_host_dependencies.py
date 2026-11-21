#!/usr/bin/env python3
"""R152: unattended client-host dependencies from REAL VM4706/4707 lessons.

Ubuntu 24.04 signed Docker package, ZeroTier vendor GPG-signed installer
with pinned release-signing KEY fingerprint, actual public ad-hoc network
join, pinned Besu and Lighthouse OCI image digests. No user prompts,
wallets, new genesis or validator services. Only call for an explicitly
selected node role on a BRAND NEW host with the exact original genesis
already available. ZeroTier transport is an initial research bridge, NOT
claimed as decentralized Internet infrastructure or a permissionless
Ethereum native P2P discovery service.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.request

import sse_pos_r59_native_ipv6_observer as r59

VENDOR_KEY = "https://raw.githubusercontent.com/zerotier/ZeroTierOne/master/doc/contact%40zerotier.com.gpg"
VENDOR_SCRIPT = "https://install.zerotier.com/"
VENDOR_FINGERPRINT = "74A5E9C458E1A431F1DA57A71657198823E52A61"
NETWORK = r59.NETWORK

class Refused(ValueError):
    pass

def call(argv, *, timeout=240):
    if type(argv) is not list or any(type(s) is not str for s in argv):
        raise Refused("invalid command")
    try:
        p=subprocess.run(argv,capture_output=True,text=True,check=False,
                         timeout=timeout,env={
                             **os.environ,"DEBIAN_FRONTEND":"noninteractive",
                             "NEEDRESTART_MODE":"a","GIT_TERMINAL_PROMPT":"0",
                             "APT_LISTCHANGES_FRONTEND":"none"})
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise Refused("local system prerequisite unavailable") from exc
    if p.returncode:
        raise Refused("local prerequisite operation failed; inspect unattended host logs")
    return p.stdout

def fetch_https(url):
    if url not in (VENDOR_KEY,VENDOR_SCRIPT):
        raise Refused("unapproved third-party download URL")
    try:
        with urllib.request.urlopen(url,timeout=20) as r:
            data=r.read(200001)
    except OSError as exc:
        raise Refused("official signed vendor artifact unavailable") from exc
    if not 0<len(data)<=200000:
        raise Refused("oversized or empty vendor artifact")
    return data

def verify_official_install_script(key, signed, *, runner=call):
    if (type(key) is not bytes or type(signed) is not bytes
            or not 0<len(key)<=200000 or not 0<len(signed)<=200000):
        raise Refused("invalid vendor GPG artifacts")
    with tempfile.TemporaryDirectory(prefix="sse-zt-gpg-") as tmp:
        base=Path(tmp)
        base.chmod(0o700)
        keyfile=base/"vendor-key.gpg"
        signedfile=base/"official-signed-installer"
        plain=base/"verified-installer.sh"
        keyfile.write_bytes(key)
        signedfile.write_bytes(signed)
        runner(["gpg","--batch","--homedir",tmp,"--import",str(keyfile)])
        inventory=runner(["gpg","--batch","--homedir",tmp,
                          "--with-colons","--fingerprint"])
        fprs=[line.split(":")[9] for line in inventory.splitlines()
              if line.startswith("fpr:")]
        if len(fprs)!=1 or fprs[0].upper()!=VENDOR_FINGERPRINT:
            raise Refused("ZeroTier release key fingerprint differs")
        # GPG verifies the official clearsigned script and emits ONLY
        # independently authenticated script bytes. No pipe-to-shell.
        # With checked single primary key, a good signature cannot be from
        # a different imported identity.
        runner(["gpg","--batch","--homedir",tmp,"--output",str(plain),
                "--decrypt",str(signedfile)])
        if not plain.is_file() or plain.stat().st_size>200000:
            raise Refused("verified vendor script unavailable")
        return plain.read_bytes()

def setup(*, execute=False, runner=call, fetcher=fetch_https):
    if os.geteuid()!=0:
        raise Refused("root required for reviewed host provisioning")
    if not execute:
        return {
            "schema":"SSE_R152_HOST_PREREQUISITES_V1",
            "planned":True,"installed":False,
            "imagesPulled":False,"overlayJoined":False,
            "originalChainOrSigningKeysChanged":False,
        }
    runner(["apt-get","update","-qq"],timeout=180)
    runner(["apt-get","install","-y","-qq","--no-install-recommends",
            "docker.io","sudo","gnupg","ca-certificates","iproute2"],timeout=180)
    runner(["systemctl","enable","--now","docker"],timeout=80)
    if not Path("/usr/sbin/zerotier-one").exists():
        script=verify_official_install_script(
            fetcher(VENDOR_KEY),fetcher(VENDOR_SCRIPT),runner=runner)
        with tempfile.TemporaryDirectory(prefix="sse-zt-script-") as temp:
            path=Path(temp)/"verified-zerotier-install.sh"
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,"wb") as out:
                out.write(script)
            runner(["bash",str(path)],timeout=180)
    runner(["systemctl","enable","--now","zerotier-one"],timeout=80)
    # Fixed immutable *overlay identity for the original experimental
    # chain*, not a bootstrap peer, static endpoint or admission list.
    # ZeroTier PUBLIC ad-hoc does not require cloud operator admission.
    runner(["zerotier-cli","join",NETWORK],timeout=30)
    for image in (r59.BESU_REF,r59.LIGHTHOUSE_REF):
        runner(["docker","pull",image],timeout=300)
    # Confirm exact local image digests and architecture, NOT merely tag.
    r59.images()
    # Joining a public ad-hoc overlay is asynchronous. Actual 6plane IPv6
    # must be observed, not inferred from successful "join" submission.
    last_failure=None
    for attempt in range(12):
        try:
            iface,ip=r59.overlay_ip()
            break
        except r59.R59Refused as exc:
            last_failure=exc
            if attempt < 11:
                time.sleep(5)
    else:
        raise Refused("ZeroTier joined but usable actual overlay IPv6 not observed") from last_failure
    return {
        "schema":"SSE_R152_HOST_PREREQUISITES_V1",
        "installed":True,"imagesPulled":True,
        "overlayJoined":True,"observedOverlayInterface":iface,
        "observedDynamicOverlayIpv6":ip,
        "originalChainOrSigningKeysChanged":False,
        "nativeElClP2pVerified":False,
        "internetInfrastructureIndependent":False,
    }
