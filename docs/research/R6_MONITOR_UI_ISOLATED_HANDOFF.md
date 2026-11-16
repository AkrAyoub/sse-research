# R6 — Isolated Ubuntu monitor-to-node-UI display handoff

**Status: source-only, new tests NOT YET EXECUTED by developer; no Ubuntu systems, users, services, keys, contracts or CI changed.** Base commit `1d7b260` was operator-validated: 679 discovered Python tests, 672 passed, seven skipped (one Windows symlink privilege case), zero failures; local real-Anvil selected-monitor integration also passed (23.909 s).

## Why this slice exists

The monitor service (`ssemonitor`) must own an owner-only SQLite event journal and any evidence/signing materials. The node-local browser console (`sseagent`) must not obtain access to the journal or signer keys. The already-tested display bridge writes a **sanitized, unsigned, public-status-only JSON** snapshot, but previously wrote it 0600 so a second Linux service account could not read it.

This change introduces an explicitly opt-in **group-read-only snapshot**, and a nonexecuting systemd installation **plan**. No role or EVM signing authority changes.

### Permission model — proposed, NOT deployed

| Asset | Owner | Group | Mode | Readers |
|---|---|---|---|---|
| `/var/lib/sse-monitor/` | `ssemonitor` | `ssemonitor` | `0700` | Monitor only |
| Monitor event SQLite + keys | `ssemonitor` | `ssemonitor` | `0600` | Monitor only |
| `/run/sse-monitor-display/` | `ssemonitor` | `ssemonitor-display` | `0750` | Monitor, display group can traverse |
| `/run/sse-monitor-display/tasks.json` | `ssemonitor` | `ssemonitor-display` | `0640` | Monitor, display group read-only |
| Node UI process | `sseagent` | `sseagent` + supplementary `ssemonitor-display` | N/A | Sanitized snapshot only |

**Important:** no group-write bits on the shared directory or task file. No private monitor journal, evidence archive or wallet is shared. The local node UI remains loopback-bound and requires its existing owner token for `GET /v1/monitor-work`. Snapshot records contain only `leaseId`, `sequenceId`, event kind and reviewed status, not arbitrary chain calldata, raw probe data or secrets. They cannot authorize a confirmation, vote or settlement.

## Implementation

- `tools/sse_monitor_public_snapshot.py`: `write_snapshot(...,shared_group_read=True)` is **explicit opt-in**; without it, all exports retain the previous **0600** mode. On POSIX it requires an existing ordinary export directory owned by the effective UID and expected effective GID, owner `rwx`, group `r-x`, no group-write or world access. A staged public-only file must inherit the expected GID and is then made **0640**, atomically replaced. On Windows, the shared mode fails closed; there is no synthetic POSIX permission claim.
- `services/monitor-agent/monitor_discovery.py`: the additional `--shared-display-group-read` flag is refused unless explicitly combined with `--review --export-review-snapshot <absolute path>`. Reviewing still does **read-only** RPC and SQLite journal access; no signer is available.
- `tools/sse_monitor_ui_handoff_plan.py`: renders, but **never installs**, three items: `sse-monitor-review-export.service` (one-shot read-only review with `User=ssemonitor`, `Group=ssemonitor-display`, private journal access, `RuntimeDirectoryMode=0750`, `RuntimeDirectoryPreserve=yes`), `sse-monitor-review-export.timer` (operator-reviewable default 45-second refresh; 15–90 sec bound), and a node role-agent service drop-in with `SupplementaryGroups=ssemonitor-display`, public wallet address and snapshot path. The official bootstrap currently names the console unit `sse-vm-role-agent.service`.
- `tests/test_sse_monitor_ui_handoff.py`: render-only plan tests and real POSIX file mode/owner checks. POSIX-specific checks will be **skipped on Windows** and require independent Ubuntu acceptance.

### Render-only plan example (Ubuntu paths; no writes or system changes)

From a local checkout, with an **existing nonsecret `sse-node-roles-v1` JSON manifest** containing this node's monitor public wallet:

```bash
python tools/sse_monitor_ui_handoff_plan.py \
  --roles-file /etc/sse/node-roles.json \
  --python /opt/sse/runtime/<APPROVED_REVISION>/bin/python \
  --checkout /opt/sse/releases/<APPROVED_REVISION> \
  --manifest /etc/sse/node-roles.json \
  --journal /var/lib/sse-monitor/events.sqlite \
  --rpc-url http://127.0.0.1:8545 \
  --settlement 0x<DEPLOYED_SETTLEMENT> \
  --chain-id 31337 --start-block <APPROVED_DEPLOYMENT_BLOCK>
```

