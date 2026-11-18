# ADR-004 — Stable node identity, dynamic IP failover and truthful VM failure handling

**Date:** 2026-11-18. **Status:** accepted architecture; **only bounded SSH discovery fallback is implemented in new source and tested offline**. It is **not installed on the live pinned-c9c3afa VMs**. The already implemented Tailscale enrollment primitive has **not** passed a real tailnet/VM integration test.

## Incident that motivates this ADR

After lease 1 was funded at Anvil block 25 and accepted at block 26, multiple Ubuntu VMs restarted. The existing blockchain VM `ayoubakrvm4695` retained its ED25519 SSH fingerprint `SHA256:Xw3anupwwpofutE6sm0c8sRHi1NjDHALCaLWfK17LUA`, but its eth0 changed from `10.50.56.20` to `10.50.56.14`. The `sse-rpc-tunnel.service` on Consumer VM4693 continued to connect to `.20`, received `No route to host` and restarted more than 1,700 times. The reused IP `.14` formerly belonged to Monitor VM4699; strict SSH correctly rejected it as a different host. VM4699 has **permanently failed**; its original wallet cannot be accessed, although its on-chain bonded candidate and inclusion in assignment 1's block-25 snapshot remain.

Anvil on the blockchain VM still answered on loopback at block 26, including **status-1 receipt for Provider acceptance** `0x15f0331a3a9ebeb22df7450452e6756b45dd08ac27955d64902fb19e2486f648`. **Do not recreate the chain, redeploy contracts, re-register wallets, refund, rerun lease funding or fabricate committee confirmations.** Verify state after repairs.

## Immutable identity and mutable locators

| Layer | Identity | Ephemeral locator | Security rule |
|---|---|---|---|
| Application operator | encrypted EOA + unique persisted SSE node ID | address on private network | wallet/key never replaced silently; node ID not an authentication credential |
| Machine/transport | SSH ED25519 host key (lab), overlay device identity (target) | DHCP private IP, tunnel route, overlay endpoint | verify cryptographic identity against **independent pinned key**, not first returned IP; duplicate SSH host key at two IPs fails closed |
| On-chain lease | chain ID + deployed contract IDs + lease/assignment IDs + transaction hashes | RPC endpoint | revalidate chainId 31337, bytecode/contract domain, canonical block-hash and receipts before signing |
| Workload | immutable content/image digest + signed request/response IDs | service endpoint URL/forward | never substitute another container solely because its address responds |
| Observer | durable canonical block/log cursor + local signed evidence journal | RPC/peer session | resume/backfill after outage, reconcile reorgs; do not equate a successful reconnect with evidence of service |

## Network decision

**Long-term approved target: identity-authenticated outbound overlay (Tailscale/WireGuard-class) with per-node stable mesh names, route recovery and restrictive ACLs.** The repository already has `tools/sse_vm_overlay.py` and `tools/sse_vm_enroll.py`; existing `docs/research/R6_UBUNTU_AUTOMATIC_OVERLAY.md` correctly marks real broker/tailnet enrollment as *unverified*. Do not pretend its installation/ACL setup is complete. Provider, Consumer and Monitor VMs use outbound connectivity, no publicly exposed Anvil RPC and no shared Ethereum signing key. Need an actual approved tailnet, tagged ACL and enrollment broker or equivalent before deploying. The overlay controller/relay is a **connectivity availability/trust assumption**, not a settlement oracle.

**Immediate private-lab fallback, explicitly opt-in:** `tools/sse_ssh_identity_tunnel.py`. It searches only an operator-approved private IPv4 /24 or smaller for the **single exact operator-pinned ED25519 public host key**; it does not update trust on first use or clear old known_hosts entries. Its dry-run reports a candidate but does not trust an SSH handshake. `--run` launches the normal SSH binary with `HostKeyAlias`, dedicated 0600 pinned `UserKnownHostsFile`, `StrictHostKeyChecking=yes`, an owner-only SSH client key and a local-only `127.0.0.1:<port>` forward. SSH verifies actual ownership of the host private key *after* scanning. 0 or multiple matching hosts => fail closed. Restarts rediscover the peer's current private IP without changing a fixed Anvil endpoint at localhost. Do NOT enable on a foreign subnet or assume it works across subnet changes. A bounded /24 scan is authorized **only** inside the lab and is not an internet discovery system.

**Important unresolved source-address issue:** Today Anvil SSH `authorized_keys` may constrain source addresses via `from="10.50.56.8"`. If the *client* IP changes, automatic destination discovery alone will NOT restore SSH authorization. The preferred overlay approach uses stable client device identity and peer/tag ACLs. An interim, explicitly reviewed same-subnet `from="10.50.56.0/24"` restriction still requires cryptographic per-client keys, `restrict,port-forwarding,permitopen="127.0.0.1:8545"`, strict routing/SSH firewall and source subnet isolation, but **widens source address eligibility** and must be independently approved; never change it implicitly. Do not remove all source restrictions and do not enable arbitrary remote command execution on the SSH tunnel key. Store unique tunnel keys per owner VM, not on a central broker.

## Process, retry and reconciliation semantics

