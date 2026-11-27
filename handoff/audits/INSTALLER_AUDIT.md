# Installer audit — 2026-11-27 (inventory level)

- scripts/sse_install.py plus role-specific shell installers (R147 full node refuses other roles, R336 monitor partial,
  R358 validator live-tested with manual funding/key/security steps, R361 RPC adapter, R394/R398 dashboard).
- VM-specific assumptions remain in many r-numbered scripts (vm4706/vm4707/vm4709/vm4714 names, fixed overlay endpoints).
- No unified one-command multi-role installer; no V4 contract discovery (release manifest has no V4 addresses — correct,
  as V4 is undeployed). Nothing was run. Unification is Not implemented (MASTER_TASK_CHECKLIST D-*).
