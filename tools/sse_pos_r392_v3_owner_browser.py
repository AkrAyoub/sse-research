#!/usr/bin/env python3
"""Separate owner-local browser approval service; never tunnel this listener.
One-time capability + same-origin POST + one-use preview. Terminal wallet approval
remains mandatory. Does not collect passwords in HTTP or accept arbitrary commands.
"""
import argparse,html,json,secrets,time,threading,sys
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.parse import parse_qs,urlsplit
from pathlib import Path
from sse_pos_r388_v3_owner_intent import validate
from sse_pos_r362_v3_market_operations import verify,execute,require
from sse_pos_r206_adaptive_v2_deployment_audit import rpc

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--address",required=True)
    p.add_argument("--keystore",type=Path,required=True)
    p.add_argument("--roles",required=True)
    p.add_argument("--rpc",default="http://127.0.0.1:28545")
    p.add_argument("--port",type=int,default=8771)
    a=p.parse_args()
    require(sys.stdin.isatty() and sys.stderr.isatty(),"owner terminal required")
    require(1024<=a.port<=65535,"invalid port")
    roles=set(a.roles.split(","))
    require(roles and roles<={"consumer","provider","monitor"},"invalid roles")
    ask=lambda m,p:rpc(a.rpc,m,p)
    verify(ask)
    origin="http://127.0.0.1:"+str(a.port)
    token=secrets.token_urlsafe(32)
    expiry=time.monotonic()+900
    state={"preview":None}
    esc=lambda s:html.escape(str(s),quote=True)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def setup(self):
            super().setup()
            self.connection.settimeout(5)
        def reply(self,status,body):
            data=("<!doctype html><meta charset='utf-8'><title>SSE owner approval</title>"+body).encode()
            self.send_response(status)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length",str(len(data)))
            self.send_header("Cache-Control","no-store")
            self.send_header("Referrer-Policy","no-referrer")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Security-Policy","default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(data)
        def host_ok(self):
            return self.headers.get("Host")=="127.0.0.1:"+str(a.port) and time.monotonic()<expiry
        def do_GET(self):
            if not self.host_ok() or not secrets.compare_digest(self.path,"/"+token):
                return self.reply(403,"Forbidden")
            self.reply(200,"<h1>Owner marketplace approval</h1><p>Wallet "+esc(a.address)+"</p><p>Paste the unsigned intent. Review is required on this page and in the owner terminal.</p><form method='post' action='/preview'><input type='hidden' name='token' value='"+token+"'><textarea name='intent' required rows='20' cols='80' maxlength='16384'></textarea><button>Review intent</button></form>")
        def do_POST(self):
            try:
                require(self.host_ok() and self.headers.get("Origin")==origin,"invalid origin")
                require(not self.headers.get("Transfer-Encoding") and self.headers.get_content_type()=="application/x-www-form-urlencoded","invalid encoding")
                lengths=self.headers.get_all("Content-Length") or []
                require(len(lengths)==1 and lengths[0].isdigit() and 0<int(lengths[0])<=65536,"invalid length")
                raw=self.rfile.read(int(lengths[0]))
                require(len(raw)==int(lengths[0]),"incomplete body")
                f=parse_qs(raw.decode("ascii"),strict_parsing=True,max_num_fields=3,keep_blank_values=True)
                require(all(len(v)==1 for v in f.values()),"duplicate fields")
                f={k:v[0] for k,v in f.items()}
                require(secrets.compare_digest(f.pop("token"),token),"invalid capability")
                if self.path=="/preview":
                    require(set(f)=={"intent"} and len(f["intent"])<=16384,"invalid intent")
                    d=json.loads(f["intent"])
                    target,data,value=validate(d)
                    require(d["role"] in roles,"role not enabled")
                    nonce=secrets.token_urlsafe(24)
                    state["preview"]=(nonce,d,time.monotonic()+120)
                    return self.reply(200,"<h1>Review exact intent</h1><pre>"+esc(json.dumps(d,indent=2))+"</pre><p>Contract "+esc(target)+" / value "+esc(value)+" wei</p><pre>"+esc(data)+"</pre><form method='post' action='/approve'><input type='hidden' name='token' value='"+token+"'><input type='hidden' name='nonce' value='"+nonce+"'><button>Request terminal authorization</button></form>")
                require(self.path=="/approve" and set(f)=={"nonce"},"invalid action")
                preview=state.pop("preview",None)
                require(preview is not None and secrets.compare_digest(f["nonce"],preview[0]) and time.monotonic()<preview[2],"preview expired or used")
                d=preview[1]
                # Return before blocking on the owner terminal; no browser success claim.
                self.reply(202,"<h1>Intent awaiting owner terminal</h1><p>Check the local terminal for approval and actual transaction receipt. No success is asserted.</p>")
                state["pending"]=d
            except (ValueError,KeyError,TypeError,OSError,OverflowError):
                self.reply(400,"Invalid or expired owner request")
    server=HTTPServer(("127.0.0.1",a.port),Handler)
    server.timeout=1
    print("OWNER_LOCAL_ONLY="+origin+"/"+token,flush=True)
    try:
        while time.monotonic()<expiry:
            server.handle_request()
            d=state.pop("pending",None)
            if d is not None:
                validate(d)
                require(d["role"] in roles,"role not enabled")
                print(json.dumps(d,indent=2),flush=True)
                verify(ask)
                execute(ask,d["action"],d["params"],a.address,d["maxWei"],send=True,keystore=a.keystore)
                break
    finally:server.server_close()
if __name__=="__main__":main()
