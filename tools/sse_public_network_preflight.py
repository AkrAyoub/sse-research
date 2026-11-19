#!/usr/bin/env python3
"""Fail-closed PUBLIC SSE PoS network release-manifest preflight.

This is NOT a network launcher, nor a validator-whitelist or a claim
that public peers were proven. It makes static genesis provenance and
dynamic-IP bootstrap metadata auditable before provisioning new,
independently held BLS keys. The exposed one-host chain31339 is
specifically forbidden as an Internet-public release.

--check-dns performs actual global-address DNS resolution for every
bootstrap hostname. --check-tcp tests real TCP reachability on
explicit public execution P2P ports, NOT authenticated Ethereum
peering, consensus discv5 UDP, CGNAT traversal, slot production,
staking activation or SLA. No shell commands, secrets or wallet keys.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import socket
import sys
from urllib.parse import urlsplit

CURRENT_PUBLIC_TARGET_CHAIN=31340
OLD_EXPOSED_CHAIN=31339
SCHEMA="SSE_PUBLIC_POS_RELEASE_V1"
HASH=re.compile(r"0x[0-9a-fA-F]{64}\Z")
SHA256=re.compile(r"[0-9a-fA-F]{64}\Z")
ENODE=re.compile(r"enode://([a-fA-F0-9]{128})@([a-z0-9.-]+):([1-9][0-9]{0,4})\Z")
ENR=re.compile(r"enr:[A-Za-z0-9_-]{75,2000}\Z")
DNS=re.compile(r"(?=.{4,253}\Z)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+\Z")
ID=re.compile(r"[a-z][a-z0-9-]{2,62}\Z")
FIELDS=frozenset((
    "schema","networkName","chainId","currency","executionGenesisHash",
    "beaconGenesisValidatorsRoot","secondsPerSlot","slotsPerEpoch",
    "executionGenesisFile","executionGenesisSha256",
    "consensusConfigFile","consensusConfigSha256",
    "depositContract","bootnodes","permissionlessRoles",
))
B_FIELDS=frozenset(("operatorId","nodeId","executionEnode","consensusENR"))
ROLE_RULES={
    "observer":"VERIFY_GENESIS_AND_SYNC",
    "full_node":"VERIFY_GENESIS_AND_SYNC",
    "validator":"ETHEREUM_DEPOSIT_AND_BEACON_ACTIVATION",
    "consumer":"WALLET_AND_ESCROW",
    "provider":"REAL_RESOURCE_BID_AND_LIVE_SERVICE",
    "monitor":"ONCHAIN_BOND_AND_COMMITTEE_ELECTION",
}
MAX_FILE_SIZE=65536


class PublicManifestError(ValueError):
    pass


def _fqdn(name:str)->str:
    if type(name) is not str or not DNS.fullmatch(name):
        raise PublicManifestError("bootstrap requires public DNS hostname, not a fixed IP")
    if (name.endswith((".local",".internal",".lan",".test",".invalid",".example"))
            or ".ts.net" in name
            or name.endswith((".localhost", ".onion"))):
        raise PublicManifestError("bootstrap must not require private VPN or fake DNS")
    if any(label in ("localhost","vm4705") for label in name.split(".")):
        raise PublicManifestError("private VM and localhost are not public bootnodes")
    return name


def _https_artifact(url:str)->str:
    if type(url) is not str or len(url)>1024:
        raise PublicManifestError("invalid public artifact URL")
    p=urlsplit(url)
    if (p.scheme!="https" or not p.hostname
            or p.username or p.password or p.query or p.fragment
            or p.port not in (None,443) or not p.path.startswith("/")
            or p.path=="/"):
        raise PublicManifestError("public genesis requires stable HTTPS artifact URL")
    _fqdn(p.hostname.lower())
    return url


def validate(manifest:dict)->dict:
    if type(manifest) is not dict or set(manifest)!=FIELDS:
        raise PublicManifestError("missing/unknown public release-manifest fields")
    if (manifest["schema"]!=SCHEMA
            or manifest["chainId"]!=CURRENT_PUBLIC_TARGET_CHAIN
            or type(manifest["chainId"]) is not int
            or manifest["currency"]!="UNVALUED_TEST_ETH"
            or type(manifest["networkName"]) is not str
            or not ID.fullmatch(manifest["networkName"])
            or manifest["secondsPerSlot"]!=12
            or manifest["slotsPerEpoch"]!=32):
        raise PublicManifestError("new public PoS chain id and exact consensus settings required")
    for name in ("executionGenesisHash","beaconGenesisValidatorsRoot"):
        v=manifest[name]
        if type(v) is not str or not HASH.fullmatch(v) or int(v,16)==0:
            raise PublicManifestError("missing distinct fresh nonzero genesis commitment")
    for name in ("executionGenesisFile","consensusConfigFile"):
        _https_artifact(manifest[name])
    for name in ("executionGenesisSha256","consensusConfigSha256"):
        v=manifest[name]
        if type(v) is not str or not SHA256.fullmatch(v) or int(v,16)==0:
            raise PublicManifestError("signed release must pin complete genesis/config bytes")
    addr=manifest["depositContract"]
    if (type(addr) is not str or
            not re.fullmatch(r"0x[0-9a-fA-F]{40}\Z",addr)
            or int(addr,16)==0):
        raise PublicManifestError("actual network deposit contract address required")
    if manifest["permissionlessRoles"]!=ROLE_RULES:
        raise PublicManifestError("administrator/overlay role gates are forbidden")
    nodes=manifest["bootnodes"]
    if type(nodes) is not list or not 2<=len(nodes)<=32:
        raise PublicManifestError("two or more independently operated public seed peers required")
    operators=set()
    names=set()
    public_dns=set()
    seen_keys=set()
    for node in nodes:
        if type(node) is not dict or set(node)!=B_FIELDS:
            raise PublicManifestError("bootnode public record schema invalid")
        op,node_id=node["operatorId"],node["nodeId"]
        if (type(op) is not str or not ID.fullmatch(op)
                or type(node_id) is not str or not ID.fullmatch(node_id)
                or node_id in names or op in operators):
            raise PublicManifestError("distinct independent bootstrap operators and node identities required")
        enode=node["executionEnode"]
        if type(enode) is not str:
            raise PublicManifestError("missing execution node identity")
        match=ENODE.fullmatch(enode)
        if not match or int(match[1],16)==0:
            raise PublicManifestError("malformed public execution enode")
        hostname=_fqdn(match[2])
        if not 1024<=int(match[3])<=65535:
            raise PublicManifestError("execution peer TCP discovery port invalid")
        consensus_enr=node["consensusENR"]
        if type(consensus_enr) is not str or not ENR.fullmatch(consensus_enr):
            raise PublicManifestError("consensus node must publish nonempty signed ENR")
        if hostname in public_dns or match[1].lower() in seen_keys:
            raise PublicManifestError("bootstrap nodes must not reuse DNS name or public enode key")
        operators.add(op)
        names.add(node_id)
        public_dns.add(hostname)
        seen_keys.add(match[1].lower())
    # Bootstrap independence is a DECLARATION until independently
    # attested by remote nodes and cross-domain reachability evidence.
    return {
        "schema":"SSE_PUBLIC_POS_MANIFEST_REVIEW_V1",
        "targetChainId":CURRENT_PUBLIC_TARGET_CHAIN,
        "executionGenesisHash":manifest["executionGenesisHash"].lower(),
        "beaconGenesisValidatorsRoot":manifest["beaconGenesisValidatorsRoot"].lower(),
        "testEthOnly":True,
        "nativeEthereumConsensus":True,
        "executionBootnodeRecords":len(nodes),
        "claimedDistinctBootstrapOperators":len(operators),
        "bootstrapRequiresStaticIP":False,
        "bootstrapFqdns":sorted(public_dns),
        "fullNodeAdmissionRequiresInvite":False,
        "validatorAdmissionRequiresSSEAdministrator":False,
        "genesisArtifactBytesDownloaded":False,
        "liveDNSVerified":False,
        "tcpReachabilityObserved":False,
        "consensusDiscv5HandshakeVerified":False,
        "independentPhysicalOperatorsVerified":False,
        "validatorDepositAndActivationVerified":False,
        "realCrossHostSLAObserved":False,
        "permissionlessPublicNetworkReady":False,
    }


def probe(manifest:dict,*,resolver=None,connector=None,check_tcp:bool=False)->dict:
    report=validate(manifest)
    resolver=resolver or socket.getaddrinfo
    connector=connector or socket.create_connection
    peers=[]
    try:
        for node in manifest["bootnodes"]:
            m=ENODE.fullmatch(node["executionEnode"])
            assert m is not None
            host,port=m[2],int(m[3])
            addrs=resolver(host,port,proto=socket.IPPROTO_TCP)
            ips=set()
            for family,_,_,_,sockaddr in addrs:
                if family not in (socket.AF_INET,socket.AF_INET6):
                    continue
                ip=ipaddress.ip_address(sockaddr[0])
                if ip.is_global and not ip.is_multicast:
                    ips.add(str(ip))
            if not ips:
                raise PublicManifestError("bootstrap hostname resolves only to non-public addresses")
            if check_tcp:
                # DNS may change at any time. Passing the original
                # hostname to the connector uses current OS resolution.
                # A TCP connection does NOT prove devp2p identity or UDP.
                sock=connector((host,port),timeout=3)
                sock.close()
            peers.append({"nodeId":node["nodeId"],"dnsName":host,
                          "publicIpAddresses":sorted(ips),
                          "tcpPort":port,"tcpObserved":check_tcp})
    except (OSError,TimeoutError,ValueError) as exc:
        raise PublicManifestError("public DNS/TCP probe failed; no admission claim") from exc
    report["liveDNSVerified"]=True
    report["tcpReachabilityObserved"]=check_tcp
    report["dnsAndTcpProbe"]=peers
    # No P2P protocol handshake, consensus correctness or independence
    # proof is made by DNS lookup and TCP connect.
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description="Static and optional live DNS/TCP preflight for a fresh public SSE PoS manifest")
    p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--check-dns",action="store_true")
    p.add_argument("--check-tcp",action="store_true")
    args=p.parse_args(argv)
    try:
        if args.check_tcp and not args.check_dns:
            raise PublicManifestError("--check-tcp requires --check-dns")
        if (args.manifest.is_symlink() or not args.manifest.is_file()
                or args.manifest.stat().st_size>MAX_FILE_SIZE):
            raise PublicManifestError("missing or oversized public release manifest")
        manifest=json.loads(args.manifest.read_text("utf-8"))
        output=(probe(manifest,check_tcp=args.check_tcp)
                if args.check_dns else validate(manifest))
        print(json.dumps(output,sort_keys=True,indent=2))
        return 0
    except (PublicManifestError,ValueError,OSError,TypeError) as exc:
        print("SSE_PUBLIC_POS_RELEASE_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
