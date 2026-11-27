#!/usr/bin/env python3
"""SSE one-entry-point setup orchestrator (chain client + V4 application roles).

SOURCE-ONLY (2026-11-27): written in a source-code-only session; never executed.

It does NOT reimplement any installer. It selects, orders and (only with
--apply and an explicit per-step "yes") invokes the existing, separately
reviewed installers, each of which keeps its own guards (exact commit, clean
tree, owner terminal, private directories, pinned images):

  full_node / observer  scripts/sse_install.py (R147 source acquisition + role state)
                        scripts/sse_install_node_cli.sh (owner CLI)
  validator             scripts/r358_install_native_validator.sh (needs an existing
                        encrypted key + canonical deposit; manual funding stays manual)
                        scripts/sse_install_native_reward_timer.py (R424 collector)
  consumer / provider / monitor / keeper
                        scripts/sse_v4_app_install.py (refuses until a V4 manifest exists)

Default is --plan: print the ordered steps with prerequisites and stop. It never
creates wallets, never funds anything, never deploys contracts and never runs
with root (the delegated installers ask for sudo themselves where they need it).
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHAIN_ROLES = ("full_node", "observer", "validator")
APP_ROLES = ("consumer", "provider", "monitor", "keeper")
ROLES = CHAIN_ROLES + APP_ROLES
SHA = re.compile(r"^[0-9a-f]{40}$")


class Refused(ValueError):
    pass


def plan(roles, commit, publish_console=False):
    """Ordered, de-duplicated steps. Pure function (unit-tested, not executed)."""
    roles = list(dict.fromkeys(roles))
    if not roles or any(r not in ROLES for r in roles):
        raise Refused("roles must be a non-empty subset of " + ",".join(ROLES))
    if not SHA.fullmatch(commit or ""):
        raise Refused("exact 40-hex --commit required (the reviewed source revision)")
    steps = []
    chain = [r for r in roles if r in CHAIN_ROLES]
    # Every application role needs a local, synced node for finalized reads; validators need a full node.
    needs_node = bool(chain) or any(r in APP_ROLES for r in roles)
    node_roles = sorted(set(chain) | ({"full_node"} if needs_node and not chain else set()))
    if needs_node:
        steps.append({"id": "source-and-role-state", "argv": [sys.executable, "scripts/sse_install.py", "--commit", commit,
                      "--roles", ",".join(r for r in node_roles if r != "validator") or "full_node"],
                      "prerequisites": ["Ubuntu 24.04", "clean checkout at the commit"],
                      "note": "R147: source acquisition + one-time role selection; client launch stays gated."})
        steps.append({"id": "owner-cli", "argv": ["bash", "scripts/sse_install_node_cli.sh", commit],
                      "prerequisites": ["non-root user"], "note": "owner-local CLI snapshot; no services"})
    if "validator" in roles:
        steps.append({"id": "validator", "argv": ["bash", "scripts/r358_install_native_validator.sh", commit],
                      "prerequisites": ["running local native full node (one beacon)",
                                        "encrypted validator keystore in ~/.local/share/sse31340-validator (0600)",
                                        "canonical deposit already made by the owner (manual, never automated)"],
                      "note": "R358 (historically live-tested); interactive owner terminal required"})
        steps.append({"id": "reward-timer", "argv": [sys.executable, "scripts/sse_install_native_reward_timer.py",
                      "--commit", commit], "prerequisites": ["local beacon API on 127.0.0.1"],
                      "note": "R424 read-only reward collector; feeds the console rewards view"})
    app = [r for r in roles if r in APP_ROLES]
    if app:
        argv = [sys.executable, "scripts/sse_v4_app_install.py", "--roles", ",".join(app)]
        if publish_console:
            argv.append("--publish-readonly-console")
        steps.append({"id": "v4-app-roles", "argv": argv,
                      "prerequisites": ["release/chain31340-v4-manifest.json for a DEPLOYED V4 (refuses otherwise)",
                                        "synced local node RPC"],
                      "note": "wallet import/create, spending caps, hardened user services"})
        steps.append({"id": "linger", "argv": ["loginctl", "enable-linger", os.environ.get("USER", "<user>")],
                      "prerequisites": ["sudo may be required"], "note": "services survive logout/reboot"})
    return steps


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--roles", required=True, help="comma-separated: " + ",".join(ROLES))
    p.add_argument("--commit", required=True)
    p.add_argument("--publish-readonly-console", action="store_true")
    p.add_argument("--apply", action="store_true", help="run each step after an explicit yes (default: plan only)")
    a = p.parse_args(argv)
    try:
        if os.geteuid() == 0:
            raise Refused("run as the owner user, not root")
        steps = plan(a.roles.split(","), a.commit, a.publish_readonly_console)
    except Refused as exc:
        print("SSE_SETUP_REFUSED: " + str(exc), file=sys.stderr)
        return 2
    if not a.apply:
        print(json.dumps({"schema": "SSE_SETUP_PLAN_V1", "steps": steps}, indent=2))
        return 0
    for s in steps:
        print("\n== " + s["id"] + ": " + s["note"] + "\n   prerequisites: " + "; ".join(s["prerequisites"]) +
              "\n   command: " + " ".join(s["argv"]))
        if input("Run this step? type yes: ").strip() != "yes":
            print("Stopped before " + s["id"] + "; later steps not run.")
            return 3
        rc = subprocess.call(s["argv"], cwd=REPO)  # noqa: S603 - fixed argv lists, no shell
        if rc != 0:
            print("Step " + s["id"] + " refused/failed with exit " + str(rc) + "; stopping (nothing retried).")
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
