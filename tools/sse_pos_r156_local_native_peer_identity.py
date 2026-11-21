#!/usr/bin/env python3
"""R156: derive a publisher-ready peer hint from genuine LOCAL EL/CL APIs.

No Ethereum signer/key files are read. Besu NET.net_enode exposes a
PUBLIC P2P node identifier (which can announce IPv4); only the public key
is reused with this host's ACTUALLY observed 6plane IPv6 and configured
native 30404 port. Lighthouse's signed ENR comes from the real Beacon
REST node identity endpoint, and its RLP ip6/udp6/tcp6 is independently
decoded to reject stale/wrong advertised overlay addresses. Publisher
distribution/remote handshakes are separate, not claimed here.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import re
import sys
import urllib.request

import sse_pos_r59_native_ipv6_observer as r59
import sse_pos_r142_public_peer_discovery as r142
import sse_public_genesis as genesis

MAX_ENR_BYTES = 2048
ENODE = re.compile(r"enode://([0-9a-fA-F]{128})@[^\s]{3,500}\Z")
NODE_ID = re.compile(r"[a-z][a-z0-9-]{2,62}\Z")
LOOPBACK_EL = "http://127.0.0.1:28545"
LOOPBACK_BN = "http://127.0.0.1:25052"

class Refused(ValueError):
    pass

def read_json(url, *, method="GET", rpc_method=None):
    if url not in (LOOPBACK_EL, LOOPBACK_BN+"/eth/v1/node/identity",
                   LOOPBACK_BN+"/eth/v1/beacon/genesis"):
        raise Refused("only reviewed local read-only client endpoint allowed")
    if (method=="POST") != (url==LOOPBACK_EL):
        raise Refused("wrong local RPC request method")
    if method=="POST" and rpc_method not in (
            "net_enode","eth_chainId","eth_getBlockByNumber"):
        raise Refused("unapproved local JSON-RPC method")
    payload=None
    if method=="POST":
        payload=json.dumps({"jsonrpc":"2.0","id":1,
                            "method":rpc_method,"params":[] if rpc_method!="eth_getBlockByNumber" else ["0x0",False]}).encode()
    request=urllib.request.Request(url,data=payload,method=method,
        headers={"Content-Type":"application/json","Accept":"application/json"})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request,timeout=8) as response:
            if response.status!=200:
                raise Refused("actual local client HTTP status not 200")
            raw=response.read(65537)
    except (OSError,ValueError) as exc:
        raise Refused("actual local client JSON endpoint unavailable") from exc
    if len(raw)>65536:
        raise Refused("unbounded local client response")
    try:
        value=json.loads(raw)
    except (UnicodeError,ValueError) as exc:
        raise Refused("local client returned invalid JSON") from exc
    if type(value) is not dict:
        raise Refused("local client returned wrong schema")
    if method=="POST":
        if (value.get("jsonrpc")!="2.0" or value.get("id")!=1
                or "error" in value or "result" not in value):
            raise Refused("local NET/ETH RPC rejected request")
        return value["result"]
    if type(value.get("data")) is not dict:
        raise Refused("local Lighthouse response missing data")
    return value["data"]

def rlp_item(blob, start=0):
    """Strict bounded RLP parse; returns (byte-string or list, cursor)."""
    if start>=len(blob):
        raise Refused("truncated ENR RLP")
    p=blob[start]
    if p<0x80:
        return bytes([p]),start+1
    if p<=0xb7:
        size=p-0x80
        at=start+1
        if size==1 and at<len(blob) and blob[at]<0x80:
            raise Refused("noncanonical ENR short encoding")
        end=at+size
        if end>len(blob):
            raise Refused("truncated ENR string")
        return blob[at:end],end
    if p<=0xbf:
        digits=p-0xb7
        at=start+1
        if at+digits>len(blob) or blob[at]==0:
            raise Refused("invalid ENR string length")
        size=int.from_bytes(blob[at:at+digits],"big")
        if size<56:
            raise Refused("noncanonical ENR large string")
        end=at+digits+size
        if end>len(blob):
            raise Refused("truncated ENR string")
        return blob[at+digits:end],end
    if p<=0xf7:
        size=p-0xc0
        at=start+1
        end=at+size
        if end>len(blob):
            raise Refused("truncated ENR list")
        return rlp_list(blob,at,end),end
    digits=p-0xf7
    at=start+1
    if at+digits>len(blob) or blob[at]==0:
        raise Refused("invalid ENR list length")
    size=int.from_bytes(blob[at:at+digits],"big")
    if size<56:
        raise Refused("noncanonical ENR large list")
    end=at+digits+size
    if end>len(blob):
        raise Refused("truncated ENR list")
    return rlp_list(blob,at+digits,end),end

def rlp_list(blob,start,end):
    items=[]
    while start<end:
        item,nxt=rlp_item(blob,start)
        if nxt>end:
            raise Refused("ENR RLP nested item overshoot")
        items.append(item)
        if len(items)>64:
            raise Refused("unbounded ENR items")
        start=nxt
    return items

def decode_enr(value):
    if type(value) is not str or not r59.ENR.fullmatch(value):
        raise Refused("invalid real Lighthouse ENR syntax")
    encoded=value[4:]
    try:
        raw=base64.urlsafe_b64decode(encoded+"="*((-len(encoded))%4))
    except (ValueError,base64.binascii.Error) as exc:
        raise Refused("invalid Lighthouse ENR base64") from exc
    if not 1<len(raw)<=MAX_ENR_BYTES:
        raise Refused("invalid bounded ENR size")
    items,nxt=rlp_item(raw)
    if nxt!=len(raw) or type(items) is not list or len(items)<4 or len(items)%2!=0:
        raise Refused("invalid canonical ENR RLP top-level")
    if type(items[0]) is not bytes or len(items[0]) not in (64,65):
        raise Refused("invalid ENR signature encoding")
    if type(items[1]) is not bytes or not 1<=len(items[1])<=8:
        raise Refused("invalid ENR sequence")
    data={}
    previous=b""
    for i in range(2,len(items),2):
        key,body=items[i],items[i+1]
        if type(key) is not bytes or type(body) is not bytes or not key or key<=previous:
            raise Refused("invalid ENR key ordering")
        previous=key
        data[key]=body
    return data

def check_local_enr(enr, overlay):
    values=decode_enr(enr)
    if values.get(b"id")!=b"v4":
        raise Refused("unknown Beacon ENR identity scheme")
    candidate=values.get(b"ip6")
    if type(candidate) is not bytes or len(candidate)!=16:
        raise Refused("Lighthouse ENR does not advertise native IPv6")
    actual=ipaddress.IPv6Address(candidate)
    if actual!=ipaddress.IPv6Address(overlay):
        raise Refused("stale Lighthouse ENR ip6 differs from LIVE host overlay")
    for key,port in ((b"tcp6",9000),(b"udp6",9000)):
        encoded=values.get(key)
        if (type(encoded) is not bytes or not 1<=len(encoded)<=2
                or int.from_bytes(encoded,"big")!=port):
            raise Refused("Lighthouse ENR is not configured for published native ports")
    # EIP-778 ENR signature is not independently verified here; local
    # Lighthouse output and native client handshake must be checked later.
    return True

def make_record(node_id, overlay, enode, beacon_enr,
                chain, beacon_genesis):
    if type(node_id) is not str or not NODE_ID.fullmatch(node_id):
        raise Refused("invalid locally selected node identity")
    if chain!=31340 or beacon_genesis.lower()!=genesis.CL_GENESIS:
        raise Refused("incorrect actual chain31340 identity")
    found=ENODE.fullmatch(enode) if type(enode) is str else None
    if not found:
        raise Refused("Besu did not expose real public enode identity")
    overlay=ipaddress.IPv6Address(overlay)
    if overlay not in ipaddress.ip_network("fca0::/16"):
        raise Refused("not the actual expected ad-hoc overlay")
    check_local_enr(beacon_enr,str(overlay))
    enode6="enode://"+found.group(1).lower()+f"@[{overlay.compressed}]:30404"
    r59.bootnodes(enode6,beacon_enr)
    return {
        "nodeId":node_id,
        "executionEnode":enode6,
        "beaconEnr":beacon_enr,
    }

def capture(node_id, fetch=read_json, overlay_reader=r59.overlay_ip):
    iface,ip=overlay_reader()
    chain=int(fetch(LOOPBACK_EL,method="POST",rpc_method="eth_chainId"),16)
    genesis_block=fetch(LOOPBACK_EL,method="POST",rpc_method="eth_getBlockByNumber")
    if type(genesis_block) is not dict or genesis_block.get("hash")!=genesis.EL_GENESIS:
        raise Refused("wrong actual execution genesis")
    enr_identity=fetch(LOOPBACK_BN+"/eth/v1/node/identity")
    beacon_genesis=fetch(LOOPBACK_BN+"/eth/v1/beacon/genesis")
    report=make_record(
        node_id,ip,fetch(LOOPBACK_EL,method="POST",rpc_method="net_enode"),
        enr_identity.get("enr"),chain,
        beacon_genesis.get("genesis_validators_root",""))
    return {
        "schema":"SSE_R156_LOCAL_NODE_NATIVE_IDENTITY_V1",
        "capturedAtUtc":datetime.now(timezone.utc).isoformat(),
        "chainId":31340,
        "executionGenesisHash":genesis.EL_GENESIS,
        "beaconGenesisValidatorsRoot":genesis.CL_GENESIS,
        "overlayInterface":iface,
        "actualOverlayIpv6":ip,
        "publicPeerRecord":report,
        "publishedToAnyExternalDiscoveryService":False,
        "nativeRemoteHandshakeProven":False,
        "localSigningKeyRead":False,
        "independentOperatorProven":False,
    }

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--node-id",required=True)
    args=p.parse_args(argv)
    try:
        print(json.dumps(capture(args.node_id),sort_keys=True,indent=2))
        return 0
    except (Refused,r59.R59Refused,OSError,ValueError,TypeError,KeyError) as exc:
        print("R156_LOCAL_NATIVE_IDENTITY_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
