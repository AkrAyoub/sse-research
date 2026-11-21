# R146 — Corrective audit: zero-interaction onboarding based on REAL prior SSE VM evidence

**Date:** 2026-11-21. **Priority: blocking.**
**Operator clarification:** SIX fresh VMs are already provisioned. The
operator explicitly rejects further per-VM manual installs, SSH deploy-key
creation, choices, commands, wallet generation or configuration. The
operator may authorize making source publicly readable after a security
review. We MUST NOT tell them to run R145 or call a read-only plan
"automatic installation".

## Proven historical evidence, not an imagined fresh Ubuntu machine

### Current working chain31340 (preserve)

- VM4706: original live Besu EL + Lighthouse Beacon CL + sole active
  original signing VC and separate local state. Never clone/reuse its BLS
  wallet, genesis, chain data, signer or Engine JWT. Do not edit or stop
  its services to bootstrap newcomers.
- VM4707: real nonsigning independently running Besu EL and Lighthouse CL
  with native P2P peering and same chain finality. Operator R141 capture:
  EL genesis hash
  `0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf`,
  Beacon genesis validators root
  `0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd`,
  finalized epoch 204, EL peers 1, CL peers 1, no reported syncing,
  optimistic execution or EL offline, head slot 6682, execution height
  5072 (captured at 2026-11-21T22:16:38 UTC). These are ACTUAL
  observed facts, not an installation fixture.
- Original exact archive SHA256:
  `1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7`.
  R59 carries SHA256 for every genesis member and exact immutable
  Besu/Lighthouse OCI image digests. Reuse these pins; do NOT create
  a second genesis, replace working chain or accept chain ID alone.
- ZeroTier ad-hoc PUBLIC network ID `ff2328775f000000`
  assigns actual dynamic 6plane IPv6. The overlay's controllerless
  membership reduces onboarding admission authority but root/relay
  infrastructure still matters. It is not a public Internet native
  EL/CL proof, and same-cloud nodes are not independent ISPs.
- Real VM4706 initially had 4 vCPU, ~11 GiB RAM, ~93 GiB free disk,
  Ubuntu 24.04, provider-private 10.50.56.2, no public ingress
  established; VM4707 also operated behind private provider LAN.
  **Provider-private LAN may NOT be advertised as native blockchain
  peer network**, even though historical SSH/SCP was used there.
- Actual Docker socket issue: daemon active, regular user not in docker
  group; `sudo -n docker` with reviewed least-privilege local
  policy is a known working mechanism. Do NOT assume `docker info`
  succeeds unprivileged, add arbitrary users to a root-equivalent
  Docker group, or expose docker.sock via web UI.
- Historical networking failure modes included ZeroTier relay/PLANET
  dependence, mismatched EL/CL listen/public port mappings, no native
  handshake before corrected R59/R60+, and device attachment/reboot
  trouble in R92. Do not declare port publication or overlay membership
  equivalent to native Besu + Lighthouse synchronization.
- Historical chain31339 and Anvil/QBFT lab artifacts cannot bootstrap
  real chain31340. A private 31339 deployer key/faucet and hardcoded
  seven role wallets must never become public node onboarding.
- Operator's currently created additional VMs: two larger
  ~4-vCPU/12–16-GiB instances, four smaller Ubuntu 24.04 2-vCPU/4-GB
  RAM/40-GB disk instances. The small machines are initially fit for
  lightweight consumer/provider/monitor services subject to measured
  actual available capacity, NOT an unreviewed simultaneous Besu+
  Lighthouse deployment.

### Recent verified code gate, not operational deployment

At R144 pinned commit `6da0c668a23fdfec5d006a6da206dac0ce066cca`,
VM4707 actually ran **974 tests in 15.017s, OK, 3 skipped**.
R145 code was written after that and **HAS NOT BEEN RUN ON A VM**.
Its nine shell tests, even if green, could not establish installation,
peer admission, validator activation, live funding or resource delivery.

## Source audit of proposed R145 and predecessors (2026-11-21)

| File | Actual mechanism | Zero-interaction deficiency / unsafe assumption |
|---|---|---|
| `scripts/sse_fresh_vm_source_bootstrap.sh` | Requires `--ssh-key`, already provisioned private deploy key and separately authenticated known_hosts; `--apply` requires TTY and typed phrase | Circular dependency: cannot execute `scripts/` on a brand-new VM without acquiring the script first. Mandates per-host owner setup, private GitHub, manual SSH key distribution. **Do not recommend to operator.** |
| `tools/sse_join.py` | `--roles` or interactive menu + R143 local host inventory; `--observer-plan` calls R137 `--plan` only | It never installs or activates provider, consumer, monitor, validator or EL/CL. User selects a role but gets a PLAN, not an installed capability. Interactive fallback violates stated no-input requirement. |
| `tools/sse_pos_r137_independent_observer_create_once.py` | Existing real create-once Docker EL/CL code, pinned R59 original archive and image verifications, private JWT, fixed local EL/BN localhost ports, runtime `--pull never` | Requires artifact/image/ZeroTier/Docker/manual manifest and public peer feeds first; TTY typed consent; no unattended guard tied to actual provisioning; no dynamic address reconciler; no transactional partial-failure recovery; source tests only for new arbitrary fresh hosts. |
| `tools/sse_pos_r142_public_peer_discovery.py` | Two HTTPS directory sources, exact chain roots and fresh endpoint hints | No real public mirrors operated, no signed publisher/dynamic identity, no tested protection from mirror/peer Eclipse attacks. A syntactically valid ENR is NOT an authenticated live Ethereum peer. |
| `tools/sse_pos_r143_new_vm_readiness.py` | Read-only host CPU/RAM/disk/binary inspection | It is not package/bootstrap installation. Its per-role numbers are advice, not protocol eligibility; absence of a tool cannot permanently block network admission. |
| `scripts/DeploySSEPos.s.sol`, `tools/sse_pos_live_roles.py` | Historical scripts for chain31339 | Never redirect blindly to chain31340; current SSE V1 also hardcodes k=4/q=3 and unsafe randomness assumptions. |

