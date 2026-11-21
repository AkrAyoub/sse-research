# R147/R148 — Public one-command source installer and first-peer semantics

**Date:** 2026-11-21. **Operator requirement:** a fresh Ubuntu VM downloads
ONE installer from the ONE public `AkrAyoub/sse-research` repository,
responds ONLY to a local ROLE SELECTION menu, and the installer handles
all other configuration automatically. Roles are independent choices,
not administrative admission privileges. Exact host IPs, VM names and
bootstrap node ENRs must not be compiled into protocol policy.

**Current development state:** R147 source bootstrap and role-selection
and R148 no-seed first-online-peer policy are committed. The full
chain31340 original-genesis artifact has not yet been confirmed on any
public mirror, public multi-source native ENR publication is not live
verified, and role-specific services/deposits are not yet automated.
**This is NOT a complete installed blockchain node. Do not tell an
operator that R147 source success means it joined or can rent resources.**

## What changed after the operator corrected the requirements

- GitHub now reports `AkrAyoub/sse-research` as **PUBLIC**;
  no GitHub SSH key, deploy key, PAT, invitation or known_hosts step is
  required to clone public source via HTTPS.
- R145's per-host deploy-key + typed-phrase route remains **disabled**.
- `scripts/sse_install.py` uses ONLY a single role selection prompt,
  or none when predefined `--roles` is used for cloud-init.
  It installs base Ubuntu signed packages without package-manager
  questions, pins source to one immutable reviewed SHA, reads local
  unique OS machine ID, reuses `tools/sse_join.py`, refuses existing
  signer/node state, and writes a nonsecret *requested-role selection*.
- It does NOT mark roles as activated. Installing git/Python is
  different from installing Besu/Lighthouse. It does NOT clone private
  validator keys, recreate genesis, transfer money, or announce
  successful native P2P peering.
- R148 `tools/sse_join_phase.py` models the fundamental first-peer case:
  an isolated first-online full node may start and advertise itself
  with **zero bootnodes** on the EXACT already-authenticated chain.
  With no live active validators there is no new block/finality.
  Joining peers with zero known peers wait for native peer discovery
  rather than inventing fake zero-cost synchronization.

## What "first to ever join" actually means

**Case A: first host online on the pre-existing original chain31340.**
It downloads public EXACT original genesis/fork state and can start
EL/CL without connecting to anyone. It becomes discoverable as soon
as there is a transport path and a real published native enode/ENR.
For progress/finality it needs the **actual existing genesis validator
key holder(s)** active, or a reviewed standard deposit/activation
path when chain activity permits it. R148 never pretends that an
arbitrary node with a different BLS key is a genesis validator.

**Case B: first ever host of a brand-new chain.** This requires a
reproducible, finite public genesis creation ceremony (chain ID,
execution genesis, Beacon state, fork schedule, initial
validator set/contributions). There can be ZERO initial network peers,
but genesis itself cannot be discovered from an empty world by
consensus, and a network without an initially active eligible
signer cannot finalize. Independent operator contributions before
genesis reduce central genesis custody. **This case is NOT a reason
to recreate our already-running chain31340.**

**Case C: unrelated later host.** It authenticates exact existing
genesis, discovers live peers from interchangeable dynamic ENR/enode
sources and native gossip, syncs both EL and CL to actual canonical
finality without an SSE admission approval. First boot should not
require owner VM4706/4707 specifically, a private provider LAN route,
or a static IP. NAT/CGNAT operators may be outbound peers; some
independent reachable peers/relays must exist for discovery. DNS,
public HTTPS mirrors, public DHT rendezvous and independent boot
nodes are substitutable *discovery mechanisms*, not network
membership or consensus authorities.

No networking algorithm can instantly find an unrelated remote
machine with ZERO possible reachable addresses, zero external
rendezvous reference, zero common discovery medium or published
records. "No hardcoded IP" is realizable; "no initial information
or communication substrate" is not. Immutable genesis identity is
a chain identity anchor, NOT a static network endpoint.

## Minimal pinned public-source installer usage

The operator should be given a **single reviewed download/execution
command** with an immutable Git commit SHA, such as:

```bash
curl -fsSLo /tmp/sse-install.py \
  https://raw.githubusercontent.com/AkrAyoub/sse-research/REVIEWED_COMMIT_SHA/scripts/sse_install.py \
  && sudo -n python3 /tmp/sse-install.py --commit REVIEWED_COMMIT_SHA
```

Here `REVIEWED_COMMIT_SHA` is a placeholder **until a specific
commit has passed VM regression and been reviewed**; it must be the
full 40-hex SHA, not `main` or a mutable branch name. `sudo -n`
avoids an unexpected admin password prompt: if privileged access is
not already enabled through the provisioned VM policy, it fails
instead of silently asking. Do not blindly pipe mutable network
scripts into a privileged shell. Verify SHA/source through an
independently trusted release manifest before deployment. A single
signed public installation bundle would remove the current
bootstrap SHA copy requirement from the operator's experience.

A `--roles full_node,monitor` flag supports fully unattended
cloud-init; otherwise the program asks once for numbered roles.
The currently committed installer performs **only base source
provisioning**, then reports explicit missing consensus/economic
release gates.

## Required to reach the complete requested behavior

1. **Public original chain31340 artifact:** export the same R59
   `chain31340-public-native-observer-v1.tar.gz` bytes, preserve
   `SHA256=1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7`;
   independently publish on multiple read-only public mirrors.
   This archive contains only public genesis/config/consensus genesis
   state and the public manifest, NO BLS signer or EOA secrets.
   Test downloaded byte digest and every R59 member digest before
   any EL/CL startup. It is NOT currently established as a
   public GitHub release asset.
2. **Real dynamic native discovery:** publish and rotate actual EL
   enodes/CL ENRs from independently operated reachable peers.
   No baked-in VM host address, bootstrap one-owner requirement
   or private cloud LAN. Allow first-online start with none,
   and later nodes to use several dynamically discovered reachable
   records; acceptance comes from real protocol handshakes and
   exact chain finality, not directory claim.
3. **Reuse genuine R59/R137 settings after preconditions:**
   immutable OCI image digests, isolated EL/CL Engine JWT,
   non-root read-only Docker images, private Engine8551,
   localhost RPC/Beacon APIs, selected IPv6 transport publication,
   native EL+CL P2P port mapping, verified actual peer counts and
   checkpoints. Deal explicitly with Docker daemon permissions
   from VM4706 log and relay/reboot issues from R92.
4. **One-role-menu end-to-end coordinator:** install genuine
   provider/consumer/monitor agents on 2-vCPU/4-GB VMs without
   two heavy full clients, and full nodes on larger VMs.
   The actual profile can always change locally; no global
   role count or manual whitelist. Wallet/BLS identity generated
   locally; test ETH funding and activation require real public
   faucets/sponsors, actual transactions, receipt/finality checks,
   no inherited VM4706 signer.
5. **Live chain31340 marketplace:** reviewed deployed resource
   board, adaptive committee/vote/settlement runtime and safe
   evidence/escrow pipeline, with real physical workloads and
   independent monitoring. Historical 31339 scripts or mocked
   VRF must not be silently used.
6. **Acceptance:** first peer (0 bootnodes), later peer
   from a truly external ISP, dynamic IP change, seed offline,
   third/fourth/fifth nodes, independent validator activation,
   real jobs, variable `N,k,q`, safe payouts.

## Public repository security note

Making the repo publicly visible does not imply its *history* has
been audited for previous mnemonic/keystore exposures. Historical
chain31339 validator mnemonic was reported compromised; NEVER reuse it,
and audit any other signing secrets, private infra material and
historic commits urgently. Source being PUBLIC is not proof
of safe software distribution.

## Source testing

```bash
.venv-tests/bin/python -B -m unittest discover -s tests \
  -p 'test_sse_pos_r147_public_install.py' -q
.venv-tests/bin/python -B -m unittest discover -s tests \
  -p 'test_sse_join_phase.py' -q
.venv-tests/bin/python -B -m unittest discover -s tests
```

R147/R148 remain GitHub-only changes pending the next VM4707 tests.
