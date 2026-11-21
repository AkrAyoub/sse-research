#!/usr/bin/env python3
"""R63: original VM4706 operator-authorized ONE-TIME ZeroTier transport install.

--plan: read-only, verify current original signer and native clients
--install-and-join: explicit consent; install official Ubuntu24.04 signed apt
  repository package zerotier-one=1.16.2, join same PUBLIC ad-hoc network.
No Besu/Lighthouse/VC modifications, no EL/CL P2P started or published.
No private-LAN blockchain peer/ENR, no operator approval or static IP.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.request import Request, build_opener, ProxyHandler
import sse_pos_r60_owner_native_p2p_readonly_audit as r60

NETWORK = "ff2328775f000000"
VERSION = "1.16.2"
KEY_FINGERPRINT = "74A5E9C458E1A431F1DA57A71657198823E52A61"
KEY_URL = "https://raw.githubusercontent.com/zerotier/ZeroTierOne/master/doc/contact%40zerotier.com.gpg"
APT_REPO = "deb [signed-by=/usr/share/keyrings/zerotier-debian-package-key.gpg] https://download.zerotier.com/debian/noble noble main\n"
ROOT_KEY = "/usr/share/keyrings/zerotier-debian-package-key.gpg"
ROOT_SOURCE = "/etc/apt/sources.list.d/zerotier-sse.list"
G2_CONTAINERS = (r60.EL, r60.BN, r60.VC)

class R63Refused(ValueError):
    pass

def call(args: list[str], timeout: int = 25) -> str:
    try:
        p=subprocess.run(args, capture_output=True, text=True,
                         errors="replace", timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise R63Refused("reviewed local command unavailable or timed out") from exc
    if p.returncode:
        # Never print uncontrolled stderr: package/script output can include secrets.
        raise R63Refused("reviewed local command failed; do not retry blindly")
    return p.stdout.strip()

def priv(args: list[str], timeout: int = 25) -> str:
    return call(["sudo","-n",*args], timeout=timeout)

def os_guard() -> None:
    if platform.system()!="Linux" or platform.machine()!="x86_64":
        raise R63Refused("verified original Linux amd64 only")
    raw={}
    for line in Path("/etc/os-release").read_text("utf-8").splitlines():
        if "=" in line:
            k,v=line.split("=",1)
            raw[k]=v.strip('"')
    if (raw.get("ID"), raw.get("VERSION_ID"), raw.get("VERSION_CODENAME")) != ("ubuntu","24.04","noble"):
        raise R63Refused("requires original Ubuntu 24.04 noble exact OS")

def original_state_guard(commit: str) -> None:
    r60.owner_guard(commit)
    os_guard()
    state={}
    for name in G2_CONTAINERS:
        state[name]=priv(["docker","inspect","--format","{{.State.Running}}",name])
        if state[name]!="true":
            raise R63Refused("original EL/BN/VC must remain running")
        mode=priv(["docker","inspect","--format","{{.HostConfig.NetworkMode}}",name])
        if mode!=r60.NET:
            raise R63Refused("original signer/client Docker network changed")
    if priv(["docker","network","inspect","--format","{{.Internal}}",r60.NET])!="true":
        raise R63Refused("original isolated signer bridge not intact")

def default_route() -> str:
    data=call(["ip","-j","-4","route","show","default"])
    try:
        routes=json.loads(data)
    except (ValueError,UnicodeError) as exc:
        raise R63Refused("host default IPv4 route unreadable") from exc
    if not isinstance(routes,list) or not routes:
        raise R63Refused("management default route is missing")
    return json.dumps(routes,sort_keys=True,separators=(",",":"))

def membership() -> tuple[bool,str|None]:
    if shutil.which("zerotier-cli") is None:
        return False,None
    raw=priv(["zerotier-cli","-j","listnetworks"],timeout=15)
    try:
        networks=json.loads(raw)
    except (ValueError,UnicodeError) as exc:
        raise R63Refused("overlay membership response invalid") from exc
    if not isinstance(networks,list):
        raise R63Refused("overlay membership not a list")
    relevant=[n for n in networks if isinstance(n,dict) and n.get("nwid")==NETWORK]
    if not relevant:
        return False,None
    if len(relevant)!=1 or relevant[0].get("type")!="PUBLIC":
        raise R63Refused("unexpected existing overlay membership")
    if relevant[0].get("status") in ("REQUESTING_CONFIGURATION","NOT_FOUND"):
        return False,None  # asynchronous post-join provisioning; not confirmed
    if relevant[0].get("status")!="OK":
        raise R63Refused("existing ad-hoc network status is not healthy")
    assigned=relevant[0].get("assignedAddresses",[])
    if not isinstance(assigned,list):
        raise R63Refused("overlay IPv6 assignments invalid")
    ipv6=[x.partition("/")[0] for x in assigned if isinstance(x,str) and x.startswith("fca0:")]
    if len(ipv6)!=1 or not re.fullmatch(r"[a-f0-9:]{8,45}",ipv6[0]):
        raise R63Refused("unexpected overlay 6plane address")
    return True,ipv6[0]

def plan(commit: str) -> dict:
    original_state_guard(commit)
    route=default_route()
    installed=shutil.which("zerotier-cli") is not None
    active,addr=membership()
    if installed:
        version=priv(["zerotier-cli","-v"])
        if VERSION not in version:
            raise R63Refused("existing ZeroTier version differs from fixed 1.16.2")
    return {
        "schema":"SSE_R63_ORIGINAL_OWNER_SAME_PUBLIC_OVERLAY_ONE_TIME_INSTALL_PLAN_V1",
        "sourceGitExactSha":commit,
        "originalChain31340GenesisAndJwtMetadataVerified":True,
        "originalELBeaconVCStillRunning":True,
        "originalIsolatedDockerBridgeUnchanged":True,
        "hostIpv4DefaultRoutePresent":bool(route),
        "zeroTierClientAlreadyInstalled":installed,
        "alreadyOnExactPublicControllerlessNetwork":active,
        "actualHostOverlay6planeIpv6":addr,
        "targetNetworkId":NETWORK,
        "targetZeroTierVersion":VERSION,
        "officialGpgSignedAptRepositoryPlanned":True,
        "officialGpgRepositoryActuallyConfiguredByPlan":False,
        "signedZeroTierPackageActuallyInstalledByPlan":False,
        "officialGpgKeyFingerprintExpected":KEY_FINGERPRINT,
        "noNativeEthereumP2pStarted":True,
        "noHostNetworkOrSignerMutationByPlan":True,
        "originalChainFinalityRecheckedByThisPlan":False,
        "noPrivateLanNativePeerBootstrap":True,
        "thirdPartyZeroTierRootRelayDependencyRemains":True,
    }

def fetch_official_key(path: Path) -> None:
    opener=build_opener(ProxyHandler({}))
    req=Request(KEY_URL,headers={"User-Agent":"sse-chain31340-owner-zerotier-package-verify/1"})
    try:
        with opener.open(req,timeout=20) as res:
            data=res.read(120_001)
            if res.status!=200 or len(data)>120_000 or len(data)<1000:
                raise R63Refused("ZeroTier publisher key fetch invalid")
    except (OSError,ValueError) as exc:
        raise R63Refused("cannot retrieve official publisher key") from exc
    if not data.startswith(b"-----BEGIN PGP PUBLIC KEY BLOCK-----"):
        raise R63Refused("expected signed-publisher PGP armored key")
    with path.open("xb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())

def verify_key(path: Path) -> None:
    listing=call(["gpg","--batch","--with-colons","--show-keys",str(path)])
    fingerprints=[line.split(":")[9] for line in listing.splitlines()
                  if line.startswith("fpr:") and len(line.split(":"))>9]
    if KEY_FINGERPRINT not in fingerprints:
        raise R63Refused("official ZeroTier signing-key fingerprint mismatch")

def ensure_no_existing_package_sources() -> None:
    for path in (ROOT_KEY,ROOT_SOURCE,"/etc/apt/sources.list.d/zerotier.list"):
        # Reject existing files AND broken symlinks; do not overwrite any
        # package source/key material installed by another administrator.
        for flag in ("-e","-L"):
            try:
                p=subprocess.run(["sudo","-n","test",flag,path],
                                 capture_output=True,timeout=10)
            except (OSError,subprocess.TimeoutExpired) as exc:
                raise R63Refused("cannot safely inspect apt repository state") from exc
            if p.returncode==0:
                raise R63Refused("ZeroTier repository state already exists; manual review required")
            if p.returncode!=1:
                raise R63Refused("cannot safely inspect existing apt repository state")

def install_and_join(commit: str) -> dict:
    outcome=plan(commit)
    if outcome["zeroTierClientAlreadyInstalled"] or outcome["alreadyOnExactPublicControllerlessNetwork"]:
        raise R63Refused("ZeroTier already installed; no second installation or rejoin")
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        raise R63Refused("local interactive owner authorization required")
    if shutil.which("gpg") is None or shutil.which("apt-get") is None:
        raise R63Refused("system GPG / apt tooling absent")
    ensure_no_existing_package_sources()
    print("ONE-TIME network service installation: ZeroTier official GPG-signed Ubuntu 24.04 apt package 1.16.2; "
          "joins only public controllerless ad-hoc IPv6 network ff2328775f000000; "
          "does not change running Ethereum containers, keys, JWT or Docker networks. "
          "New host interface and outbound overlay connectivity will be created. "
          "Do not repeat automatically after a partial failure.",file=sys.stderr)
    answer=input("Type INSTALL-OWNER-OPEN-P2P-TRANSPORT: ")
    if answer!="INSTALL-OWNER-OPEN-P2P-TRANSPORT":
        raise R63Refused("local owner did not authorize transport installation")
    oldroute=default_route()
    with tempfile.TemporaryDirectory(prefix="sse-r63-zt-pub-") as tmp:
        td=Path(tmp)
        key=td/"publisher.asc"
        keyring=td/"publisher.gpg"
        source=td/"zerotier-sse.list"
        fetch_official_key(key)
        verify_key(key)
        call(["gpg","--batch","--dearmor","--output",str(keyring),str(key)])
        source.write_text(APT_REPO,"utf-8")
        priv(["install","-m","0644",str(keyring),ROOT_KEY])
        priv(["install","-m","0644",str(source),ROOT_SOURCE])
    # APT verifies a GPG-signed InRelease for THIS repository and its
    # package hash. Never execute curl|bash or accept unsigned packages.
    priv(["apt-get","update","-o","Acquire::Retries=1"],timeout=180)
    priv(["apt-get","install","-y","--no-install-recommends","zerotier-one="+VERSION],timeout=180)
    version=priv(["zerotier-cli","-v"],timeout=15)
    if VERSION not in version:
        raise R63Refused("installed ZeroTier version not pinned 1.16.2")
    # Service will have created its own host-local transport identity; it is
    # NOT an Ethereum validator key and must not be uploaded or copied.
    priv(["zerotier-cli","join",NETWORK],timeout=20)
    for setting in ("allowDefault=0","allowDNS=0","allowGlobal=0"):
        priv(["zerotier-cli","set",NETWORK,setting],timeout=12)
    if default_route()!=oldroute:
        raise R63Refused("host IPv4 management default route unexpectedly changed; do not rerun")
    # Membership can be temporarily REQUESTING_CONFIGURATION after join;
    # report no success until operator confirms OK PUBLIC + new 6plane IPv6.
    active,addr=membership()
    original_state_guard(commit)
    outcome.update({
        "mode":"one_time_owner_authorized_transport_install",
        "signedOfficialZeroTierPackageInstalled":True,
        "officialRepositoryConfiguredDuringInstall":True,
        "joinedPublicControllerlessOverlayConfirmed":active,
        "overlayProvisioningMayStillBePending":not active,
        "observedHost6planeIpv6":addr,
        "originalHostDefaultIpv4RouteUnchanged":True,
        "originalNativeExecutionP2pStillDisabled":True,
        "originalNativeConsensusAndExecutionServicesUnmodified":True,
        "actualNativeEthereumPeerHandshakeObserved":False,
    })
    return outcome

def main() -> int:
    parser=argparse.ArgumentParser(description="Same open-join ZeroTier native-P2P TRANSPORT on original owner VM")
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--plan",action="store_true")
    modes.add_argument("--install-and-join",action="store_true")
    parser.add_argument("--expected-commit",required=True)
    args=parser.parse_args()
    try:
        result=plan(args.expected_commit) if args.plan else install_and_join(args.expected_commit)
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0
    except (R63Refused,r60.R60Refused,OSError,ValueError,TypeError,KeyError,subprocess.TimeoutExpired) as exc:
        print("R63_SAME_OPEN_TRANSPORT_REFUSED: "+type(exc).__name__,file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
