# R276 — Actual Monitor1 native funding one-use marker CONSUMED: forensic before any further send; use standby VMs for real distributed roles

## Actual new owner VM4707 log

Owner executed R267 original-pinned source at
`4eafadae5e27a6bc5ff6467c3a76996858dbdcb5` and attempted
`--role monitor-1 --send` after the prior original native
consumer funding tx was finalized. Actual result:

```
R267_ROLE_FUNDING_REFUSED: this exact role funding attempt already consumed; DO NOT RETRY
```

This result **does NOT prove Monitor 1 received TEST ETH**. R267
writes the exact single-use `monitor-1` transaction attempt marker
***before*** its one `eth_sendRawTransaction` RPC call. Another
owner-terminal invocation could have already signed/broadcast a valid
nonce2 tx; alternatively an interrupted process could have saved the
marker but not broadcast, or remote RPC visibility may be incomplete.
Do not infer a broadcast, receipt, nonce2 success, or current balance
from existence of a marker alone. The user has NOT provided a
public Monitor1 nonce2 tx hash in the logs. Never delete, move,
edit or reset the marker, never re-sign/rebroadcast nonce2, and
do not attempt Monitor2 nonce3 before the actual canonical-finalized
Monitor1 receipt is independently verified.

### R276 new safe exact public-only forensic script

New `tools/sse_pos_r276_vm4707_monitor1_funding_attempt_forensics.py`
is a **single-shot, NO transaction** strict audit. It:

1. Uses the already-implemented R267 `read_marker("monitor-1")`
   to read ONLY the private 0600 owner-marker's PUBLIC metadata
   (role, source, recipient, exact transfer value, nonce,
   gas limits/price, precomputed tx hash). It never opens the
   signer keystore, asks password, signs or sends anything.
2. Verifies actual original chain31340 genesis, latest and finalized
   heights and actual VM4707 app source latest/pending nonces.
3. Queries by the **locally precomputed transaction hash** from
   the already-consumed marker, checks exact signed
   from/to/value/nonce/gas/gasPrice/chain/input if visible;
   independently fetches actual receipt and canonical block
   hash and inclusion height/status.
4. Reads Monitor1 recipient's latest and finalized native balances.
5. Reports unambiguously:
   - `MARKER_EXISTS_HASH_NOT_VISIBLE_DO_NOT_RESEND` (unknown if
     broadcast, not proof of permanent failure)
   - `MATCHING_SIGNED_TX_VISIBLE_NOT_INCLUDED`
   - `MATCHING_TX_SUCCESSFUL_CANONICAL_PENDING_FINALITY`
   - `MATCHING_TX_SUCCESSFUL_CANONICAL_FINALIZED`
   - `MATCHING_TX_CANONICAL_REVERTED_DO_NOT_RESEND`
   or REFUSES invalid chain, marker, signed tx/receipt or canonical
   block mismatch.
6. Only sets `monitor2PredecessorFinalizedEligible:true` if real
   exact successful canonical **FINALIZED** Monitor1 transfer is proven.
   This report STILL does not sign or send Monitor2.

**NO automatic recovery, re-broadcast, retry or skip is implemented**.
Eight new mocked regression tests
`tests/test_sse_pos_r276_vm4707_monitor1_funding_attempt_forensics.py`
are authored but **not yet owner VM4707-executed**.

Owner: fetch latest pinned SHA, ensure your previously proven VM4707
testvenv and existing separate checkout, then run 8 focused tests and
ONE read-only R276 audit. If exact marked hash is not visible,
preserve marker and investigate safely rather than arbitrarily
clearing it.

## Actual VM4709 R275 owner results

