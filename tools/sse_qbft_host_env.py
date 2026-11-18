#!/usr/bin/env python3
"""R11: signed-QBFT-lab roster -> safe, per-host Docker Compose environment.

This is a research CONSENSUS BASELINE, NOT a permissionless validator path.
It never generates/imports a key, starts Docker, joins Tailscale, makes votes
or submits transactions. The output is a 0600 local .env in a 0700 folder.

Besu's --bootnodes expects comma-separated enode URLs, NOT a filename.
We accept only a correctly signed, chain+genesis-bound four-validator
catalog and ensure this VM's locally generated node key is in it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from eth_keys import keys

from sse_network_peers import verify,validate_enode,PeerCatalogError
from sse_qbft_lab_config import qbft_extra_data
from sse_qbft_vm_preflight import parse_genesis,parse_image,PreflightError
from sse_qbft_validator_identity import inspect_local,IdentityError

APPROVED_SHA=re.compile(r"[0-9a-f]{40}\Z")
HASH=re.compile(r"0x[0-9a-f]{64}\Z")
PATH_SAFE=re.compile(r"/[A-Za-z0-9_./-]{2,200}\Z")
ROOT=Path(__file__).resolve().parents[1]


class EnvError(ValueError):
    pass


def safe_path(path:Path):
    value=str(path)
    if (not isinstance(path,Path) or not path.is_absolute()
            or not PATH_SAFE.fullmatch(value) or ".." in path.parts
            or path.is_symlink()):
        raise EnvError("refusing unsafe host volume path")
    return value


def generate(*,node_id:str,local_public:dict,catalog:dict,public_pem:str,
             source_sha:str,genesis_path:Path,genesis_sha256:str,
             genesis_block_hash:str,image:str,data_path:Path,key_path:Path,
             user_id:int,group_id:int,now=None)->tuple[str,dict]:
    if (type(source_sha) is not str or not APPROVED_SHA.fullmatch(source_sha)
            or type(genesis_block_hash) is not str
            or not HASH.fullmatch(genesis_block_hash)
            or type(node_id) is not str
            or type(user_id) is not int or not 1<=user_id<=65534
            or type(group_id) is not int or not 1<=group_id<=65534):
        raise EnvError("invalid source SHA, measured genesis hash, node ID or UID/GID")
    image=parse_image(image)
    cfg=parse_genesis(genesis_path,genesis_sha256)
    if cfg["chainId"]!=31338:
        raise EnvError("wrong network")
    signed=verify(catalog,public_pem,chain_id=31338,
                  genesis_hash=genesis_block_hash,now=now)
    if signed["revision"]!=source_sha:
        raise EnvError("signed peer catalog points to a different GitHub revision")
    nodes=signed["nodes"]
    validators=[entry for entry in nodes if entry["role"]=="validator"]
    if len(validators)!=4:
        raise EnvError("R11 QBFT test genesis requires exactly four validator addresses")
    if (type(local_public) is not dict
            or local_public.get("schema")!="SSE_QBFT_PUBLIC_VALIDATOR_V1"
            or local_public.get("nodeId")!=node_id
            or local_public.get("privateKeyIncluded") is not False):
        raise EnvError("invalid local Besu P2P identity record")
    self_entries=[e for e in nodes if e["nodeId"]==node_id]
    if (len(self_entries)!=1 or self_entries[0]["role"]!="validator"
            or self_entries[0]["enode"]!=local_public.get("enode")):
        raise EnvError("local key/enode not matched by signed catalog")
    self_key,own_ip,own_port=validate_enode(local_public["enode"])
    if (self_key!=local_public.get("enodePublicKey")
            or own_ip!=local_public.get("overlayIPv4") or own_port!=30303):
        raise EnvError("local advertised locator/key mismatch")
    addrs=[]
    for item in validators:
        key,_,_=validate_enode(item["enode"])
        addrs.append(keys.PublicKey(bytes.fromhex(key)).to_checksum_address().lower())
    genesis_doc=json.loads(genesis_path.read_text("utf-8"))
    if (genesis_doc.get("extraData")!=qbft_extra_data(addrs)):
        raise EnvError("validator identities differ from genesis extradata")
    if local_public.get("validatorAddress") not in addrs:
        raise EnvError("local consensus address missing from genesis")
    if (safe_path(data_path)==safe_path(key_path)
            or safe_path(data_path)==safe_path(genesis_path)):
        raise EnvError("unsafe overlapping data/key/genesis paths")
    peers=[e["enode"] for e in nodes if e["nodeId"]!=node_id]
    if len(peers)<3 or len(set(peers))!=len(peers):
        raise EnvError("missing independent signed initial peers")
    # Escape dollar signs and newlines by refusing all but strongly
    # validated URL contents; do not put JSON or secrets into an env var.
    bootnodes=",".join(peers)
    if any(not re.fullmatch(r"enode://[0-9a-fA-F]{128}@[A-Za-z0-9.-]+:[0-9]{4,5}",x)
           for x in peers):
        raise EnvError("unvalidated bootnode in catalog")
    env={
        "BESU_IMAGE":image,
        "BESU_UID":str(user_id),"BESU_GID":str(group_id),
        "BESU_DATA":safe_path(data_path),
        "BESU_GENESIS":safe_path(genesis_path),
        "BESU_NODE_KEY":safe_path(key_path),
        "BESU_BOOTNODES_LIST":bootnodes,
        "TAILSCALE_IPV4":own_ip,
    }
    output="\n".join(f"{k}={v}" for k,v in env.items())+"\n"
    report={
        "schema":"SSE_QBFT_SIGNED_HOST_CONFIG_V1",
        "consensusMode":"PERMISSIONED_QBFT_RESEARCH",
        "permissionlessValidatorMembership":False,
        "nodeId":node_id,"approvedGitCommit":source_sha,
        "chainId":31338,"genesisFileSha256":genesis_sha256,
        "observedGenesisBlockHash":genesis_block_hash,
        "besuImageDigestPinned":True,
        "image":image,
        "sourceCatalogSignatureVerified":True,
        "expectedGenesisValidatorCount":4,
        "initialBootnodeCount":len(peers),
        "initialBootnodeKeysArePublic":True,
        "localPrivateKeyMaterialExported":False,
        "nodeStarted":False,"validatorMembershipChanged":False,
        "ethereumTransactionsSent":False,
        "envSha256":hashlib.sha256(output.encode()).hexdigest(),
    }
    return output,report


def _load(path:Path,limit:int=65536):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>limit:
        raise EnvError("missing, symlinked or oversized file")
    return path.read_text("utf-8")


def write_once(path:Path,content:str):
    if (not path.is_absolute() or not path.parent.is_dir()
            or path.is_symlink() or path.exists()
            or path.parent.is_symlink() or
            (os.name=="posix" and (
                path.parent.stat().st_mode&0o077
                or path.parent.stat().st_uid!=os.geteuid()))):
        raise EnvError("destination must be NEW inside owner-controlled 0700 folder")
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):flags|=os.O_NOFOLLOW
    fd=os.open(path,flags,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())


def main(argv=None):
    p=argparse.ArgumentParser(description="Generate signed-key-verified lab QBFT per-node .env; never start chain")
    p.add_argument("--node-id",required=True)
    p.add_argument("--expected-sha",required=True)
    p.add_argument("--signed-peer-catalog",type=Path,required=True)
    p.add_argument("--signer-public-pem",type=Path,required=True)
    p.add_argument("--genesis",type=Path,required=True)
    p.add_argument("--genesis-sha256",required=True)
    p.add_argument("--observed-genesis-block-hash",required=True)
    p.add_argument("--image",required=True)
    p.add_argument("--private-dir",type=Path,required=True)
    p.add_argument("--data-dir",type=Path,required=True)
    p.add_argument("--output-env",type=Path,required=True)
    p.add_argument("--apply",action="store_true")
    a=p.parse_args(argv)
    try:
        if (sys.platform!="linux" or os.geteuid()==0):
            raise EnvError("must be an unprivileged owning Ubuntu operator")
        current=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,
                                         text=True,timeout=5).strip()
        dirty=subprocess.check_output(["git","status","--porcelain",
                                       "--untracked-files=no"],cwd=ROOT,
                                       text=True,timeout=5).strip()
        if current!=a.expected_sha or dirty:
            raise EnvError("source not at exactly approved clean GitHub revision")
        if not a.data_dir.is_dir() or a.data_dir.is_symlink():
            raise EnvError("persistent data directory must exist before apply")
        record=inspect_local(a.private_dir,
                             public_file=a.private_dir/(a.node_id+".public.json"))
        content,report=generate(
            node_id=a.node_id,local_public=record,
            catalog=json.loads(_load(a.signed_peer_catalog)),
            public_pem=_load(a.signer_public_pem,limit=8192),
            source_sha=a.expected_sha,genesis_path=a.genesis,
            genesis_sha256=a.genesis_sha256,
            genesis_block_hash=a.observed_genesis_block_hash,
            image=a.image,data_path=a.data_dir,
            key_path=a.private_dir/"node.key",
            user_id=os.geteuid(),group_id=os.getegid())
        if a.apply:
            write_once(a.output_env,content)
            report["environmentWritten"]=True
            report["environmentPath"]=str(a.output_env)
        else:
            report["environmentWritten"]=False
            report["mode"]="DRY_RUN"
        print(json.dumps(report,sort_keys=True,indent=2))
        return 0
    except (EnvError,PeerCatalogError,PreflightError,IdentityError,
            OSError,ValueError,KeyError,TypeError,
            subprocess.SubprocessError) as exc:
        print("SSE_QBFT_HOST_ENV_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
