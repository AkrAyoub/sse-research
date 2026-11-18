#!/usr/bin/env python3
"""Observe actual QBFT validator-set membership from independent RPC views.

This is the baseline's permissionED validator authority checker, NOT
stake-based/permissionless admission. It never calls qbft_proposeValidatorVote
or signs a transaction. A key-bound candidate can request the validator
role from anywhere, but QBFT only grants blockmaking to active validators.
Two HTTPS or independently tunneled localhost RPC endpoints are the minimum
for a provisional observation; physical endpoint independence requires
separate evidence and is never cryptographically inferred from URL count.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

from eth_keys import keys

from sse_qbft_readiness import rpc, safe_rpc, QBFTReadinessError

ADDRESS=re.compile(r"0x[0-9a-fA-F]{40}\Z")
PUBKEY=re.compile(r"[0-9a-fA-F]{128}\Z")
BLOCKHASH=re.compile(r"0x[0-9a-fA-F]{64}\Z")
# secp256k1 field modulus; reject curve-invalid remote consensus identities.
SECP256K1_P=(1 << 256) - (1 << 32) - 977


class ValidatorAuthorityError(ValueError):
    pass


def validator_address(public_key: str) -> str:
    if type(public_key) is not str or not PUBKEY.fullmatch(public_key):
        raise ValidatorAuthorityError("expected 64-byte uncompressed secp256k1 P2P public key")
    raw = bytes.fromhex(public_key)
    x, y = int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")
    if x >= SECP256K1_P or y >= SECP256K1_P or (y*y-x*x*x-7) % SECP256K1_P != 0:
        raise ValidatorAuthorityError("consensus P2P key is not on secp256k1")
    try:
        return keys.PublicKey(raw).to_checksum_address().lower()
    except (ValueError, TypeError):
        raise ValidatorAuthorityError("invalid validator public key") from None


def validator_membership(urls, *, chain_id, genesis_hash, enode_public_key,
                         call=rpc, minimum_views=2):
    if (type(urls) is not list or not minimum_views <= len(urls) <= 8
            or any(type(url) is not str for url in urls)
            or len(set(urls)) != len(urls)):
        raise ValidatorAuthorityError("need distinct, independently provisioned RPC view URLs")
    if (type(chain_id) is not int or chain_id != 31338
            or type(genesis_hash) is not str
            or not BLOCKHASH.fullmatch(genesis_hash)
            or int(genesis_hash,16)==0):
        raise ValidatorAuthorityError("QBFT baseline chain and immutable genesis required")
    subject=validator_address(enode_public_key)
    for url in urls:
        safe_rpc(url)
    heights=[]
    for url in urls:
        chain=call(url,"eth_chainId",[])
        if type(chain) is not str or chain.lower()!=hex(chain_id):
            raise ValidatorAuthorityError("RPC is not on approved chain")
        block0=call(url,"eth_getBlockByNumber",["0x0",False])
        if (type(block0) is not dict
                or type(block0.get("hash")) is not str
                or block0["hash"].lower()!=genesis_hash.lower()):
            raise ValidatorAuthorityError("RPC genesis differs from approved genesis")
        height=call(url,"eth_blockNumber",[])
        if type(height) is not str or not re.fullmatch(r"0x[0-9a-fA-F]+\Z",height):
            raise ValidatorAuthorityError("invalid observed block height")
        heights.append(int(height,16))
    common=min(heights)
    if common==0:
        raise ValidatorAuthorityError("only genesis observed; not an active chain")
    views=[]
    head_hashes=[]
    for url in urls:
        block=call(url,"eth_getBlockByNumber",[hex(common),False])
        if (type(block) is not dict or type(block.get("hash")) is not str
                or not BLOCKHASH.fullmatch(block["hash"])):
            raise ValidatorAuthorityError("unparseable common-height block")
        head_hashes.append(block["hash"].lower())
        members=call(url,"qbft_getValidatorsByBlockNumber",[hex(common)])
        if (type(members) is not list or len(members)<4 or len(members)>1024):
            raise ValidatorAuthorityError("invalid QBFT validator set")
        lower=[]
        for entry in members:
            if (type(entry) is not str or not ADDRESS.fullmatch(entry)
                    or int(entry,16)==0):
                raise ValidatorAuthorityError("invalid validator address")
            lower.append(entry.lower())
        if len(set(lower)) != len(lower):
            raise ValidatorAuthorityError("duplicate active consensus identity")
        views.append(tuple(sorted(lower)))
    if len(set(head_hashes))!=1 or len(set(views))!=1:
        raise ValidatorAuthorityError("RPC views disagree on canonical head or validator set")
    active=subject in views[0]
    return {
        "kind":"SSE_QBFT_OBSERVED_VALIDATOR_AUTHORITY_V1",
        "chainId":chain_id,
        "genesisHash":genesis_hash.lower(),
        "subjectValidatorAddress":subject,
        "observedAtCommonBlock":common,
        "observedCommonBlockHash":head_hashes[0],
        "independentRpcViewCountClaimed":len(urls),
        "validatorSetSize":len(views[0]),
        "activeQBFTValidatorObserved":active,
        "status":"ACTIVE_QBFT_SET_MEMBER" if active else "CANDIDATE_NOT_ACTIVE",
        "validatorVotesSent":False,
        "ethereumTransactionsSent":False,
        "proofOfStakeEligibilityVerified":False,
        "permissionlessConsensusEstablished":False,
        "physicalHostIndependenceProved":False,
        "tailnetMembershipRequired":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Read only: is a claimed validator key actually in active QBFT set?")
    p.add_argument("--rpc-url",action="append",required=True)
    p.add_argument("--genesis-hash",required=True)
    p.add_argument("--enode-pubkey",required=True)
    a=p.parse_args(argv)
    try:
        result=validator_membership(a.rpc_url,chain_id=31338,
                                    genesis_hash=a.genesis_hash,
                                    enode_public_key=a.enode_pubkey)
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0
    except (ValidatorAuthorityError,QBFTReadinessError,OSError,ValueError,TypeError) as exc:
        print("SSE_QBFT_ROLE_REFUSED: "+str(exc),file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
