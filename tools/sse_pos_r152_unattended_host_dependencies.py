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
import urllib.error
import urllib.request

import sse_pos_r59_native_ipv6_observer as r59

VENDOR_KEY = "https://raw.githubusercontent.com/zerotier/ZeroTierOne/master/doc/contact%40zerotier.com.gpg"
VENDOR_SCRIPT = "https://install.zerotier.com/"
VENDOR_FINGERPRINT = "74A5E9C458E1A431F1DA57A71657198823E52A61"
NETWORK = r59.NETWORK
# ZeroTier upstream installer source maps Ubuntu 24.04 -> noble, and
# points apt at download.zerotier.com/debian/noble. Use HTTPS and a
# fingerprint-verified scoped signing key instead of the HTTP403 script.
ZEROTIER_APT_URL="https://download.zerotier.com/debian/noble"
ZEROTIER_APT_LINE=(
    "deb [arch=amd64 signed-by=/usr/share/keyrings/sse-zerotier.gpg] "
    +ZEROTIER_APT_URL+" noble main\n"
)
ZEROTIER_KEYRING=Path("/usr/share/keyrings/sse-zerotier.gpg")
ZEROTIER_APT_SOURCE=Path("/etc/apt/sources.list.d/sse-zerotier.list")
# Exact R175 malformed line observed on VM4709; no arbitrary rewrites.
ZEROTIER_APT_R175_BAD_LINE=ZEROTIER_APT_LINE[:-1]+chr(92)+"n"


class Refused(ValueError):
    pass

def stage_of(argv):
    """Public fixed labels only; never log arguments, scripts or tokens."""
    if argv[:2]==["apt-get","update"]:
        return "APT_UPDATE"
    if argv[:2]==["apt-get","install"]:
        return ("ZEROTIER_SIGNED_APT_INSTALL" if "zerotier-one" in argv
                else "APT_DOCKER_GNUPG")
    if argv[:3]==["systemctl","enable","--now"]:
        return ("DOCKER_DAEMON" if argv[-1]=="docker"
                else "ZEROTIER_DAEMON" if argv[-1]=="zerotier-one"
                else "SYSTEMD_UNIT")
    if argv and argv[0]=="gpg":
        return "ZEROTIER_GPG_VERIFY"
    if argv and argv[0]=="bash":
        return "ZEROTIER_VENDOR_INSTALL"
    if argv[:2]==["zerotier-cli","join"]:
        return "ZEROTIER_JOIN"
    if argv[:2]==["docker","pull"]:
        return "PINNED_CLIENT_IMAGE_PULL"
    return "HOST_DEPENDENCY"

def call(argv, *, timeout=240):
    if type(argv) is not list or any(type(s) is not str for s in argv):
        raise Refused("invalid command")
    stage=stage_of(argv)
    try:
        p=subprocess.run(argv,capture_output=True,text=True,check=False,
                         timeout=timeout,env={
                             **os.environ,"DEBIAN_FRONTEND":"noninteractive",
                             "NEEDRESTART_MODE":"a","GIT_TERMINAL_PROMPT":"0",
                             "APT_LISTCHANGES_FRONTEND":"none"})
    except subprocess.TimeoutExpired as exc:
        raise Refused("R152_"+stage+"_TIMED_OUT") from exc
    except OSError as exc:
        raise Refused("R152_"+stage+"_UNAVAILABLE") from exc
    if p.returncode:
        raise Refused(f"R152_{stage}_EXIT_{p.returncode}")
    return p.stdout

