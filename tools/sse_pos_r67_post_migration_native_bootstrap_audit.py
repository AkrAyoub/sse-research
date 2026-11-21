#!/usr/bin/env python3
"""R67: READ ONLY after actual R65 owner native-public-overlay migration.

Extract the genuine source EL identity from Besu NET RPC and the source CL ENR
from Lighthouse Beacon REST. Validate original live genesis, owner public
overlay IPv6, effective Docker P2P publishing, connected peer counts and
checkpoint progression. Never read private node keys, JWT, wallets or signer
files; never inspect raw logs, change Docker or add a peer.

Important: enodeV6 is composed from the actual Besu-reported public node ID,
the verified live configured owner overlay host, and the published IPv6 port.
This is a *source-derived bootstrap locator*, not a remote reachability proof.
RLP ENR fields are checked; cryptographic ENR signature is not independently
validated by this script. Owner Lighthouse provides its locally signed ENR.
"""
from __future__ import annotations
import argparse
import base64
import ipaddress
import json
import re
import sys
import urllib.error
import urllib.request

import sse_pos_r65_original_chain_native_public_p2p_migration as r65
import sse_pos_r59_native_ipv6_observer as r59

EL_URL="http://127.0.0.1:18545/"
BN_URL="http://127.0.0.1:15052"
BASELINE_FINALIZED_EPOCH=120
MAX_HTTP_BYTES=40_000
MAX_ENR_BYTES=4096

class R67Refused(ValueError):
    pass

def endpoint_json(url:str,payload:dict|None=None)->dict:
    allowed={
        EL_URL,
        BN_URL+"/eth/v1/node/identity",
        BN_URL+"/eth/v1/node/peer_count",
        BN_URL+"/eth/v1/node/syncing",
        BN_URL+"/eth/v1/beacon/genesis",
        BN_URL+"/eth/v1/beacon/headers/head",
        BN_URL+"/eth/v1/beacon/states/head/finality_checkpoints",
    }
    if url not in allowed:
        raise R67Refused("unreviewed endpoint is forbidden")
    data=json.dumps(payload,separators=(",",":")).encode() if payload is not None else None
    request=urllib.request.Request(
        url,method="POST" if data else "GET",data=data,
        headers={"Content-Type":"application/json","Accept":"application/json"}
    )
    # Ignore environment proxies, never send local APIs to a remote proxy.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request,timeout=6) as response:
            if response.status!=200:
                raise R67Refused("localhost native API returned a non-200 status")
            raw=response.read(MAX_HTTP_BYTES+1)
    except (OSError,urllib.error.URLError,ValueError) as exc:
        raise R67Refused("localhost original native API unavailable") from exc
    if len(raw)>MAX_HTTP_BYTES:
        raise R67Refused("native API response too large")
    try:
        out=json.loads(raw)
    except (ValueError,UnicodeError) as exc:
        raise R67Refused("invalid native API JSON") from exc
    if not isinstance(out,dict):
        raise R67Refused("native API response is not an object")
    return out

def rpc(method:str)->object:
    if method not in ("eth_chainId","eth_blockNumber","net_listening",
                      "net_peerCount","net_enode","eth_syncing"):
        raise R67Refused("unreviewed execution JSON-RPC method")
    response=endpoint_json(
        EL_URL,{"jsonrpc":"2.0","id":1,"method":method,"params":[]}
    )
    if response.get("jsonrpc")!="2.0" or response.get("id")!=1 or (
        "error" in response or "result" not in response
    ):
        raise R67Refused("original Besu NET/ETH RPC method unavailable")
    return response["result"]

def rest(path:str)->dict:
    response=endpoint_json(BN_URL+path)
    data=response.get("data")
    if not isinstance(data,dict):
        raise R67Refused("Lighthouse REST data unavailable")
    return data

