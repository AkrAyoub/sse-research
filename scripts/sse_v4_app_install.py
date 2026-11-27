#!/usr/bin/env python3
"""SSE V4 application-role installer (consumer/provider/monitor/keeper + console).

SOURCE-ONLY (2026-11-27): written, statically reviewed, NEVER executed.
Owner-run validation: handoff/planning/DEFERRED_RUNTIME_VALIDATION.md DRV-INST-V4.

Scope: the application layer on a host that already has either a synced local
EL node (validator/full-node installers: R151/R358) or a verified RPC endpoint.
It does NOT install clients, does NOT create validator keys, and never moves funds.

One command, idempotent:
  python3 scripts/sse_v4_app_install.py --roles consumer,monitor [--plan]
Interactions are limited to legitimate owner choices: roles, wallet keystore
(import path or create), spending caps, and whether to publish the read-only
console. No IPs, contract addresses, VM names or ports are typed by the user:
contracts come from the verified release manifest; RPC comes from the local
node or the manifest's replaceable rpcHints, each verified by chain id+genesis.
"""
import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

ROLES = ("consumer", "provider", "monitor", "keeper")
HOME = Path.home()
STATE = HOME / ".local/share/sse-v4"
CONFIG = HOME / ".config/sse-v4"
UNITS = HOME / ".config/systemd/user"
MANIFEST = REPO / "release/chain31340-v4-manifest.json"
LOCAL_RPCS = ("http://127.0.0.1:28545", "http://127.0.0.1:18545", "http://127.0.0.1:8545")
UNIT_TEMPLATES = REPO / "systemd"


class Refused(SystemExit):
    pass


def preflight():
    problems = []
    if sys.version_info < (3, 12):
        problems.append("Python >= 3.12 required (Ubuntu 24.04 default)")
    if os.geteuid() == 0:
        problems.append("run as the unprivileged owner account, not root")
    if not shutil.which("systemctl"):
        problems.append("systemd user services required")
    try:
        import eth_abi, eth_account  # noqa: F401
    except ImportError:
        problems.append("pinned Python deps missing: install requirements.txt into the SSE venv first")
    if not MANIFEST.is_file():
        problems.append("V4 release manifest not present: V4 is not deployed yet (expected until owner deployment)")
    return problems


def pick_rpc(manifest, ask_factory):
    import sse_v4_state as st
    candidates = list(LOCAL_RPCS) + [u for u in manifest.get("rpcHints", []) if isinstance(u, str)]
    for url in candidates:
        try:
            ask = ask_factory(url)
            st.verify_deployment(ask, manifest)
            return url
        except Exception:  # noqa: BLE001 - try next replaceable hint
            continue
    raise Refused("no local node or verified RPC hint matches chain31340 genesis and the V4 deployment")


def policy_for(roles, wallet, keystore, caps, extra):
    p = {"schema": "SSE_V4_AGENT_POLICY_V1", "roles": roles, "wallet": wallet.lower(), "keystore": str(keystore),
         "spending": caps, "selfKeep": True,  # advance only own leases (D-09); owner may set false
         "consumer": {"epochRequests": {}},
         "provider": {"approvedOfferHashes": [], "approvedTermsHashes": [], "leaseTerms": {},
                      "profiles": {}, "offers": {}, "workers": {},
                      "capacity": {"cpuCores": 0, "memoryMiB": 0, "maxConcurrentLeases": 0}},
         "monitor": {"autoConfirm": False, "allowFailureVotes": False, "providerEndpoints": {}, "services": {},
                     "approvedPolicies": {}}}
    for k, v in extra.items():
        p[k].update(v)
    return p


def ask_caps(input_fn=input):
    print("Spending authorization (gas only; automatic actions never send value).")
    def num(prompt, default):
        raw = input_fn(f"{prompt} [{default}]: ").strip() or str(default)
        if not raw.isdigit() or int(raw) <= 0:
            raise Refused("positive integer required")
        return int(raw)
    return {"maxFeePerGasWei": num("Max fee per gas (wei)", 50 * 10**9),
            "maxPriorityFeePerGasWei": num("Max priority fee per gas (wei)", 2 * 10**9),
            "maxGasPerTx": num("Max gas per transaction", 3_000_000),
            "dailyGasWeiBudget": num("Max total gas spend per 24h (wei)", 10**17)}