Source SHA `beec19c14c9ae9090518d303eea746682aa08e7f`:
new focused R275 **9/9 PASS**, prior compute Docker
**16/16 PASS**, existing V2 provider server
**5/5 PASS**, **30 actual unit tests all passed**.
No live VM4709 Docker compute workload has been started.
The existing real rootful Docker daemon is Ubuntu
`docker.io 29.1.3-0ubuntu3~24.04.2`.
`apt-cache policy` finds **no**
`docker-ce-rootless-extras` package in current configured
Ubuntu archives; rootlesskit/uidmap/slirp4netns/fuse-overlayfs
are available. Actual *nonmutating apt simulation* for those
four packages selected SIX new package installs:
`fuse-overlayfs`, `libslirp0`, `libsubid4`,
`rootlesskit`, `slirp4netns`, `uidmap`,
with **0 upgrades, 0 removals** (73 others not upgraded).
This does NOT itself supply both absent
`dockerd-rootless.sh` and `dockerd-rootless-setuptool.sh`,
so a careless `apt install` could leave rootless Docker
still unusable. Avoid replacing Docker.io, restarting the
running native chain31340 PoS containers or adding nonroot
users to Docker group. No package install authorized yet.

## Available standby VM fleet — retrieved from prior research history

`docs/SSE_COMPLETE_ROLES_PERMISSIONLESS_SCALING_AND_VM_EXPERIMENTS.md`,
section **9** (2026-11-21 research design), records that user
had **two additional large VMs** around 4 vCPU and 12–16 GiB RAM
and **four smaller Ubuntu24.04 VMs** each around
2 vCPU, 4 GiB RAM, 40 GiB disk. These were recorded as
**provisioned**, not as running blockchain clients or
physically independent organizations. These were called
`New large A`, `New large B`, `New small C/D/E/F`,
not assigned verified VM numeric identifiers. Existing
real VM4709 later became an actual additional EL+CL host;
do not assume which historical category it is without
fresh inventory.

Standby VM allocation should be role-selectable and based
on actual resource readings, NOT hardwired permanent roles:

| Historical standby category | Suggested first test | Proof needed |
|---|---|---|
| Large A / Large B | Independent native EL+CL peers or later independent-validator with UNIQUE BLS keys and deposits | Real zero-invite P2P, matching finalized chain, no cloned keys |
| Small C | Remote monitor probe host with its own encrypted application EOA | Real remotely measured provider API, signed evidence, separate fault domain |
| Small D | Another remote monitor and real fault injection | Independently observed network/timeouts, operator independence not assumed |
| Small E | Dedicated actual Docker compute provider | Real CPU/RAM/disk; isolated worker and HTTPS; unlike VM4709 need not coexist with the PoS Docker daemon |
| Small F | Separate consumer / monitor for other leases | Separate EOA, actual funded request and signed traffic |

A single host may play any eligible roles, but multiple
local wallets on VM4707 are NOT independent auditors.
For current onchain `f=1` committee, at least four
distinct registered eligible monitor EOAs are required
and independently operated monitors are needed for strong
physical adversarial experiments. Assign new monitors
to **different standby machines**, not VM4707. Their
public EOA addresses can be created locally with existing
audited encrypted-keystore tool and later considered for
separately approved bounded TEST ETH funding. Zero-
balance full nodes can join without any EOA gas.

## Next operator actions

- VM4707: R276 one-shot public tx-forensic and only if
  Monitor1 canonical finalized success, existing R267
  Monitor2 **default READ-ONLY** proposal; owner
  does not need any repeat Monitor1 --send.
- VM4709: keep its original live Besu+Lighthouse Docker
  daemon unchanged, encrypted provider wallet untouched
  and available as future provider; no more rootless
  package installation shortcuts.
- Standby VMs: operator picks two small machines with
  actual capacity, uses read-only `nproc`, `free -h`,
  `df -h`, `id -un`, `lsb_release -ds` checks;
  allocate real monitor and isolated compute based on
  actual reachability/CPU. Host names from new owner
  logs only, never fabricate VM IDs or operators.

The original native chain31340 genesis, validator custody,
market and ledger contracts are unchanged.