The output contains **text of units and a drop-in, not executable shell commands**. It does not create `ssemonitor` or `ssemonitor-display`, install units, modify files or activate a timer. **Do not copy the placeholders into live units.**

### Operational flow AFTER approved deployment (future acceptance)

1. Operator provisions distinct `ssemonitor` and `sseagent` accounts and an `ssemonitor-display` group that only grants the UI read access to the **public display directory**. Verify private journal and wallet directories retain owner-only permissions.
2. Read-only `sse-monitor-discovery.service` scans deployed contract logs and maintains the monitor-owned event journal. It requires an explicit operator-approved start block, settlement, trusted RPC and chain ID.
3. The approved timer triggers `sse-monitor-review-export.service` to use the **existing read-only action queue** to recheck event/block provenance and current lease state, then atomically exports a nonsecret snapshot into `/run/sse-monitor-display/tasks.json`.
4. The node-local `sse-vm-role-agent.service` runs separately as `sseagent`, with supplementary membership in the display group. It can only read the public snapshot through `GET /v1/monitor-work` after the owner passes the local token. It never invokes the monitor signing process.
5. If the chain is unavailable, a reorganization is detected or the timer stops, no replacement snapshot is created; once the previous snapshot ages beyond 120 seconds the UI returns **503 stale/unavailable**, not a fake current success.

**Operational cautions:** systemd's `RuntimeDirectory=` creates runtime directories under `/run/` and their lifetime follows the service. `RuntimeDirectoryPreserve=yes` retains the directory after a one-shot service exits; it is ephemeral across reboot. Service `Group=` controls directory group ownership. These behaviors must be validated on the selected Ubuntu/systemd version before deployment. See [systemd.exec(5)](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html).

The proposed review service runs `Group=ssemonitor-display` while maintaining `User=ssemonitor`. Its private journal access depends on the same Linux **UID** and the monitor-owned `0700` directory; adding the UI user to `ssemonitor` itself is forbidden. The role-agent drop-in grants only the display group. Separate Linux accounts are important even on one multi-role VM.

## Developer validation (Windows Git Bash)

```bash
git status --short
git fetch origin research/r6-monitor-ui-isolated-handoff-no-ci
git switch --detach origin/research/r6-monitor-ui-isolated-handoff-no-ci
git rev-parse --short HEAD

python -m unittest discover -s tests -p 'test_sse_monitor_ui_handoff.py' -v
python -m unittest discover -s tests -p 'test_sse_monitor_public_snapshot.py' -v
python -m unittest discover -s tests -p 'test_sse_node_console.py' -v
python -m unittest discover -s tests -q
```

Optional locally funded real Anvil selected-monitor workflow (no contracts or CI modified):

```bash
SSE_RUN_ANVIL_INTEGRATION=1 python -m unittest discover -s tests -p 'test_sse_direct_delivery_anvil.py' -v
```

Because the new branch adds **nine** Python tests, the unverified Windows discovery target is **688 tests, nine skipped** (seven previous + two POSIX-only). Linux should execute those two POSIX-specific file ownership/mode checks, although other environment-dependent skips remain possible.

## Required Ubuntu acceptance, before any actual installation

- Run `systemd-analyze verify` against reviewed unit text; confirm the installed systemd honors `RuntimeDirectoryMode=0750` and `RuntimeDirectoryPreserve=yes`.
- Confirm **actual effective UID/GID**, staged-file ownership/mode, and that `sseagent` can read the public snapshot but **cannot** open the event journal, evidence archive or any private key.
- Confirm a different unprivileged local user cannot read the snapshot or node token; confirm changing the node/wallet in the snapshot causes a 503.
- Restart/disconnect/reboot the monitor process, exercise timer-triggered review, and verify failed/stopped reviews cause the UI to refuse stale data after 120 seconds.
- Validate no group or permission widening occurs when a node has both provider and monitor roles.
- Keep all financial and signed actions explicit; new systemd units have no `--execute`, `--capture`, `--monitor-vote`, Docker or private signer inputs.
- Only then integrate with a controlled, signed R6 release and actual independent Ubuntu VM / Tailscale experiments; production or testnet transactions remain a separate explicit approval gate.

No changes to the project's official `PHASES_TRACKER.csv` are justified by this source-only provisioning plan.
