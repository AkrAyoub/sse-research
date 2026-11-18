#!/usr/bin/env python3
"""Create a nonce-bearing request for ANY SSE role combination (no privilege).

Wallet signing stays in an independent wallet agent; generated request is
signed using sse_open_role_requests.signing_message() and verified with
sse_open_role_requests.verify(). This utility holds NO private keys and
cannot fund a wallet, activate a role, or start a Tailscale daemon.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import sys
import time

from sse_open_role_requests import (
    SCHEMA, TRANSPORTS, inspect_request, requested_roles, RoleRequestError
)


def build(*, node_id, account, roles, genesis_hash, transport="auto",
          chain_id=31338, now=None, ttl_seconds=600):
    stamp=int(time.time()) if now is None else now
    if type(ttl_seconds) is not int or not 60<=ttl_seconds<=3600:
        raise RoleRequestError("role request TTL must be 60-3600 seconds")
    envelope={
        "schema":SCHEMA,
        "chainId":chain_id,
        "genesisHash":genesis_hash,
        "nodeId":node_id,
        "account":account,
        "roles":list(requested_roles(roles)),
        "transportPreference":transport,
        "nonce":"0x"+secrets.token_hex(32),
        "issuedAt":stamp,
        "expiresAt":stamp+ttl_seconds,
    }
    inspect_request(envelope,now=stamp,chain_id=chain_id,
                    genesis_hash=genesis_hash)
    return envelope


def write_exclusive(path:Path, data:dict):
    if (not path.is_absolute() or path.exists() or path.is_symlink()
            or not path.parent.is_dir() or path.parent.is_symlink()):
        raise RoleRequestError("output must be a new absolute file in an existing directory")
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):flags|=os.O_NOFOLLOW
    fd=os.open(path,flags,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2,sort_keys=True)
        f.write("\n")


def main(argv=None):
    p=argparse.ArgumentParser(description="Open SSE multi-role request; wallet signature not applied")
    p.add_argument("--node-id",required=True)
    p.add_argument("--account",required=True)
    p.add_argument("--roles",required=True,
                   help="comma-separated observer,full_node,consumer,provider,monitor,validator")
    p.add_argument("--transport",choices=sorted(TRANSPORTS),default="auto")
    p.add_argument("--genesis-hash",required=True)
    p.add_argument("--chain-id",type=int,default=31338)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args(argv)
    try:
        request=build(node_id=a.node_id,account=a.account,roles=a.roles,
                      genesis_hash=a.genesis_hash,chain_id=a.chain_id,
                      transport=a.transport)
        write_exclusive(a.output,request)
        print(json.dumps({
            "kind":"SSE_UNSIGNED_ROLE_REQUEST_CREATED_V1",
            "requestFile":str(a.output),
            "requestedRoles":request["roles"],
            "transportPreference":request["transportPreference"],
            "walletSignatureAttached":False,
            "walletPrivateKeyUsed":False,
            "rolesActivated":[],
            "ethereumTransactionsSent":False,
        },indent=2,sort_keys=True))
        return 0
    except (RoleRequestError,OSError,ValueError,TypeError) as exc:
        print("SSE_ROLE_REQUEST_CREATE_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
