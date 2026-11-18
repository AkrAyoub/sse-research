# R9 code rollout and VM lifecycle: GitHub first, no Actions

Date: 2026-11-18. **Source package, not a running four-validator network.**
Existing Anvil application leases and pending monitor stakes must be audited
before any old-system teardown or migration.

## Exact answer: Which machines should pull updated source NOW?

| Host role | Source action | Runtime action | Rationale |
|---|---|---|---|
| VM4695 original Anvil31337 | **NONE now** | **NONE** | Preserve funded lease1, provider acceptance, monitor bonds, chain state and traces |
| VM4693 consumer/monitor agent | **NONE now** | **NONE** | Preserve EOA, signed evidence, roles and current Anvil endpoint; cannot simply switch chains |
| VM4696 provider | **NONE now** | **NONE** | Preserve local provider signing key and provider-side delivery evidence |
| VM4700–4703 monitors | **NONE now** | **NONE** | Do not substitute historical identities or alter monitor voting eligibility |
| Lost VM4699 | **NEVER attempt key recreation** | None | Lost signer is irrevocable; fail closed, use governance/recovery |
| VM4704 **fresh R9** | After new GitHub commit validated on Windows, fetch/pin exact SHA with read-only host-specific Git deploy key | Run read-only doctor and Ubuntu security gate; explicit Tailscale login then create validator-1's own private key | Fresh disposable validator, chain31338 only |
| Future VM4705–4707 etc. | Bootstrap *same approved SHA* with own read-only deploy key or signed source snapshot | Run same one-command Ubuntu script with validator-2/3/4, each separately authorized | 4 independent consensus machines; never clone disk after identity creation |
| Future external consumer/provider/monitor | Verified signed release or own repo access | Enroll via HTTPS Tailscale broker; generate local wallets and register per-role on new chain | App nodes do NOT gain validator voting authority by joining mesh |

**A GitHub commit does not cause a VM to update itself.** No GitHub Actions,
remote push-to-VM, hidden SSH, or background agent deploys a source revision.
The operator or a locally supervised updater must pull each approved version.

## VM4704 facts established by operator

- Ubuntu 24.04.4, Python3.12.3, Git2.43, Docker29.1.3, Compose2.40.3.
- 2 vCPU, 3.8 GiB RAM, ~35 GiB free disk: enough for preliminary tests,
  but **not a scientifically representative high-throughput host**. Limit JVM
  heap, monitor memory and run larger benchmark arms on resource-controlled
  hosts; no performance claims before measurement.
- Old lab DHCP `10.50.56.20` was reused. It does NOT establish blockchain
  identity and must never be hardcoded as a persistent peer endpoint.
- Tailscale1.98.4 was installed but `NeedsLogin`; a running daemon does
  NOT mean admission. User must create/approve a tailnet.
- Docker socket restricted to root: `sudo docker info` succeeded, ordinary
  `docker info` did not. Do NOT chmod the socket or indiscriminately grant
  privileged Docker group access.
- This host's read-only GitHub deploy key works; original R9 commit
  `0f070f6f676336be3decc02a41dd2361cb81100e` was cloned cleanly,
  Ubuntu gate discovered and ran **50 tests, 0 skips/failures**.
- Exact SSH host public fingerprint was recorded separately, without
  exposing a private SSH key. The portal hostname is reused on other hosts;
  hostname is NOT accepted as unique identity.

## A. The one command for every NEW Ubuntu validator host

After a private GitHub read-only deploy key or separately signed release
provides an approved checkout with the actual full commit SHA:

```bash
cd ~/sse-r9
bash scripts/r9_ubuntu_firsthost.sh validator-1 FULL_REVIEWED_40_HEX_SHA
```

This script refuses root, non-Ubuntu/WSL, dirty tracked source and wrong
SHA. It prepares a local Python3.12 venv if absent, installs the approved
minimum dependencies, runs the **real POSIX Ubuntu security gate** (0
skips allowed), runs QBFT Python tests, prints a read-only host doctor,
records local logs and pip versions in `~/sse-r9-validation`, and makes
NO Besu keys until `--apply-identity` is explicitly given.

The read-only doctor can run standalone:

```bash
python tools/sse_r9_host_setup.py doctor --expected-commit FULL_SHA
```

The environment is not ready while Tailscale shows `NeedsLogin`. No
owned DNS name is necessary. For first lab setup:

1. Operator creates one Tailscale tailnet and approves an appropriate ACL
   policy; no validator secrets or Tailscale OAuth credentials in GitHub.
2. On VM4704, if the tailnet owner approves, run *interactively*:

   ```bash
   sudo tailscale up --hostname=sse-validator-1 --accept-routes=false --accept-dns=true
   tailscale status
   tailscale ip -4
   ```

   `tailscale up` may provide a one-time URL/browser approval. Never
   share its authentication URL/token. Tailscale's device identity and
   `100.64.0.0/10` address become independent of the 10.50.56.x DHCP
   subnet. Repeat using `sse-validator-2` through `-4` on different
   machines. Use restrictive grants and review tag ownership.
   The separate existing SSE HTTP OAuth broker is for application
   `consumer/provider/monitor/observer` roles, **not automatic QBFT
   validator voting rights**.
