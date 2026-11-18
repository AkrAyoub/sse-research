#!/usr/bin/env python3
"""SSE validator-only, one-time headless Tailscale invitation broker.

Separate credentials, database, listener, tailnet tag and admission policy
from the app-role broker. An invitation only grants a tagged overlay device,
NEVER QBFT voting status. OAuth credentials remain on the broker, not a VM.
This WSGI pilot MUST sit behind a hardened HTTPS reverse proxy with rate
limits; do not expose Python wsgiref directly to the public Internet.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import time
from wsgiref.simple_server import WSGIRequestHandler, make_server
from urllib.parse import quote, urlencode
import base64

from sse_mesh_broker import API, _post, EnrollmentError
from sse_mesh_broker_http import validate_file, private_file, _result, _unique_pairs, BrokerHTTPError

TAG="tag:sse-validator"
VALID_IDS=frozenset(f"validator-{i}" for i in range(1,5))
LISTEN_PORT=18782
MAX_BODY=2048

class ValidatorInviteError(ValueError):
    pass


def checked_id(value):
    if type(value) is not str or value not in VALID_IDS:
        raise ValidatorInviteError("only the four preapproved genesis validator IDs are eligible")
    return value


def init_database(db):
    db.execute("""CREATE TABLE IF NOT EXISTS validator_invitation(
      digest TEXT PRIMARY KEY, node_id TEXT NOT NULL,
      expires INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0
    )""")


def issue_invitation(db, node_id, *, now=None, ttl_seconds=600):
    checked_id(node_id)
    if type(ttl_seconds) is not int or not 60 <= ttl_seconds <= 1800:
        raise ValidatorInviteError("invitation lifetime must be between 60 and 1800 seconds")
    stamp=int(time.time()) if now is None else now
    token=secrets.token_urlsafe(32)
    digest=hashlib.sha256(token.encode("ascii")).hexdigest()
    init_database(db)
    with db:
        db.execute("INSERT INTO validator_invitation(digest,node_id,expires,used) VALUES(?,?,?,0)",
                   (digest,node_id,stamp+ttl_seconds))
    return token


def redeem_invitation(db, node_id, token, *, now=None):
    checked_id(node_id)
    if type(token) is not str or not 32 <= len(token) <= 256:
        raise ValidatorInviteError("invalid invitation credential")
    stamp=int(time.time()) if now is None else now
    digest=hashlib.sha256(token.encode("utf-8")).hexdigest()
    init_database(db)
    db.execute("BEGIN IMMEDIATE")
    try:
        row=db.execute("SELECT node_id,expires,used FROM validator_invitation WHERE digest=?",
                       (digest,)).fetchone()
        if row is None or row[0]!=node_id or row[1]<=stamp or row[2]:
            raise ValidatorInviteError("invitation invalid, expired or spent")
        changed=db.execute("UPDATE validator_invitation SET used=1 WHERE digest=? AND used=0",
                           (digest,))
        if changed.rowcount!=1:
            raise ValidatorInviteError("invitation already consumed")
        db.commit()
    except BaseException:
        db.rollback()
        raise


def mint_validator_key(client_id, client_secret, *, tailnet="-", post=_post):
    if (type(client_id) is not str or not client_id
            or type(client_secret) is not str or not client_secret
            or type(tailnet) is not str or not tailnet or "/" in tailnet):
        raise ValidatorInviteError("invalid dedicated OAuth provisioning credentials")
    basic=base64.b64encode((client_id+":"+client_secret).encode()).decode("ascii")
    auth=post(API+"/oauth/token",
              urlencode({"grant_type":"client_credentials","scope":"auth_keys"}).encode(),
              {"Authorization":"Basic "+basic,
               "Content-Type":"application/x-www-form-urlencoded"})
    access=auth.get("access_token")
    if type(access) is not str or not access:
        raise ValidatorInviteError("dedicated validator OAuth unavailable")
    request={
        "capabilities":{"devices":{"create":{
            "reusable":False,"ephemeral":False,"preauthorized":True,
            "tags":[TAG]}}},
        "expirySeconds":300,
        "description":"SSE approved genesis-validator overlay admission",
    }
    result=post(API+"/tailnet/"+quote(tailnet,safe="")+"/keys",
                json.dumps(request,separators=(",",":")).encode(),
                {"Authorization":"Bearer "+access,
                 "Content-Type":"application/json"})
    key=result.get("key")
    if type(key) is not str or not key.startswith("tskey-auth-") or len(key)>2048:
        raise ValidatorInviteError("no valid Tailscale auth key returned")
    return key


class ValidatorInvitationApp:
    def __init__(self, database:Path, client_id:str, client_secret:str,
                 *, tailnet="-", mint=mint_validator_key):
        self.database=Path(database)
        self.client_id=client_id
        self.client_secret=client_secret
        self.tailnet=tailnet
        self.mint=mint

    def __call__(self, environ, start_response):
        path=environ.get("PATH_INFO","")
        method=environ.get("REQUEST_METHOD","")
        if path=="/healthz" and method=="GET":
            return _result(start_response,"200 OK",
                           {"status":"ready","ethereumTransactionsSent":False})
        if path!="/v1/mesh/validator":
            return _result(start_response,"404 Not Found",{"error":"not found"})
        if method!="POST":
            return _result(start_response,"405 Method Not Allowed",
                           {"error":"method not allowed"})
        if environ.get("CONTENT_TYPE","").split(";")[0].strip().lower()!="application/json":
            return _result(start_response,"415 Unsupported Media Type",
                           {"error":"JSON required"})
        try:
            length=environ.get("CONTENT_LENGTH","")
            if not length.isdecimal() or not 1 <= int(length) <= MAX_BODY:
                raise ValidatorInviteError("invalid request length")
            raw=environ.get("wsgi.input").read(int(length))
            if len(raw)!=int(length):
                raise ValidatorInviteError("truncated request")
            doc=json.loads(raw.decode("utf-8"),object_pairs_hook=_unique_pairs)
            if type(doc) is not dict or set(doc)!={"node_id","invitation"}:
                raise ValidatorInviteError("unexpected admission fields")
            node_id=checked_id(doc["node_id"])
            with closing(sqlite3.connect(self.database,isolation_level=None,timeout=8)) as db:
                redeem_invitation(db,node_id,doc["invitation"])
            # Burn before mint: upstream failure requires a new owner-issued invitation.
            key=self.mint(self.client_id,self.client_secret,tailnet=self.tailnet)
            return _result(start_response,"200 OK",{
                "nodeId":node_id,"role":"validator-overlay-only",
                "tailnetAuthKey":key,"expiresInSeconds":300,
                "qbftVotingGranted":False,
            })
        except (ValidatorInviteError, EnrollmentError, BrokerHTTPError,
                ValueError, TypeError, UnicodeError, sqlite3.Error,
                OSError, AttributeError):
            return _result(start_response,"403 Forbidden",{"error":"enrollment denied"})


class QuietRequestHandler(WSGIRequestHandler):
    def log_message(self, fmt, *args):
        pass


def main(argv=None):
    p=argparse.ArgumentParser(description="SSE dedicated loopback-only validator enrollment broker")
    p.add_argument("--issue",action="store_true",
                   help="admin only: issue a short-lived invitation ONCE to private stdout")
    p.add_argument("--node-id")
    p.add_argument("--database",required=True,type=Path)
    p.add_argument("--client-id-file",type=Path)
    p.add_argument("--client-secret-file",type=Path)
    p.add_argument("--tailnet",default="-")
    p.add_argument("--port",type=int,default=LISTEN_PORT)
    args=p.parse_args(argv)
    try:
        if args.issue:
            if not args.node_id:
                raise ValidatorInviteError("validator ID required to issue invitation")
            parent=args.database.parent
            if (not args.database.is_absolute() or args.database.is_symlink()
                    or not parent.is_dir() or parent.is_symlink()
                    or parent.stat().st_uid!=os.geteuid()
                    or (parent.stat().st_mode & 0o077)):
                raise ValidatorInviteError("database parent must be owner-controlled mode 0700")
            if args.database.exists():
                validate_file(args.database,max_bytes=20_000_000)
            else:
                flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY
                if hasattr(os,"O_NOFOLLOW"):
                    flags|=os.O_NOFOLLOW
                fd=os.open(args.database,flags,0o600)
                os.close(fd)
            with closing(sqlite3.connect(args.database,timeout=8,isolation_level=None)) as db:
                token=issue_invitation(db,args.node_id)
            print(token)
            return 0
        if not args.client_id_file or not args.client_secret_file:
            raise ValidatorInviteError("dedicated OAuth client files required")
        if not 1024<=args.port<=65535 or not args.tailnet or "/" in args.tailnet:
            raise ValidatorInviteError("invalid loopback broker configuration")
        validate_file(args.database,max_bytes=20_000_000)
        client_id=private_file(args.client_id_file,max_bytes=512)
        secret=private_file(args.client_secret_file,max_bytes=4096)
        with make_server("127.0.0.1",args.port,
                ValidatorInvitationApp(args.database,client_id,secret,tailnet=args.tailnet),
                handler_class=QuietRequestHandler) as server:
            print("SSE_VALIDATOR_BROKER_LOOPBACK_ONLY",flush=True)
            server.serve_forever()
        return 0
    except (ValidatorInviteError,BrokerHTTPError,EnrollmentError,OSError,
            sqlite3.Error,ValueError) as exc:
        print("SSE_VALIDATOR_BROKER_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
