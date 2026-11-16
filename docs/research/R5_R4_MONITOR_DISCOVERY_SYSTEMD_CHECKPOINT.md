# R5/R4/R6 — Multi-role systemd supervision and read-only monitor discovery

**Status:** research implementation on a new [skip ci] branch; **new tests NOT YET RUN on developer Windows host**, new optional real-Anvil assertions not yet confirmed. Base `6b723ff` was verified by developer: 644 Python discovered, 638 pass, six skips, zero errors; standalone monitor 11/11 and node console 9/9. Earlier local real Anvil + signed selected-monitor archive integration passed. These are separate local checkpoints, not an independently deployed multi-VM system.

## Phase/task mapping

The repository's 2026-11-15 tracker numbers are historical acceptance estimates, **not recalculated or modified here**: R0 100%, R1 62%, R2 26%, R3 38%, R4 38%, R5 10%, R6 5%, R7 15%, R8 10%, R9 5%, R10/R11 0%. Subsequent test-backed R4/R5/R7 work advances research **subtasks**, but no whole-phase completion is claimed.

1. **R5 operator-owned agents:** multi-role public wallet manifest and role checks implemented, node UI and explicit marketplace CLI implemented; now **read-only event discovery**. Autonomous signed bids/funding/confirmations remain under explicit local approval, not automatic.
2. **R4 monitoring:** signed positive provider observation, selected monitor, chain-pinned archive; now discovery of contract assignments/admitted epochs. Independent physical SLA truth, authenticated finality, operator independence, negative evidence adjudication and vote policy remain open.
3. **R6 operations:** Ubuntu bootstrap / overlay source and safe local release preflights; now a **render-only isolated systemd monitor unit plan**. No VM installation, user account creation, Tailscale config or update/release performed.
4. **R7:** local deterministic Docker worker and selected-provider signed-result path implemented/tested in combined Anvil+Docker lab. Standalone real-Docker test skip remained unaccepted. Production capacity manager, OCI, storage and service-specific physical metrics remain open.
5. **R3/R2:** election, economics and N/F/S Solidity research remain unchanged; the new scheduler does not turn signed evidence into settlement votes or authorize money changes.
6. **R8/R9/R10/R11:** independent observatory, multi-VM experiments, performance/fairness evaluation and public reproducible release remain to be accepted.

## What new read-only monitor scheduling actually does

`tools/sse_monitor_discovery.py` implements bounded, crash-persistent `eth_getLogs` discovery of the **actual** deployed `SSESettlement` events:

- `CommitteeAssigned(uint256,uint256)` identifies a *possible* selected-monitor confirmation needing the **monitor owner** to review.
- `EpochAdmitted(uint256,uint256,bytes32)` identifies a *possible* epoch needing reviewed evidence collection; it is **not itself an SLA claim**.
- Every record must be from the configured settlement address, match the ABI event topic/argument types, appear on an RPC-reported canonical block, and be corroborated against an EIP-1898 **block-hash pinned** on-chain lease/epoch inspection.
- The exact locally configured monitor address must be among four selected addresses; active funded marketplace lease and nonzero committed SLA/resource hashes are required; local public role wallets must not belong to the lease consumer/provider. An admitted epoch must have all four monitor confirmations and open monitoring/evidence windows.
- Scans are bounded to at most 256 blocks (default 128) and at most 1,024 logs per call. Default two-block confirmation delay is a **lag**, NOT consensus finality.
- A SQLite journal under a private existing directory stores `COMMITTEE_ASSIGNED / REVIEW_CONFIRMATION` and `EPOCH_ADMITTED / REVIEW_EVIDENCE_CAPTURE` notifications and the last scanned block hash; restart uses the same cursor. New DBs are explicitly created mode 0600 under a mode-0700 owner-only parent on POSIX.
- A conflicting prior block hash or a malformed/removed log fails closed. Manual repair/rewind is needed on actual reorganization; there is no silent reset and no automatic rollback of emitted off-chain observations.
- **No signing key**, Docker API, Tailscale administrative credential, Ethereum transaction or remote process-control privilege exists in this scheduler.

This is **read-only autonomous assignment/epoch discovery**, not yet end-to-end autonomous monitor operation. Epoch selection/finality and monitor confirmation are separate obligations. The scheduler is deliberately not a voting oracle.