1. Persist Anvil chain state, monitor journals, Ethereum keystores, SSH/overlay keys and role manifests **outside** the Git checkout and ephemeral `/run`. On VM reboot systemd resumes Anvil, read-only agents, and foreground peer tunnels. Do not blindly start any key-bearing transaction agent.
2. A systemd service for a pinned SSH tunnel uses `After=network-online.target`, `Wants=network-online.target`, `Restart=always`, `RestartSec=20` to avoid subsecond retries; on each new start the resolver discovers the current peer by identity. SSH exits after peer loss, triggering rediscovery. The live unit has not been updated; review and install using an explicit change window and capture unit/journal evidence.
3. Readiness requires (a) known peer identity verified; (b) localhost RPC responds; (c) chain ID and known contracts validate; (d) expected receipt/canonical block context survive. A tunnel reconnect is **not** proof that the chain has the same state after an Anvil restart.
4. Each monitor replays on-chain CommitteeAssigned/EpochAdmitted from its durable cursor with block hash/reorg reconciliation (existing `tools/sse_monitor_discovery.py` prototype). Missing events/observations during downtime must be recorded as **gaps**, not backfilled as pretend live probes. Signed evidence and delivery journal processing must be idempotent and linked to on-chain request/epoch IDs.
5. Outages create liveness states `ONLINE`, `SUSPECT`, `OFFLINE`, `RECOVERING`, `READY`, `RETIRED`. Reconnect starts `RECOVERING`, not automatic committee eligibility or SLA proof. Only verified local keys, current chain state, signed service checks, due windows and human-approved role signing can restore `READY`.
6. Keep bounded retries and distinct metrics for IP readdressing, authentication failure, chain RPC downtime, provider service downtime and observer outage. A host-key mismatch must fail closed and alert; it is never silently whitelisted.

## On-chain liveness and scientific truth

- **Pre-epoch:** committee size is **four confirmations**, not 3-of-4. `SSESettlement.replaceNoShowMonitor(leaseId)` works only after its confirmation deadline, with a **seed-derived currently active bonded standby**, never caller-chosen. The original lease can continue if a valid standby exists. It does not manufacture a vote or slash anyone.
- **During epoch:** **3-of-4** monitor voting quorum may tolerate one unavailable monitor; not two. This does not prove honest reports, physical independence, or justify declaring a provider failure solely from missing network traffic.
- **Provider restart/outage:** differentiate transport/monitor unavailability from signed service result. The committed current SLA includes `TIMEOUT_IS_INCONCLUSIVE_V1`. Missing evidence/timeouts do not automatically imply an authenticated physical failure; execute contract windows/escrow and dispute policy faithfully, recording missed deadlines and impacts.
- **Permanent loss:** on-chain registered EOA remains an identity unless the wallet can sign `requestExit`, or a future audited protocol explicitly supports liveness-based removal. **VM4699's signer is unrecoverable**; do not import its public address into a replacement VM or pretend its candidate is eligible for a fresh experiment. Its bond may be irretrievable under this contract. Its selection can potentially be repaired by a *live* standby after the expiry of the pre-epoch no-show window. If standby is exhausted, fail closed and use lease close/refund and pool expiry/release rules; don't lower the four confirmations.
- **Original assignment 1:** snapshot taken at block25 contains VM4699's address. At last direct on-chain observation Provider accepted in block26; candidate election status and `randomnessTimeout` must be verified against **block timestamp** before mining. If expired, `OpenMonitorCommittee.expire(1)` is permissionless and `SSESettlement.closeLease(1)` is Consumer-owned; inspect the contract path, escrow credit and future withdrawal carefully. Some `closeLease` paths do **not** automatically cancel an awaiting delayed-block pool snapshot, so do not assume no funds or bonds remain locked.
- **No automatic EOA move or gas action on restart:** all transactions remain signed solely by the correct wallet, with explicit cap/preflight, and no automatic re-send of uncertain tx hashes. Never reset account nonces or reuse prior signed epoch payloads.

## Tests required before claiming solution deployed

1. Move blockchain VM IP to a reused Monitor IP; the **same host public key** is found, strict SSH reconnect succeeds, localhost chain/receipt/contract checks agree, no redeploy or duplicate transaction.
2. Change the **client** IP as well; verify overlay ACL identity or reviewed dynamic-source SSH policy, not a hidden reliance on `from=<old IP>`.
3. MITM / unexpected new host key / duplicate matching host keys / no available host: no SSH tunnel established and no transactions signed.
4. Reboot Provider/Consumer/each Monitor mid-request, mid-committee confirmation, and mid-epoch; distinguish reconnect from correct signed backfill and time-window compliance. Verify all local encrypted keys and journals survive.
5. Permanently lose one selected Monitor vs one standby; verify 4-of-4 confirmation after valid standby replacement only, and fail-closed when no standby survives.
6. Lose one vs two voting Monitors after epoch admission; verify true 3/4 quorum condition and timeout-inconclusive semantics, without invented SLA failures.
7. Restart Anvil with persisted chain vs wiped chain; on wiped/replaced chain detect missing receipts/code and **refuse** to attach stale transaction history to a different network state.
8. Test across more than one private subnet and unavailable discovery service (overlay/relay) before claiming universal IP-change tolerance.

**Current verification:** five offline unit tests for `tools/sse_ssh_identity_tunnel.py` passed in isolated Python environment as authored; GitHub source and tests are now committed. **No SSH rediscovery program or overlay reconnection has been deployed/tested on the live Ubuntu VMs**. Keep R5/R6/R9 original phase estimates unchanged until true end-to-end failure/recovery acceptance.