def rlp_value(blob:bytes,pos:int=0)->tuple[bytes|list,int]:
    """Small bounded RLP decoder for public Beacon ENR metadata only."""
    if pos>=len(blob):
        raise R67Refused("incomplete Beacon ENR RLP")
    first=blob[pos]
    if first<0x80:
        return bytes([first]),pos+1
    if first<0xb8:
        n=first-0x80
        start=pos+1
        end=start+n
        if end>len(blob):raise R67Refused("short Beacon ENR RLP field")
        return blob[start:end],end
    if first<0xc0:
        n=first-0xb7
        if n>4 or pos+1+n>len(blob):raise R67Refused("invalid Beacon ENR RLP string length")
        size=int.from_bytes(blob[pos+1:pos+1+n],"big")
        start=pos+1+n
        end=start+size
        if end>len(blob) or size>MAX_ENR_BYTES:raise R67Refused("long Beacon ENR RLP field")
        return blob[start:end],end
    if first<0xf8:
        size=first-0xc0
        start=pos+1
    else:
        n=first-0xf7
        if n>4 or pos+1+n>len(blob):raise R67Refused("invalid Beacon ENR RLP list length")
        size=int.from_bytes(blob[pos+1:pos+1+n],"big")
        start=pos+1+n
    end=start+size
    if end>len(blob) or size>MAX_ENR_BYTES:raise R67Refused("invalid Beacon ENR RLP list")
    children=[]
    cursor=start
    while cursor<end:
        item,cursor=rlp_value(blob,cursor)
        children.append(item)
        if len(children)>60:raise R67Refused("excessive Beacon ENR fields")
    if cursor!=end:raise R67Refused("Beacon ENR list parse mismatch")
    return children,end

def parse_enr_fields(enr:str)->dict[str,bytes]:
    if not isinstance(enr,str) or not r59.ENR.fullmatch(enr):
        raise R67Refused("genuine Lighthouse Beacon ENR absent/malformed")
    b64=enr[4:]
    try:
        payload=base64.urlsafe_b64decode(b64+"="*((-len(b64))%4))
    except (ValueError,base64.binascii.Error) as exc:
        raise R67Refused("Beacon ENR base64 malformed") from exc
    if len(payload)>MAX_ENR_BYTES or len(payload)<70:
        raise R67Refused("Beacon ENR payload unexpected length")
    decoded,consumed=rlp_value(payload)
    if not isinstance(decoded,list) or consumed!=len(payload) or len(decoded)<4 or len(decoded)%2:
        raise R67Refused("Beacon ENR RLP unexpected structure")
    if not all(isinstance(x,bytes) for x in decoded):
        raise R67Refused("Beacon ENR has invalid nested fields")
    signature,seq,*kvs=decoded
    if len(signature)!=64 or len(seq)>8:
        raise R67Refused("Beacon ENR signature or sequence structure invalid")
    fields:dict[str,bytes]={}
    for i in range(0,len(kvs),2):
        try:
            key=kvs[i].decode("ascii")
        except UnicodeError as exc:
            raise R67Refused("Beacon ENR key invalid") from exc
        if not re.fullmatch(r"[a-z0-9]{1,25}",key) or key in fields:
            raise R67Refused("Beacon ENR duplicated/unexpected field key")
        fields[key]=kvs[i+1]
    return fields

def enode_bootstrap_from_rpc(identity:object,ip:str)->str:
    if not isinstance(identity,str):
        raise R67Refused("Besu net_enode returned non-string")
    m=re.fullmatch(
        r"enode://([a-fA-F0-9]{128})@(?:\[[0-9a-fA-F:]+\]|[A-Za-z0-9.]+):[1-9][0-9]{1,4}"
        r"(?:\?discport=[1-9][0-9]{1,4})?",identity
    )
    if not m:
        raise R67Refused("Besu net_enode did not expose a valid actual public node ID")
    ipv6=ipaddress.IPv6Address(ip)
    if ipv6 not in ipaddress.IPv6Network("fca0::/16"):
        raise R67Refused("Besu bootstrap IP is not owner open-overlay 6plane")
    candidate=f"enode://{m.group(1).lower()}@[{ipv6.compressed}]:30404"
    if not r59.ENODE6.fullmatch(candidate):
        raise R67Refused("derived original execution enodeV6 invalid")
    return candidate