## How to run the monitor scanner safely

`services/monitor-agent/monitor_discovery.py` is preview-only by default, without RPC access or file writes. Public node roles file must match `sse-node-roles-v1` and explicitly list a `monitor` wallet.

```bash
python services/monitor-agent/monitor_discovery.py \
  --node-roles-file /etc/sse/node-roles.json \
  --journal /var/lib/sse-monitor/events.sqlite \
  --rpc-url http://127.0.0.1:8545 \
  --settlement 0x<DEPLOYED_SETTLEMENT> \
  --chain-id 31337 --start-block <DEPLOYMENT_BLOCK>
```

No RPC calls above. After reviewing the node's role manifest, endpoint, funded chain and scope, add **`--scan`** for one bounded, read-only RPC scan. Add **`--watch`** only for an operator-approved long-running read-only watcher. No monitor confirmations or votes will be sent. The journal's parent must already exist and be owner-only; it is not provisioned automatically.

The collector for approved positive evidence remains the **separate** opt-in `services/monitor-agent/monitor_capture_once.py --capture`. The scheduler does not automatically call it because that would load a role signing key and trigger network observations. Negative timeouts never automatically become `FAILURE` votes.

## Multi-role supervisor: intentionally staged

`tools/sse_multi_role_systemd.py` renders a **review-only** `sse-monitor-discovery.service` unit for a node with the `monitor` role. systemd is the intended supervisor; the unit has its *own* `ssemonitor` Linux account, private `StateDirectory=sse-monitor` mode 0700, strict filesystem protections, `NoNewPrivileges` and no signer key. It does not write units, install users, start services or change any VM. The existing node console remains a separate `sseagent` unit.

When one VM also has consumer/provider/observer roles, those roles still require distinct local owner-controlled processes and wallets; **the generated monitor unit never starts the provider/consumer signer**, and the global observer/dashboard never obtains keys.

Before real activation, the owner must review the full Git revision, install a dedicated nonprivileged `ssemonitor` service account and Python runtime, provision a private roles manifest, trusted RPC and required dependencies, inspect the unit, and separately approve/start it. A reviewed automated installer for all role-specific services is a future R6 task.

### Tests: operator Windows host

```bash
git status --short
git fetch origin research/r5-r4-role-supervisor-monitor-discovery-no-ci
git switch --detach origin/research/r5-r4-role-supervisor-monitor-discovery-no-ci
git rev-parse --short HEAD

python -m unittest discover -s tests -p 'test_sse_monitor_discovery.py' -v
python -m unittest discover -s tests -p 'test_sse_multi_role_systemd.py' -v
python -m unittest discover -s tests -p 'test_sse_monitor_multirole.py' -v
python -m unittest discover -s tests -q
```

The new tests use injected RPC/inspector fixtures and temporary SQLite journals to cover bounded event indexing, confimation delay, restart/replay, reorg stop, malformed event topics and log hashes, conflict checks, source provenance and read-only CLI behavior. The new combined-Anvil assertion additionally reads *real* `CommitteeAssigned` and `EpochAdmitted` events from the temporary lease, discovers its selected monitor and checks duplicate scans produce no new notifications.

```bash
SSE_RUN_ANVIL_INTEGRATION=1 python -m unittest discover -s tests -p 'test_sse_direct_delivery_anvil.py' -v
```

Optional `SSE_DIRECT_ANVIL_USE_DOCKER=1` still requires local working Docker and the immutable image ID, as in the previous R7 checkpoint. No remote Ubuntu machine or mainnet contract is touched by these offline tests.

### Next acceptance gates

- Green new offline suite and opt-in real-Anvil event scanner, with preserved original signed marketplace/delivery/evidence workflow
- Run read-only monitor watcher under isolated systemd unit on a disposable Ubuntu VM with stable owner-controlled identity and trusted RPC
- Monitor local owner confirms committee assignments; scheduler detects admitted epochs and proposes separate signed evidence capture
- At least four **independent operator** monitors, not four wallet aliases, over separate network paths, with failure/partition/reorg/adversarial tests
- Qualify physical delivery and timing evidence, resolve N/F/S ambiguity before enabling any on-chain vote or settlement automation
- R6 updates and discovery, R8 observatory, R9/R10 experimental metrics, R11 public signed reproducible release
