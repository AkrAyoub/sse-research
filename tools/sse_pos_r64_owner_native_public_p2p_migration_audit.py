#!/usr/bin/env python3
"""R64 original-owner CURRENT state-preserving public-native P2P migration gate.

Read-only. Confirms completed R63 owner open-join overlay + actual R62 EL+CL
local chain health. Inventories original Docker startup/mount relationships
without disclosing host private paths, argv passwords, JWT, signing keys.
No Docker/container/network changes, backup, key export or new P2P service.
"""
from __future__ import annotations
import argparse
import ipaddress
import json
from pathlib import Path
import re
import sys
import sse_pos_r62_original_container_namespace_health as r62
import sse_pos_r63_owner_open_overlay_install as r63

class R64Refused(ValueError):
    pass

SAFE_ARG_KEYS={
 "network-id","p2p-enabled","p2p-port","p2p-port-ipv6",
 "p2p-interface","p2p-interface-ipv6","p2p-host-ipv6",
 "discovery-enabled","discovery-mode","discovery-port","discovery-port6",
 "listen-address","port","port6","quic-port6",
 "enr-address","enr-tcp6-port","enr-udp6-port","enr-quic6-port",
 "enable-private-discovery","disable-upnp","nat-method",
 "rpc-http-enabled","rpc-http-port","engine-rpc-enabled","engine-rpc-port",
 "http","http-port","http-address","allow-insecure-genesis-sync",
}
# Exclude key paths, CLI args, full Docker argv, full env, host volume sources,
# wallet/validator path and Engine secret. Only known-safe network option values.
SAFE_VAL=re.compile(r"[A-Za-z0-9.:,_-]{1,72}\Z")
NO_VALUE_KEYS={"rpc-http-enabled","engine-rpc-enabled","http",
               "enable-private-discovery","disable-upnp",
               "allow-insecure-genesis-sync"}

def safe_runtime_flags(args: object) -> dict:
    if not isinstance(args,list) or not all(isinstance(x,str) for x in args):
        raise R64Refused("unexpected Docker command array")
    out={}
    for value in args:
        if not value.startswith("--"):
            continue
        key,sep,val=value[2:].partition("=")
        if key not in SAFE_ARG_KEYS:
            continue
        if sep:
            if not SAFE_VAL.fullmatch(val):
                raise R64Refused("unsafe networking flag value")
            out.setdefault(key,[]).append(val)
        elif key in NO_VALUE_KEYS:
            out.setdefault(key,[]).append("enabled")
    return out

def safe_mounts(raw: str) -> dict:
    try:
        mounts=json.loads(raw)
    except (TypeError,ValueError) as exc:
        raise R64Refused("Docker mounts not valid JSON") from exc
    if not isinstance(mounts,list) or len(mounts)>20:
        raise R64Refused("original Docker mount layout unexpectedly changed")
    allowed={"/data","/testnet","/jwt/engine.jwt","/validators",
             "/validator","/secrets","/wallets","/slashing-protection"}
    names=[]
    all_bind=True
    for m in mounts:
        if not isinstance(m,dict):
            raise R64Refused("Docker mount has invalid shape")
        t=m.get("Type")
        if t!="bind":
            all_bind=False
        target=m.get("Destination")
        # Do not include any unknown/secret-bearing path in printed JSON.
        names.append(target if target in allowed else "<redacted_other_mount>")
    return {
        "mountCount":len(mounts),
        "knownMountTargetsOnly":sorted(names),
        "allExistingMountsAreBinds":all_bind,
        "hostMountSourcePathsNeverPrinted":True,
        "mountContentsOrSignerFilesNeverRead":True,
    }

def original_container(name: str) -> dict:
    state=json.loads(r63.priv(["docker","inspect","--format","{{json .State}}",name]))
    if not isinstance(state,dict) or state.get("Running") is not True:
        raise R64Refused("original EL/BN/VC not running")
    network=r63.priv(["docker","inspect","--format","{{.HostConfig.NetworkMode}}",name])
    if network!=r63.r60.NET:
        raise R64Refused("original Docker bridge mode not preserved")
    networks=json.loads(r63.priv(["docker","inspect","--format",
                                  "{{json .NetworkSettings.Networks}}",name]))
    if not isinstance(networks,dict) or set(networks)!={r63.r60.NET}:
        raise R64Refused("original signing containers gained an unreviewed network")
    args=json.loads(r63.priv(["docker","inspect","--format","{{json .Config.Cmd}}",name]))
    mounts=safe_mounts(r63.priv(["docker","inspect","--format","{{json .Mounts}}",name]))
    img=r63.priv(["docker","inspect","--format","{{.Image}}",name])
    if not re.fullmatch("sha256:[0-9a-f]{64}",img):
        raise R64Refused("original native client image identity invalid")
    return {
        "originalStillRunning":True,
        "originalDockerInternalOnly":True,
        "noExtraAttachedNetworks":True,
        "immutableDockerImageIdentityPresent":True,
        "reviewedNetworkRuntimeFlags":safe_runtime_flags(args),
        "originalPreservedMountLayout":mounts,
        "noContainerRecreatedOrDockerNetworkChanged":True,
    }