def validate_enr_host(fields:dict[str,bytes],ip:str)->dict:
    address=ipaddress.IPv6Address(ip)
    if fields.get("id")!=b"v4" or len(fields.get("secp256k1",b""))!=33:
        raise R67Refused("Beacon ENR identity scheme unexpected")
    if fields.get("ip6")!=address.packed:
        raise R67Refused("Beacon ENR not actually advertising owner overlay IPv6")
    def port(k:str)->int:
        val=fields.get(k,b"")
        return int.from_bytes(val,"big") if val and len(val)<=2 else -1
    if port("tcp6")!=9000 or port("udp6")!=9000:
        raise R67Refused("Beacon signed ENR IPv6 P2P ports differ from original published ports")
    if "ip" in fields and len(fields["ip"])==4:
        candidate=ipaddress.IPv4Address(fields["ip"])
        if candidate.is_private or candidate.is_loopback or candidate.is_link_local:
            raise R67Refused("Beacon ENR leaks unreviewed private/provider IPv4 advertisement")
    return {
        "beaconEnrIp6VerifiedAsActualOwnerOpenOverlay":True,
        "beaconEnrTcp6":9000,
        "beaconEnrUdp6":9000,
        "beaconEnrClaimedSignatureNotIndependentlyVerified":True,
    }

def safe_hex_quantity(value:object)->int:
    if not isinstance(value,str) or not re.fullmatch(r"0x[0-9a-fA-F]{1,16}",value):
        raise R67Refused("invalid on-chain quantity")
    return int(value,16)

def check_running(original:str)->bool:
    state=r65.get_json(["inspect","--format","{{json .State}}",original])
    return isinstance(state,dict) and state.get("Running") is True

def check_cmd(name:str,expected:list[str])->None:
    argv=r65.get_json(["inspect","--format","{{json .Config.Cmd}}",name])
    if not isinstance(argv,list) or not all(isinstance(x,str) for x in argv):
        raise R67Refused("actual migrated native client CLI unreadable")
    if any(x not in argv for x in expected):
        raise R67Refused("actual native client lacks reviewed P2P startup option")

