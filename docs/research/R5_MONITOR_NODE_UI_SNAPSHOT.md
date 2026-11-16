# R5 — Monitor work in the owner-local node interface

**Status: RESEARCH CODE COMMITTED, NEW TESTS AND NEW ANVIL ASSERTIONS NOT YET VALIDATED.** Base `869fa09` was validated on Windows: 668 Python tests discovered, 662 pass, six skips, zero errors, plus an opt-in real Anvil integration passed (24.012 s). No smart contracts, live VMs, installed units, public repository releases or CI are changed by this slice.

## Problem and trust boundary

The R5 monitor watcher can find real `CommitteeAssigned` / `EpochAdmitted` events and save them to its **monitor-owned SQLite event journal**. The read-only action queue then checks *fresh* block-hash-pinned lease state to mark an old task `NO_LONGER_ACTIONABLE`, `REVIEW_CONFIRMATION`, or `REVIEW_EVIDENCE_CAPTURE`. Previously, the node-local browser console could not present those tasks without importing the monitor's EVM SDK or opening its owner-only SQLite journal.

This slice makes **one-way, nonsecret status sharing**:

```text
 ssemonitor (read-only RPC, no signer)
  event SQLite -> --review current chain -> validated public snapshot JSON
                                                  |
                                                  | operator-approved read-only file access
                                                  v
 sseagent (stdlib-only local UI, no signer or RPC)
     GET /v1/monitor-work [local admin token]
     /ui -> "View recent monitor tasks" -> text-only display
```

The R4 monitor evidence archive and actual signing process stay **separate**. The independent network-wide dashboard is not given this private management endpoint. This slice does not register bonds, confirm committee seats, authorize transactions, spawn Docker, auto-capture provider data or submit settlement votes.

## Code changed

- `tools/sse_monitor_public_snapshot.py`: stdlib-only bounded JSON snapshot schema `sse-monitor-work-display-v1`. It deliberately **drops all proposed execution parameters**, wallet private data and raw chain evidence. All records display only event kind, lease ID, epoch/assignment sequence and reviewed status. Only a result asserting `readOnly=true`, `signerLoaded=false`, `transactionsSent=false`, `autoCapturePerformed=false` and `finalityVerified=false` may be published. Atomic write with small maximum size; refuse symlinks, missing parent, or world-writable parent on POSIX. Reader requires exact node ID + public monitor wallet, strict schema, and a snapshot less than 120 seconds old (allowing 15 seconds positive clock skew).
- `services/monitor-agent/monitor_discovery.py`: explicit `--review --export-review-snapshot <absolute path>` runs the same fresh, read-only RPC verification before publishing. `--scan` and `--watch` unchanged; no export on default dry-run or non-review mode.
- `services/role-agent/agent.py`: optional `SSE_MONITOR_WORK_SNAPSHOT_FILE` and `SSE_MONITOR_WALLET` public configuration. Enables `GET /v1/monitor-work` **only** when the local VM has a monitor role *and* an owner token; requires that token for the request. Stale, invalid or missing snapshots return 503 without leaking tasks. The browser shows read-only text data with `textContent` (no HTML from the snapshot, no signer, no RPC, no transaction button). The server remains bound to `127.0.0.1`.
- `tests/test_sse_monitor_public_snapshot.py`: offline atomic export, stale/tampered/missing file, wrong role/wallet, authorized/unauthorized localhost HTTP and negative CLI coverage.
- `tests/test_sse_direct_delivery_anvil.py`: optional integration now exports the selected monitor's live-read action queue as a public display snapshot, reloads it without signer and verifies no approval/vote claims.

## Running on one developer host (not a deployment)

The reader requires a public node identity, *not an Ethereum private key*. An **illustrative** operator-owned manifest (not an actual wallet):

```json
{"schema":"sse-node-roles-v1","nodeId":"vm-a",
 "roles":["provider","monitor","observer"],
 "wallets":{"provider":"0x1111111111111111111111111111111111111111",
            "monitor":"0x2222222222222222222222222222222222222222"}}
```