def safe_overlay_address(addr: object) -> str:
    if not isinstance(addr,str):
        raise R64Refused("no owner overlay address")
    try:
        ipv6=ipaddress.IPv6Address(addr)
    except ValueError as exc:
        raise R64Refused("owner overlay address not valid IPv6") from exc
    if ipv6 not in ipaddress.IPv6Network("fca0::/16"):
        raise R64Refused("overlay address outside ZeroTier 6plane")
    return addr

def current_owner_audit(commit: str) -> dict:
    transport=r63.plan(commit)  # read only; validates original owner and OS state
    if not transport.get("alreadyOnExactPublicControllerlessNetwork"):
        raise R64Refused("original owner not actually on shared public open-join overlay")
    owner_overlay=safe_overlay_address(transport.get("actualHostOverlay6planeIpv6"))
    if transport.get("targetNetworkId")!=r63.NETWORK or transport.get("targetZeroTierVersion")!=r63.VERSION:
        raise R64Refused("unexpected owner transport network/version")
    clients={role:original_container(name) for role,name in (
        ("execution",r63.r60.EL),("beacon",r63.r60.BN),("validator",r63.r60.VC))}
    health=r62.audit(commit)  # also read-only; actual owner netns EL+BN local APIs
    el=health["execution"]["insideExistingContainerNetnsApiReadings"]
    bn=health["beacon"]["insideExistingContainerNetnsApiReadings"]
    if (el["eth_chainId"].get("value")!=hex(31340) or
        bn["genesis"].get("genesisTime")!=r63.r60.GENESIS_TIME):
        raise R64Refused("original live EL/CL identity mismatch; no networking migration")
    return {
        "schema":"SSE_R64_REAL_OWNER_COMMON_OPEN_TRANSPORT_NATIVE_MIGRATION_READINESS_V1",
        "sourceGitExactSha":commit,
        "mode":"readonly_migration_readiness_not_implementation",
        "actualOwnerOverlayIpv6":owner_overlay,
        "actualOwnerOverlayNetworkId":r63.NETWORK,
        "actualOwnerPublicOverlayMembershipConfirmed":True,
        "ownerOverlayTransportModeOrUnderlayPathVerified":False,
        "originalExecutionChainId31340Live":True,
        "originalBeaconGenesisMatchesOriginalLive":True,
        "originalExecutionBlockHex":el["eth_blockNumber"].get("value"),
        "originalBeaconHeadSlot":bn["head"].get("headSlot"),
        "originalBeaconFinalizedEpoch":bn["finality"].get("finalizedEpoch"),
        "originalBeaconFinalizedRoot":bn["finality"].get("finalizedRoot"),
        "originalExecutionPeerCountHex":el["net_peerCount"].get("value"),
        "existingOwnerClients":clients,
        "originalValidatorContainerRunning":health["originalValidatorContainerRunning"],
        "originalELP2pExplicitlyDisabled":clients["execution"]["reviewedNetworkRuntimeFlags"].get("p2p-enabled")==["false"],
        "noNativeEthereumExternalPeerObservedByAudit":True,
        "noNewSignerOrBlockchainGenesisCreated":True,
        "noPrivateLanEthereumBootstrapUsed":True,
        "noServicesOrNetworkConfigurationsChanged":True,
        "existingELBNDataAndOriginalVCMustBePreservedByLaterMigration":True,
        "engineApi8551MustStayUnpublished":True,
        "externalOutsideProviderP2pAndFinalityStillRequired":True,
    }

def main() -> int:
    p=argparse.ArgumentParser(description="R64 read-only original owner shared overlay P2P migration inventory")
    p.add_argument("--audit",action="store_true")
    p.add_argument("--expected-commit",required=True)
    a=p.parse_args()
    if not a.audit:
        print("R64_REFUSED: only --audit supported",file=sys.stderr)
        return 2
    try:
        print(json.dumps(current_owner_audit(a.expected_commit),indent=2,sort_keys=True))
        return 0
    except (R64Refused,r63.R63Refused,r63.r60.R60Refused,r62.R62Refused,
            OSError,ValueError,KeyError,TypeError) as exc:
        print("R64_READONLY_MIGRATION_GATE_REFUSED: "+type(exc).__name__,file=sys.stderr)
        return 2
if __name__=="__main__":
    raise SystemExit(main())
