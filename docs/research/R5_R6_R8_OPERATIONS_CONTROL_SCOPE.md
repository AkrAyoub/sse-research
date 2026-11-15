# R5/R6/R8/R9 — VM fleet, NAT discovery, releases, operator console

**Status:** operator-requested scope specification, **not implemented**, **not an acceptance report**. 2026-11-15.
**Base:** R6 portal testfix commit `e44ade6b82afe99bd9f0b6377c2b9ba9aee6ebfc`. This file defines new work without changing contracts, existing tests, node processes, transactions, repository visibility, CI, or deployment.

## Scope mapping (baseline vs extension)

- **Existing R6 acceptance:** a new Ubuntu VM behind NAT joins without static public IP or manual peer edits (documented in `PHASES_TRACKER.csv`); installer today stops at pinned checkout + chain preflight + local read-only systemd heartbeat.
- **Existing R5 acceptance:** autonomous independently operated consumer/provider/monitor agents submit authorized transactions.
- **Existing R8 acceptance:** read-only, rebuildable chain-finance observatory and protected node console; existing `apps/control-plane/api.py` supports only local inventory/proposals/audit/scenarios and nonexecuting deployment plans.
- **Existing R9 acceptance:** reproducible independent failure/workload experiments.
- **New explicit scope:** safe release/update workflow for running agents; node-discovery control plane; independent full marketplace/operator/experiment dashboard. None of these should be called complete because a UI appears.

## Target architecture / trust boundaries

1. **Public onboarding site** (static, no credentials) distributes an audited/pinned installer and documents network setup. The source repository may later be made public only after history/secret/license review.
2. **Control-plane service** runs independently of provider/consumer/monitor machines. A separately hosted UI interacts only with its authenticated API, not arbitrary on-chain wallet secrets.
3. **Per-VM node management agent** establishes an outbound mutually authenticated TLS/WireGuard connection and registers a stable **node ID + public service identity + ephemeral reachable overlay address + capability inventory**. Store liveness and tunnel health; never assume node IP is static. Node enrollment is distinct from on-chain monitor registration.
4. **Network data plane:** choose an operator-managed WireGuard/Tailscale-style overlay for the lab, with DNS/service discovery based on stable node IDs and an authenticated relay/DERP-like fallback where peers are NATed. Avoid requiring incoming internet ports. Explicitly measure connectivity between independent VM operators; a lab overlay controller is a central **connectivity** trust dependency, not on-chain SLA authority.
5. **Blockchain read model:** index events, tx hashes, receipts, gas, block/header hashes, requests, bids, winning selection, lease states, committee assignments, qualified evidence references, epoch accounting and withdrawals from configured RPC. Persist chain ID, contract ABI/version and block-hash provenance. Detect reorgs and reconcile; never call a provisional/latest block finalized. This index is a rebuildable cache, not canonical authority.
6. **Off-chain evidence & observability:** each monitor/provider writes structured, signed local logs and raw immutable evidence; forward access-controlled metadata and hashes to an append-only archive. Dashboard links a record to its raw bytes, signature, event, block hash and qualification decision. Show absent/missing evidence explicitly.
7. **Control/API boundary:** RBAC roles: observer (read), consumer (its own requests/price caps, bid selection, payments), provider (its own bids, capacity, workloads), monitor (its own observation, bond, confirmation), operator (node/update/fault test). Transactions require the role's own signer or narrowly delegated authorization; dashboard/operator must NOT be able to forge unrelated on-chain roles or override contract payouts.
8. **Experiment orchestrator:** isolated lab-only authenticated actions to stop/restart provider containers or monitor processes, partition traffic and resume, with explicit target confirmation, time-bounded fault, automatic recovery, operator audit event and before/after telemetry. Never expose arbitrary remote shell or Docker socket to the public dashboard. Keep simulation/evidence/protocol outcomes distinct.

## Release/update mechanism (new R6 work)

**Goal:** after a new approved GitHub release is published, the fleet can receive a reviewed update without manually logging into each VM. A raw `git pull` of every `main` push is NOT safe for running money-handling services.

