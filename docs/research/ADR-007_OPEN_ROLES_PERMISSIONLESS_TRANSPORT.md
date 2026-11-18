# ADR-007 — Open role requests, permissionless networking, and validator eligibility

Date: 2026-11-18. **Approved as target architecture; code below is source
only. It is not evidence that live public P2P, staking, dynamic validators or
multi-VM consensus have been deployed.**

## 1. Correct the roles/admission mental model

**Five distinct checks**, never replaceable by one another:

1. **Source integrity:** source archive is verified against a publisher
   key and exact immutable GitHub revision; does NOT authorize a role.
2. **P2P connectivity:** bootstrap seeds from multiple independent sources,
   authenticated Besu enodes + native discovery and/or audited relay. No
   SSE administrator required for arbitrary external nodes to discover
   public network peers. Tailscale is ONE optional transport for controlled
   labs, not a mandatory shared account.
3. **Self-sovereign applicant:** `SSE_ROLE_REQUEST_V1` lists any subset of
   `observer,full_node,consumer,provider,monitor,validator` and is signed
   EIP-191 by the applicant's own wallet. Signed domain contains chain ID,
   genesis hash, nonce, expiry, node identity and requested roles. Any
   participant may create a request. Validation proves possession of
   the signing wallet only. **This is not proof of an independent human,
   physical VM, economic collateral, or consensus membership.**
4. **Objective eligibility:** checked by the responsible subsystem,
   not by matching a role label or Tailscale tag:
   - observer: verify genesis and synchronization;
   - full_node: verify reachable native P2P, persistent chain data and
     correct chain headers; request does not permit block proposal;
   - consumer: wallet control, correct contract/chain and enough gas/
     escrow for its intended contract operation; open entry;
   - provider: wallet, viable service resources and reproducible SLA
     probe (actual performance/delivery evidence), on-chain conditions
     and any economic deposit required by the deployed protocol;
   - monitor: independent self-controlled wallet, registered active
     on-chain candidate with sufficient bond, selection only for an
     eligible lease and exclusion of the lease consumer/provider;
     **a global bond never implies authority to vote on all leases**;
   - validator: independent secp256k1 P2P node key, correct genesis,
     connectivity, finality checks and actual membership in the
     consensus protocol's current validator set. Proof-of-stake
     eligibility, if selected, also requires objective stake, minimum
     resource commitment, activation/exit, slashing and rewards.
5. **Activation / ongoing authorization:** on-chain contracts and the
   consensus protocol enforce permissions, expiry, bans/slashing and
   conflicts **continuously**. A valid role request must never directly
   activate a role. Some roles coexist on a machine, but a monitor must
   not verify its own provider execution and two wallets on one host do
   not count as two independent monitors/validators.

New source:
- `tools/sse_open_role_requests.py`: verifies a short-lived canonical
  EIP-191 wallet-signed role request. Always returns
  `rolesActivated: []` and `eligibilityVerified: false`.
  It does not yet implement a distributed nonce replay registry or
  admission transaction; those are necessary before accepting state
  changes driven by role requests.
- `tools/sse_qbft_role_authority.py`: read-only compares at least two
  independently trusted chain31338 RPC views, common block hash,
  active QBFT validator set, and correctly derived node-key address.
  Merely requesting `validator` cannot pass as a QBFT validator.
  This is NOT a PoS oracle or proof of remote host independence.
- `tools/sse_monitor_role_authority.py`: reads
  `OpenMonitorCommittee.candidates(address)` and `minimumBond()`
  from two views and checks bond/active status, not lease-specific
  committee membership.
- `tools/sse_external_transport.py`: pure transport planning, does
  not modify the user's already connected Tailscale, and selects
  native-P2P/relay as first attempts for external hosts.
  **None of these four scripts completes every activation condition.**
- The old `sse_vm_join_preflight.py` remains the legacy Anvil-era
  source/context check; it must not be portrayed as the new universal
  role-admission gate. A later integration will replace its role parser
  once actual dynamic validator governance is implemented and tested.

## 2. Provisional QBFT baseline is NOT permissionless

Current Besu chain31338 uses four genesis QBFT validators; additional
validator addresses require existing-validator voting (or a separately
designed contract governance mode). It is PoA/BFT membership, NOT an
open PoS validator-selection protocol and NOT competitive PoW mining.

Research plan:
- **R9 QBFT baseline:** preserve fixed four-host configuration to
  measure block periods, gas, latency, fault tolerance and the existing
  SSE contracts. New non-validator full nodes can be public once
  the chain has reachable public discovery peers. Validator candidates
  may submit open requests, but voting remains QBFT-permissioned.
