# R178 — Real VM4709 first native client run: restart loops, security blockers and reproducible recovery

Date: 2026-11-23. Original pinned R170 rollout; R177 signed APT repair. Operator-provided real VM4709 logs.

## Verified completed milestones and architecture

1. Public original chain31340 execution and beacon genesis archive, SHA256 `1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7`. Existing running VM4707 original signer/chain state must never be changed/reset.
2. A single real node VM4707 published its *live actual* Besu enode and Lighthouse ENR to one expiring public GitHub Issue #42 comment; VM4709 independently discovered it anonymously from public GitHub REST. Both a historical stale listing after PATCH and TTL expiry were reproduced. GitHub is temporary centralized rendezvous, not independent permissionless native discovery.
3. Actual fresh VM4709 Ubuntu 24.04 installation: original pinned `df3df85190789cc14fe6920a248f6a7545a44197` R170 public source and original genesis copied intact; observer selected to private root-owned 0600 `/var/lib/sse/selection.json`, node ID `node-8be265272c35f3d8c3a0`. Never rerun R147 or delete original state.
4. Observed and fixed installer integration failures (all from *real VM4709*):
   - R170 suppressed all subprocess failure details; R172 fixed bounded safe stage errors.
   - R172 unprivileged read-only inventory initially failed due root-owned 0700 selection parent; later R173 gate requires sudo.
   - R173 full suite attempted with fresh system Python and failed 34 imports from absent marketplace Python test-only libraries; 3/13/15/18 focused tests passed, later R175 18/3/15/18 and R177 21/3/15 targeted tests OK.
   - Root-owned selected original release and verified archive survived. R151 actual privileged continuation is required after R147 partial state, rather than resetting and repeating first role selection.
   - `https://install.zerotier.com/` HTTP 403 while pinned official public signing key downloaded (3175 bytes). R175 moved to upstream Noble signed-by HTTPS APT with pinned primary GPG fingerprint.
   - R175 generated malformed exact APT source with literal backslash+n instead of newline; observed `apt-cache policy zerotier-one`: no package. R177 fixed actual source generator and repaired only that exact previously created malformed line, preserving scoped signing key.
   - GitHub anonymous API rate diagnostic showed 44/60 requests remaining, but a public peer record had expired; refresh before an actual join, avoid treating temporary GitHub mirror as sustainable native discovery.
5. R177 actual R151 `--execute` successfully installed ZeroTier 1.16.2, joined public network `ff2328775f000000`; actual host VM4709 assigned dynamic IPv6 `fca0:2328:77e5:740c:ce60::1/40`. Docker created real dual-stack client network and *two genuine* pinned EL/CL containers, on the actual new VM. No validator signer, no new chain genesis. Local evidence systemd timer installed and active.

## NEW blocking evidence from REAL VM4709

User's 2026-11-23 VM4709 read-only R153 diagnostics show:
- `sse31340-r137-node-8be265272c35f3d8c3a0-el`: Restarting (1).
- `sse31340-r137-node-8be265272c35f3d8c3a0-bn`: Restarting (1).
- Besu image entrypoint repeatedly outputs `chmod: changing permissions of '/testnet/genesis.json': Read-only file system`; `su: cannot set groups: Operation not permitted`; `chown: changing ownership of '/data': Operation not permitted`. Existing R137 Docker run has deliberate `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`, and mounts original genesis readonly. **Do not weaken file/host security or simply enable privileged containers.** Investigate the pinned image's exact entrypoint/binary and correct nonprivileged execution.
- Lighthouse v8.3.3 boot log: `The current head state is outside the weak subjectivity period` when `Starting from known genesis state`; refuses to start and restarts. This is an intended consensus security safeguard, not a networking error. **Do not silently use `--ignore-ws-check` or purge genesis/DB**. First obtain a trustworthy finalized checkpoint from already-running chain31340 owner CL or establish if owner chain itself lacks live finality; require owner-controlled explicit experimental bypass only if justified.
- Lighthouse also warns `--port6`, `--discovery-port6`, `--quic-port6` are ignored when listening IPv6 only. Review command syntax and native port bindings; warnings are not demonstrated handshake failure yet.
- R153 returned `WAITING_FOR_ACTUAL_EL_CL_FINALITY` / `reason: Refused`, no evidence. The evidence timer is active, but cannot manufacture successful peers/finality.

**Important:** Actual container creation is confirmed but healthy operation, native EL/CL peering, finality, independent ISP connectivity, validator activation, market workloads and SLA measurements are NOT confirmed. Do not publish success flags for them.

## Operational recovery rules for new hosts

- Do NOT rerun create-once R147, R151 or R137 on existing R177 VM4709; they will fail or harm partial state. Preserve original genesis, selected role, Engine JWT, root data, Docker volumes and correct package setup.
- Before any change, capture READ-ONLY `docker image inspect` entrypoint/Cmd, `docker inspect` container user/caps/security/mounts, client logs and localhost-only official owner Beacon API finality checkpoint. Do not output Engine JWT, environment variables or wallet keys. Verify immutable images and exact original genesis.
- Any future repair of one already-created container requires explicit owner authorization, strict exact name/image/boot parameters, a fresh nonsecret configuration audit and reversible handling with no data root deletion. Never indiscriminately `docker rm -f` or reset database. No native P2P verified until local read-only APIs show EL and CL actual peers and same finalized checkpoint across hosts.
- Future `sse_install` must be an idempotent state-machine with phase journaling, signed prereqs, persistent true native dynamic bootstrap, startup readiness and recovery on known partially installed states. Adding a node must not require this sequence of GitHub comments, manual commands or operator login.
- An independently run release remains research-only until real native peer authentication/finality; recurring 600s GitHub comment TTL and shared infrastructure are known design shortcomings.

## Remaining scope for the complete academic project

- Repeat actual VM4707 and VM4709 native EL/CL status and **matching finalized root** under same epoch.
- Provision on a host/network outside original VM infrastructure to validate actual dynamic IP reachability and independent peering.
- Replace centralized GitHub temporary rendezvous with discovery-v5/native P2P bootstrap and multiple replaceable independently operated discovery endpoints, no fixed IP, memberships or paid API.
- Independent real Ethereum PoS validator lifecycle (keys, test ETH, deposit, churn, attestation/proposal/rewards) under sound network rules and no unsafe signer cloning.
- Actual SSE provider/consumer/monitor runtime onboarding; escrow, bonding, VRF/monitor selection, evidence, payment, slashing/dispute workflows and deployed contract integration, not just isolated unit tests.
- Real machine resource leasing/probing, reproducible performance/SLA and fault-injection experiments. Scientifically justified block/gas limits, slots, committee selection and threat models; objective report/figures.
- Harden security boundaries and recovery, test automated multi-VM runs, document reproducibility and release versioning.

This log is a *runbook and incident record*, not evidence that the blockers are already resolved.
