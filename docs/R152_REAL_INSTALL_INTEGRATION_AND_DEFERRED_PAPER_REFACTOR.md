# R150–R152 — Reuse proven native chain instead of reimplementing, postpone paper refactor

**Date:** 2026-11-21. **Operator decision:** keep implementing and testing the
real permissionless SSE network now. AFTER real multi-VM experiments, perform
an exhaustive codebase/architecture refactor and publish one paper-ready
reproducible install repository. Do not risk the functioning chain by
deleting historical code or merging numerous stacked branches now.

## Implemented during this slice, with no VM runtime change yet

**R150:** `tools/sse_pos_r150_verified_genesis_release.py`:
public-only, create-once exact-original archive release preparation.
Verifies the original 2026-11-21 R59 archive SHA256,
`1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7`,
all four original file digests, Beacon genesis state byte length and
original 31340 execution config. The allowed tar members are only
`genesis.json`, `config.yaml`, `genesis.ssz`,
`deposit_contract_block.txt` and `manifest.json`.
The tool never reads signing keys, builds genesis or touches the
original archive; output is a separate verified public distribution
candidate, NOT a published release. Public download in R149 now
revalidates every internal member before a new host stores it.

**R151:** `tools/sse_pos_r151_unattended_full_node.py`:
connects the public, locally owner-selected R147 role plan to the
**existing proven R137/R59 native EL+CL launch path**. It requires
the private locally created selected-role record, the precise
GitHub release SHA, exact authentic public original genesis,
valid real client images, a working local Docker daemon,
an actual observed ZeroTier ad-hoc IPv6 and public peer hints
if they exist. It creates fresh local Engine JWT and state only,
then calls R137's genuine Besu and Lighthouse container creator
without asking for another confirmation. The R137 underlying
source has a new tightly scoped `unattended=True` path that
requires the private root-owned R147 role-selection record and
refuses any existing original signer or observer state in
`/home/*/.local/share`. The older default R137 manual
approval path remains unchanged for prior reproducibility.
Docker volumes/images remain under review for privilege and
partial-failure recovery.

When no real public peer records have been published, a newly
installed first-online node may start clients in an isolated
`ZERO_PUBLISHED_BOOTSTRAPS_WAIT_FOR_DISCOVERY` state. There is
**no automatic finality claim**: native peers and active consensus
validators remain objectively necessary for live progress.

**R152:** `tools/sse_pos_r152_unattended_host_dependencies.py`:
for verified new full-node hosts only, installs Docker and basic
packages from Ubuntu's signed APT repos; downloads the official
ZeroTier *GPG-signed* installer and validates the release-signing
key's full fingerprint before executing it (never blindly
`curl|bash`); joins the existing public controllerless ad-hoc
transport; pulls **exact pinned immutable Besu/Lighthouse OCI
images**; checks those images via original R59 code, and waits
for actual 6plane IPv6 assignment. The network ID is the
existing experimental transport's immutable identifier, not
an allowlist of peers or static address. Full independence
from ZeroTier's third-party root/relay infrastructure and
alternative P2P transport remain an explicit release blocker.

The single R147 installer now automatically dispatches
R151/R152 native startup *after* authentic original genesis
is publicly available, instead of ending at a role plan.
The required source revision, exact genesis bytes and host
software are still checked. The output distinguishes
submitted real nonsigning clients from actual observed
peer handshakes and finality.

**R153 — unattended objective chain evidence:** after R151 has actually
submitted new Besu and Lighthouse containers, it attempts to install a
local systemd timer invoking `tools/sse_pos_r153_local_node_evidence.py`
at regular intervals. That read-only tool reuses R141's real loopback
EL/CL API checks and produces an atomically replaced private
`/var/lib/sse/evidence/latest.json`. If clients are absent, syncing,
optimistic, offline, disconnected or have not finalized, the
record explicitly says `WAITING_FOR_ACTUAL_EL_CL_FINALITY` and
contains **no forged checkpoint**. A successful local R141
capture is still not proof of an outside operator, public ISP
reachability, active validator deposits or remote resource delivery.
The timer runs only on newly created hosts from a reviewed pinned
release; never touch the original VM4706 signer. Timer installation
failure is recorded without rolling back running clients.

