# R271 — Consumer nonce1 included & canonical but still unfinalized; unblock real provider-host preparation

## Actual latest owner VM4707 observation (2026-11-24)

After actual consumer funding nonce1 send acknowledged on VM4707:
`0x9f3a13cb295b5ba2f642804a30c391b9cce266784a83dd293d0dd7fb7d1f9fdd`,
the owner has now **twice** run R267 monitor1 preliminary checks.
Both yielded the **actual** status
`R267_EARLIER_ROLE_FUNDING_PENDING_FINALITY_DO_NOT_RESEND:
previous role funding not yet finalized; DO NOT RESEND`.
This exact R267 code reaches the error **only after**
it has loaded the original one-shot local consumer marker,
retrieved the actual consumer tx and receipt, validated
exact from/to/value/nonce/gas, success status, and canonical
included block. Thus the consumer transfer was successful
and canonical **at the time of each R267 read**, but no
actual finalized execution coverage yet. The finality gap
has NOT been quantified by the owner logs. Monitor1 nonce2
was not authorized at the owner terminal and was NOT sent.
No retries of consumer nonce1 or marker deletion.

Existing R267 one-time owner sender implements correct
predecessor finality gating. A new tool MUST NOT bypass this
security boundary or repeatedly rerun `--send` to poll.

## New R271 read-only single snapshot (no polling)

`tools/sse_pos_r271_consumer_native_tx_finality_snapshot.py`
provides exact current real chain31340 canonical consumer
transfer status and execution head/finalized heights,
consumer receipt included block, the **numeric remaining
execution-block distance** to its finality, actual latest
and finalized recipient balances, current original
Lighthouse Beacon genesis, Beacon head slot,
finalized epoch and Beacon epoch lag.

No keys, role passwords, signing, broadcast, Docker,
validator action, loops, artificial chain progress,
or automatic role registration. The script distinguishes:
- `SUCCESSFUL_CANONICAL_NOT_YET_FINALIZED`
- `SUCCESSFUL_CANONICAL_FINALIZED`
- `VISIBLE_NO_RECEIPT`
- `NOT_VISIBLE`

It REFUSES wrong original EL/Beacon genesis, invalid
consumer signed transfer, reverted receipt, noncanonical
inclusion, Lighthouse optimistic/offline/syncing,
or finalized recipient balance inconsistency. It does
not interpret `NOT_VISIBLE` as proof of never sent;
the owner R267 first-stage marker remains immutable.

Mock-focused test suite is staged in
`tests/test_sse_pos_r271_consumer_native_tx_finality_snapshot.py`,
**not yet executed on VM4707**.

### Exact VM4707 owner command

Checkout newest Git SHA from ChatGPT, then:

```bash
PY=/tmp/tmp.Ridv9nIavf/testvenv/bin/python
"$PY" -B -m unittest discover -s tests \
 -p test_sse_pos_r271_consumer_native_tx_finality_snapshot.py -q
"$PY" -B tools/sse_pos_r271_consumer_native_tx_finality_snapshot.py \
 --rpc http://127.0.0.1:28545
```

When status is `SUCCESSFUL_CANONICAL_FINALIZED`, the
EXISTING independently checked exact SHA
`225257a17d4270f454fed3d1d48d0fdda7d1fb62`
R267 `--role monitor-1 --send` can be run once
(with owner interactive consent) after checkout,
without resubmitting consumer nonce1. After Monitor1
nonce2 real successful finalized receipt, monitor2
nonce3 can proceed. No retroactive claims.

## VM4709 real additional blockchain host, possible resource provider

VM4709 was a genuine EL+CL peer on original chain31340
in operator-provided R191 evidence, not a synthetic
node. That observation was on Nov 23 at finalized
Beacon epoch570, and **its current state/capacity
has not been freshly verified**. VM4709 is a
candidate for physical application provider if
it has the actual available CPU/memory/disk and
isolated Docker capacity plus public authenticated
worker endpoint. No provider role or resource
availability is yet claimed.

Do NOT restart VM4709's recovered Besu/Lighthouse
containers or reuse their data/keys as new app
identities. Operator can safely first check current
capacity/read-only Docker inventory:

```bash
(
 set -euo pipefail
 echo "HOST=$(hostname) USER=$(id -un)"
 echo "LOGICAL_CPUS=$(nproc)"
 free -h
 df -h "$HOME"
 docker ps --format '{{.Names}} {{.Status}}' 2>&1 || true
 python3 - <<'PY'
try:
 import eth_account
 print("ETH_ACCOUNT_INSTALLED=true")
except ImportError:
 print("ETH_ACCOUNT_INSTALLED=false")
PY
)
```

Once the user confirms VM4709 has sufficient actual
unused resources, the EXISTING audited
`tools/sse_pos_test_wallet.py` can create
`adaptive-v2-provider` as an encrypted app-only EOA
on that host in a fresh nonroot owner-owned 0700
directory (only with eth_account installed).
This creates no native TEST ETH, service, registered
marketplace provider or independently fulfilled
lease. Additional actual monitors must run in
different physical fault domains to support an
independence experiment; two VM4707 monitor wallets
do NOT establish such an experiment.

## Remaining security limitations

- Original V2 deployed contracts are final and immutable.
- Finality is consensus-protocol liveness, not
  a command to mine blocks or disable validators.
- 0.001 TEST ETH bond is economically worthless and
  is no Sybil deterrence.
- Physical CPU provider, independent monitor
  availability and externally reachable HTTPS
  endpoints remain unproven; user requests real,
  permissionless cross-operator onboarding.
