# R96 — Chain 31340 failure memory, recovery and deployment reliability contract
Status: incident record + design requirements, NOT proof of unattended recovery.
Incident date: 2026-11-21. Applies to VM4706 owner / VM4707 non-signing observer. Preserve prior R27–R70 evidence.

## Architecture invariants (do not regress)
1. Real Besu execution and Lighthouse beacon/validator PoS clients on chain ID 31340; never simulated blocks, consensus, SLA, or mining.
2. Original chain genesis, persistent Docker volumes/binds, validator signing keys, JWT, and preserved R65 migration containers are immutable recovery inputs. Never recreate genesis or spawn a second signing instance.
3. Ethereum peers use native EL RLPx/devp2p and native CL discovery/TCP/QUIC. ZeroTier public/controllerless overlay transports these protocols; proving Internet access by arbitrary external infrastructure remains a separate acceptance test.
4. VM4706 original private Docker bridge `sse31340-g2-internal` is `Internal=true`. Besu `sse31340-g2-el-r40` / `172.18.0.2`, alias `sse31340-g2-el`; BN `sse31340-g2-bn` / `172.18.0.3`. Port 8551 Engine API must never be host-published. VM4706 only signs through its original validator `sse31340-g2-vc` after manual signing safety checks.
5. VM4707 `sse31340-r59-nonsigning-bridge` is `Internal=false`; EL `sse31340-r59-nonsigning-el`, BN `sse31340-r59-nonsigning-bn`. No validator private keys or signer.
6. Required host-only read APIs on owner: 127.0.0.1:18545 (EL), 127.0.0.1:15052 (BN); observer: 28545 and 25052. Required native 6plane IPv6 P2P: EL TCP/UDP 30404, CL TCP/UDP 9000 and UDP/QUIC 9001. Do not publish local REST/RPC to 0.0.0.0, LAN, or 6plane.
7. Source, review, tests and reproducible deployment go through GitHub; no ad-hoc VM-only architectural drift.

## Actual 2026-11-21 failures, evidence and fixes
| Failure/observation | Evidence | Reliable lesson |
| --- | --- | --- |
| Host reboot before ZeroTier assigned 6plane IPv6 | Docker boot journals failed binding [fca0:...]:30404 and :9000 with cannot assign requested address | daemon ready != IP ready; gate on actual interface address AND route before start |
| Docker 29.1.3 containers running but no host ports | HostConfig.PortBindings populated, NetworkSettings.Ports null / empty; `docker port` empty | process running and even EL health healthy DO NOT prove host publication |
| VM4707 containers lost network attachments | NetworkSettings.Networks={} and Docker bridge Containers={} after reboot and restart | guarded `docker network connect` followed by restart restored same containers, internal IPv4, expected published ports |
| VM4706 retained attached endpoints but port publication absent | Internal=true bridge, 172.18.0.2/3 registered, effective ports null; restart and disconnect/reconnect failed | DO NOT blindly retry reconnect; internal-only network different behavior |
| Owner host relay R92 on internal bridge | Seven exact host socket listeners verified, localhost BN GET /syncing 200, EL eth_chainId=0x7a6c 200, systemd active no restart | host transport and RPC restored without touching Engine 8551; **native peer connectivity still unproven** |
| Historical checkpoint matches on 2 disconnected nodes | epoch 148 finalized root 0x9bbbe47799a6019692cc9ff8b92bf7a4274036d8482b93808c58f870cd6f4b39 on both | historical agreement != current finality, peers or live consensus |
| VM4707 -> VM4706 TCP reachability | native TCP 30404 and 9000 CONNECTED, both EL and CL peer counts 0 | socket reachability != Ethereum peer handshake, identity, discovery, QUIC nor chain synchronization |
| VM4707 BN repeatedly searches at peer_count=0 | logs low peer count, searching slots ~5941-5970; peer /peers empty | fix discovery/dial/UDP, not Docker by default |
| VM4707 EL EngineQoS warning | Besu "Execution engine not called in 120 seconds", despite earlier Lighthouse el_offline=false | EL HTTP responsiveness != working Engine API traffic; inspect authenticated Engine handshakes and BN state. Do not claim EL/CL healthy from one field |
| GitHub HTTPS authentication failure | password authentication refused; VM4706 existing readonly SSH key succeeds with explicit `GIT_SSH_COMMAND=ssh -i $HOME/.ssh/sse_vm4706_readonly ...` | fetch private source by existing pinned, readonly SSH identity; never ask for password or expose private keys |
| Over-eager install success claim | relay initially active but immediate curl failed; later all 7 sockets + both APIs verified | gate readiness on live listeners/APIs with bounded retries; `systemctl active` alone insufficient |
| Pasted commands have escaped/missing line breaks | earlier commands contain concatenated tokens and malformed curl flags | supply small, copy-paste-safe commands; separate dry-run and apply; validate actual terminal output |

