# R144 — One repository, one role-selecting SSE installer entry point

**Single canonical repository:** `AkrAyoub/sse-research`.
**Single operator entry point:** `python3 -B tools/sse_join.py`.
**Current state:** interactive and noninteractive role selection, prerequisite planning,
and read-only delegation to the guarded R137 full-node installer preflight.
**Not yet:** complete unattended OS/bootstrap installation, direct full-node
creation from a fresh empty machine, automatic validator activation,
marketplace service installation, public release mirrors, or active on-chain roles.

This document is explicit to prevent confusing a successful *plan* with an
installed node or an activated role.

## User experience target

One repository must contain:
- First-boot installation on clean supported Linux, including pinned dependencies,
  authenticated public genesis, client images, secure node-local identities,
  dynamic network transport, startup service and restart/update handling;
- role-neutral EL/CL full-node clients;
- optional independently keyed validator software with secure local BLS custody
  and actual standard chain31340 deposit/Beacon activation;
- consumer, provider and monitor services (each independently elected, economically
  eligible and authorized on-chain as applicable);
- operator-local API/UI, resource telemetry, signed evidence and safe settlement;
- tests, full research reference docs and reproducible experiments;
- a single role-selection menu; no separate repository, whitelist, fixed VM quota,
  or custom manual script for every participant.

**Fundamental model:** network joining is independent of application role activation.
An observer/full node needs compatible software/genesis/P2P, **no wallet balance**.
A validator needs a real deposit and consensus activation, even if its local
role preference says validator. A monitor needs a real bond and selected seat
to attest a lease. A consumer needs a funded lease; provider needs actually
measured/offered physical capacity. Selecting several roles on one VM is permitted,
except for conflicts such as monitoring the same operator's own lease.

## What works in R144

```bash
python3 -B tools/sse_join.py --node-id large-new-a --plan
```

If `--roles` is omitted, a numbered role menu appears:

```text
1. full_node
2. observer
3. validator
4. provider
5. consumer
6. monitor
```

Choose one or several numbers. This runs the real R143 local resource
inventory and reports per-role prerequisites and honest next gates; no packages
or containers are created. To use a predefined noninteractive selection:

```bash
python3 -B tools/sse_join.py --node-id large-new-a --roles full_node --plan
python3 -B tools/sse_join.py --node-id small-new-c --roles monitor --plan
python3 -B tools/sse_join.py --node-id new-provider-x --roles provider,consumer --plan
python3 -B tools/sse_join.py --node-id fresh-validator-x --roles validator --plan
```

The validator example automatically includes a full-node dependency in the
plan; it **does not create or activate a staking key** or clone the original
VM4706 validator.

When a new, genuinely fresh and independently controlled full-node host
has a reviewed R136 observer manifest, exact source-hash-verified original
genesis archive, pinned Docker images, healthy Docker/ZeroTier, and at least
two real public discovery sources, this *single entry point* delegates to
the R137 **read-only plan**:

```bash
python3 -B tools/sse_join.py \
  --node-id large-new-a --roles full_node --observer-plan \
  --manifest /path/to/new-operator-observer.json \
  --archive "$HOME/chain31340-public-native-observer-v1.tar.gz" \
  --discovery-source 'https://REAL-FIRST-INDEPENDENT-MIRROR/peers.json' \
  --discovery-source 'https://REAL-SECOND-INDEPENDENT-MIRROR/peers.json'
```

No URLs are live or hardcoded into this documentation. **DO NOT run that
command using placeholders.** The existing R137 `--apply` requires explicit
interactive local owner authorization and is intentionally **not** exposed
by R144 until a reviewed end-to-end installer and fresh-host acceptance
test are available. Never run R137 apply on VM4706 or VM4707.

## Crucial fresh-VM limitation

A brand-new Ubuntu VM has **no checkout and no `tools/` directory**.
The operator must first obtain a verifiable copy of the single repo, then
run `tools/sse_join.py`. This is not a second repository; GitHub is the
source of every component.

At this stage the repo is **private**, so unauthenticated
`git clone https://github.com/AkrAyoub/sse-research.git` is NOT a reliable
onboarding method for arbitrary outside operators. Configure a
node-specific **read-only** deploy key using secure provisioning or
publish a signed/hash-pinned read-only public release/mirror. Do not paste
personal access tokens, signing wallets or deploy private keys into
terminal commands, screenshots or GitHub issues. A private GitHub
account is a development dependency, **not** a permissible permanent
network admission prerequisite.

For an already configured SSH deploy key on the NEW VM:

```bash
git clone --no-checkout git@github.com:AkrAyoub/sse-research.git "$HOME/sse-research"
cd "$HOME/sse-research"
git fetch --no-tags origin feature/r136-independent-observer-preflight
git switch --detach <EXACT_REVIEWED_R144_GIT_COMMIT>
python3 -B tools/sse_join.py --node-id large-new-a --plan
```

This is SOURCE BOOTSTRAP ONLY. `<EXACT_REVIEWED_R144_GIT_COMMIT>`
must be replaced by the SHA reported in the PR and verified with
`git rev-parse HEAD`. A node without a configured deploy key will be
refused by GitHub, without any impact to the existing chain.

## Implementation stages still necessary in the same repository

1. **Public immutable software/genesis distribution**: checksum and signed
   release manifest hosted on independent mirrors; no mandatory private
   GitHub access. Keep original genesis and independent operator secret
   keys unchanged. Do not reinitialize a live chain.
2. **First-boot installer**: safe OS package/image provisioning and
   upgrades, service units, creation-only local identities, ZeroTier
   PUBLIC overlay or replaceable native Internet transport, current
   dynamic enodes/ENRs, native EL/CL peer checks and real finality.
3. **Role services**: package provider and monitor standalone agents for
   2-vCPU/4-GB machines and consumer services without forcing full EL/CL
   on every application node. Provider/monitor endpoints need real
   HTTPS authentication and resource/network telemetry.
4. **Validator ceremony**: individual BLS custody, 32 TEST ETH deposit,
   actual Beacon pending→active transition, isolated signer, slashing
   protection; separate multi-operator consensus evidence.
5. **Economic roles**: transparent faucet/sponsorship, actual SSE app
   contracts on chain31340 after adaptive committee/randomness/security
   review, funded leases/bonds, independent real probes, qualified
   evidence, bounded financial settlement and finalized withdrawals.
6. **Upgrade/recovery**: independently published peer rotation and
   readdressing, no master controller, no rollback, no automatic
   spending/validator signing authorization by role checkbox.
7. **Research scale**: varying actual full nodes, validator keys, provider
   capacity, consumers, registered monitors, selected committee k and
   frozen quorum q separately, with robust fault-domain evidence.

## Research status and verification

Last owner-verified prior integration commit R142:
`32a5a768c460cb5ab1bb93f2784834141fc9969f` ran
**951 Python tests, OK (3 skipped)** on VM4707. R143/R144 are
**GitHub commits pending the next complete VM regression**.
Passing their tests cannot prove fresh-host end-to-end automatic install.

Normative deep role explanation:
`docs/SSE_COMPLETE_ROLES_PERMISSIONLESS_SCALING_AND_VM_EXPERIMENTS.md`.
Current architectural vetoes:
`docs/ARCHITECTURE.md`, `docs/DECENTRALIZATION_INVARIANTS.md`.
