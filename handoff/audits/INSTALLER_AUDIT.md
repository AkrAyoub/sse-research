# Installer audit — 2026-11-27 (inventory level)

- scripts/sse_install.py plus role-specific shell installers (R147 full node refuses other roles, R336 monitor partial,
  R358 validator live-tested with manual funding/key/security steps, R361 RPC adapter, R394/R398 dashboard).
- VM-specific assumptions remain in many r-numbered scripts (vm4706/vm4707/vm4709/vm4714 names, fixed overlay endpoints).
- No unified one-command multi-role installer; no V4 contract discovery (release manifest has no V4 addresses — correct,
  as V4 is undeployed). Nothing was run. Unification is Not implemented (MASTER_TASK_CHECKLIST D-*).

## Pass 2 update
scripts/sse_v4_app_install.py (e8c1df1) installs the V4 application roles as hardened user services from a verified manifest,
verifying RPC by chain id + genesis + module wiring, with role/wallet/spending caps as the only prompts. It refuses to run
until a real V4 manifest exists. Chain client installation remains in the existing R151/R358 installers (not unified).
`loginctl enable-linger` needs sudo and is left as an explicit owner step.

## Pass 4 update — one entry point (design + source)
scripts/sse_setup.py is a plan-first orchestrator: `--roles ... --commit SHA` prints the ordered steps (R147 source/role
state → owner CLI → R358 validator + R424 reward timer → V4 application roles → linger) with prerequisites; `--apply` runs
each delegated installer only after a typed "yes" and stops at the first refusal. It reimplements nothing, so every existing
guard (exact commit, clean tree, owner terminal, pinned images, private dirs) still applies; it never creates or funds
wallets, deploys, or runs as root. Status: Newly implemented, statically reviewed, plan tests written (tests/test_sse_setup.py),
not executed. Validation: DRV-SETUP-01. Remaining gap: the delegated installers are still separate programs with different
output formats; a fresh-host end-to-end run is owner-only.