## Deployment state machine (target design, not yet achieved)
`DISCOVER -> PREFLIGHT -> WAIT_FOR_OVERLAY_IP -> VALIDATE_DOCKER_NETWORK -> RECONCILE_EXISTING_EL -> RECONCILE_EXISTING_BN -> VERIFY_BINDINGS -> VERIFY_LOCAL_EL_BN -> VERIFY_EL_CL_ENGINE -> VERIFY_NATIVE_P2P -> VERIFY_SYNC_FINALITY -> READY`.
- Every step fail-closed with distinct diagnostic codes and structured logs. Retry only transient absence of overlay address, Docker readiness, and service startup; bounded backoff + alert escalation. Do not automatically change genesis, images, chain spec, secrets, role, IP, or trust boundaries.
- Start/restore only original known containers for repair. Exact network mode/alias/IP/port/JWT mount and expected genesis fingerprint checked before any mutation. Snapshot state for audit. Work per role. If mismatch: stop recovery and require operator intervention.
- Use systemd dependencies `docker.service`, ZeroTier availability plus **address-specific** `ExecStartPre`/equivalent; bring up networking in order, check effective publications, and retry safely. For internal-only bridge owner, restricted fixed-address host relay is required. Protect service from wildcard binding; never publish Engine 8551.
- Make readiness more stringent than process alive: exact EL chain ID, BN API, no optimistic execution, EL/CL Engine calls observed or authenticated relationship positively checked, native EL/CL peer IDs, reachable peer transport including UDP/QUIC, common finalized root and progress under active validators. If validator down, report `DEGRADED_NO_FINALITY`, not `READY`.
- Signing safety is a distinct manual gated transition: validate original keystore and slashing protection, confirm no duplicate signing process or migrated preserved container; never force a validator restart as side-effect of API/peer recovery.
- Preserve honest status: overlay route is NOT unconditionally globally reachable Internet; require outsider from independent provider under no fixed public IP to join with native EL+CL and sync. Evaluate restart, power loss, overlay loss/return, EL crash, BN crash, Docker daemon restart, lost Docker endpoint, stale ENR and invalid peer bootnodes in controlled tests.

## New VM onboarding reliability contract
- **Do not hardcode VM4706/VM4707 names, IDs, IPs or paths into generic deployment.** The R92 existing-node recovery scripts currently intentionally hardcode those two installed roles. Future onboarding requires schema-validated per-node manifest (chain/genesis fingerprint, role and signing capability, image digests, ports, overlay discovery mode and dynamic address, data/JWT mounts, network topology, bootstrap peer records).
- Generate manifest through reviewed GitHub code; no baked-in private key, copied validator wallet, fixed host IP or privileged Docker socket exposure. Join permissionless native PoS as an observer first; separately satisfy deposit/activation/signing requirements before enabling validator role.
- Make operations idempotent, crash consistent and observable. Use exclusive deployment locks; no duplicate Docker resources; verify existing chain state rather than overwriting. Backup and restore tests of key custody and slashing protection should not print secrets.
- Synthetic/tests are suitable for testing implementation logic only; SLA and network performance must be measured from actual resources and real independent peer nodes.

## Release gates / actions outstanding
1. VM4706 relay is installed and API works, but **EL/CL peering is still zero on both nodes**. Diagnose native Besu/Lighthouse bootstrap/dial, UDP/QUIC packet path, host relay UDP semantics and EngineQoS warning; do not infer protocol success from TCP_CONNECT.
2. R92 initial scripts and 8 narrow tests passed on VM4706; not yet tested in realistic reboot/power-loss/peer-fault exercises. PR #40 remains draft until rigorous acceptance. Audit host relay's UDP per-source proxy protocol suitability and rate limits; do not claim compatibility without real peering proof.
3. Enable and verify guarded boot recovery on both known VMs only after code review. Test repeated reboots, delayed overlay allocation, Docker restart and restored network attachments, relay startup ordering, idempotence and no validator auto-sign.
4. Confirm actual native EL/CL peers both sides, current matching finalized checkpoints, valid chainID/genesis and honest state transitions after safe manual validator recovery.
5. Add CI tests for all failure modes, integration tests on isolated ephemeral test networks, rollback actions, structured logs/alerts; only then promote GitHub PR.
