# R141 — Real multi-VM PoS fleet experiment, unrestricted protocol roles

**Source:** `tools/sse_pos_r141_independent_fleet_audit.py`.
**State:** implementation plus pure regression tests committed; live node capture
and fleet acceptance **not yet observed**. No host or chain mutations.

## A fleet is not a fixed two-node architecture

Every node independently chooses its role(s). Observers/full nodes require
the exact public chain31340 genesis and compatible EL/CL, but no wallet or
administrator; validators must independently control BLS keys and meet
the REAL standard deposit/activation rules. Provider, consumer and monitor
roles have their own objective on-chain and physical requirements and may
coexist on one host subject to monitoring conflicts of interest. A real
experiment can use 2, 4, 8, 16, 32, or more VMs. The R141 input batch has
a 256-report parser limit to bound one audit, **not a P2P, PoS, economic-role,
validator or experiment-cap limit**. Additional batches can be audited.

A larger number of VM instances in the SAME cloud/provider/account
does not establish multiple independent infrastructure or human fault
domains. Independent ISPs/operators need separate evidence.

## 1. Capture ACTUAL local client state on EACH VM

Run in the checked-out GitHub source tree using Python 3 on each participant.
These commands have no Docker or signing side effects, call only
local read-only Ethereum JSON-RPC and Beacon endpoints, and write
a nonsecret JSON file on that machine. Name and paths must be
unique per local host. The concrete ports shown here are historical
owner/observer values, **not a requirement for new hosts**.

VM4706 (first observed owner, does not touch validator):

```bash
python3 -B tools/sse_pos_r141_independent_fleet_audit.py \
  --capture --node-id vm4706-owner \
  --el http://127.0.0.1:18545 --bn http://127.0.0.1:15052 \
  > /tmp/sse-r141-vm4706.json
```

VM4707 (first non-signing observer):

```bash
python3 -B tools/sse_pos_r141_independent_fleet_audit.py \
  --capture --node-id vm4707-observer \
  --el http://127.0.0.1:28545 --bn http://127.0.0.1:25052 \
  > /tmp/sse-r141-vm4707.json
```

Every additional real host runs `--capture` locally with **its own
locally mapped EL/BN ports**, and a new unique node ID. Running
the same command repeatedly on one VM with multiple node IDs
does NOT count as new hosts. Do not fabricate reports or
duplicate credentials.

The capture fails closed if chain ID != 31340, if the native EL is still
syncing, if BN reports sync/optimistic/EL offline, if local head state
readings disagree, or if finalized state is absent. A capture does
not prove remote peer identity, independent validator duties,
a correct physical workload or anything about on-chain SSE contracts.

## 2. Compare a set of real collected reports OFFLINE

Transfer public reports to a single analyst machine using a transport
you trust; transfer **no** BLS/EOA keys, JWTs, keystores, passwords or
private node files. From the same R141 checkout:

```bash
python3 -B tools/sse_pos_r141_independent_fleet_audit.py \
  --compare /tmp/sse-r141-vm4706.json /tmp/sse-r141-vm4707.json
```

Add one report path for each other real node. The script checks:
- identical execution genesis block hashes and Beacon genesis validators roots;
- identical finalized checkpoint epoch AND root, not merely slot/time;
- nonzero EL and CL native peer counts on every reported node;
- capture timestamps within a configured 180-second collection skew;
- strictly unique node IDs, complete schemas and safe bounded input.

If some peers finalize different epochs because they are catching up,
the report is **inconclusive**. Never label different-epoch roots as forks
without querying the canonical history at a *common* checkpoint.
If native peers are zero, audit doesn't claim peer network success.
The machine-readable status `OBSERVED_CONSISTENT_CHECKPOINTS`
means exactly these observed data are consistent, not that the reports
are cryptographically authenticated or independently operated.

## 3. Evidence still required for permissionless scaling claims

1. A third node genuinely started under a separate operator and provider,
   discovered canonical native EL+CL peers without owner-admin approval,
   and showed advancing matching finalized checkpoints.
2. Multiple *independently keyed* validators did REAL 32-test-ETH
   deposits and became active in Lighthouse Beacon, proposing and
   attesting. A node without keys is not a validator just because
   its role manifest says so.
3. More real consumer/provider/monitor nodes ran distinct deployments,
   registered and bonded via actual contract transactions; real
   provider CPU/RAM/network resources were allocated for a funded
   lease, actual remote HTTP work was delivered and signed, independent
   monitors recorded raw evidence and conservative settlement occurred.
4. Vary honest and adversarial committee population independently of
   validator/node count; vary `k`, `q`, resource budgets and entropy
   assumptions with actual gas costs, consensus finality, missed votes,
   latency, partitions, crash recovery and service-level accuracy.
5. Change host underlay addresses, take bootstrap servers offline and
   demonstrate independently replaceable discovery paths. ZeroTier
   PUBLIC ad-hoc membership is not equivalent to Internet
   infrastructure independence.
6. Retain time-series captures, sanitized node logs, finalized tx
   receipts, provider/consumer measurement receipts and deployment
   version fingerprints. Publishing node claims is not authentication;
   report signed provenance and independent fault domain assessment
   are future research gates.

No network-wide participant count, role roster or permission gate is
introduced by R141. It is an observer and experiment evidence layer only.

## Pure regression tests

```bash
.venv-tests/bin/python -B -m unittest discover -s tests \
  -p 'test_sse_pos_r141_independent_fleet_audit.py' -v
```

Run the full existing regression suite after these targeted tests,
and inspect any new regressions before merging PR #41.
