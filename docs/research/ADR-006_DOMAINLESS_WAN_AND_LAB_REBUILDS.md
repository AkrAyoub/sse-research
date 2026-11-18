# ADR-006 — Domainless WAN admission, decentralized peer discovery, safe VM rebuilds

Date 2026-11-18. Status: **implementation and source tests underway; no real external host, Funnel endpoint or independent four-validator chain has been demonstrated**. No GitHub Actions.

## Why this decision

The operator has **no public domain** and wants any external Ubuntu machine to download the approved source and join the SSE network across home, campus and separate cloud networks. Earlier failures included a changed private VM4695 IP, an unrecoverable VM4699 signer and repeated SSH tunnel restarts, as well as non-unique portal hostnames and POSIX-only tests failing on native Windows.

**Immediate choice:** hosted Tailscale + MagicDNS + Funnel for *transport and enrollment*; native Besu discovery (bootnodes, peer gossip and optionally static peers) for *blockchain connection maintenance*; contract rules and QBFT governance for *authorization*. This is not anonymous permissionless validator admission.

Tailscale provides its own `<machine>.<tailnet>.ts.net` HTTPS name via MagicDNS. Funnel publishes the local enrollment service on public HTTPS port 443 without a purchased domain or publicly routable IP. A one-time owner approval for Funnel and tailnet ACL/tag configuration is required. In 2026 the CLI documents `tailscale funnel --bg --https=443 18781`; on Linux the operator reviews the result and may need to complete admin browser approval. Funnel has platform, traffic and port constraints and is **a public endpoint**.

References:
- https://tailscale.com/docs/features/tailscale-funnel
- https://tailscale.com/docs/reference/tailscale-cli/funnel
- https://tailscale.com/docs/features/magicdns
- https://tailscale.com/docs/features/access-control/auth-keys
- https://github.com/besu-eth/besu-docs/blob/main/docs/private-networks/how-to/configure/bootnodes.md
- https://github.com/besu-eth/besu-docs/blob/main/docs/private-networks/how-to/configure/consensus/qbft.md

## Three independent layers (never conflate)

1. **Transport admission:** Tailscale initially connects approved external machines. A dedicated provisioner at `https://enroll.<tailnet>.ts.net/v1/mesh/enroll` consumes a **one-time operator-approved, role-scoped, node-ID-scoped enrollment token**. Client `tools/sse_vm_enroll.py` obtains a 300-second auth key without receiving OAuth secrets; `sse_vm_overlay.py` joins the tailnet. Tailnet access policies must default deny and restrict P2P/agent ports by tag. The pilot broker currently supports application roles `consumer/provider/monitor/observer` only, not validator admission.
2. **P2P discovery:** Each Besu node has its own P2P private key (never copied or stored on GitHub). The operator publishes two or more mutually independent bootnode **enode public keys** with a fresh signed association to actual Tailscale device names/addresses, genesis hash and chain ID. After initial contact, Besu's native peer discovery can learn and maintain connections, and static peers can be configured for validator resilience. A signed catalog is only a bootstrap trust anchor and readdressing hint, not a centralized always-on block producer. A malicious seed cannot change signed genesis/chain identity. Signed catalog refresh does not magically hot-reload every Besu P2P connection: confirm client behavior and restart affected nodes under a safe rolling policy.
3. **Economic/consensus membership:** A new full node or app role does not become a consensus validator by joining Tailscale. QBFT validator addition/removal requires governance/votes; SSE monitors separately register bonds and satisfy committee eligibility, and all role wallets are generated locally with independent keys. Consumer/provider/monitor identities must be checked for prohibited self-attestation.

**Do not equate "decentralized discovery" with "anyone can become a validator".** Tailscale coordination is centralized; if fully permissionless transport is a research requirement, implement and test a non-Tailscale public UDP/TCP peer discovery path with authenticated ENRs, DHT/gossip, NAT traversal/relays, open admission rules, Sybil-resistance economics and separate validator selection. Headscale would replace the hosted control plane but needs a stable reachable control endpoint; it does not remove the need for bootstrap trust. No project claim of full permissionlessness is made.