1. Run the already-tested read-only monitor discovery CLI `--scan` on an approved local RPC with the correct node manifest, chain ID, contract and deployment start block. This creates/advances the **monitor-owned** private SQLite journal. It sends no Ethereum transactions.
2. Run the **separate** explicit review/export pass, using matching arguments:

```bash
python services/monitor-agent/monitor_discovery.py \
  --node-roles-file /opt/sse/config/node-roles.json \
  --journal /var/lib/sse-monitor/events.sqlite \
  --rpc-url http://127.0.0.1:8545 \
  --settlement 0x<DEPLOYED_SETTLEMENT_ADDRESS> \
  --chain-id 31337 --start-block <DEPLOYMENT_BLOCK> \
  --review --export-review-snapshot /run/sse-monitor-display/tasks.json
```

The last path's parent must **already exist**, be owned by the monitor exporter, not be world-writable, and its permissions must be approved. On Windows, use an actual absolute Windows path instead of the illustrative Ubuntu paths.

3. Configure the **local** `sseagent` process with its existing owner token and settings path, `SSE_ROLES` containing `monitor`, the same `SSE_NODE_ID` and `SSE_MONITOR_WALLET` public address, plus `SSE_MONITOR_WORK_SNAPSHOT_FILE=/run/sse-monitor-display/tasks.json`. The node console's `/ui` now contains a "View recent monitor tasks" button that uses the existing local owner token. It is not a "Confirm" or "Vote" button.

**Important multi-user Ubuntu note:** snapshot writes default to **mode 0600**, deliberately. The `ssemonitor` service account cannot automatically share that file with a separately isolated `sseagent` account. This path is a research protocol boundary, **not yet an installed cross-account IPC integration**. Before real activation, provision an explicitly reviewed read-only file ACL / nonsecret snapshot forwarder, preserving both daemons' separate user identities and preventing the UI from writing the review. Simply making the monitor's private journal or signing key readable to the console is forbidden. Do not change permissions on monitor private SQLite or wallet files.

No code automatically refreshes the snapshot: an operator must re-run review/export, or a future isolated systemd timer may perform only this reviewed read-only RPC operation. A stale snapshot is explicitly refused. Time freshness is UI metadata **not an SLA clock certification**.

## Validate code (Git Bash / Windows)

```bash
git status --short
git fetch origin research/r5-node-monitor-work-ui-snapshot-no-ci
git switch --detach origin/research/r5-node-monitor-work-ui-snapshot-no-ci
git rev-parse --short HEAD

python -m unittest discover -s tests -p 'test_sse_monitor_public_snapshot.py' -v
python -m unittest discover -s tests -p 'test_sse_node_console.py' -v
python -m unittest discover -s tests -p 'test_sse_monitor_action_queue.py' -v
python -m unittest discover -s tests -q
```

Then (optional but recommended) the local Anvil integration with actual selected monitors and chain-anchored evidence:

```bash
SSE_RUN_ANVIL_INTEGRATION=1 python -m unittest discover -s tests -p 'test_sse_direct_delivery_anvil.py' -v
```

This branch adds **11** Python unit/integration tests relative to baseline 668 (target **679 discovered, six skipped**, not yet verified). Failure to refresh, missing file or missing role are hard errors, not passing SLA outcomes.

## Next actual acceptance gates

- Independent Ubuntu monitor + provider/consumer **processes**, with Tailscale Serve, private signer isolation and validated cross-account read-only review snapshot handoff
- Real owner-side **confirmation approvals** with fresh chain preflight, nonce management and identity separation; do not automate financial voting
- Staged systemd install/update + loopback UI exposure through authenticated overlay; no global god-controller
- Monitor seat replacement, backlog reconciliation, partition/reorg and clock faults; operator independence policies
- Witnessed physical service evidence and safe N/F/S adjudication before any evidence-driven settlement
