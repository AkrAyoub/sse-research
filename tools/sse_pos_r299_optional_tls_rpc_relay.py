#!/usr/bin/env python3
"""R299 optional public-overlay TLS JSON-RPC relay and local client adapter.

No keys, accounts, Engine API, admin calls, or participant admission.
Explicit endpoint certificate trust is required; remote RPC is not a
trustless consensus proof. Any full node can run a relay. Default read-only;
raw signed transaction forwarding requires explicit server opt-in.
"""
import argparse
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import json
import re
import ssl
import sys
from pathlib import Path

READ=frozenset(("eth_chainId","eth_getBlockByNumber","eth_getTransactionByHash",
    "eth_getTransactionReceipt","eth_getCode","eth_call","eth_estimateGas",
    "eth_gasPrice","eth_getBalance","eth_getTransactionCount","eth_getLogs",
    "eth_syncing","net_peerCount","eth_blockNumber","eth_getBlockByHash","web3_clientVersion"))
MAX_REQUEST=65536
MAX_RESPONSE=131072

def overlay(address):
    ip=ipaddress.IPv6Address(address)
    if ip not in ipaddress.IPv6Network("fca0::/16"):
        raise ValueError("expected controllerless overlay IPv6")
    return str(ip)

def unique(pairs):
    out={}
    for k,v in pairs:
        if k in out: raise ValueError("duplicate JSON key")
        out[k]=v
    return out

def validate(raw,allow_send=False):
    if not 0<len(raw)<=MAX_REQUEST: raise ValueError("request size")
    obj=json.loads(raw,object_pairs_hook=unique)
    if (type(obj) is not dict or set(obj)!={"jsonrpc","id","method","params"} or
        obj["jsonrpc"]!="2.0" or type(obj["id"]) not in (int,str) or
        type(obj["method"]) is not str or type(obj["params"]) is not list):
        raise ValueError("single JSON-RPC request required")
    method=obj["method"]
    if method not in READ:
        if not allow_send or method!="eth_sendRawTransaction":
            raise ValueError("method not allowed")
        p=obj["params"]
        if len(p)!=1 or type(p[0]) is not str or not re.fullmatch(r"0x(?:[0-9a-fA-F]{2}){1,16384}",p[0]):
            raise ValueError("bounded signed raw transaction required")
    if method=="eth_getLogs":
        p=obj["params"]
        if len(p)!=1 or type(p[0]) is not dict:
            raise ValueError("explicit log filter required")
        f=p[0]
        if "blockHash" not in f:
            a,b=f.get("fromBlock"),f.get("toBlock")
            if not all(type(x) is str and re.fullmatch(r"0x[0-9a-fA-F]+",x) for x in (a,b)) or not 0<=int(b,16)-int(a,16)<=2048:
                raise ValueError("explicit bounded log range required")
    return obj

def forward(conn,raw,obj):
    try:
        conn.request("POST","/",body=raw,headers={"Content-Type":"application/json","Connection":"close"})
        res=conn.getresponse()
        if res.status!=200: raise ValueError("upstream status")
        data=res.read(MAX_RESPONSE+1)
        if len(data)>MAX_RESPONSE: raise ValueError("upstream response too large")
        result=json.loads(data,object_pairs_hook=unique)
        if type(result) is not dict or result.get("jsonrpc")!="2.0" or result.get("id")!=obj["id"] or (("result" in result)==("error" in result)):
            raise ValueError("upstream JSON-RPC response mismatch")
        return data
    finally:
        conn.close()

def make_handler(connect,allow_send):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(10)
            super().setup()
        def reply(self,status,data):
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(data)))
            self.send_header("Connection","close")
            self.end_headers()
            self.wfile.write(data)
        def do_POST(self):
            try:
                lengths=self.headers.get_all("Content-Length",[])
                if self.path!="/" or self.headers.get("Transfer-Encoding") or len(lengths)!=1 or not lengths[0].isdecimal() or not 1<=int(lengths[0])<=MAX_REQUEST:
                    raise ValueError("invalid HTTP request")
                n=int(lengths[0])
                raw=self.rfile.read(n)
                if len(raw)!=n: raise ValueError("truncated request")
                obj=validate(raw,allow_send)
                data=forward(connect(),raw,obj)
            except (ValueError,OSError,http.client.HTTPException):
                return self.reply(400,b'{"error":"relay request refused or upstream unavailable"}')
            self.reply(200,data)
        def log_message(self,*args): pass
    return Handler

class IPv6Server(HTTPServer):
    import socket
    address_family=socket.AF_INET6
    def get_request(self):
        sock,addr=super().get_request()
        sock.settimeout(10)
        return sock,addr

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="mode",required=True)
    s=sub.add_parser("serve")
    s.add_argument("--bind",required=True,type=overlay)
    s.add_argument("--cert",required=True,type=Path)
    s.add_argument("--key",required=True,type=Path)
    s.add_argument("--upstream-port",required=True,type=int,choices=(18545,28545))
    c=sub.add_parser("client")
    c.add_argument("--remote",required=True,type=overlay)
    c.add_argument("--cert",required=True,type=Path,help="independently verified public server certificate")
    c.add_argument("--fingerprint",required=True,help="expected lowercase SHA256 DER certificate fingerprint")
    c.add_argument("--local-port",type=int,choices=(18545,28545),default=28545)
    for q in (s,c):
        q.add_argument("--allow-raw-send",action="store_true")
    a=p.parse_args()
    if a.mode=="serve":
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version=ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(a.cert,a.key)
        server=IPv6Server((a.bind,19443),make_handler(lambda:http.client.HTTPConnection("127.0.0.1",a.upstream_port,timeout=8),a.allow_raw_send))
        # Handshake timeout applies before TLS negotiation.
        original=server.get_request
        def tls_request():
            sock,addr=original()
            try: return ctx.wrap_socket(sock,server_side=True),addr
            except Exception:
                sock.close()
                raise
        server.get_request=tls_request
    else:
        pem=a.cert.read_text("ascii")
        der=ssl.PEM_cert_to_DER_cert(pem)
        if hashlib.sha256(der).hexdigest()!=a.fingerprint:
            raise ValueError("certificate fingerprint mismatch")
        ctx=ssl.create_default_context(cafile=str(a.cert))
        ctx.minimum_version=ssl.TLSVersion.TLSv1_2
        # Standard certificate verification and IP SAN matching remain enabled.
        server=HTTPServer(("127.0.0.1",a.local_port),make_handler(lambda:http.client.HTTPSConnection(a.remote,19443,context=ctx,timeout=12),a.allow_raw_send))
    print("R299_RELAY_READY",a.mode,"raw_send",a.allow_raw_send,flush=True)
    try: server.serve_forever()
    finally: server.server_close()

if __name__=="__main__":
    try: main()
    except (ValueError,OSError) as exc:
        print("R299_REFUSED:",exc,file=sys.stderr)
        sys.exit(2)
