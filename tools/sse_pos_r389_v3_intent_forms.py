"""Stateless marketplace intent forms. No signing, RPC writes or local file writes."""
import html,json
from urllib.parse import parse_qs
from sse_pos_r388_v3_owner_intent import ACTIONS,validate
# Only expose straightforward actions. Evidence-bound operations remain agent-driven.
FIELDS={
"bid":(("requestId","Request ID"),("feeWei","Epoch fee (wei)")),
"register":(),
"confirm":(("leaseId","Lease ID"),),
"accept":(("leaseId","Lease ID"),("termsHash","Exact agreed terms hash")),
"draw":(("leaseId","Lease ID"),),
"close":(("leaseId","Lease ID"),),
"finalize":(("leaseId","Lease ID"),("epochId","Epoch ID")),
"close-evidence":(("leaseId","Lease ID"),("epochId","Epoch ID")),
"market-withdraw":(),
"ledger-withdraw":(),
"monitor-exit":(),
}
def render(roles):
    esc=lambda x:html.escape(str(x),quote=True)
    parts=["<section class='panel' id='market-actions'><h2>Prepare marketplace operations</h2><p>Download a transaction intent for review and execution by the wallet owner. This page cannot sign, submit or unlock funds.</p>"]
    for role in sorted(set(roles)&set(ACTIONS)):
        parts.append("<h3>"+esc(role.title())+"</h3>")
        for action in sorted(ACTIONS[role]&FIELDS.keys()):
            parts.append("<details class='blockdetail'><summary>"+esc(action.replace("-"," ").title())+"</summary><form method='post' action='/v3/intent'><input type='hidden' name='role' value='"+esc(role)+"'><input type='hidden' name='action' value='"+esc(action)+"'>")
            for name,label in FIELDS[action]:
                parts.append("<p><label>"+esc(label)+" <input required name='"+esc(name)+"' maxlength='78'></label></p>")
            parts.append("<p><label>Maximum total spend (wei) <input required name='maxWei' inputmode='numeric' maxlength='19' value='"+("1000010000000000" if action=="register" else "10000000000")+"'></label></p><button type='submit'>Download unsigned intent</button></form></details>")
    parts.append("</section>")
    return "".join(parts)
def parse(body,roles):
    if len(body)>4096:raise ValueError("form too large")
    f=parse_qs(body.decode("ascii"),strict_parsing=True,keep_blank_values=True,max_num_fields=10)
    if any(len(v)!=1 for v in f.values()):raise ValueError("duplicate field")
    f={k:v[0] for k,v in f.items()}
    role=f.pop("role"); action=f.pop("action"); cap=f.pop("maxWei")
    if role not in roles or role not in ACTIONS or action not in ACTIONS[role] or action not in FIELDS:raise ValueError("unsupported action")
    if set(f)!={name for name,label in FIELDS[action]}:raise ValueError("incorrect fields")
    def uint(v):
        if not v or len(v)>78 or not v.isascii() or not v.isdecimal():raise ValueError("invalid unsigned integer")
        n=int(v)
        if n>=2**256:raise ValueError("integer out of range")
        return n
    params={}
    for k,v in f.items():
        if k=="termsHash":
            if len(v)!=66 or not v.startswith("0x") or len(bytes.fromhex(v[2:]))!=32:raise ValueError("invalid hash")
            params[k]=v
        else:params[k]=uint(v)
    d=dict(schema="SSE_V3_OWNER_INTENT_V1",chainId=31340,role=role,action=action,params=params,maxWei=uint(cap))
    validate(d)
    return json.dumps(d,indent=2).encode("utf-8")