## High priority missing REAL infrastructure

1. The R59 original public archive is still *on an operator VM*
   (VM4706/4707 user-space file), and **not publicly published**.
   R150 can verify and prepare the existing artifact without secrets,
   but a real authorized owner-to-public release upload still has
   to occur. No GitHub connector in this environment exposes the
   private bytes or an upload-release-asset action. Do not fabricate
   the contents or replace genesis.
2. `release/chain31340-public-release.json` explicitly has EMPTY
   `originalGenesisArchiveSources` and
   `replaceablePeerDirectorySources`. Real independent mirrors
   and a verifiable changing-peer publication mechanism must
   be implemented and observed. A first-online isolated node does
   not need a peer hint; a later node needs real rendezvous.
3. The currently proven IPv6 overlay is the public controllerless
   ZeroTier ad-hoc network. It is open-membership, but **not yet
   transport infrastructure independence**. Future direct native
   Internet P2P and replaceable overlay/DNS/DHT strategies require
   actual third-party ISP tests and must never hardcode owner VM IP.
4. The candidate peer ENR/EL enode auto-refresh/reannouncement after
   dynamic IP change is not yet implemented; R137 currently disables
   Lighthouse ENR auto-update for the tested 6plane design.
5. Full CI and user VM4707 suite for all R147–R152 changes are not
   yet observed, and no third host has actually synchronized yet.
6. Validator BLS/key custody, **actual** 32-test-ETH deposit
   funding/activation, adaptive SSE committee/settlement, and
   real provider/consumer/monitor service deployment on chain31340
   remain uncompleted. Selecting a role is not meeting its
   staking, bonding or physical-world obligations.
7. R151/R152 are first-implementation slices; complete
   idempotent recovery from partially created Docker resources,
   alternate transport implementations, complete local service
   UI and role uninstall/upgrade require observed failure testing.
   DO NOT blindly delete a partial data directory or duplicate a VC.

## Research outcomes and acceptance

Initial research fleet: preserve original VM4706 signing node and
VM4707 nonsigning node; two new larger VMs can join as independent
**nonsigning** EL+CL peers, then independently keyed/funded validators;
four new 2-vCPU/4GB/40GB VMs initially host lightweight actual
consumer/provider/monitor agents. Do not count machines sharing
cloud account/ISP as independently controlled operators.

True user acceptance is: **on fresh Ubuntu**, one reviewed public
installer download, **only one role-selection interaction**, then
automatic verified source+package+original genesis+P2P+role
installation, no admin whitelist, no fixed bootnode/IP, and actual
finalized on-chain economic actions. An outsider on an unrelated
ISP must reproduce the join after the original machines/discovery
publishers are unavailable. The current repo does **not** pass
that acceptance yet.

## Deferred paper-ready full refactor

Only AFTER the actual multi-host measurements and adversarial
tests have finished:
- Audit and remove dormant 31339/Anvil/QBFT/Tailscale permissioned
  production paths; retain scientifically labeled historical
  experiment fixtures in an archive only as necessary.
- Consolidate GitHub stacked PRs, directory layout and duplicate
  preflight scripts; one canonical launcher/installable package.
- Unify contracts' current fixed 4/3 quorum and V2 adaptive
  ledgers into one audited upgrade/deployment mechanism.
- Reproducible one-command release with pinned binary/image
  versions, public immutable genesis, peer discovery,
  no privileged owner dependencies and secure wallet custody.
- Full architecture diagrams, reasoned algorithms/parameters,
  threat model, proofs and counterexamples, performance datasets,
  gas/latency/resource experiments and paper reproducibility
  instructions including deployment receipts and expected outputs.
- Document what is genuinely permissionless versus dependent on
  valueless TEST ETH faucets or third-party transit infrastructure.

**Do not describe a successful unit test as a successful actual
remote network/validator/resource-market experiment.**
