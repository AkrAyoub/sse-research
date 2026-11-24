#!/usr/bin/env python3
"""R291 common no-controller SSE31340 transport for NEW resource/monitor/peer hosts.

THE EXISTING NETWORK is ZeroTier controllerless public ad-hoc IPv6,
ff2328775f000000, fca0::/16; the same overlay underlies genuine
VM4706/VM4707/VM4709 Besu + Lighthouse native P2P. Any Linux
participant may join without *network operator* approval; it still
requires its own local OS permission, installed ZeroTier and egress.
ZeroTier planets/relays are external transport dependencies, not
a proof of infrastructure-independent public native Internet P2P.

--status  read-only local ZeroTier+overlay network observation.
--join    separate interactive local operator consent to execute ONLY
          sudo -n zerotier-cli join ff2328775f000000. No other writes.

No Docker, Ethereum RPC, validator/EVM/SSH keys, network listen,
iptables, sshd, app provider/monitor enrollment, "private LAN"
transport, or user-registration service. Does NOT claim that a
network join is a native EL/CL peer handshake or signed SLA.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import platform
import pwd
import shutil
import subprocess
import sys

NETWORK_ID="ff2328775f000000"
OVERLAY=ipaddress.IPv6Network("fca0::/16")
MIN_PORT=9000
MAX_PORT=30559
REQUIRED_PORTS=(9000,9001,29000,29001,29002,29080,30303,30404)
PROTECTED_ORIGINAL_OWNERS=frozenset({
    "ayoubakrvm4706","ayoubakrvm4707","ayoubakrvm4709"
})


class Refused(ValueError):
    pass


def protocol_guard():
    if (len(NETWORK_ID)!=16 or not NETWORK_ID.startswith("ff") or
        NETWORK_ID[10:]!="000000" or
        int(NETWORK_ID[2:6],16)!=MIN_PORT or
        int(NETWORK_ID[6:10],16)!=MAX_PORT or
        not all(MIN_PORT<=p<=MAX_PORT for p in REQUIRED_PORTS)):
        raise Refused("original public controllerless overlay P2P policy changed")
    return {
        "publicControllerlessZeroTierNetworkId":NETWORK_ID,
        "destinationPortMinimum":MIN_PORT,
        "destinationPortMaximum":MAX_PORT,
        "originalNativeBesuP2pPortsIncluded":True,
        "originalNativeLighthouseP2pPortsIncluded":True,
        "independentOverlayEchoPortsIncluded":True,
        "futureAuthenticatedProviderPort29080Included":True,
        "sshPort22ExcludedFromOverlay":True,
        "enginePort8551ExcludedFromOverlay":True,
        "networkControllerInvitationRequired":False,
        "thirdPartyPlanetaryRootsAndRelaysStillRequired":True,
    }


def _sudo_json(operation,*,run=subprocess.run):
    if operation not in ("info","listnetworks"):
        raise Refused("only two fixed read-only ZeroTier commands permitted")
    argv=["sudo","-n","zerotier-cli","-j",operation]
    try:
        process=run(argv,capture_output=True,text=True,shell=False,
                    timeout=8,check=False)
    except (OSError,subprocess.TimeoutExpired):
        return None
    if (process.returncode!=0 or
        type(process.stdout) is not str or len(process.stdout)>65536):
        return None
    try:
        return json.loads(process.stdout)
    except (ValueError,TypeError):
        return None


def _member(networks):
    if type(networks) is not list:
        return None,None,None
    matches=[entry for entry in networks
             if type(entry) is dict and entry.get("nwid")==NETWORK_ID]
    if len(matches)!=1:
        return None,None,None
    network=matches[0]
    if network.get("status")!="OK" or network.get("type")!="PUBLIC":
        return network,None,None
    assigned=network.get("assignedAddresses")
    if type(assigned) is not list:
        return network,None,None
    seen=set()
    for raw in assigned:
        if type(raw) is not str:
            continue
        try:
            ip=ipaddress.ip_interface(raw).ip
        except ValueError:
            continue
        if (ip.version==6 and ip in OVERLAY and
            not ip.is_multicast and not ip.is_unspecified):
            seen.add(str(ip))
    if len(seen)!=1:
        return network,None,None
    interface=network.get("portDeviceName")
    if (type(interface) is not str or not interface.startswith("zt") or
        len(interface)>20 or not interface[2:].isalnum()):
        return network,None,None
    return network,next(iter(seen)),interface


def status(*,run=subprocess.run,which=shutil.which):
    protocol=protocol_guard()
    installed=bool(which("zerotier-cli"))
    info=_sudo_json("info",run=run) if installed else None
    networks=_sudo_json("listnetworks",run=run) if installed else None
    membership,ip,interface=_member(networks)
    has_cli=(type(info) is dict and type(networks) is list)
    online=(has_cli and info.get("online") is True)
    ready=bool(online and membership and membership.get("status")=="OK" and
               membership.get("type")=="PUBLIC" and ip and interface)
    return {
        "schema":"SSE_R291_ROLE_NEUTRAL_EXISTING_PUBLIC_IPV6_OVERLAY_READONLY_V1",
        **protocol,
        "zerotierClientInstalled":installed,
        "readOnlyZeroTierCliAccessible":has_cli,
        "daemonReportsOnline":bool(online),
        "networkIsJoined":membership is not None,
        "networkReportsOkPublic":bool(membership and
                                     membership.get("status")=="OK" and
                                     membership.get("type")=="PUBLIC"),
        "assignedActual6planeIpv6":ip,
        "actualOverlayInterface":interface,
        "actualOpenOverlayReadyForCrossHostTransport":ready,
        "private10Dot50InfrastructureAddressUsedForDataPlane":False,
        "participantRoleOrVmAllowlistControlsOverlayAdmission":False,
        "nativeBesuLighthousePeerHandshakeVerified":False,
        "physicalIndependentInternetIspVerified":False,
        "providerSignedHttpsEndpointVerified":False,
        "marketplacePaidLeaseOrSlaVerified":False,
        "dockerOrSshModified":False,
        "walletValidatorOrEvmRpcTouched":False,
        "hostNetworkOrAptModified":False,
    }


def _operator_guard(*,uid_fn=os.geteuid,user_fn=None,
                    os_name=platform.system,arch=platform.machine,
                    home_fn=Path.home):
    if user_fn is None:
        user_fn=lambda u:pwd.getpwuid(u).pw_name
    uid=uid_fn()
    if uid==0 or os_name()!="Linux" or arch() not in ("x86_64","aarch64"):
        raise Refused("join requires ordinary nonroot Linux operator console")
    username=user_fn(uid)
    if username in PROTECTED_ORIGINAL_OWNERS:
        raise Refused("original live Besu/Lighthouse owners protected: use existing R63/R151 machinery")
    home=home_fn()
    for sub in (
        ".local/share/sse-r35-chain31340-g2-private",
        ".local/share/sse-r27-bls-operator-private",
    ):
        path=home/sub
        if path.exists() or path.is_symlink():
            raise Refused("original BLS/signing material present: no role-machine join")
    return username


def join(*,run=subprocess.run,which=shutil.which,
         input_fn=input,stdin=None,stderr=None,
         owner_guard=_operator_guard):
    username=owner_guard()
    report=status(run=run,which=which)
    if report["actualOpenOverlayReadyForCrossHostTransport"]:
        return {**report,"joinAction":"ALREADY_JOINED_READONLY","joinCommandSent":False}
    if not report["zerotierClientInstalled"]:
        raise Refused("ZeroTier client absent; use independently reviewed signed vendor APT install first")
    if not report["readOnlyZeroTierCliAccessible"]:
        raise Refused("local sudo -n ZeroTier CLI info/listnetworks unavailable")
    if not report["daemonReportsOnline"]:
        raise Refused("existing ZeroTier daemon is not online; do not attempt join")
    if report["networkIsJoined"]:
        raise Refused("existing network not healthy; inspect without rejoining")
    ins=sys.stdin if stdin is None else stdin
    err=sys.stderr if stderr is None else stderr
    if not (ins.isatty() and err.isatty()):
        raise Refused("actual interactive operator terminal required")
    phrase="JOIN-EXISTING-OPEN-SSE31340-ZEROTIER"
    if input_fn(
        "Join the SAME public open controllerless IPv6 network "
        "ff2328775f000000 (ZeroTier vendor root/relay dependency). "
        "No Ethereum keys, SSH trust or Docker modified. Type "+phrase+": "
    )!=phrase:
        raise Refused("no exact independent owner approval for local overlay join")
    argv=["sudo","-n","zerotier-cli","join",NETWORK_ID]
    try:
        p=run(argv,capture_output=True,text=True,shell=False,
              timeout=15,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise Refused("local ZeroTier join command unavailable or timed out") from exc
    if p.returncode!=0:
        raise Refused("real open-join ZeroTier CLI command refused; no fallback network")
    next_state=status(run=run,which=which)
    return {
        **next_state,
        "joinAction":"PUBLIC_ADHOC_NETWORK_JOIN_COMMAND_SENT",
        "joinCommandSent":True,
        "joinedAsLocalOwner":username,
        "membershipRequiresRecheckingWhenAsync":not next_state[
            "actualOpenOverlayReadyForCrossHostTransport"
        ],
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    m=p.add_mutually_exclusive_group(required=True)
    m.add_argument("--status",action="store_true",
                   help="real read-only existing open-join ZeroTier status")
    m.add_argument("--join",action="store_true",
                   help="real exact locally authorized join ONLY, no apt/daemon/network changes")
    args=p.parse_args(argv)
    try:
        report=status() if args.status else join()
        print(json.dumps(report,indent=2,sort_keys=True))
        print("R291_SAME_PERMISSIONLESS_OVERLAY_NO_PRIVATE_LAN_NO_NATIVE_MUTATION=true")
        return 0
    except (Refused,TypeError,ValueError,OSError,KeyError) as exc:
        print("R291_OPEN_PARTICIPANT_OVERLAY_REFUSED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