def fetch_https(url):
    if url not in (VENDOR_KEY,VENDOR_SCRIPT):
        raise Refused("unapproved third-party download URL")
    stage=("ZEROTIER_SIGNING_KEY_DOWNLOAD" if url==VENDOR_KEY
           else "ZEROTIER_SIGNED_INSTALLER_DOWNLOAD")
    try:
        with urllib.request.urlopen(url,timeout=20) as r:
            if r.status!=200:
                raise Refused("R152_"+stage+"_UNEXPECTED_HTTP_STATUS")
            data=r.read(200001)
    except urllib.error.HTTPError as exc:
        # An explicit 404/403 pinpoints the missing external artifact.
        # Never disclose complete URLs, proxy headers or remote bodies.
        raise Refused(f"R152_{stage}_HTTP_{exc.code}") from exc
    except urllib.error.URLError as exc:
        # DNS, TLS, egress, and proxy failures differ from HTTP 4xx.
        raise Refused("R152_"+stage+"_TRANSPORT_UNAVAILABLE") from exc
    except (OSError,TimeoutError) as exc:
        raise Refused("R152_"+stage+"_TRANSPORT_UNAVAILABLE") from exc
    if not 0<len(data)<=200000:
        raise Refused("oversized or empty vendor artifact")
    return data

def verify_primary_vendor_key_fingerprint(colon_report):
    """Require exactly one release certificate, allow its actual subkeys.

    GPG --with-colons prints an fpr for the primary pub and may print
    additional fpr lines for legitimate sub keys. The old len(fprs)==1
    incorrectly rejected valid certificates with subkeys.
    """
    if type(colon_report) is not str:
        raise Refused("missing GPG public key inventory")
    primaries=[]
    expecting=False
    for line in colon_report.splitlines():
        columns=line.split(":")
        kind=columns[0]
        if kind=="pub":
            primaries.append(None)
            expecting=True
        elif kind=="sub":
            expecting=False
        elif kind=="fpr" and expecting and primaries:
            if len(columns)<=9 or primaries[-1] is not None:
                raise Refused("ambiguous vendor primary key fingerprint")
            primaries[-1]=columns[9].upper()
            expecting=False
    if primaries!=[VENDOR_FINGERPRINT]:
        raise Refused("ZeroTier release primary key fingerprint differs")
    return True

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
        verify_primary_vendor_key_fingerprint(inventory)
        # GPG verifies the official clearsigned script and emits ONLY
        # independently authenticated script bytes. No pipe-to-shell.
        # With checked single primary key, a good signature cannot be from
        # a different imported identity.
        runner(["gpg","--batch","--homedir",tmp,"--output",str(plain),
                "--decrypt",str(signedfile)])
        if not plain.is_file() or plain.stat().st_size>200000:
            raise Refused("verified vendor script unavailable")
        return plain.read_bytes()

def verify_vendor_repo_metadata(*,getter=None):
    """Read-only HTTPS transport check; apt separately verifies GPG signature."""
    url=ZEROTIER_APT_URL+"/dists/noble/InRelease"
    if getter is None:
        def getter(target):
            request=urllib.request.Request(
                target,headers={"User-Agent":"SSE-chain31340-zerotier-apt-check"})
            with urllib.request.urlopen(request,timeout=15) as response:
                if response.status!=200:
                    raise Refused("R175_ZEROTIER_APT_METADATA_BAD_STATUS")
                return response.read(131073)
    try:
        data=getter(url)
    except urllib.error.HTTPError as exc:
        raise Refused(f"R175_ZEROTIER_APT_METADATA_HTTP_{exc.code}") from exc
    except (urllib.error.URLError,OSError,TimeoutError) as exc:
        raise Refused("R175_ZEROTIER_APT_METADATA_TRANSPORT_UNAVAILABLE") from exc
    if (type(data) is not bytes or not 0<len(data)<=131072 or
            not data.startswith(b"-----BEGIN PGP SIGNED MESSAGE-----")):
        raise Refused("R175_ZEROTIER_APT_METADATA_NOT_CLEAR_SIGNED")
    return {"officialNobleRepoMetadataReachable":True,
            "aptSignatureVerificationStillRequired":True,
            "aptOrServiceStateModified":False}

