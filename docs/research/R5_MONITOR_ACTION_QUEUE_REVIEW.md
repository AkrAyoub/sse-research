# R5 — Owner-reviewed, nonexecuting monitor action queue

**Status:** new research implementation, unvalidated on developer's Windows host; all commits [skip ci], no release/VM/contract changes. Base `b6cfc72` **was operator-validated**: 658 Python tests, 652 pass, six skips, zero errors; optional real Anvil integrated selected-monitor discovery + evidence test passed.

## Why the queue exists

The prior monitor scheduler persisted **past events** in `monitor_notifications`. Without a fresh read of chain state, a still-persisted `CommitteeAssigned` could be displayed as requiring confirmation **after all four monitors confirmed**; similarly an old `EpochAdmitted` could be displayed after the monitoring/evidence window closed. A persistent notification is not an approval to sign anything.

`tools/sse_monitor_action_queue.py` now produces **owner-reviewed action proposals**, not executable jobs, by:

1. Opening the **existing** monitor SQLite journal in `mode=ro`, checking the persisted monitor wallet, chain ID, settlement and last scanned block hash;
2. Checking the **current canonical block hash returned by configured RPC** for every displayed event, not just the cursor. A changed hash blocks the entire review pending manual reorg inspection;
3. Reading the current Solidity `SSESettlement` lease/epoch with `inspect_chain(...,pin_block_hash=True)`, using EIP-1898 block-hash selectors. RPC authenticity is an external trust input; this **does not verify independent PoS finality**;
4. Rechecking that the exact local monitor wallet is selected, the lease is funded with committed policy/resource hashes, and **none of this node's disclosed consumer/provider wallet addresses** controls the lease counterparties. Multiple roles on one VM remain supported; **operator independence is not proven by local role declarations**;
5. Showing only `REVIEW_CONFIRMATION` when the **current** lease is Accepted and not all four have confirmed, or `REVIEW_EVIDENCE_CAPTURE` for a confirmed, Active epoch with still-open monitoring window. Other stored notifications are `NO_LONGER_ACTIONABLE`;
6. Including `approvalRequired=true`, `signerLoaded=false`, `votesSubmitted=false` and `finalityVerified=false` on all returned tasks. A confirmation proposal matches the existing `make_plan("monitor-confirm",...,params={"leaseId":...})` schema; the evidence proposal identifies the **separate** `monitor_capture_once.py --capture` action.

**Limitations:** the existing Solidity V1 `confirmedMonitor` mapping is private; this preview **cannot establish whether this individual monitor already confirmed** while some other monitor remains outstanding. Therefore `REVIEW_CONFIRMATION` is merely an owner prompt, not a guaranteed-valid transaction. Likewise the queue does not check that the provider has persisted a consumer receipt, does not hold evidence signing keys, and never automatically submits on-chain votes or money transactions.

The queue returns the latest at most **64** archived notifications; `moreNotificationsExist=true` signals historical entries not shown. Complete pagination, refresh/acknowledge queues, replacement-monitor rotation event handling, and autonomous deadline management remain later engineering tasks. Bounded chain-block confirmation depth is **not** chain finality.

## Commands: safe preview, explicit event scan, then review

First fetch this revision and run tests (below). **Do not run with real signing keys or use a production RPC yet.** To preview the read-only watcher with an operator-owned public manifest:

```bash
python services/monitor-agent/monitor_discovery.py \
  --node-roles-file /etc/sse/node-roles.json \
  --journal /var/lib/sse-monitor/events.sqlite \
  --rpc-url http://127.0.0.1:8545 \
  --settlement 0x<DEPLOYED_SETTLEMENT> \
  --chain-id 31337 --start-block <DEPLOYMENT_BLOCK>
```

Above is **dry run**: no RPC and no SQLite file write. For an approved local test, `--scan` reads one bounded contract event range and persists the scanner cursor. After at least one scan, replace `--scan` with **`--review`** to open the existing journal read-only, validate current chain state and print suggested owner actions. A missing journal fails closed. Neither flag sends a transaction.

The role-specific **node-local UI** remains a separate component and currently displays only owner-entered transaction plans. The queue does not silently add signing controls to the network dashboard or install a systemd unit. Existing monitor discovery `--watch` remains read-only, and any future UI integration must preserve per-VM ownership and require explicit action confirmation.

## Validate on Windows/Git Bash

```bash
git status --short
git fetch origin research/r5-monitor-role-action-review-no-ci
git switch --detach origin/research/r5-monitor-role-action-review-no-ci
git rev-parse --short HEAD

python -m unittest discover -s tests -p 'test_sse_monitor_action_queue.py' -v
python -m unittest discover -s tests -p 'test_sse_monitor_discovery.py' -v
python -m unittest discover -s tests -p 'test_sse_monitor_multirole.py' -v
python -m unittest discover -s tests -q
```

Opt-in actual local Anvil `CommitteeAssigned + EpochAdmitted` proof (no monitor vote or physical-SLA qualification):

```bash
SSE_RUN_ANVIL_INTEGRATION=1 python -m unittest discover -s tests -p 'test_sse_direct_delivery_anvil.py' -v
```

The new Anvil test asserts that the selected monitor's queue identifies the active admitted epoch as `REVIEW_EVIDENCE_CAPTURE` while the now-ready committee confirmation event is no longer actionable. This **new assertion is untested** until you execute the commands.

## Next release gates

1. Validate source/ABI compatibility and approve a controlled Ubuntu VM deployment for the **read-only** scheduler and reviewer.
2. Implement independently operated monitor registration/confirmation scheduling with **owner-local signatures and explicit approval**, plus watcher handling for `CommitteeSeatRotated` and timeouts.
3. Build role-local monitor evidence **capture recommendations** tied to exact approved policy/resource manifest bytes, not an arbitrary RPC probe.
4. Run 4 independently owned monitor VMs through Tailscale, including reorg, partition, missing receipt and Byzantine monitor fault injections.
5. Prove/qualify physical fulfillment and timing before authorizing any Solidity `monitor-vote` automation or economic finality claim.
