# R286 — REAL Docker-backed CPU compute succeeded on VM4714; next independently observe real VM4711–VM4713 network paths without leaking raw worker publicly

## Owner ACTUAL observed VM4714 milestone (2026-11-24)

The owner ran **R285 nine tests PASS** and the actual R285
**STRICT READ-ONLY three previously-owned old exited hello-world
Docker container gate PASS**, confirming all three IDs/names/
hello-world images, exactly exited with exit0 and unchanged.
Then chose and typed special interactive consent to existing
`--run-sudo` R281/R283/R285 compute launcher, which
actually BUILT and STARTED a NEW fourth Docker container on
dedicated compute-only VM4714, WITHOUT touching the three old
stopped containers or any original PoS Docker daemon.

The result is **not simulated**:

- Container name `sse-compute-vm4714`
- Actual full Docker container ID:
  `59b9086543110acd2ef44da7fddeb100ab0341204de3dac595093803985f535b`
- Actual image SHA256 ID from real local Docker build:
  `sha256:848cde736008713d2f72e8de20cc669326abc678e41f644d3d63480ce77bd20d`
- 0.5 vCPU quota and 256 MiB RAM/swap caps
  validated through actual local Docker inspect
- Nonroot container process UID10001:10001, readonly
  rootfs, all Linux capabilities dropped, 32 PIDs cap,
  no-new-privileges and built-in seccomp.
- Docker bridge network and host-only
  `127.0.0.1:8877` binding. This is deliberately
  **not** a public HTTPS endpoint.
- Actual local HTTP `/healthz` passed, followed
  by real HTTP `/v1/compute` and independent
  recomputation of **8192 SHA256 rounds**, matching
  `sha256:11b9981300b43f797513824e01fe62e3cc3d225ba5542b66ef20d33869c6882e`
  for an OS-generated observed challenge
  `0x2565cd8e3d2568bcd0b33bde8f7e6bd8325937ea25d5b0c72b033a1e9a5ba62d`.
- Actual owner-local one-shot observed HTTP probe duration
  **0.002379 seconds** (2.379ms). This is ONE local
  response latency measurement, **not** sustained throughput,
  GPU/CPU usage history, source authenticity, an externally
  measured SLA, trustworthy hardware attestation or
  proof of a paid lease.
- Program printed
  `R283_VM4714_ACTUAL_DEDICATED_SUDO_DOCKER_CPU_WORKER_VERIFIED=true`
  and exact container+image IDs, so it reported
  live running worker after its strict check.
  The latest process/container liveness beyond
  that terminal output still requires a fresh observation.

The actual build used floating base tag
`python:3.12-slim` and downloaded an actual
base digest `sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b`;
future reproducible public operator builds must
pin base digests and publish content attestations.
Do not rebuild or replace the live verified worker
merely to cosmetically change this lab run.

Public factual artifact:
`evidence/r286_vm4714_real_prelease_physical_cpu_worker_verified.json`.

## New R286 source-only read-only NETWORK readiness

`tools/sse_pos_r286_cross_vm_real_worker_reachability.py`
runs under *only* four known nonroot VM usernames,
corresponding to VM4711, VM4712, VM4713 and VM4714.
It has two explicit modes:

- `--plan`: no network packets, Docker calls,
  CPU exercises or transactions; only reports
  planned fixed private VM4714 IP 10.50.56.22
  and loopback-only actual worker endpoint
  `http://127.0.0.1:8877`.
- `--probe`: performs EXACTLY two TCP connect
  attempts per invoking VM, from its own network
  namespace to VM4714's *previously owner-observed*
  private IPv4 `10.50.56.22`, ports **22** (SSH)
  and **8877** (worker). Each bounded to 2sec.
  Responses distinguish TCP handshake, refusal,
  timeout or network error; they do NOT authenticate
  SSH, establish private tunnel, prove public
  Internet ingress or change firewall/service.
  Since real Docker worker binds only 127.0.0.1,
  remote port8877 should ordinarily be refused/
  filtered; unexpected OPEN is a reason for
  investigation, NOT a completed unsigned
  monitor SLA probe.
