"""Ubuntu SSE role-local console and read-only heartbeat (stdlib only).

Each node owns its local UI and role-scoped *draft preferences*. Neither the
independent network dashboard nor this early console can sign/send blockchain
transactions, activate roles, control Docker or attest SLA truth.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import secrets
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

NAME = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
ROLES = frozenset({"provider", "consumer", "monitor", "ethereum_full_node",
                   "validator", "rpc", "observer", "dashboard", "logs"})
# This is local policy drafting only; not an authorized on-chain price.
SETTINGS = {
    "consumer": {"max_epoch_fee_wei": (1, 2**128 - 1), "max_epochs": (1, 64)},
    "provider": {"min_epoch_fee_wei": (0, 2**128 - 1),
                 "offered_capacity_units": (0, 100000)},
    "monitor": {"probe_interval_seconds": (1, 3600),
                "probe_timeout_ms": (1, 60000)},
    "observer": {},
}
PAGES = {
    "consumer": ("Consumer", "Draft resource requests and price ceilings; signing unavailable"),
    "provider": ("Provider", "Draft capacity and bid settings; deployment unavailable"),
    "monitor": ("Monitor", "Probe settings and evidence visibility; bond and vote signing unavailable"),
    "observer": ("Observer", "Read-only network and chain inspection, once connected"),
}
STYLE = """
:root{font:15px/1.55 system-ui,sans-serif;color:#edf5ff;background:#0a1424}
*{box-sizing:border-box}body{max-width:980px;margin:auto;padding:32px 18px}
h1{font-size:2rem}small,p{color:#bdcde1}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:15px}
article,section{border:1px solid #34506b;border-radius:13px;padding:20px;background:#13243a;margin:14px 0}
strong{color:white}textarea,input{display:block;width:100%;margin:8px 0 14px;background:#09182b;
color:white;border:1px solid #54728c;padding:10px;border-radius:7px}
textarea{min-height:100px}button{padding:10px 18px;border:0;border-radius:8px;
background:#72d8cd;color:#07303a;font-weight:650;cursor:pointer}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#0a1424;padding:12px;border-radius:7px}
"""


def config(environ=None):
    env = os.environ if environ is None else environ
    name = env.get("SSE_NODE_ID", "sse-local-node")
    roles = [x.strip() for x in env.get("SSE_ROLES", "observer").split(",")]
    if (not NAME.fullmatch(name) or not roles or any(x not in ROLES for x in roles)
            or len(roles) != len(set(roles))):
        raise ValueError("invalid node name or roles")
    host = env.get("SSE_AGENT_HOST", "127.0.0.1")
    if host != "127.0.0.1":
        raise ValueError("node console must bind only to loopback; use authenticated proxy")
    port = int(env.get("SSE_AGENT_PORT", "8765"))
    if not 1024 <= port <= 65535:
        raise ValueError("invalid node console port")
    revision = env.get("SSE_REVISION", "local")
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,80}", revision):
        raise ValueError("invalid revision")
    token = env.get("SSE_NODE_UI_TOKEN", "")
    cred_dir = env.get("CREDENTIALS_DIRECTORY", "")
    if not token and cred_dir:
        credential = Path(cred_dir) / "ui-token"
        if credential.is_symlink():
            raise ValueError("console credential symlink forbidden")
        token = credential.read_text(encoding="utf-8").strip()
    settings_file = env.get("SSE_NODE_SETTINGS_FILE", "")
    chain_values = [env.get(key, "") for key in
                    ("SSE_CHAIN_ID", "SSE_BOARD_ADDRESS", "SSE_SETTLEMENT_ADDRESS",
                     "SSE_COMMITTEE_POOL_ADDRESS")]
    chain = None
    if any(chain_values):
        if not all(chain_values):
            raise ValueError("node marketplace requires complete public chain configuration")
        chain_id, board, settlement, pool = chain_values
        if not chain_id.isdigit() or int(chain_id) < 1 or int(chain_id) >= 2**256:
            raise ValueError("invalid node marketplace chain ID")
        if any(not re.fullmatch(r"0x[0-9a-fA-F]{40}", value) or int(value, 16) == 0
               for value in (board, settlement, pool)):
            raise ValueError("invalid node marketplace contract address")
        chain = {"chain_id": int(chain_id), "board": board,
                 "settlement": settlement, "pool": pool}
    if bool(token) != bool(settings_file):
        raise ValueError("local writes require both token and settings file")
    if token and len(token) < 32:
        raise ValueError("local admin token too short")
    if settings_file and (not Path(settings_file).is_absolute()
                          or ".." in Path(settings_file).parts):
        raise ValueError("settings file path must be absolute and safe")
    monitor_snapshot = env.get("SSE_MONITOR_WORK_SNAPSHOT_FILE", "")
    monitor_wallet = env.get("SSE_MONITOR_WALLET", "")
    if bool(monitor_snapshot) != bool(monitor_wallet):
        raise ValueError("monitor display requires both snapshot path and public monitor wallet")
    if monitor_snapshot:
        if ("monitor" not in roles or not token or
                not Path(monitor_snapshot).is_absolute() or
                ".." in Path(monitor_snapshot).parts or
                re.fullmatch(r"0x[0-9a-fA-F]{40}", monitor_wallet) is None or
                int(monitor_wallet,16) == 0):
            raise ValueError("monitor display requires owner-authenticated local monitor role")
    return {"node_id": name, "roles": roles, "port": port, "host": host,
            "revision": revision, "admin_token": token,
            "settings_file": settings_file, "chain": chain,
            "monitor_snapshot": monitor_snapshot,
            "monitor_wallet": monitor_wallet.lower()}


def validate_preferences(roles, payload):
    if type(payload) is not dict or any(r not in roles or r not in SETTINGS for r in payload):
        raise ValueError("preferences must contain only configured application roles")
    result = {}
    for role, fields in payload.items():
        if type(fields) is not dict:
            raise ValueError("role settings must be an object")
        parsed = {}
        for key, value in fields.items():
            limit = SETTINGS[role].get(key)
            if limit is None or type(value) is not int or not limit[0] <= value <= limit[1]:
                raise ValueError("unsupported or out-of-range role setting")
            parsed[key] = value
        result[role] = parsed
    return result


def read_preferences(conf):
    path = conf.get("settings_file")
    if not path:
        return {}
    f = Path(path)
    if f.is_symlink():
        raise ValueError("settings symlink forbidden")
    if not f.exists():
        return {}
    if f.stat().st_size > 8192:
        raise ValueError("settings file too large")
    return validate_preferences(conf["roles"], json.loads(f.read_text(encoding="utf-8")))


def write_preferences(conf, data):
    path = Path(conf["settings_file"])
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink() or path.is_symlink():
        raise ValueError("settings directory missing or symlinked")
    # Mode bits have different meanings under Windows' ACL emulation.
    # Enforce the POSIX permission boundary when actually running on Ubuntu.
    if os.name == "posix" and parent.stat().st_mode & 0o022:
        raise ValueError("settings directory must not be group/world writable")
    fd, stage = tempfile.mkstemp(prefix=".sse-settings-", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            if hasattr(os, "fchmod"):
                os.fchmod(out.fileno(), 0o600)
            else:
                # Windows-only offline functional testing; Ubuntu always uses
                # the secure POSIX fchmod path.
                os.chmod(stage, 0o600)
            json.dump(data, out, sort_keys=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(stage, path)
    finally:
        if os.path.exists(stage):
            os.unlink(stage)


def page(conf):
    monitor_panel = ("""<section><h2>Monitor work review (read-only)</h2>
<p>Owner-authenticated local snapshot only. No signing, voting, confirmation,
execution, or SLA certification. Review tasks can become stale between checks.</p>
<button id="monitor-review">View recent monitor tasks</button>
<pre id="monitor-review-result">No review loaded. Enter local admin token before viewing.</pre>
</section>""" if "monitor" in conf["roles"] else "")
    cards = "".join(
        "<article><strong>" + html.escape(PAGES[r][0]) +
        "</strong><p>" + html.escape(PAGES[r][1]) + "</p></article>"
        for r in conf["roles"] if r in PAGES
    )
    return ("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer"><title>SSE Node Console</title><style>"""
            + STYLE + """</style></head><body><small>SSE INTERCLOUD / UBUNTU NODE</small><h1>"""
            + html.escape(conf["node_id"]) + """</h1><p>Local, role-owned console. Draft settings do not submit transactions or change running workloads.</p><div class="grid">"""
            + cards + """</div>""" + monitor_panel + """<section><h2>Node status</h2><pre id="status">Loading...</pre></section>
<section><h2>Local preferences (draft)</h2>
<p>Only role-specific non-secret numeric preferences are accepted. Changes are
stored locally but not activated on-chain. Use a separate network-wide dashboard
for aggregate observation.</p><textarea id="preferences" spellcheck="false">{}</textarea>
<label for="token">Node-local admin token (never stored by this page)</label>
<input type="password" id="token" autocomplete="off"><button id="save">Save draft</button>
<pre id="message">Read-only unless an owner-provisioned local admin token and settings path exist.</pre>
</section><section><h2>Role-owned marketplace transaction preview</h2>
<p>This does not sign, send, or fund transactions. It generates the exact
contract call for review by the owner of this Ubuntu VM.</p>
<label for="txrole">Owner role</label><select id="txrole"></select>
<label for="txaction">Action</label><select id="txaction"></select>
<label for="txparams">Action parameters (JSON)</label>
<textarea id="txparams" spellcheck="false">{}</textarea>
<button id="txpreview">Preview transaction only</button>
<pre id="txresult">No transaction submitted.</pre>
</section><script>
const out=document.getElementById('message'), area=document.getElementById('preferences');
const monitorReviewButton=document.getElementById('monitor-review');
if(monitorReviewButton){
 monitorReviewButton.addEventListener('click',async()=>{
  const target=document.getElementById('monitor-review-result');
  const token=document.getElementById('token').value;
  document.getElementById('token').value='';
  try {
   const response=await fetch('/v1/monitor-work',{
     headers:{'Authorization':'Bearer '+token},
     cache:'no-store'
   });
   const data=await response.json();
   target.textContent=response.ok?JSON.stringify(data,null,2):
      (data.error||'Monitor review unavailable');
  }catch(_){target.textContent='Monitor review unavailable';}
 });
}
async function refresh(){
 const [s,p]=await Promise.all([fetch('/v1/status'),fetch('/v1/preferences')]);
 document.getElementById('status').textContent=JSON.stringify(await s.json(),null,2);
 const state=await p.json();area.value=JSON.stringify(state.preferences,null,2);
}
document.getElementById('save').addEventListener('click',async()=>{
 try {
  const body=JSON.parse(area.value);
  const token=document.getElementById('token').value;
  document.getElementById('token').value='';
  const r=await fetch('/v1/preferences',{method:'PUT',
   headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},
   body:JSON.stringify(body)});
  const data=await r.json();
  out.textContent=r.ok?'Draft saved locally; not applied to blockchain.':data.error;
  if(r.ok)await refresh();
 }catch(_){out.textContent='Invalid JSON or request failure';}
});
const roleSelect=document.getElementById('txrole');
const actSelect=document.getElementById('txaction');
const txOutput=document.getElementById('txresult');
const actionRoles={
 consumer:['request','fund','admit-epoch','close-lease','withdraw',
           'seal-epoch','settle-epoch','close-evidence','release-committee'],
 provider:['bid','accept','withdraw',
           'seal-epoch','settle-epoch','close-evidence','release-committee'],
 monitor:['monitor-register','monitor-confirm','monitor-vote','withdraw',
          'seal-epoch','settle-epoch','close-evidence','release-committee']
};
const ownedRoles=""" + json.dumps([r for r in conf["roles"] if r in ("consumer", "provider", "monitor")]) + """;
for(const role of ownedRoles.filter(r=>actionRoles[r])) {
 const option=document.createElement('option');option.value=role;option.textContent=role;
 roleSelect.appendChild(option);
}
function updateActions(){
 actSelect.replaceChildren();
 for(const action of actionRoles[roleSelect.value]||[]) {
  const opt=document.createElement('option');opt.value=action;opt.textContent=action;
  actSelect.appendChild(opt);
 }
}
roleSelect.addEventListener('change',updateActions);updateActions();
document.getElementById('txpreview').addEventListener('click',async()=>{
 const token=document.getElementById('token').value;
 document.getElementById('token').value='';
 try {
  const params=JSON.parse(document.getElementById('txparams').value);
  const r=await fetch('/v1/transaction-plans',{method:'POST',
   headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},
   body:JSON.stringify({role:roleSelect.value,action:actSelect.value,params})});
  const data=await r.json();
  txOutput.textContent=r.ok?JSON.stringify(data,null,2):(data.error||'Preview refused');
 }catch(_){txOutput.textContent='Invalid JSON or request error';}
});
refresh().catch(()=>{out.textContent='Node status unavailable';});
</script></body></html>""")


def transaction_preview(conf, message):
    if not conf.get("chain"):
        raise ValueError("node marketplace addresses not configured")
    if type(message) is not dict or set(message) != {"role", "action", "params"}:
        raise ValueError("expected role/action/params only")
    role = message["role"]
    if type(role) is not str or role not in conf["roles"] or role not in SETTINGS:
        raise ValueError("this node does not own the requested role")
    action = message["action"]
    if type(action) is not str:
        raise ValueError("transaction action must be a string")
    # No signing keys or raw RPC access are available in this endpoint.
    root = Path(__file__).resolve().parents[2] / "tools"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from sse_node_marketplace import make_plan, NodeTxError
    try:
        plan = make_plan(action, role, params=message["params"], **conf["chain"])
    except (NodeTxError, ValueError, TypeError) as exc:
        raise ValueError("invalid role transaction arguments") from exc
    return {**plan.public(), "previewOnly": True, "canBroadcastHere": False,
            "roleOwnerApprovalRequired": True}


def make_server(conf):
    guard = threading.RLock()
    class Handler(BaseHTTPRequestHandler):
        def _local_owner(self):
            token = conf.get("admin_token", "")
            auth = self.headers.get("Authorization", "")
            origin = self.headers.get("Origin")
            return (bool(token) and
                    secrets.compare_digest(auth, "Bearer " + token) and
                    (not origin or origin == "http://127.0.0.1:" + str(conf["port"])))

        def reject_unauthorized_owner(self):
            """Send a stable 403 after draining only a small declared request body.

            An early rejection with unread PUT/POST bytes may make Windows TCP
            reset the connection before the client receives the 403. Keep the
            input size bounded and use a short deadline: untrusted callers
            must never be able to stall the node-local UI.
            """
            declared = self.headers.get("Content-Length")
            if declared is not None:
                try:
                    if len(declared) <= 8:
                        size = int(declared)
                        if 0 < size <= 4096:
                            self.connection.settimeout(1.0)
                            self.rfile.read(size)
                except (ValueError, OSError, OverflowError):
                    pass
            self.close_connection = True
            return self.send_payload(
                403, {"error": "local owner authorization required"})

        def send_payload(self, code, body, content_type="application/json; charset=utf-8"):
            raw = (json.dumps(body, sort_keys=True).encode("utf-8")
                   if not isinstance(body, str) else body.encode("utf-8"))
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path == "/healthz":
                body = {"ok": True, "component": "role-agent", "chain_verified": False}
            elif self.path == "/v1/status":
                body = {"node_id": conf["node_id"], "roles": conf["roles"],
                        "revision": conf["revision"], "software_running": True,
                        "blockchain_synced": None, "monitor_eligible": None,
                        "provider_capacity_verified": None,
                        "checked_at": datetime.now(timezone.utc).isoformat()}
            elif self.path == "/v1/monitor-work":
                if "monitor" not in conf["roles"]:
                    return self.send_payload(404, {"error": "not found"})
                if not self._local_owner():
                    return self.reject_unauthorized_owner()
                if not conf.get("monitor_snapshot"):
                    return self.send_payload(503, {"error": "monitor review snapshot not configured"})
                try:
                    root = Path(__file__).resolve().parents[2] / "tools"
                    if str(root) not in sys.path:
                        sys.path.insert(0, str(root))
                    from sse_monitor_public_snapshot import read_snapshot
                    snapshot=read_snapshot(
                        conf["monitor_snapshot"],node_id=conf["node_id"],
                        monitor_address=conf["monitor_wallet"])
                except (OSError, ValueError, TypeError):
                    return self.send_payload(503, {
                        "error": "monitor work review unavailable or stale; refresh on monitor node"})
                return self.send_payload(200, {**snapshot, "displayOnly": True})
            elif self.path == "/v1/preferences":
                try:
                    with guard:
                        p = read_preferences(conf)
                except (OSError, ValueError, TypeError):
                    return self.send_payload(503, {"error": "settings unavailable"})
                body = {"preferences": p,
                        "editable": bool(conf.get("admin_token") and conf.get("settings_file")),
                        "activeOnChain": False, "activeInRuntime": False}
            elif self.path in ("/", "/ui"):
                return self.send_payload(200, page(conf), "text/html; charset=utf-8")
            else:
                return self.send_payload(404, {"error": "not found"})
            self.send_payload(200, body)

        def do_POST(self):
            if self.path != "/v1/transaction-plans":
                return self.send_payload(404, {"error": "not found"})
            if not self._local_owner():
                return self.reject_unauthorized_owner()
            if not conf.get("chain"):
                return self.send_payload(503, {"error": "node marketplace not configured"})
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                return self.send_payload(415, {"error": "JSON required"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 4096:
                    return self.send_payload(413, {"error": "bounded request required"})
                request = json.loads(self.rfile.read(length).decode("utf-8"))
                plan = transaction_preview(conf, request)
            except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
                return self.send_payload(422, {"error": "invalid node-owned transaction plan"})
            return self.send_payload(200, plan)

        def do_PUT(self):
            if self.path != "/v1/preferences":
                return self.send_payload(404, {"error": "not found"})
            if not self._local_owner():
                return self.reject_unauthorized_owner()
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                return self.send_payload(415, {"error": "JSON required"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 4096:
                    return self.send_payload(413, {"error": "bounded request required"})
                settings = validate_preferences(conf["roles"],
                           json.loads(self.rfile.read(length).decode("utf-8")))
                with guard:
                    write_preferences(conf, settings)
            except (OSError, ValueError, TypeError, UnicodeError, json.JSONDecodeError):
                return self.send_payload(422, {"error": "invalid role-specific settings"})
            return self.send_payload(200, {"saved": True, "activeOnChain": False,
                                            "activeInRuntime": False, "preferences": settings})

        def log_message(self, fmt, *args):
            return  # avoid accidental sensitive header/body logs
    return ThreadingHTTPServer((conf["host"], conf["port"]), Handler)


def main():
    parser = argparse.ArgumentParser(description="Local Ubuntu SSE node console (no transactions)")
    parser.parse_args()
    conf = config()
    print("SSE local console http://127.0.0.1:" + str(conf["port"]) + "/ui", flush=True)
    make_server(conf).serve_forever()


if __name__ == "__main__":
    main()
