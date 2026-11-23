# R143 — Six new VM inventory, safe host sizing and onboarding gates

This file accompanies the detailed role architecture:
[`SSE_COMPLETE_ROLES_PERMISSIONLESS_SCALING_AND_VM_EXPERIMENTS.md`](SSE_COMPLETE_ROLES_PERMISSIONLESS_SCALING_AND_VM_EXPERIMENTS.md).

**Date:** 2026-11-21. **Status:** GitHub source with pure tests; no fresh host
has been installed, joined to original chain31340 or used as an active
validator by this change. The original VM4706 signer and VM4707
nonsigning clients must not be restarted or duplicated.

## User's actual provisioned fleet

- Existing VM4706 — live original validator + EL/CL: PRESERVE.
- Existing VM4707 — live nonsigning EL/CL: PRESERVE.
- New larger A and B — each provisioned with the previously recommended
  approximately 4 vCPU / 12–16 GiB RAM, to be **read-only checked and
  then independently onboarded as nonsigning full nodes first**.
- New smaller C, D, E and F — 2 vCPU / 4 GB RAM / 40 GB storage,
  CPU-only Ubuntu 24.04. Initially use for real monitor probes,
  provider compute and consumer tasks after marketplace deployment;
  **do not silently install two full blockchain clients on all four**.
  The 4 GB includes OS memory and monitoring reserves; do not lease
  nonexistent or already-committed capacity.
- All these VMs may be in one cloud operator/fault domain. For
  permissionless/independent-operator research claims, include outsider
  computers/ISPs without common owner control.

**Eight machines are an initial experiment**, not a permanent network
cap. Any compatible independent node can join later.

## The immediate real gate: local, read-only inventory per NEW VM

From a checked-out exact GitHub source tree on each fresh Linux x86-64 host:

```bash
python3 -B tools/sse_pos_r143_new_vm_readiness.py \
  --node-id large-new-a --roles full_node
```

On the *other* larger VM use a different ID:

```bash
python3 -B tools/sse_pos_r143_new_vm_readiness.py \
  --node-id large-new-b --roles full_node
```

On a small monitor VM:

```bash
python3 -B tools/sse_pos_r143_new_vm_readiness.py \
  --node-id small-new-c --roles monitor
```

And similarly `small-new-d --roles monitor`,
`small-new-e --roles provider`, `small-new-f --roles consumer`.
Multiple initially *compatible* roles can be requested as a comma
list; no real role activation is inferred.

The tool checks host architecture, observed CPU count, installed RAM
and available home-volume space, presence of standard binaries
(`python3`, `git`, `docker`, `zerotier-cli`, `ip`, `curl`) and
refuses a host that contains original owner signer state or the existing
R59 observer data root. It **does not** use sudo, read keys, install OS
packages, join overlay networks, pull images, download genesis, run
Docker or transact. Its operating system prerequisites and role
recommendations are just that: **planning margins**, not protocol
admission rules.

Preliminary recommended profiles used solely for capacity planning:

| Role | vCPU | RAM | Home-volume free disk |
|---|---:|---:|---:|
| Full node, nonsigning EL+CL observer, future validator | 4 | 10 GiB | 50 GiB |
| Lightweight resource provider (not customer-reserved resources) | 2 | 4 GiB | 10 GiB |
| Consumer or standalone monitor agent | 1 | 2 GiB | 5 GiB |

Provider resources above are just a host service *starting point*,
not a statement of rentable capacity, guaranteed isolation or SLA.
For large VMs the actual disk space might not be sufficient; inspect
what is provisioned. Future actual Besu/Lighthouse measurements and
profile-specific experiments must replace planning numbers.

Output flags `initialSizingAdviceMet` and `missingBinaries`
are actionable host setup information but DO NOT determine protocol
permission to join; `eligibleToJoinConsensusOrSseMarketplaceClaimed`
remains false until actual on-chain/service requirements are met.

## Next step after the inventory — new larger VM only

R137 `--plan` is the existing independent operator-neutral
nonsigning EL+CL installer preflight. It requires the original verified
chain31340 archive at the exact operator-local path, immutable pinned
official images, ready Docker and ZeroTier, a new host manifest, and
valid execution/Beacon seed records. R142 can obtain peer hints
from at least two working public HTTPS directories, but *publicly
hosted operational R142 directories are not yet present*.

**Do not run R137 `--apply` yet merely because this inventory passes.**
It creates real Docker resources and must have actual verifiable
genesis, real P2P bootstrap hints and explicit local owner consent.
It intentionally refuses the existing two VMs. After an independently
controlled new VM has actually installed both clients and passed R141
capture, follow the standard Beacon deposit/activation ceremony
for a *new* locally controlled BLS validator key; never copy the
original VM4706 VC/HD wallet.

The blockers to true zero-touch onboarding remain: public release
of genesis and binaries, independently published and refreshed
native discovery feeds, authenticated dynamic ENR publication,
reviewed safe package installation/permission model, separate
operator wallet custody, real role-specific transactions,
automatic restart and re-address recovery, and off-cloud
acceptance evidence.

## Source regression

```bash
.venv-tests/bin/python -B -m unittest discover -s tests \
  -p 'test_sse_pos_r143_new_vm_readiness.py' -v
.venv-tests/bin/python -B -m unittest discover -s tests
```

No manual edits to tracked source on a VM. All changes go through
the GitHub PR; record exact SHA and observed outputs. Do not
upload JWTs, BLS/EIP-2335 keys, local signing material or raw
secret-bearing logs.