1. Review changes; build a versioned release manifest containing immutable Git commit, artifact hashes, dependency locks, supported role versions, ABI/protocol compatibility and publisher signature. Public deployment artifacts must be retrievable without injecting GitHub tokens into VMs.
2. A VM polls the approved release feed by **outbound HTTPS** (or receives an authenticated control-plane notice), verifies manifest signature/hashes/compatibility and reports available revision. Updates must not be triggered by arbitrary unreviewed pushes.
3. Download into an isolated staging path, not the live executable; verify and run offline smoke/config/chain preflight without loading signing secrets. Preserve state, identity, keys, journals and off-chain evidence outside the code release directory.
4. Operator approval / defined lab auto-rollout policy controls **apply**. Stop only affected role units, atomically switch release symlink after validation, restart systemd services and perform read-only health/end-to-end checks.
5. Rollback automatically on failed health (to previous executable revision, with explicit data/schema migration rules); never rollback blockchain transactions or erase irreversible signed observations. Record release events and hashes centrally and on node.
6. Stage **monitor and provider waves separately**; preserve quorum during rollout. Defer updates of actively assigned monitors and running provider leases unless planned maintenance/replication explicitly keeps their contractual obligations. Expose mixed-version compatibility and halt on mismatch.
7. **Different scope:** contract bytecode and deployed chain state do not update when GitHub code updates; deploy new versions/address by an explicit versioning/migration/governance plan.

**Initial acceptance:** use two Ubuntu VMs, deliver release A then B, prove both adopt B from outward-only network access, preserve identities and evidence, observe no unplanned quorum loss, and roll back a deliberately broken B while older A remains healthy. Test malicious feed, tampered hashes, incompatible ABI, interrupted download, offline node and replayed update.

## Independent Operations Console (new R8 extension)

### Views and operations
- **Fleet:** each node's stable ID, operator identity, role, capabilities, current revision, overlay connectivity, health, restart history, update progress and logs.
- **Marketplace:** create resource requests and price caps, browse open requests, provider bids and availability, compare bids, select winner and show on-chain funded lease with tx receipt. Bid choice stays with authorized consumer.
- **Leases:** provider acceptance, monitor sortition (seed/source/mode), committee and confirmations, per-epoch state, deadlines, funds/bonds/rewards/exposure, residual and withdrawals.
- **Chain explorer:** blocks, hashes, txs, emitted logs, calldata ABI interpretation, gas, chain status, contract addresses/version, reorg/finality qualification; display trust/source boundaries.
- **Evidence viewer:** real-time monitor probes (HTTP latency, status, signed digest, signer), provider service/job logs, raw off-chain archive, signature verification, hash cross-check and world-history narrowing. Mark any vote-only conclusions as conditional.
- **Control actions:** node config proposals, authorized role-bound consumer/provider actions, protected release upgrades/restarts and lab fault experiments (stop provider/monitor, network partition, restore). Every action attributed, audited and reversible when technically possible.
- **Experiments:** run IDs, wall-clock vs block-time distinctions, ground truth, all participant observations, on-chain outcomes, economics, failure-recovery latency, artifact export.

### Non-negotiable separation
The console may *operate managed lab machines* and *observe network state*, but it cannot have omnipotent authority over unaffiliated independent providers/consumers/monitors or force an EVM contract to make arbitrary settlement decisions. Avoid centralizing all signing keys, oracle truth, provider capacity or monitoring attestations. Use least privilege and explicit delegation, never a single god-token for all role signatures.

## Critical-path build slices and measurable gates

**Slice A — release/discovery foundation (R6, R5):** installer live Ubuntu test; public verified release feed; two VMs outbound-enroll and show stable IDs; mutually authenticated control channel; systemd versioned agent & read-only fleet dashboard.

**Slice B — independent on-chain actors (R5/R2/R3):** one consumer, one provider and at least four independently signed monitor identities transacting on shared Anvil over authenticated network; real request/bid/selection/escrow/confirm/vote/settle/withdraw trace. Separate operational nodes vs four signing identities transparently.

**Slice C — visibility and control (R8/R4):** event indexer and transaction explorer + role-bound request/bid/price UI + signed monitor/provider log/evidence archive; explicit physical-truth caveat and chain provenance.

**Slice D — faults and reproducibility (R9/R7):** stop actual provider container / monitor process, disconnect network, collect independent probe traces, verify no-show recovery and payout/held accounting, explain fault model and correct timing, export complete reproduction artifacts.

**Slice E — public testnet / research exit:** compatible deployment to Sepolia with only native test ETH; validated contract addresses, audited signing controls, finality/reorg qualification, repeated independent-VM scenarios, gas/statistical analysis and papers.

## Immediate risks / dependencies

- A public repository removes clone authentication but does not establish signed release provenance. Audit **all Git history** before changing visibility; private material remains in separate secret stores.
- Public repo GitHub Pages and authenticated private dashboard are separate hosting surfaces.
- The current website's `http://127.0.0.1:8545` refers to the VM where the command runs. Remote shared Anvil requires a secure tunnel/overlay on that VM; it cannot silently reach the Windows development host.
- The existing `tools/plan_deploy.py` is **planning only**, not an update actuator. The existing firstboot installer explicitly refuses silent upgrades.
- A `3-of-4` committee vote is not a sound physical-service certificate. Operator-driven fault injection must not be represented as decentralized oracle proof.
- No progress percentages change in the official tracker until target acceptance evidence is produced and reviewed.