def wallet(keystore_dir, input_fn=input):
    keystore_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    existing = sorted(keystore_dir.glob("UTC--*"))
    if existing:
        doc = json.loads(existing[0].read_text())
        return "0x" + doc["address"].lower().removeprefix("0x"), existing[0]
    choice = input_fn("No V4 wallet found. [i]mport encrypted keystore path or [c]reate new? ").strip().lower()
    if choice == "i":
        src = Path(input_fn("Absolute path to encrypted UTC-V3 keystore: ").strip())
        from sse_pos_r237_v2_approved_local_eip712_sign import safe_keystore
        doc = safe_keystore(src)
        dest = keystore_dir / src.name
        dest.write_text(json.dumps(doc))
        dest.chmod(0o600)
        return "0x" + doc["address"].lower().removeprefix("0x"), dest
    if choice == "c":
        from eth_account import Account
        pw = getpass.getpass("New wallet passphrase: ")
        if len(pw) < 12 or pw != getpass.getpass("Repeat: "):
            raise Refused("passphrase mismatch or shorter than 12 characters")
        acct = Account.create()
        doc = Account.encrypt(acct.key, pw)
        dest = keystore_dir / ("UTC--sse-v4--" + acct.address.lower())
        fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(doc, fh)
        print("Created wallet", acct.address, "- fund it with TEST ETH (faucet or donor); nothing is funded automatically.")
        return acct.address.lower(), dest
    raise Refused("no wallet selected")


def render_unit(name, **values):
    text = (UNIT_TEMPLATES / name).read_text()
    for k, v in values.items():
        text = text.replace("@" + k + "@", str(v))
    return text


def plan_actions(roles, publish, rpc):
    acts = [("dir", STATE), ("dir", CONFIG), ("policy", CONFIG / "policy.json"),
            ("unit", "sse-v4-agent.service"), ("unit", "sse-v4-console.service")]
    if "provider" in roles:
        acts.append(("unit", "sse-v4-provider-outputs.service"))
    if publish:
        acts.append(("unit", "sse-v4-console-public.service"))
    acts.append(("enable", [a[1] for a in acts if a[0] == "unit"]))
    return {"roles": roles, "rpc": rpc, "actions": [(k, str(v)) for k, v in acts],
            "note": "Re-running is idempotent: policy and wallet are never overwritten; units are re-rendered."}


def install(roles, publish, rpc, python, input_fn=input):
    for d in (STATE, CONFIG, UNITS):
        d.mkdir(mode=0o700, parents=True, exist_ok=True)
    pol_path = CONFIG / "policy.json"
    if pol_path.exists():
        existing = json.loads(pol_path.read_text())
        if set(existing.get("roles", [])) != set(roles):
            raise Refused("existing policy roles differ; review and update the policy explicitly before reinstall")
        print("Keeping existing policy", pol_path)
    else:
        addr, ks = wallet(CONFIG / "keystore", input_fn)
        pol = policy_for(roles, addr, ks, ask_caps(input_fn), {})
        fd = os.open(pol_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(pol, fh, indent=2)
    common = dict(PYTHON=python, REPO=REPO, MANIFEST=MANIFEST, RPC=rpc, STATE=STATE, POLICY=pol_path,
                  REWARDS=str(Path.home() / ".local/share/sse-native-rewards"),  # R424 collector output
                  BEACON="http://127.0.0.1:25052")  # local BN default (R358 layout); unreachable => "unavailable"
    units = {"sse-v4-agent.service": render_unit("sse-v4-agent.service.in", **common),
             "sse-v4-console.service": render_unit("sse-v4-console.service.in", MODE="local", PORT=8790, **common)}
    if "provider" in roles:
        units["sse-v4-provider-outputs.service"] = render_unit("sse-v4-provider-outputs.service.in", **common)
        print("Provider: point the existing TLS front (R304) at 127.0.0.1:8881 and publish its URL; endpointHash = keccak(URL).")
    if publish:
        units["sse-v4-console-public.service"] = render_unit("sse-v4-console.service.in", MODE="public", PORT=8791, **common)
    for name, text in units.items():
        (UNITS / name).write_text(text)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    for name in units:
        subprocess.run(["systemctl", "--user", "enable", "--now", name], check=True)
    print("Persistence across logout requires: loginctl enable-linger $USER (owner decision, needs sudo).")
    print("Public URL: run scripts/sse_publish_application_dashboard.sh against port 8791 (read-only instance).")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--roles", help="comma-separated subset of " + ",".join(ROLES))
    p.add_argument("--publish-readonly-console", action="store_true")
    p.add_argument("--plan", action="store_true", help="print the plan, change nothing")
    a = p.parse_args()
    raw = a.roles or input("Roles (" + ",".join(ROLES) + "): ")
    roles = [r.strip() for r in raw.split(",") if r.strip()]
    if not roles or len(set(roles)) != len(roles) or set(roles) - set(ROLES):
        raise Refused("invalid roles")
    problems = preflight()
    if problems:
        print(json.dumps({"preflight": "FAILED", "problems": problems}, indent=2))
        raise Refused(2)
    import sse_v4_state as st
    from sse_chain_read import LocalRPC
    manifest = st.load_manifest(MANIFEST)
    # LocalRPC only permits 127.0.0.1 endpoints; remote rpcHints need a verified local
    # TLS adapter (R361) that exposes them on loopback.
    rpc = pick_rpc(manifest, lambda u: LocalRPC(u).request)
    if a.plan:
        print(json.dumps(plan_actions(roles, a.publish_readonly_console, rpc), indent=2))
        return
    install(roles, a.publish_readonly_console, rpc, sys.executable)


if __name__ == "__main__":
    main()