**Additional hard blockers:** whether GitHub repository history contains exposed
mnemonics, private keys, portal infrastructure or sensitive records is
**not yet fully audited**. Publicizing the existing private repository
without a history/secret scrub could disclose material beyond valueless
test funds. Prior journal explicitly records a compromised historical
validator mnemonic. Neither an unauthenticated mutable branch
download nor blindly trusting a `curl | bash` script is acceptable
bootstrap provenance.

## Required revised implementation contract

### Operator experience

- For **NEW cloud VMs created from now on**, one preauthorized immutable
  cloud-init/user-data boot profile delivered by the infrastructure at
  provisioning time must automatically perform the entire reviewed
  installation and provide a role-independent identity. User need not
  SSH and answer menus or create deploy keys. The role selection is
  encoded as a **data profile** given to provisioning, not a terminal
  prompt. If the infrastructure cannot inject user-data or initial
  remote execution, a precreated empty VM cannot start the installer
  magically from GitHub.
- For **already provisioned six VMs**, the project needs an
  authenticated management channel (existing cloud provider orchestration,
  cloud-init restart with approved user-data, SSH integration, or
  other authorized remote executor). Merely changing GitHub cannot run
  code on machines we cannot access. Do NOT claim automatic install
  until such a channel exists and is owner-authorized.
- No hardcoded fixed VM4706/4707 IP, private LAN/bootstrap-only
  exception, one mandatory publisher, one permanent validator roster,
  or arbitrary total network node/role cap.
- The user does not personally run per-VM package or key-generation
  commands. Remote unattended installer generates node-local keys
  safely and records **only nonsecret public identity/health outputs**.
  Wallet/validator signing and TEST ETH spending require policy-
  constrained preauthorization or a safe pending state, never
  fabricated funding/activation. No exposed mnemonic or auto-signing
  with copied original key.
- A **single repository** contains installer, all roles, contracts,
  node UI, tests, peer discovery and real evidence services.
  Source can be publicly mirrored **after full history/secret audit**,
  with immutable artifact checksums and reproducible signed releases.
- The installer must be idempotent/resumable on failures, preserve
  existing owner/observer state, never delete client datadirs
  automatically, never duplicate a validator signing identity and
  never restart the original chain without explicit reviewed rollout.
  Auto-update must not silently introduce incompatible EL/CL forks.

### Acceptance gates in exact order

1. **Security/release audit:** scan tracked files and reachable git history
   for sensitive signer keys, previous mnemonics, local credentials,
   private cloud and identifying data. Review default branch and
   cumulative research PRs, choose publishable audited history before
   making any repo public; pin exact public source release SHA,
   release signature/checksums, pinned Docker image digests, original
   chain31340 archive.
2. **Infra handoff design:** identify which real provider API/cloud-init
   channel can install software on **already created** VM4708–VM4713
   (actual VM identifiers must be observed, not guessed).
   No remote shell access has been granted via GitHub connector.
   Operator may supply cloud auth through a supported, authorized
   tool, not paste passwords/secrets into chat.
3. **One unattended provisioning agent:** install minimal audited
   packages, Docker with known privileged socket constraints,
   overlay or replaceable public-native P2P transport, checksum-verified
   pinned clients and original genesis; generate unique local
   Engine JWT/node identities in owner-private storage; read
   explicitly selected role profile; start safe nonsigning node only
   where selected and resource-eligible.
4. **Dynamic discovery**: operate >=2 actual independently
   mirrored sources containing real native EL enodes/CL ENRs, refresh
   after public dynamic address changes, prove genuine EL+CL peer
   handshakes and finalized chain agreement without owner approval;
   prove recovery when original seeds and a mirror are offline.
5. **Validator activation**: independent BLS key custody, actual
   standard 32 TEST ETH deposit per validator, activation, slashing
   protection, proposals/attestations, rewards and fault-domain logs.
   Never assume selecting `validator` creates an active validator.
6. **App roles**: install provider/consumer/monitor agents as
   lightweight services even on 4-GB machines, then conduct real
   chain31340 consumer escrow, provider capacity/HTTPS work,
   monitor bond/selection/physical probes, sound EIP-712 evidence
   and conservative settlement. Current fixed 4/3 design is a
   blocker for claimed adaptive public research.
7. **Measured experiments**: same-host and distinct ISP, variable
   node/validator/monitor/lease populations, gas/budget-limited dynamic
   committee k/q, actual CPU/RAM/disk/latency, partitions, timeout,
   service errors, fallbacks and adversarial evidence; archive
   finalized receipts and original logs, no synthetic success.

## R145 immediate disposition

**R145 source-bootstrap is DEPRECATED AS THE USER'S ONBOARDING PROCEDURE.**
It may remain in git only as a clearly labeled development experiment;
do not instruct the operator to run it, make SSH deploy keys, or type
installation prompts on six new machines. Replace it with reviewed
unattended cloud-init/authorized-remote-execution and signed
publishable release, then verify real host outcomes. Existing
R144/R145 unit tests alone do not release-block correctness of
the complete external join.

Nothing in this document changes the running chain31340 or grants
permission to publish the private repository automatically.