## No purchased domain — controlled first deployment

On a **dedicated NEW Ubuntu enrollment VM**, not original Anvil VM4695:

1. An SSE operator creates a Tailscale account/tailnet, enables MagicDNS and configures default-deny ACL/tag ownership. Only the enrollment VM gets public-Funnel authority. Verify device and network roles and enable Funnel once in its admin approval flow. Provision the OAuth client on this protected broker host; keep its secret mode-0600 and NEVER in GitHub.
2. Install Tailscale from an approved, pinned package and verify it is online. Publish only the guarded `sse_mesh_broker_http.py` service on local port `127.0.0.1:18781` behind a reviewed, resource-limited service wrapper. Add external throttling/WAF/proxy controls. A Python `wsgiref` pilot endpoint is NOT a hardened internet service; leave public exposure off until a load/security review.
3. Run `python3 tools/sse_funnel_pilot.py` to review the action. On an explicitly authorized test host with review of public exposure, `python3 tools/sse_funnel_pilot.py --apply --i-accept-public-credential-endpoint` verifies the local broker and online tailnet, then runs `tailscale funnel --bg --https=443 18781`. Record the actual `*.ts.net` name from Tailscale; do not invent it. The browser/admin confirmation may be required once. A public Funnel URL is not an anonymous membership pass.
4. Optionally serve a **separate reviewed, signed and scrubbed source-release directory** through Funnel HTTPS port `8443` (supported port), strictly separate from the broker and wallet folders. Never serve a private Git checkout, `.git`, `.env`, SSH keys or real chain data. Tailscale Funnel limits transfer capacity; use a public GitHub release mirror or object storage instead if packages exceed tested limits. `tools/sse_signed_release_install.py` verifies publisher Ed25519 signature, chain/contract/roles and archive SHA-256.
5. A new external node receives a **publisher-public-key fingerprint pinned out-of-band**, a signed release, its approved node ID/roles and a short-lived one-time enrollment token via private authenticated channel. This initial out-of-band authorization cannot be removed merely by installing Tailscale; cryptographic trust roots must be established.
6. The node obtains vetted Python and Tailscale dependencies, runs signed-release install, then calls `tools/sse_vm_enroll.py --broker-url https://enroll.<actual-tailnet>.ts.net --node-id ... --roles ... --apply`. The client does not need the original VM's changing 10.50.56.x IP. It then uses its local encrypted wallet from `sse_vm_role_setup.py` and role-specific on-chain preflight/registration. No GitHub token shared.
7. If authorized as a Besu full node, read a signed peer catalog, check chain/genesis and make native P2P connections. If proposing a *validator* role, first obtain permission under a recorded QBFT validator voting experiment; never confer a vote by simply setting a CLI role string.

## How discovery survives failures

- **IP change:** Tailscale device key/MagicDNS resolve stable host identity; signed enode locator can be reissued; bootnodes and other peers continue peer discovery. Test readdress, state persistence and rejoin with the *same* P2P node key.
- **One bootstrap down:** Configure at least two independent bootstrap nodes; existing Besu peers should continue gossiping if their direct transport remains up. Quantify time-to-discover during a bootstrap outage.
- **Enrollment broker/Funnel down:** existing authorized nodes can remain connected; new outside admission waits. The broker is a known onboarding availability dependency; later add a backup service and signer-rotation procedure.
- **Lost node or cloned key:** fail closed; never invent/recreate historical EOA or validator identity. Revoke overlay device, preserve on-chain bond obligations and issue a *new* key only under governance.
- **Disjoint partitions:** fail closed on inconsistent genesis; QBFT four-node chain may halt after losing quorum. Do not mint fake blocks or force-enable an unsafe validator subset.

## VM lifecycle — choose REHEARSAL, OBSERVATION or FINAL; do not blindly reset