- **R10 open consensus comparison:** choose a real permissionless
  Sybil-resistance/consensus stack (e.g. existing public PoS network
  for on-chain SSE execution, or a self-managed PoS engine with
  stake-weighted validator selection and slashing) BEFORE claiming
  dynamic open validators and block rewards. Required evidence:
  adversarial Sybil tests, stake accounting, objective admission,
  key custody, liveness/finality, reward distribution, exits/slashing,
  join/leave under NAT, and realistic resource/throughput benchmarks.
  Merely adding `validator` to a Tailscale OAuth tag is NOT sufficient.

The **administrator** creates laboratory VMs, funds experimental gas,
provisions source releases, controls private infrastructure access, and
collects research evidence. That administrator should NOT get to veto
ordinary blockchain participation in the permissionless deployment.

## 3. What if the external user already has another Tailscale account?

**Do not `tailscale logout`, `tailscale switch`, `tailscale up`,
retag, or overwrite its current daemon.** A normal Tailscale client
uses one active tailnet at a time. Options, in preferred order:

1. **Native Besu devp2p over reachable public addresses** with
   authenticated enode identities and public discovery/bootstrap.
   Requires reachable TCP/UDP 30303 or audited ingress; many NATs block
   unsolicited inbound connectivity. No Tailscale account needed.
2. **Audited public P2P relay/bridge** if direct P2P is impossible.
   A relay must not become a consensus authority or wallet custodian.
   This relay and actual public P2P discovery remain to be developed
   and measured in the live network.
3. **Cross-tailnet device sharing** if supported and explicitly agreed
   by the user; Tailscale supports sharing an individual node with
   another account, but sharing individual devices is not an open
   decentralized peer-discovery protocol.
4. **Separate isolated userspace Tailscale process** on an operator-
   controlled lab node after explicit user consent, with separate
   socket/state and no takeover of the user's main daemon. This
   requires its own integration and security tests and is NOT
   implemented by the current scripts. No manual switching of
   a person's existing account as a side effect.
5. For a fresh controlled lab VM with no existing Tailscale account,
   the distinct one-use tag broker may enroll it noninteractively.

Do not confuse a Tailscale host in 100.64.0.0/10 with a publicly routable
Internet IP. It is private to the respective tailnet; another tailnet
does not automatically reach it just because the numeric range matches.

The existing signed `SSE_QBFT_PEERS_V1` catalog and source signer are
operator-maintained for the R9 lab. Fully open peer discovery needs
public bootstrap peers (multiple operators), native peer gossip,
and optionally signed per-node public locator announcements. It cannot
require the lab's privately signed validator roster to join as a
read-only public full node.

## 4. User-observed validation state and commands

- Windows `bb1877b2fc7ae2498521c1c5274de6d11a736531`:
  886 Python tests, 20 Windows skips, 144 Foundry passed.
- VM4704 is still at **`a084793d22928219a557a10e637a5347d6befd17`**
  (or must be checked with `git rev-parse HEAD`) and joined
  Tailscale as `sse-validator-1`, address `100.65.29.101`.
  The command `sse_r9_host_setup.py doctor --expected-commit bb1877...`
  correctly refused because the **checkout SHA did not match**.
  This is unrelated to Tailscale login and is not evidence of failure
  to authenticate.
- The new open-role and transport tools MUST pass Windows offline
  tests and native Ubuntu security tests at their own new Git SHA.
  No new machine, external P2P, role activation, or chain transaction
  was performed merely by committing source.

## 5. Acceptance questions deliberately NOT yet answered

1. Production-grade public bootstrap, signed peer advertisements,
   relay availability, and NAT-hole-punching feasibility with Besu;
2. Strong PoP and replay storage for distributed role admissions;
3. Fully automatic provider service benchmarking/SLAs;
4. Monitor conflict-of-interest detection across aliases and hosts,
   actual on-chain registration and lease-specific selection;
5. PoS validator admission, dynamic set and token economics if a true
   permissionless *validator* network is required;
6. Autonomous private-repo source publisher with secure release mirrors;
7. Full external cross-network join, broker outage, malicious API/peers,
   chain partition and VM destruction/rebuild experiments.

Sources (current public vendor docs):
- https://github.com/besu-eth/besu-docs/blob/main/docs/private-networks/how-to/configure/consensus/qbft.md
- https://tailscale.com/docs/features/client/fast-user-switching
- https://tailscale.com/docs/features/sharing
- https://tailscale.com/docs/features/access-control/auth-keys