def post_migration_audit()->dict:
    iface,ip=r59.overlay_ip()
    for original in (r65.EL,r65.BN,r65.VC):
        if not check_running(original):
            raise R67Refused("an original live EL, BN or signer is not running")
    for old in r65.PRESERVED.values():
        if check_running(old):
            raise R67Refused("a preserved old process unexpectedly restarted")
    for name in (r65.EL,r65.BN):
        actual=r65.binding_set(name)
        expected=set(r65.validated_host_ports(ip)[name])
        if actual!=expected:
            raise R67Refused("actual new native peer host endpoints differ from reviewed owner IPv6")
        nets=r65.get_json(["inspect","--format","{{json .NetworkSettings.Networks}}",name])
        if not isinstance(nets,dict) or set(nets)!={r65.TRUSTED,r65.PUBLIC_BRIDGE}:
            raise R67Refused("original native client P2P/trusted bridge attachment unexpected")
    check_cmd(r65.EL,[
        "--network-id=31340","--p2p-enabled=true","--p2p-port-ipv6=30404",
        "--p2p-host-ipv6="+ip
    ])
    check_cmd(r65.BN,[
        "--enr-address="+ip,"--port6=9000","--discovery-port6=9000",
        "--disable-enr-auto-update"
    ])
    chain_id=safe_hex_quantity(rpc("eth_chainId"))
    if chain_id!=31340:raise R67Refused("live original Besu execution chain id differs")
    block=safe_hex_quantity(rpc("eth_blockNumber"))
    peer_count=safe_hex_quantity(rpc("net_peerCount"))
    listening=rpc("net_listening")
    if listening is not True:raise R67Refused("live original Besu reports networking not listening")
    native_identity=rpc("net_enode")
    ipv6_enode=enode_bootstrap_from_rpc(native_identity,ip)
    genesis=rest("/eth/v1/beacon/genesis")
    if str(genesis.get("genesis_time"))!=str(r65.OWNER.GENESIS_TIME):
        raise R67Refused("Lighthouse original Beacon genesis differs")
    identity=rest("/eth/v1/node/identity")
    enr=identity.get("enr")
    fields=parse_enr_fields(enr)
    hostcheck=validate_enr_host(fields,ip)
    head=rest("/eth/v1/beacon/headers/head")
    try:
        head_slot=int(head["header"]["message"]["slot"])
    except (KeyError,TypeError,ValueError) as exc:
        raise R67Refused("original Beacon head slot invalid") from exc
    finality=rest("/eth/v1/beacon/states/head/finality_checkpoints")
    finalized=finality.get("finalized")
    if not isinstance(finalized,dict):
        raise R67Refused("original Beacon finalized checkpoint missing")
    try:
        epoch=int(finalized["epoch"])
        root=finalized["root"]
    except (KeyError,ValueError,TypeError) as exc:
        raise R67Refused("original Beacon finality fields invalid") from exc
    if epoch<BASELINE_FINALIZED_EPOCH or not isinstance(root,str) or not re.fullmatch(
        r"0x[0-9a-fA-F]{64}",root
    ):
        raise R67Refused("original Beacon finalized checkpoint regressed/malformed")
    peers=rest("/eth/v1/node/peer_count")
    try:
        connected=int(peers["connected"])
    except (KeyError,ValueError,TypeError) as exc:
        raise R67Refused("original Beacon peer count invalid") from exc
    syncing=rest("/eth/v1/node/syncing")
    return {
        "schema":"SSE_R67_REAL_ORIGINAL_OWNER_POST_MIGRATION_PUBLIC_P2P_BOOTSTRAP_V1",
        "mode":"readonly_after_original_r65_apply",
        "originalExecutionChainId":chain_id,
        "originalExecutionLatestBlock":block,
        "originalExecutionNativePeerCount":peer_count,
        "originalExecutionP2pListeningFromRpc":True,
        "sourceDerivedBesuEnodeV6":ipv6_enode,
        "executionEnodeV6DerivedFromActualLocalBesuNetEnodeAndConfigured6plane":True,
        "executionEnodeV6RemoteAdvertiseOrReachabilityNotYetProved":True,
        "originalBeaconHeadSlot":head_slot,
        "originalBeaconFinalizedEpoch":epoch,
        "originalBeaconFinalizedRoot":root,
        "originalBeaconFinalizedBeyondR65Epoch120":epoch>BASELINE_FINALIZED_EPOCH,
        "originalBeaconConnectedNativePeers":connected,
        "sourceLighthouseBeaconEnrFromLiveNodeIdentity":enr,
        "originalBeaconIdentityPeerId":identity.get("peer_id"),
        "originalBeaconIsSyncing":syncing.get("is_syncing"),
        **hostcheck,
        "openJoinControllerlessOverlayId":r59.NETWORK,
        "ownerOverlayIPv6":ip,
        "openJoinOverlayInterfaceValidated":True,
        "oldOriginalELAndBeaconContainersRemainStopped":True,
        "originalValidatorContainerRunning":True,
        "nativeP2pHostPublicationsOnActualOverlayVerified":True,
        "engineApi8551StillNotPublishedByExpectedBindings":True,
        "outsideProviderExecutionAndConsensusSyncProved":False,
        "noSecretsReadOrFilesChanged":True,
        "noContainerOrOverlayModification":True,
    }

def main()->int:
    p=argparse.ArgumentParser(description="read-only actual chain31340 native migrated P2P, public bootnode identities")
    p.add_argument("--audit",action="store_true")
    args=p.parse_args()
    if not args.audit:
        print("R67_ONLY_READONLY_AUDIT_ALLOWED",file=sys.stderr)
        return 2
    try:
        result=post_migration_audit()
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (R67Refused,r65.R65Refused,r59.R59Refused,
            OSError,ValueError,TypeError,KeyError) as exc:
        print("R67_ORIGINAL_NATIVE_PEER_BOOTSTRAP_AUDIT_REFUSED: "
              +type(exc).__name__,file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
