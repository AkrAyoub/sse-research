"""R403: opt-in provider owner control page, with injected EIP-1193 wallet.
No private keys, passwords, external scripts, or generic RPC forwarding."""
import json,html
SCRIPT=r"""
"use strict";
const status=document.getElementById("result");
const btn=document.getElementById("interrupt");
async function post(path,data){
 const r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data),credentials:"omit",cache:"no-store",redirect:"error"});
 const v=await r.json();if(!r.ok)throw Error(v.error||"Request refused");return v;
}
btn.addEventListener("click",async()=>{
 btn.disabled=true;
 try{
  if(!window.ethereum)throw Error("An injected browser wallet is required");
  const accounts=await window.ethereum.request({method:"eth_requestAccounts"});
  const seconds=Number(document.getElementById("seconds").value);
  const c=await post("/v3/control/challenge",{seconds});
  const owner=c.challenge.owner;
  if(!accounts.some(a=>a.toLowerCase()===owner.toLowerCase()))throw Error("Select the enrolled node owner wallet");
  if(c.challenge.durationSeconds!==seconds||c.challenge.operation!=="provider-interrupt")throw Error("Challenge mismatch");
  const signature=await window.ethereum.request({method:"eth_signTypedData_v4",params:[owner,JSON.stringify(c.typedData)]});
  const r=await post("/v3/control/approve",{challenge:c.challenge,signature,parameters:c.parameters});
  status.textContent="Provider suspension requested and applied. Recovery timer: "+r.recoveryTimer+". Recovery is not yet verified.";
 }catch(e){status.textContent=String(e.message||e);}
 finally{btn.disabled=false;}
});
"""
def page(node):
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>SSE owner control</title><h1>Provider control / "+html.escape(node)+"</h1><p>Only the enrolled owner wallet can authorize suspension. Existing leases may be affected. Automatic timed recovery is scheduled before suspension.</p><label>Duration <select id='seconds'><option>15</option><option>60</option><option>120</option><option>240</option></select> seconds</label> <button id='interrupt'>Review and sign interruption</button><pre id='result' aria-live='polite'></pre><p><a href='/'>Return to marketplace</a></p><script src='/v3/control.js'></script></html>").encode()
def dispatch(broker,path,data):
    if type(data) is not dict:raise ValueError("invalid request")
    if path=="/v3/control/challenge" and set(data)=={"seconds"}:
        return broker.issue(data["seconds"])
    if path=="/v3/control/approve" and set(data)=={"challenge","signature","parameters"}:
        return broker.approve(data["challenge"],data["signature"],data["parameters"])
    raise ValueError("invalid control request")