- On **VM4714 only**, `--probe` also performs
  exact read-only Docker `sudo -n ... container
  inspect sse-compute-vm4714`, checks that both
  actual image SHA256 and full live container
  ID still match the real owner's previous
  observed R285 result, that strict hardening
  is intact, and independently sends one more
  NEW OS-random local HTTP SHA256 request with
  8192 rounds, recording real elapsed time.
  This uses the existing tested `sse_compute_docker`
  functions; no container mutation or keys.
  A changed image/container ID REFUSES; it does
  not silently accept a replacement with same
  friendly name.

New nine OFFLINE MOCKED safety tests are authored
in `tests/test_sse_pos_r286_cross_vm_real_worker_reachability.py`.
**These R286 tests, probes and on-host remeasurement
have NOT yet run on the four owner VMs.** Code
creation on GitHub is NOT an actual cross-VM probe.

### Why this intermediate private network test?

The final SSE protocol `tools/sse_pos_r232_v2_monitor_probe.py`
correctly requires an actual *finalized*, paid,
committee-ready lease, selected+confirmed
monitor EOA, provider's lease-committed public
HTTPS origin and authenticated signed EIP712
provider response before any monitor success
claim. Existing VM4714 worker HTTP is
UNSIGNED, raw computational output only,
and listens **locally**; it MUST NOT be
made public as-is or reinterpreted as a
real SLA success/failure vote.

First establish real VM4711–13 -> VM4714
private SSH TCP reachability and ensure raw
port8877 remains inaccessible off-host.
Then use a specifically reviewed
authenticated tunnel or TLS ingress with
verified public certificate, explicit
authorization, bounded access controls,
real time observation and preserved
original onchain lease checks.
Existing G2 PoS native public permissionless
P2P still separately needs actual public
EL/CL seed ingress; more 10.50.56.x
same-cloud VMs alone do not prove arbitrary
outside-ISP joining. Do NOT accidentally
expose original Besu Engine/Beacon APIs,
Docker socket or validator secrets.

### Exact next owner action: four VM checks

On each **VM4711, VM4712, VM4713 and VM4714**,
after fetching and pinning the same newest exact
Git SHA from chat in its already-existing checkout:
```bash
python3 -B -m unittest discover -s tests \
 -p 'test_sse_pos_r286_cross_vm_real_worker_reachability.py' -q
"$HOME/.local/share/sse-v2-app-only/pyvenv/bin/python" -B \
  tools/sse_pos_r286_cross_vm_real_worker_reachability.py --plan
"$HOME/.local/share/sse-v2-app-only/pyvenv/bin/python" -B \
  tools/sse_pos_r286_cross_vm_real_worker_reachability.py --probe
```

This invokes no native JSON-RPC broadcast, Docker
build/run/stop or mutable host configuration.
The owner has previously approved use of these
small VMs for actual real remote monitor and
resource tests, but cross-VM port observations
remain distinct from actual V2 EIP712
signed monitor evidence.

**Important:** R285's strict baseline exactly
three existing stopped containers was a PRE-WORKER
gate. Now that an actual fourth worker is running,
do not rerun the R285 original baseline as a
post-start "health test" — it will correctly
refuse because it sees a fourth container.
Use R286's exact expected worker read-only
runtime recheck instead. Also never rerun
R281 `--run-sudo` against a running worker:
that would attempt a duplicate build/container,
and R285 should refuse its changed inventory.

## Native TEST ETH status unchanged

All THREE previously approved native chain31340
role grants (VM4707 consumer nonce1, Monitor1
nonce2, Monitor2 nonce3) are already FINALIZED.
Four NEW encrypted standby VM EOAs are created,
unfunded and unregistered. R282 real native
RPC read-only quote for four additional 0.005 TEST
ETH grants (maximum debit including gas
0.020000000084 TEST ETH) PASSED but was
NOT authorized. No new funding senders,
monitor staking, provider bid, onchain
lease/escrow or monitor reward payout have
been executed or claimed.
