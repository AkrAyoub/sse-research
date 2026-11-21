#!/usr/bin/env python3
"""R158 experimental unprivileged permissionless discovery-hint relay.

Serves R142 JSON and accepts fresh R156 public identities via one path,
without an EOA, owner allowlist, staking key, chain RPC or private keys.
Bind only localhost. Independently-operated reverse proxies MUST provide
verified public HTTPS, rate/abuse controls, logging and source diversity.
A relay is NOT an admission authority, validator, consensus oracle, nor
a proof of native peer reachability or authenticated operator identity.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from threading import RLock
import time

import sse_pos_r157_public_peer_directory as directory
import sse_pos_r142_public_peer_discovery as r142

PATH="/peers.json"
MAX_BODY=directory.MAX_FILE

class Refused(ValueError):
    pass

class PeerStore:
    def __init__(self, *, clock=time.time):
        self.clock=clock
        self.lock=RLock()
        self.records={}

    @staticmethod
    def public_key(record):
        enode=record["publicPeerRecord"]["executionEnode"]
        return enode.split("@",1)[0]

    def _expire(self,now):
        for node,item in list(self.records.items()):
            if item["expiresAt"]<=now:
                del self.records[node]

    def announce(self,obj):
        now=int(self.clock())
        try:
            peer,expiry=directory.parse_record(obj,now=now)
        except (directory.Refused,ValueError,TypeError,KeyError) as exc:
            raise Refused("malformed, stale or wrong-chain public peer record") from exc
        identity=peer["nodeId"]
        with self.lock:
            self._expire(now)
            old=self.records.get(identity)
            if old and self.public_key(old)!=self.public_key(obj):
                raise Refused("different native node key cannot take over live ID")
            if not old and len(self.records)>=directory.MAX_RECORDS:
                raise Refused("directory at bounded capacity; no new hint accepted")
            self.records[identity]=obj
            return {"accepted":True,"nodeId":identity,"expiresAt":expiry,
                    "nativePeerReachabilityOrOwnershipVerified":False,
                    "membershipOrRoleGranted":False}

    def snapshot(self):
        now=int(self.clock())
        with self.lock:
            self._expire(now)
            if not self.records:
                raise Refused("no live public native records")
            try:
                return directory.build(list(self.records.values()),now=now)
            except directory.Refused as exc:
                raise Refused("unusable untrusted public directory state") from exc

def handler_factory(store):
    class Handler(BaseHTTPRequestHandler):
        # HTTP/1.0 closes each request. No CORS headers, no admin endpoints.
        def _send(self,status,data):
            blob=(json.dumps(data,sort_keys=True)+"\n").encode()
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(blob)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.end_headers()
            self.wfile.write(blob)
        def do_GET(self):
            if self.path!=PATH:
                self._send(404,{"error":"unknown endpoint"})
                return
            try:
                self._send(200,store.snapshot())
            except Refused:
                self._send(503,{"error":"no current native peer hints"})
        def do_POST(self):
            if self.path!=PATH:
                self._send(404,{"error":"unknown endpoint"})
                return
            length=self.headers.get("Content-Length")
            if (length is None or not re.fullmatch(r"[0-9]{1,6}",length)
                    or not 0<int(length)<=MAX_BODY):
                self._send(413,{"error":"bounded JSON required"})
                return
            if self.headers.get("Content-Type","").split(";",1)[0].strip()!="application/json":
                self._send(415,{"error":"application/json required"})
                return
            raw=self.rfile.read(int(length))
            try:
                obj=json.loads(raw,object_pairs_hook=r142._unique_keys)
                result=store.announce(obj)
            except (ValueError,UnicodeError,TypeError,Refused):
                self._send(422,{"error":"invalid or conflicting public node record"})
                return
            self._send(202,result)
        def log_message(self,format,*args):
            # Avoid logging raw payloads, token strings, signer files etc.
            return
    return Handler

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--listen",default="127.0.0.1",
                   help="localhost only; use independent TLS proxy for public hosting")
    p.add_argument("--port",type=int,default=18090)
    args=p.parse_args(argv)
    if args.listen!="127.0.0.1" or not 1024<=args.port<=65535:
        p.error("experimental directory must bind localhost behind a reviewed HTTPS proxy")
    server=ThreadingHTTPServer((args.listen,args.port),
                                handler_factory(PeerStore()))
    server.daemon_threads=True
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
    return 0

if __name__=="__main__":
    raise SystemExit(main())
