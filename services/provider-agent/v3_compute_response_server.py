#!/usr/bin/env python3
"""R368 owner-authorized V3 live compute service for one lease.
Unlocks locally once; signs only actual worker results for the accepted
proposal and an existing canonical epoch. No transaction broadcaster.
Runs alongside V2 on a distinct loopback port.
"""
import argparse,json,sys,time,threading
from pathlib import Path
from getpass import getpass
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from eth_account import Account
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
from sse_pos_r367_v3_compute_wire import snapshot,check_proposal,typed,response_hash,validate_reply
from sse_pos_r362_v3_market_operations import verify,require
from sse_pos_r206_adaptive_v2_deployment_audit import rpc
from sse_pos_r237_v2_approved_local_eip712_sign import safe_keystore
from sse_pos_r231_v2_compute_wire import payload_from_result
from v2_compute_response_server import make_docker_executor,unique_pairs
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--proposal",type=Path,required=True)
    p.add_argument("--keystore",type=Path,required=True)
    p.add_argument("--lease",type=int,default=1)
    p.add_argument("--port",type=int,default=8880)
    p.add_argument("--rpc",default="http://127.0.0.1:28545")
    a=p.parse_args()
    require(sys.stdin.isatty() and sys.stderr.isatty(),"owner terminal required")
    d=json.loads(a.proposal.read_text())
    ask=lambda m,v:rpc(a.rpc,m,v)
    verify(ask)
    s=snapshot(ask,a.lease,0);check_proposal(d,s)
    require(s["headTimestamp"]<=s["lastProgressAt"]+s["confirmationSeconds"],"idle allowance expired")
    execute=make_docker_executor(d["profile"],"http://127.0.0.1:8877","sse-compute-vm4714",dedicated_vm4714_sudo_docker=True)
    print("Authorize live compute response signatures only for lease",a.lease,"provider",s["provider"],flush=True)
    require(input("Type ENABLE-V3-PROVIDER: ")=="ENABLE-V3-PROVIDER","not authorized")
    account=Account.from_key(Account.decrypt(safe_keystore(a.keystore),getpass("Provider wallet password: ")))
    require(account.address.lower()==s["provider"].lower(),"wrong provider wallet")
    lock=threading.Lock()
    cache={}
    class Handler(BaseHTTPRequestHandler):
        def reply(self,status,body):
            raw=json.dumps(body,separators=(",",":")).encode()
            try:
                self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError):
                # Client disconnected or timed out; do not attempt a second reply.
                self.close_connection=True
                print("V3_HTTP_CLIENT_DISCONNECTED",flush=True)
        def do_GET(self):
            if self.path=="/healthz":self.reply(200,{"service":"SSE_V3_PROVIDER","lease":a.lease})
            else:self.reply(404,{})
        def do_POST(self):
            try:
                require(self.path=="/v3/challenge","wrong route")
                self.connection.settimeout(8)
                n=int(self.headers.get("Content-Length","0"));require(0<n<=1024,"bad body size")
                q=json.loads(self.rfile.read(n),object_pairs_hook=unique_pairs)
                require(set(q)=={"leaseId","epochId","requestHash"} and q["leaseId"]==a.lease and type(q["epochId"]) is int and 0<=q["epochId"]<d["terms"]["epochs"],"wrong challenge")
                with lock:
                    s=snapshot(ask,a.lease,q["epochId"]);check_proposal(d,s)
                    require(s["exists"] and not s["sealed"] and s["requestHash"]==q["requestHash"] and s["headTimestamp"]<=s["monitoringClose"],"inactive challenge")
                    key=(q["epochId"],q["requestHash"])
                    # Reject expired first responses before spending worker resources.
                    if key not in cache:
                        require(s["headTimestamp"]<=s["responseDeadline"],"first response deadline expired")
                    result=execute(a.lease,q["epochId"],q["requestHash"])
                    payload=payload_from_result(a.lease,q["epochId"],q["requestHash"],s["profileHash"],s["policyHash"],result)
                    h=response_hash(payload)
                    fresh=snapshot(ask,a.lease,q["epochId"])
                    require(fresh["requestHash"]==s["requestHash"] and not fresh["sealed"] and fresh["headTimestamp"]<=fresh["monitoringClose"],"epoch changed")
                    key=(q["epochId"],q["requestHash"])
                    if key not in cache:
                        require(fresh["headTimestamp"]<=fresh["responseDeadline"],"first response deadline expired")
                        cache[key]={**payload,"responseHash":h,"providerSignature":"0x"+bytes(account.sign_message(typed(s,"ProviderResponse",h)).signature).hex()}
                    reply=cache[key];validate_reply(reply,fresh)
                self.reply(200,reply)
            except (ValueError,TypeError,KeyError,OSError,RuntimeError):
                self.reply(503,{"error":"live workload or authorization unavailable"})
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(("127.0.0.1",a.port),Handler)
    print("V3_PROVIDER_LOOPBACK_READY=true",flush=True)
    server.serve_forever()
if __name__=="__main__":main()