| Environment | Action | Why |
|---|---|---|
| Legacy Anvil VM4695 chain31337 and attached role agents | **PRESERVE** until lease1 escrow/refund/bonds and historical evidence are reconciled; keep baseline copy afterward if feasible | Real accepted provider transaction and funded obligations; cannot migrate by resetting |
| Dedicated small offline or one-host scratch laboratory | **DISPOSABLE** after exact Git SHA, logs, and test dataset archived | Useful for rapid syntax and config probes; not physical independence evidence |
| First cross-cloud validation fleet | **CREATE NEW** independent VMs; reuse/rebuild deliberately per fault experiment | Correct independent host and admin behavior; no risk to legacy escrow |
| Final demonstration / production-like network | **CREATE NEW GENESIS** only after integrated release acceptance and rehearsal results | Clean key custody, stable manifest, operational hardening, reproducibility |

A scientifically convincing experiment should test a fresh participant from an unrelated outside network. A full independent baseline ideally has **4 validator hosts + consumer host + provider host + 4 independent monitor hosts**, potentially plus a standalone broker/observatory. Where resources prohibit 10+ hosts, cohosting must be recorded as a limitation; NEVER claim four independent administrative failure domains just because four containers run on one host.

### Evidence that must exist before a scratch VM is deleted

1. Full immutable Git commit, signed source release, deployment/image digests, OS/client versions, R9 genesis JSON/hash, actual validator public addresses and unique machine/network identities (do NOT export private keys).
2. Test **inputs and outcomes**: gas limit, target period, offered load, random seed, number of replications, UTC start/end, host CPU/memory, peer graphs, proposer distributions, tx receipt hashes, block headers, CPU/network data and negative/failure test timeline.
3. Lab evidence bundle, hashed and reviewed, stored safely on the research machine or a secured archive, not only on the disposable VM. Use `tools/sse_experiment_evidence.py` to create a checksum index; that tool **does not copy logs** and always reports `vmSafeToDestroy=false`.
4. Chain/state snapshots or deliberately non-restorable declaration for disposable rehearsal; resolve all app leases, deposits and bonds first. Never delete live validator node keys or databases for a running persistent chain.
5. Fresh node rebuilt from zero using approved GitHub source, tested signed bootstrap, restarted and reconnected, with all phases repeated. Only then is a teardown meaningful acceptance test.

## Required validation matrix

- **Install and discovery:** fresh Ubuntu 22.04/24.04, different private/public NATs, no static IP, no incoming port, unique hostname collisions, Tailscale key expiry, IP change, broker unreachable, bootstrap1/2 unreachable, invalid DNS, missing signed catalog, stale replay, wrong chain/genesis, wrong wallet/role, unauthorized monitor, duplicate keys.
- **Consensus:** four independent validators, head/hash agree at a common height, 0/1/2 failures, reconnect/restart, node key persistence, new full node, QBFT validator-vote admission, proposer/reward fairness, long partition, genesis mismatch, unauthorized RPC and P2P isolation.
- **App:** separate consumer/provider/4 monitors, 3-of-4 SLA vote threshold, selected/standby confirmation, no-show, remote compute and HTTP challenge, signed evidence and provenance, impossible/late/contradictory evidence, refund/accounting/gas caps.
- **Evaluation:** controlled 5/12s and 15/30/60M gas baselines, transaction rate and size, p50/p95/p99 latency, downtime and recovery, byte-size/gas relationship, per-VM resources and multi-run uncertainty. Do not call theoretical block-gas arithmetic measured TPS.

## Acceptance gates

G0 code/build: full Python/Foundry suite green on exact SHA (Windows POSIX tests appropriately skipped and Ubuntu executes them); EIP170 + gas results.
G1 WAN: actual out-of-private-infrastructure Ubuntu host enrolled using no purchased domain, stable identity, no inbound public IP and no GitHub token; packet/trust logs retained.
G2 QBFT: four distinct validators, stable genesis, changing IP, real gossip, failure quorum and recovery demonstrated.
G3 SSE: complete independent marketplace lease, evidence and settlement, with refunds/bond resolution.
G4 production-like release: clean new genesis, repeatable install, signed artifacts, recovery/rollback and public research report.

**No stage is considered accepted without execution evidence.** GitHub Actions remain prohibited; these commands are manual and source-pinned.
