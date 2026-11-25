#!/usr/bin/env python3
"""R304 bounded provider HTTPS front end. Health only until lease backend enabled.
Never accesses Docker, wallet keys or raw worker port. No SLA claim.
"""
import argparse
import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import ssl
import socket

class Server(HTTPServer):
    address_family=socket.AF_INET6
    def get_request(self):
        sock,addr=super().get_request()
        sock.settimeout(8)
        try:
            return self.context.wrap_socket(sock,server_side=True),addr
        except Exception:
            sock.close()
            raise

def handler(enable_backend):
    class Handler(BaseHTTPRequestHandler):
        def reply(self,status,data):
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(data)))
            self.send_header("Cache-Control","no-store")
            self.send_header("Connection","close")
            self.end_headers()
            self.wfile.write(data)
        def do_GET(self):
            if self.path!="/healthz":
                return self.reply(404,b'{"error":"not found"}')
            self.reply(200,b'{"service":"SSE_PROVIDER_TLS","physicalSlaVerified":false,"leaseVerified":false}')
        def do_POST(self):
            if self.path!="/v2/challenge":
                return self.reply(404,b'{"error":"not found"}')
            if not enable_backend:
                return self.reply(503,b'{"error":"lease backend not enabled"}')
            sizes=self.headers.get_all("Content-Length",[])
            if self.headers.get("Transfer-Encoding") or len(sizes)!=1 or not sizes[0].isdecimal() or not 1<=int(sizes[0])<=1024:
                return self.reply(400,b'{"error":"invalid body size"}')
            conn=http.client.HTTPConnection("127.0.0.1",8879,timeout=8)
            try:
                raw=self.rfile.read(int(sizes[0]))
                if len(raw)!=int(sizes[0]):
                    raise ValueError("truncated request")
                conn.request("POST","/v2/challenge",body=raw,headers={"Content-Type":"application/json","Connection":"close"})
                res=conn.getresponse()
                data=res.read(8193)
                if len(data)>8192 or res.status not in (200,400,404,503):
                    raise ValueError("invalid backend response")
                status=res.status
            except (OSError,ValueError,http.client.HTTPException):
                status,data=503,b'{"error":"lease backend unavailable"}'
            finally:
                conn.close()
            self.reply(status,data)
        def log_message(self,*args):
            pass
    return Handler

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bind",required=True)
    p.add_argument("--cert",required=True)
    p.add_argument("--key",required=True)
    p.add_argument("--enable-lease-backend",action="store_true")
    a=p.parse_args()
    ip=ipaddress.IPv6Address(a.bind)
    if ip not in ipaddress.IPv6Network("fca0::/16"):
        p.error("overlay IPv6 only")
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(a.cert,a.key)
    with Server((str(ip),9443),handler(a.enable_lease_backend)) as server:
        server.context=ctx
        print("R304_PROVIDER_TLS_READY backend_enabled="+str(a.enable_lease_backend),flush=True)
        server.serve_forever()

if __name__=="__main__":
    main()