def install_verified_zerotier_apt(*, runner=call, fetcher=fetch_https,
                                  keyring=ZEROTIER_KEYRING,
                                  source=ZEROTIER_APT_SOURCE):
    """Root-only install via upstream Noble apt packages, not installer script.

    The exact ZeroTier primary signing key is pinned, and APT must validate
    the vendor-signed Release metadata through signed-by. Never invoke
    apt with AllowUnauthenticated / trusted=yes or run unreviewed scripts.
    Existing nonmatching files are refused, never overwritten.
    """
    if os.geteuid()!=0:
        raise Refused("root required for verified ZeroTier apt source")
    verify_vendor_repo_metadata()
    key=fetcher(VENDOR_KEY)
    if type(key) is not bytes or not 0<len(key)<=200000:
        raise Refused("R175_ZEROTIER_SIGNING_KEY_UNAVAILABLE")
    with tempfile.TemporaryDirectory(prefix="sse-zt-apt-") as td:
        tmp=Path(td)
        tmp.chmod(0o700)
        original=tmp/"upstream-public-key.gpg"
        prepared=tmp/"verified-zerotier.gpg"
        original.write_bytes(key)
        runner(["gpg","--batch","--homedir",str(tmp),
                "--import",str(original)])
        report=runner(["gpg","--batch","--homedir",str(tmp),
                       "--with-colons","--fingerprint"])
        verify_primary_vendor_key_fingerprint(report)
        runner(["gpg","--batch","--yes","--dearmor","--output",
                str(prepared),str(original)])
        converted=prepared.read_bytes()
        if not 0<len(converted)<=200000:
            raise Refused("R175_ZEROTIER_VERIFIED_KEYRING_EMPTY")
    # Existing verified keyring must match. Only the precise R175 single
    # malformed line (literal backslash+n) is eligible for repair. All
    # unrelated existing repo configuration remains protected.
    for location,body in (
        (keyring,converted),
        (source,ZEROTIER_APT_LINE.encode("ascii")),
    ):
        if location.is_symlink():
            raise Refused("R175_ZEROTIER_APT_CONFIG_SYMLINK_REFUSED")
        if location.exists():
            if not location.is_file():
                raise Refused("R175_ZEROTIER_APT_CONFIG_CONFLICT")
            existing=location.read_bytes()
            if existing==body:
                # APT's _apt sandbox must read the public keyring even under umask 077.
                os.chmod(location,0o644)
                continue
            if (location!=source or
                    existing!=ZEROTIER_APT_R175_BAD_LINE.encode("ascii")):
                raise Refused("R175_ZEROTIER_APT_CONFIG_CONFLICT")
            # Atomic, exclusive same-directory replacement; never truncate
            # an existing file, never touch original keyring or chain state.
            with tempfile.NamedTemporaryFile(prefix=".sse-r177-",
                    dir=source.parent,delete=False) as out:
                staged=Path(out.name)
                try:
                    os.fchmod(out.fileno(),0o644)
                    out.write(body)
                    out.flush()
                    os.fsync(out.fileno())
                except BaseException:
                    staged.unlink(missing_ok=True)
                    raise
            try:
                if source.is_symlink() or source.read_bytes()!=existing:
                    raise Refused("R177_ZEROTIER_REPO_CHANGED_DURING_REPAIR")
                os.replace(staged,source)
            finally:
                staged.unlink(missing_ok=True)
            continue
        fd=os.open(location,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
        with os.fdopen(fd,"wb") as out:
            os.fchmod(out.fileno(),0o644)
            out.write(body)
            out.flush()
            os.fsync(out.fileno())
    runner(["apt-get","update","-qq"],timeout=180)
    runner(["apt-get","install","-y","-qq","--no-install-recommends",
            "zerotier-one"],timeout=180)
    if not Path("/usr/sbin/zerotier-one").is_file():
        raise Refused("R175_ZEROTIER_APT_PACKAGE_NOT_INSTALLED")
    return True

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
        install_verified_zerotier_apt(runner=runner,fetcher=fetcher)
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