3. After Tailscale is online, run the same approved bootstrap with an
   explicit key-creation flag:

   ```bash
   bash scripts/r9_ubuntu_firsthost.sh validator-1 FULL_SHA --apply-identity
   ```

   Creates `~/sse-qbft-private/node.key` (0600) **only once**, and
   `validator-1.public.json`. Never commit, print or copy node.key.
   Re-running `--apply-identity` after creation is intentionally refused.
4. Obtain public host identity report via `sse_qbft_fleet_evidence.py collect`;
   never assume hostname distinctness proves physical independence.
5. After 4 reports pass the operator audit, assemble the shared genesis,
   verify Besu image version/digest, and launch the P2P-disabled canary.
   The four real validators start only AFTER approved signed peer catalog,
   actual canary genesis block0 hash and all host preflights.

Do NOT run the 4-validator Compose just because a first VM has a key.
Don't mix original Anvil wallet keys or private service agent secrets.

## B. Repeatable update command for stopped R9 machines

`tools/sse_r9_release_update.py` supplies an **exact-SHA approval gate**.
It only works with a normal private Git checkout with a vetted SSH deploy
key and correct Git origin. It will not update a node exposing the
standard local Anvil/Besu RPC listener. It refuses root, other operating
systems and tracked modifications. It does not modify Docker or chains.

```bash
# On a STOPPED R9 Ubuntu checkout, with the host's .venv-r9 active:
mkdir -p "$HOME/sse-r9-update-logs"
chmod 700 "$HOME/sse-r9-update-logs"

python tools/sse_r9_release_update.py \
  --approved-current OLD_PINNED_FULL_SHA \
  --approved-target NEW_REVIEWED_FULL_SHA \
  --private-log-dir "$HOME/sse-r9-update-logs"

# Only after reviewing and approving the exact fetched GitHub commit:
python tools/sse_r9_release_update.py \
  --approved-current OLD_PINNED_FULL_SHA \
  --approved-target NEW_REVIEWED_FULL_SHA \
  --private-log-dir "$HOME/sse-r9-update-logs" --apply
```

Upon `--apply`, Git fetches the reviewed integration branch; **FETCH_HEAD
must equal the approved new SHA**. The updater detaches at that commit,
runs the Ubuntu test gate and full Python suite, and logs results in the
private folder. A failure switches the source back to the earlier SHA.
No Git hard reset, no force, no automatic Docker start or restart, no
migration or chain write. This is **only source installation**; a *separate*
approved procedure must validate runtime compatibility and rollout each
consensus process. Any on-chain upgrade requires explicit contract/chain
state migration design, not just a Git update.

A locally stopped container without a listening port might not be fully
observable; the operator must confirm **all Besu services stopped** before
using this tool. Running it on old Anvil/agents is prohibited by policy
even if ports happen to be closed.

## C. Distinguish peer discovery and privileges

- Native Besu peer discovery: signed initial bootstrap P2P node keys and
  live peer gossip; IP address is only a routable locator. Signed catalog
  updates/restarts are governed by the operator.
- Tailscale: encrypted outbound overlay and MagicDNS, solves NAT and
  host-private DHCP. Its coordination server is centralized. Existing
  device keys are separate from Besu P2P/node keys.
- GitHub: immutable source distribution/approved release, not node
  discovery, consensus, or the authoritative network's on-chain state.
- On-chain SSE: provider bidding, consumer funding, independent monitor
  bonding and evidence voting. Monitor eligibility is not Besu validator
  admission.
- QBFT: four genesis validators and later governance votes. Rotating
  block proposers are not proof-of-work miners, nor native PoS reward/slashing
  without separate mechanisms.

No arbitrary Internet machine can automatically obtain validator status
by downloading code; request/admission and governance are separate.

## D. Test and rebuild policy

Each rehearsal VM carries an experiment ID and full source SHA. Preserve
raw test logs, observable signed public identities, Ubuntu/Docker/Besu image
versions, genesis block0 hash, measured delays/faults, and client metrics
outside the disposable VM BEFORE deleting it. No private credentials in
GitHub. A source log SHA256 is a *pointer*, not a backup.

Before updating the OLD app VMs for new chain31338:
1. Audit original Anvil31337 funded lease1, provider acceptance, bonds,
   selected monitors and unlock/refund/settlement traces.
2. Freeze and archive contracts, chain DB, agent journals and signed
   evidence. Keep sensitive wallets in separate protected custody.
3. Deploy a fresh new chain with unique keys and contracts and obtain
   new addresses. Re-register per-role on-chain under the new deployment.
4. Migrate application agents one at a time, with exact per-VM source
   revisions, explicit chainId/RPC/contract addresses and independent
   wallet owners. No hidden on-chain mutation or shared owner keys.
