# R287 — ALL FOUR actual VM4711–14 network checks PASS (36/36 tests), provider exact Docker worker reverified + second real 8192-SHA result; pinned temporary SSH remote CPU source-only

Owner VM4711/4712/4713/4714 each ran R286
**9/9 focused tests PASS** (total **36/36 PASS**).
Actual independent private network TCP probes to
VM4714 private IPv4 **10.50.56.22**: all
three candidate monitors established SSH
TCP22 handshakes (2ms/1ms/1ms); provider
local IP check also TCP22 connected (0ms).
ALL FOUR raw HTTP TCP8877 probes
**TCP_REFUSED**, which confirms intended
loopback-only VM4714 worker exposure at
that moment. These are private host TCP
results, NOT authenticated SSH, public
Internet reachability or onchain monitoring.

Actual VM4714 R286 **re-inspected
the exact originally owner-launched full
Docker worker container ID and immutable
image digest**, verified it was still
running under strict CPU/memory/security
caps, and executed a SECOND actual OS-random
**8192 SHA256-round CPU challenge** with
independent local digest match. Actual
second localhost HTTP elapsed **0.015428s
(15.428ms)**, digest
`sha256:676dbe62ec36cd3f42a14ee6b65e3753be3a5ae71df244161b1a886732728abe`.
The first earlier real CPU trial was
2.379ms, but neither proves sustained
throughput, physical independent fault
domains, paid SLA or hardware attestation.
Evidence
`evidence/r287_real_four_vm_private_tcp_and_second_docker_cpu_probe.json`.

NEW R287 GitHub SOURCE ONLY
`tools/sse_pos_r287_three_vm_authenticated_temporary_compute_ssh_probe.py`
and **14 new mock safety tests**
`tests/test_sse_pos_r287_three_vm_authenticated_temporary_compute_ssh_probe.py`.
Provider VM4714 `--provider-hostkey` reads
ONLY standard public ED25519 host key and
prints public SHA256 fingerprint; operator
carries it OUT OF BAND from trusted
VM4714 console. Monitor VM4711–13
`--preflight --expected-host-fingerprint`
uses actual bounded ssh-keyscan but
**does NOT trust unpinned scan alone**;
verifies exact expected fingerprint,
creates only private ephemeral pinned
known_hosts, runs noninteractive strict
publickey SSH auth with no passwords,
no permanent knownhosts, proxyjump,
agent forwarding, X11 or host config.
May use an explicit EXISTING owner-private
SSH identity; never creates/copies/prints
a key. If login unavailable, no tunnel.
On monitors whose noninteractive SSH
preflight succeeds, explicit `--probe`
opens ONE short-lived monitor loopback
forward over authentic SSH to provider
loopback127.0.0.1:8877, performs REAL
HTTP health and OS-random remote 8192-SHA
challenge, recomputes digest on monitor,
measures actual encrypted cross-VM
response time and terminates its exact
SSH process in finally. No raw LAN/public
HTTP exposed, native chain tx, Docker or
validator modifications. Still offchain,
unsigned PRE-LEASE CPU observation, not
R232 final selected/confirmed EIP712 SLA.
R287 tests/provider SSH fingerprint/monitor
auth/tunnel **NOT YET RUN on owner VMs**.
Owner step order and precise trust assumptions:
`docs/R287_REAL_4VM_NETWORK_AND_PINNED_TEMPORARY_SSH_COMPUTE.md`.

ALL 3 original VM4707 consumer/monitor1/
monitor2 native chain31340 grants FINALIZED.
FOUR new VM4711–14 role EOA encrypted
wallets remain UNFUNDED; new bounded
4x0.005 TEST ETH quote (max combined
0.020000000084 incl gas) passed R282
real RPC and STILL NO additional owner
approval, signing or broadcast.
Real public EL/CL P2P admission for
independent Internet participants, public
provider HTTPS TLS, actual bonded monitors,
onchain paid finalized V2 lease/votes/
settlement all remain outstanding.

---

# R286 — REAL VM4714 Docker CPU WORKER operational and independently computed 8192 SHA256 rounds; source-only cross-VM reachability staged

Owner VM4714 ACTUALLY executed R285 nine focused
safety tests PASS and live exact old-container
no-mutation gate PASS; then typed explicit
R283 dedicated sudo-Docker worker consent.
Actual Docker image BUILT
`sha256:848cde736008713d2f72e8de20cc669326abc678e41f644d3d63480ce77bd20d`
and real fourth container
`59b9086543110acd2ef44da7fddeb100ab0341204de3dac595093803985f535b`
named `sse-compute-vm4714` STARTED, while
all three earlier stopped hello-world containers
were unchanged. Actual strict Docker configuration
inspection matched 0.5CPU, 256MiB RAM+swap,
UID10001 nonroot, readonly rootfs,
drop all Linux caps, seccomp builtin,
no-new-privileges, 32 PIDs and isolated
bridge with ONLY localhost port
`127.0.0.1:8877`. Local real HTTP health
and actual independent work challenged
8192 SHA256 rounds; result digest
`sha256:11b9981300b43f797513824e01fe62e3cc3d225ba5542b66ef20d33869c6882e`
matched local recomputation, one owner
probe observed 0.002379sec wall elapsed.
Printed
`R283_VM4714_ACTUAL_DEDICATED_SUDO_DOCKER_CPU_WORKER_VERIFIED=true`.
This was ACTUAL CPU activity and actual
Docker resource-limit configuration,
**NOT** outside-host SLA, proof of
sustained CPU consumption, trusted
hardware, paid finalized lease, selected
bonded monitors or onchain settlement.
Actual worker running at launch end,
present live state after log needs new check.
No new TEST ETH funds or transactions.

Public factual recorded evidence:
`evidence/r286_vm4714_real_prelease_physical_cpu_worker_verified.json`.

New GitHub R286 SOURCE ONLY
`tools/sse_pos_r286_cross_vm_real_worker_reachability.py`
and nine mocked tests
`tests/test_sse_pos_r286_cross_vm_real_worker_reachability.py`
prepare explicitly opt-in `--probe` on
four actual VM4711–VM4714 nonroot accounts:
two bounded real private TCP checks
on fixed VM4714 10.50.56.22 ports22/8877
to establish whether SSH private forwarding
is even feasible and verify raw compute
HTTP has NOT leaked off localhost.
On VM4714 only, re-inspects exact real
worker Docker full ID+image SHA/strict
caps and sends ONE fresh OS-random actual
localhost SHA compute request, independently
verifying 8192 rounds. `--plan` does no
network. No wallet, key, privileged
mutations, new listeners, Docker
start/stop, native chain RPC send or
funding. R286 owner VM tests/probes
**NOT YET RUN**. Distinct VM 10.50.56.x
private reachability will NOT be called
outside-ISP public Internet access.
R232 monitor agent still requires real
finalized paid onchain V2 lease,
elected/confirmed bonded monitor,
public TLS endpoint and provider
EIP712 attribution. Full runbook:
`docs/R286_REAL_VM4714_DOCKER_COMPUTE_PROOF_AND_CROSS_VM_MONITOR_REACHABILITY.md`.
Do not rerun R285 exact-three baseline AFTER
worker creation; it will correctly refuse
because an actual fourth container now exists.

ALL original 3 native TEST ETH grants
were previously proven FINALIZED on
chain31340. The four new VM4711–14
encrypted app wallets remain unfunded.
R282 4x0.005 native TEST ETH at gas
cap max debit0.020000000084 quote
is real-readonly eligible but NO
new owner authorization or send
has been provided.

---

# R285 — ACTUAL VM4714 32/32 focused tests PASS and only THREE old EXITED hello-world containers; preserve them, source-only real Docker worker coexistence gate

Owner actual VM4714 tests after R283 fixture fix:
8 R283 + 8 R281 + 16 Docker inspector =
**32/32 PASS**. Owner actual privileged
READ-ONLY `docker ps -a --no-trunc` lists
EXACTLY three old hello-world containers:
`serene_sammet`, `friendly_saha`,
`zealous_wilson`, each
`Exited (0) 5 months ago`; NO running
Docker containers observed. They are NOT
live chain31340 PoS containers, but are
owner objects and must be left untouched.
No real CPU compute Docker worker yet built,
started, benchmarked or publicly reachable.

New Github **R285 SOURCE ONLY** dedicated
VM4714 read-only strict existing-container
preservation gate:
`tools/sse_pos_r285_vm4714_preserve_existing_docker_readonly_gate.py`
and nine new mocked tests
`tests/test_sse_pos_r285_vm4714_preserve_existing_docker_gate.py`.
Requires exact owner and explicit local
`sudo -n docker --host unix:///var/run/docker.sock`,
two immutable read-only full-ID inventory
reads and `container inspect`, checks
exact three full IDs+names, actual image
hello-world, stopped exit0, no changes,
no running/unexpected containers, no
remote Docker context or shell mutation.
New R285 tests/read-only real audit
**NOT YET owner-VM4714 executed**.
Updated owner-gated
`scripts/r281_vm4714_real_compute_worker.sh`
allows only these exact preserved
three exited objects via R285 proof,
not arbitrary existing Docker containers;
all other state REFUSES; original `--run`
still denies any existing Docker container.
Explicit `--run-sudo` still requires
owner TTY and approved phrase, fixed
local sudo daemon; actual proposed
worker 0.5 CPU, 256MiB RAM, strict
isolation, loopback only. Added bounded
real local healthz startup check before
real OS-random SHA256 8192-round proof.
**NO OWNER WORKER START YET**.

Previously VM4707 original native chain31340
consumer+Monitor1+Monitor2 transfers
ALL actual FINALIZED. R282 exact
new 4-EOA 0.005 TEST ETH each RPC
gas and nonce quote PASS but separate
NEW spending not authorized; no new
funding/registration/bond transactions.
User still has other standby VMs if
dedicated VM4714 host state changes.
Owner read-only test+real audit and
subsequent separately consented
pre-lease CPU measurement: runbook
`docs/R285_VM4714_EXACT_EXISTING_EXITED_HELLOWORLD_PRESERVATION_AND_REAL_WORKER.md`,
evidence
`evidence/r285_vm4714_three_existing_stopped_hello_world_and_original_grants_finalized.json`.

---

# R284 — ALL THREE existing approved chain31340 TEST ETH grants FINALIZED; four NEW wallets preflight verified and UNAUTHORIZED; VM4714 test-fixture bug corrected, existing Docker containers protected

Owner VM4707 actual native R278 strict read-only
Monitor2 nonce3 funding transaction
`0x0c6b2e79f930b8e23e5ee9b32bd151733bb09d88a7ecbc8c145cec091cdb389a`
is **MATCHING_TX_SUCCESSFUL_CANONICAL_FINALIZED**:
included block26008, execution finalized26100,
EL head26250, 0.005 native TEST ETH at
both latest and finalized recipient balance.
Original consumer nonce1 and Monitor1 nonce2
previously proven finalized; all three approved
native funding transfers are now FINALIZED.
Source latest/pending nonce4. Never resend any
of original once-only attempts.

Owner VM4707 actual R282 four-standby-EOA
**READONLY_SCENARIO_QUOTE_ELIGIBLE_FOR_SEPARATE_APPROVAL**:
each real VM4711-4714 previously created
encrypted EOA clean, balance0, nonce0, code0,
live 21000-gas EOA estimate at actual
gasPrice1000wei, original app deployer EOA
balance979999993320597000wei. Proposed
only 4x0.005 native TEST ETH at source
nonces4/5/6/7, maximum debit
20000000084000000wei=0.020000000084
TEST ETH including fees. **No authorization,
sender implementation, signing or funding for
these NEW EOAs.** Approval scope separate.

Owner VM4714 R283 new test suite yielded
**7 PASS, 1 FAIL** because TEST-FIXTURE fake
`id` helper contained literal escaped newline
in shebang; original Bash script non-TTY
test did not get to intended assertion.
New GitHub FIX replaces escaped shell
helper newlines; **new test not yet
VM4714 re-executed**. Due set-e, prior
R281 and Docker inspector suites did not run
in that VM owner shell. Owner separately
chose explicit `--run-sudo`, typed R283
special consent and passed privileged local
Docker daemon connection to actual `ps -a`.
Actual script then **CORRECTLY REFUSED**:
`R281_REFUSED: dedicated compute host has
existing Docker containers; do not disturb them`.
This proves SOME existing containers (could
be stopped or running), not their names or
purposes. It stopped BEFORE Docker build/
start, so **NO real worker or CPU trial
ran**, and preexisting containers were
untouched. DO NOT delete/migrate any container
or disable the guard without read-only
inventory `sudo -n docker --host
unix:///var/run/docker.sock ps -a --no-trunc
--format '{{.ID}} {{.Names}} {{.Image}}
{{.Status}} {{.Ports}}'`.

Exact public owner evidence staged:
`evidence/r284_vm4707_finalized_all_original_grants_vm4714_worker_refused_existing_containers.json`.
Runbook:
`docs/R284_ALL_3_NATIVE_FUNDING_FINALIZED_VM4714_SAFELY_REFUSED_EXISTING_CONTAINERS.md`.
Actual physical CPU, independent monitor
HTTPS probes, bonded monitors, funded lease,
payout/refund and outside-ISP P2P joining
NOT yet achieved.

---

# R283 — actual new VM4714 R281 eight tests PASS, rootful Docker permission denied; R282 six tests PASS, Monitor2 still pending. Dedicated explicit-sudo Docker worker optional SOURCE ONLY.

Operator VM4714 `ayoubakrvm4714` ran R281
eight new mocked safety tests PASS and no-effect
compute worker preview:
real pilot proposed one isolated 0.5CPU/256MiB,
nonroot UID10001, read-only rootfs, 32PIDs, drop
all caps, built-in seccomp and loopback
`127.0.0.1:8877`. Actual
`/var/run/docker.sock` is root:docker
mode0660; unprivileged Docker read-only listing
failed permission denied. Rootless setup scripts
not present at guessed Ubuntu path.
**NO REAL Docker container was started or CPU
challenge measured yet**.

Operator VM4707 R282 six tests PASS; actual
R282 NO-SEND report
`MONITOR2_NOT_FINALIZED_NO_STANDBY_FUNDING_QUOTE`.
Exact Monitor2 nonce3 native TEST ETH transfer
already successful canonical by prior R278,
still NOT finalized at owner R282 read.
No additional funding quote from RPC,
no new standby funds authorized/sent.
R267 monitor2 attempt marker must not be
reset, resent or replaced.

New GitHub R283 source-only safety option:
`scripts/r281_vm4714_real_compute_worker.sh`
now adds **explicit owner-TTY-only --run-sudo**
to fixed local rootful Docker socket on
dedicated compute-only **VM4714**, separate
from original PoS Docker hosts. It never
silently falls back to sudo; refuses any
preexisting Docker container on host.
Uses `sudo -n` only if already available,
requires exact typed special consent, strict
resource isolation, real Docker image digest,
real independent 8192 SHA workload and
live CPU timing. Newly extended
`tools/sse_compute_docker.py` uses
`dedicated_vm4714_sudo_docker=True` to
read-only inspect ONLY exact named
`sse-compute-vm4714` at loopback port8877,
under exact VM4714 nonroot user with explicit
fixed local Unix socket, and sanitizes
Docker context/host env. Reject root, other
owners, nonstrict/remote/wrong socket.
Eight new mock tests authored
`tests/test_sse_pos_r283_vm4714_explicit_sudo_compute.py`
but **NOT yet tested on actual VM4714**.
The rootful Docker API is root-equivalent on
the dedicated VM, a CONTROLLED experiment
only, not a production permissionless worker
security guarantee. No PoS/keys/EVM/funds
modified by commits. Need actual VM4714
sudo -n *read-only* Docker inventory & new
test pass before a separate optional TTY
owner start. Full evidence:
`evidence/r283_vm4714_dedicated_docker_socket_denied_and_vm4707_monitor2_pending.json`
and runbook
`docs/R283_VM4714_DEDICATED_EXPLICIT_SUDO_DOCKER_REAL_WORKER_GATE.md`.

---

# R282 — actual third original native TEST ETH grant nonce3 successful canonical but NOT YET FINALIZED; FOUR new encrypted separate-VM EOAs CREATED, dedicated real CPU worker source staged, new 4-grant no-send quote only

VM4707 actual R267 final third already-approved
Monitor2 TEST ETH transfer nonce**3**
`0x0c6b2e79f930b8e23e5ee9b32bd151733bb09d88a7ecbc8c145cec091cdb389a`
submitted by owner TTY with encrypted app-only EOA;
R278 **5/5 tests PASS**, real original chain31340
same tx SUCCESSFUL+CANONICAL included block**26008**,
EL finalized**25876** / head**26011**,
**132 blocks from finality AS OF THAT capture**;
Monitor2 recipient latest balance **0.005 TEST ETH**,
finalized balance **0** and source nonce now**4**.
R267 exact marker consumed; NEVER resend or reset.
All three original funds NOT YET confirmed finalized.

REAL standby role identity results supplied in four
owner-terminal attachments at previously pinned Git
SHA`52033d7099a9981d6652de27d5e23cb3f20388e4`.
R279 7/7 tests PASS on **each** of four distinct
VM accounts (total 28 PASS). Actual owner terminal
consent, actual pinned app-dependency venv install,
actual new private encrypted EOA created once each:
- VM4711 monitor A `0x1a89D81288522912643e15D8e06a2a7D9dc4bc08`
- VM4712 monitor B `0x30dc70daA83B2D4199B98Cf1b93f31f1BA80f0Aa`
- VM4713 monitor C `0x001f529E8d17A243078631100CA7Ad93c001Ea2d`
- VM4714 provider `0x016B91ED50Ec350e600327C4287F2ED882E0Cf66`.
All four are unfunded and unregistered; no
secrets, passwords or validator keys committed.
Actual evidence
`evidence/r280_vm4707_monitor2_canonical_pending_and_four_distinct_standby_role_wallets_created.json`.

NEW GitHub SOURCE ONLY R281:
`scripts/r281_vm4714_real_compute_worker.sh`
has default no-effect `--preview` and optional
individually owner-consented `--run` with real
dedicated VM4714 isolated Docker:
0.5 CPU, 256MiB RAM+swap, 32 PIDs, nonroot
UID10001, read-only rootfs, seccomp builtin,
all caps dropped, no-new-privileges, bridge
network with loopback-only port 8877,
real pinned-postbuild image SHA and per-request
strict local Docker inspection and real CPU
8192 SHA rounds with fresh OS-random challenge.
No auto sudo, rootful PoS VM usage, key reads,
or chain tx. If proof fails, removes only the
newly started exact container. **R281 not yet
VM4714-tested or started.** Eight new preview
safety/mocked tests authored.
Details:
`docs/R281_REAL_FOUR_STANDBY_ROLE_EOAS_AND_DEDICATED_CPU_WORKER.md`.

NEW GitHub SOURCE ONLY R282:
`tools/sse_pos_r282_standby_four_eoa_funding_readonly_quote.py`
and six mocked tests stage exact safe NO-SEND quote
for the four newly created separate host wallets,
proposed 0.005 native TEST ETH per EOA, max
**0.020000000084 TEST ETH** including four
21000gas*1000wei legacy cap. One-shot quote
will NOT reach real RPC recipient/gas/balance
quote unless previous Monitor2 canonical successful
FINALIZED as independently checked by R278, source
nonce4 and all new EOA accounts empty/clean.
**Not authorized**: no new funds, bonding, bids
or worker setup approved beyond owner's own TTY
launch. Needs separate explicit exact owner
approval BEFORE any four new sends; no new
transaction sender created yet.
**R282 tests and live quote have NOT yet VM4707-run.**

Neither creating a unique app-only EOA on separate
VMs nor actual pre-lease compute worker CPU rounds
by itself proves independent organizational fault
domains, public HTTPS accessibility, paid SLA,
authenticated monitor evidence or onchain payouts.

---

# R279 — REAL native Monitor1 nonce2 finalized and funded; four REAL standby VM4711–VM4714 host capacities measured; separate role-wallet bootstrap staged

Actual owner VM4707 R276 **8/8 tests PASS** and exact
original-chain31340 Monitor1 nonce2 TX
`0xaf024159fe0b34d255689ab6ab5137c55aa247e7044f9792d56e6297ad447ebc`
now **SUCCESSFUL_CANONICAL_FINALIZED** at block25739,
execution finalized25812/head25956. VM4707 monitor1 EOA
`0xd63b2Ba14E8aD16Cf5f494259dAE05AD59fE0147`
latest AND finalized balance **0.005 TEST ETH**,
app funder latest/pending nonce**3**.
Previous R267 "marker consumed" was correctly protecting
an **ALREADY SUCCESSFUL** native funding send; NEVER retry.
Monitor2 nonce3 remains the last of three explicitly
approved exact funding transfers but **no Monitor2
broadcast/receipt is yet evidenced**. Existing R267
exact pinned `fc50985a7bf067ff83485c931069211bc572863f`
preflight can send once if fresh nonce3 and predecessor
finality permit + owner TTY consent; R267 writes a
one-time marker before sending. No new owner consent
is implied for extra monitors or bonding.

Actual owner SSH inventory for standby **VM4711,
VM4712, VM4713, VM4714**, all Ubuntu24.04,
**2 vCPU, 3.8GiB RAM (3.3GiB available), 35GB
available disk**, Docker CLI+Python3 installed.
Distinct usernames and private eth0 IP logs, but
multiple hosts share TEMPLATE hostnames; no
physical/ISP/operator independence or public
WAN reachability proven. Suggest first lab
roles: 4711-13 separate remote monitor EOAs,
4714 dedicated compute EOA (avoids VM4709
rootful PoS Docker daemon). New `scripts/r279_standby_vm_app_identity.sh`
uses existing encrypted wallet tool+Python pinned
requirements, strict reviewed SHA, owner account
allowlist for **this experiment only**, --preview
read-only default and interactive per-host --create
wallet encryption 0700/0600; no native tx,
Docker, BLS or PoS modifications.
New `tests/test_sse_pos_r279_standby_vm_app_identity.py`
has seven authored no-effect preview checks.
Also R276 extended with `--role monitor-2`
via R278 plus five new mocked status tests:
exact successful pending/finalized/fail unknown
nonce3 attempt, no broadcast. **R278/R279
test suites have NOT yet run on actual VMs**.
Public evidence
`evidence/r277_vm4707_monitor1_native_funding_finalized_and_four_standby_small_vm_capacities.json`
and detailed action runbook
`docs/R279_REAL_MONITOR1_FINALIZED_VM4711_4714_STANDBY_ROLE_BOOTSTRAP.md`.

---

# R276 — Monitor1 nonce2 owner marker ALREADY CONSUMED (status UNKNOWN), exact public-only chain audit authored; actual provider regressions 30/30 PASS, standby VMs available

Actual VM4707 owner's next R267 `--role monitor-1 --send`
returned `R267_ROLE_FUNDING_REFUSED: this exact role funding
attempt already consumed; DO NOT RETRY`. This indicates
the existing PRIVATE write-once R267 public attempt
marker is already present; R267 creates it BEFORE the
actual RPC send. **NO proof of Monitor1 broadcast,
receipt, or funds in provided logs**. Do NOT replay,
delete marker, skip nonce2, or submit Monitor2 nonce3.
New GitHub `tools/sse_pos_r276_vm4707_monitor1_funding_attempt_forensics.py`
+ eight authored mocked tests will READ ONLY public
nonce2 marker metadata and original chain31340 RPC
signed hash, exact transaction, receipt, inclusion
canonicality, execution finality, latest/finalized
monitor balance. No EOA keystore, signing, transmission
or key access. Missing RPC tx hash is UNKNOWN
broadcast state, NEVER an automatic new send.
**New R276 tests/real auditor not yet VM4707 run**.

Real owner VM4709 R275 focused suites **9+16+5 = 30 tests PASS**,
native existing Ubuntu docker.io **29.1.3**, apt-cache
rootlesskit/uidmap/slirp4netns/fuse-overlayfs available;
`docker-ce-rootless-extras` package unavailable in current
configured apt sources. `apt-get -s` read-only solver
selected **six NEW packages**, 0 upgrades/removals,
73 old upgrades outstanding. This is NOT a working
rootless Docker install and would not necessarily add
missing rootless dockerd scripts. Do NOT modify rootful
PoS Docker daemon just to host app provider.

Reviewed actual earlier `docs/SSE_COMPLETE_ROLES_PERMISSIONLESS_SCALING_AND_VM_EXPERIMENTS.md`
section9: owner stated **two extra large VMs**
(roughly 4CPU/12–16GiB), **four small Ubuntu24.04
VMs** (roughly 2CPU/4GiB/40GiB) standby. They were
named New large A/B and New small C/D/E/F in role
plan, NOT verified numbered VM IDs or independent
operators. Prefer independent small machines for
separate actual monitoring identities, compute-only
provider without contention with original rootful
PoS containers, and real fault injection.
Actual host inventory and independent network domain
must be measured; don't assume VM provisioning
means running role agent.

Public-only runbook and source test command:
`docs/R276_VM4707_MONITOR1_CONSUMED_ATTEMPT_AND_STANDBY_VM_ALLOCATION.md`.

---

# R275 — REAL original chain31340 CONSUMER TEST ETH FUNDING FINALIZED; VM4709 provider rootless Docker execution isolation SOURCE ONLY

Actual owner VM4707 R271 one-shot shows first consumer nonce1
funding TX `0x9f3a13cb295b5ba2f642804a30c391b9cce266784a83dd293d0dd7fb7d1f9fdd`
status **SUCCESSFUL_CANONICAL_FINALIZED** in block
**25564**, actual finalized execution **25588**, EL
head **25728**; consumer EOA
`0xD74A2aBC5a906BaFe39471CEe222c48BDD62DE3f`
balance actual `latest` **AND finalized**
**10000000000000000wei (0.01 native TEST ETH)**.
No more consumer resend. Previous 8-block finality gap
FULLY CLOSED. Beacon epoch854 head, 850 finalized.
**No Monitor1 nonce2 or Monitor2 nonce3 signed/sent
yet**; R267 tested sender may now submit owner-approved
single Monitor1 transfer only after fresh finalized
consumer preflight and exact TTY+hidden signer approval.
Monitor2 still waits until Monitor1 finalized.

Actual VM4709 R274 7/7 targeted tests PASS and host
rootless readiness inspected: owner `/run/user/1001`
0700, 65536 subuid/subgid available starting165536.
Docker rootless binaries and private owner rootless
socket are MISSING. Actual separate original-chain
Besu+Beacon clients on existing ROOTFUL Docker daemon
must remain untouched; provider EOA
`0xBbd4F07be80E1f4c40A1b470A180C0F38352bEaf`
encrypted owner-local, still UNFUNDED, no worker/SLA.

New GitHub **R275 source only**, no VM host install or
transmit: optional explicitly private-rootless Docker
socket restriction in `tools/sse_compute_docker.py`,
rootless-only `--rootless-docker` option on
`services/provider-agent/v2_compute_response_server.py`,
9 new mocked tests
`tests/test_sse_pos_r275_rootless_worker_inspection.py`.
Nonroot owner-only /run/user/UID/docker.sock,
0700 owner private runtime-dir, Unix-socket actual
owner and local accessibility, explicit
`docker --host unix://...`, strip `DOCKER_HOST`
/`DOCKER_CONTEXT`, fail closed no rootful fallback.
Actual Docker provider hardening validation remains.
**R275 tests have NOT yet been owner VM4709-run**.
The code does NOT install Docker or claim physical
CPU/SLA proof. Next run owner R275 test/compatibility
suites and one-shot `apt-cache`/ `apt-get -s`
read-only rootless package solver on VM4709, then
review how to install a separate user rootless daemon
without touching running native PoS Docker daemon.
Evidence `evidence/r275_real_vm4707_consumer_native_tx_finalized_and_vm4709_rootless_gap.json`
and runbook
`docs/R275_FINALIZED_CONSUMER_FUNDING_AND_VM4709_NONROOT_ROOTLESS_PROVIDER_SOCKET.md`.

---

# R274 — consumer funding canonical but still short of native finality; source-only nonprivileged VM4709 rootless worker readiness

Owner retried R267 Monitor1 --send on actual VM4707; safety gate
again returned `R267_EARLIER_ROLE_FUNDING_PENDING_FINALITY_DO_NOT_RESEND`.
Canonical successful consumer funding TX
`0x9f3a13cb295b5ba2f642804a30c391b9cce266784a83dd293d0dd7fb7d1f9fdd`
was in block25564; previous exact R271 last observed EL finalized25556
(**8 blocks remaining AS OF THAT PREVIOUS SNAPSHOT only**);
new R267 refusal provides NO new finalized height.
No Monitor1 nonce2 or Monitor2 nonce3 transaction signed/sent;
never replay consumer or bypass predecessor finalized gate.
Do not repeatedly run `--send` as a finality check;
use R271 read-only single-shot diagnostic when needed.

VM4709 real provider app EOA
`0xBbd4F07be80E1f4c40A1b470A180C0F38352bEaf`
is encrypted and created, but remains unfunded.
Both original real EL+CL containers remain running
as verified at the earlier sudo read-only Docker check.
Unprivileged Docker Unix socket access denied; existing
R234 strict per-request Docker inspector would therefore fail
on VM4709. NO permission/grant/restart shortcut.
NEW `tools/sse_pos_r274_vm4709_rootless_compute_readiness.py`
and 7 mock offline tests inspect only public current
owner-local rootless daemon prerequisites:
binaries, subordinate ID mappings, private runtime
directory and owner-owned rootless Unix socket.
NO sudo/install/start/stop/network/key/tx functionality.
**New R274 tests and actual VM4709 prereq have not yet run**.
Evidence `docs/R274_VM4709_ROOTLESS_WORKER_NONMUTATING_READINESS_AND_R267_UNFINALIZED_CONSUMER.md`.

---

# R273 — Actual provider application EOA CREATED on VM4709, native PoS Docker containers verified; consumer nonce1 only 8 blocks short of finality

Owner VM4707 actual R271: five targeted tests PASS; real
original-chain31340 consumer nonce1 funding transaction
`0x9f3a13cb295b5ba2f642804a30c391b9cce266784a83dd293d0dd7fb7d1f9fdd`
successful canonical in block**25564**, recipient latest
balance**10000000000000000 wei**, finalized balance**0**.
Actual EL head**25697**, finalized**25556**,
**8 blocks gap**; Beacon head slot27309 epoch853,
finalized epoch849. No Monitor1 nonce2, Monitor2 nonce3
funding occurred. No consumer replay or gate bypass.

Owner VM4709 at pinned R272 SHA: seven focused tests PASS,
real host probe 4 logical CPUs, 11.27 GB MemAvailable,
97.73 GB free disk, `docker ps` unprivileged permission
denied due to root-owned Unix socket. Authorized separate
`sudo -n docker --host unix:///var/run/docker.sock ps`
actually lists two running Besu EL and Lighthouse BN
containers (EL healthy). Owner installed original pinned
requirements into isolated owner local app-only venv and
actually CREATED new encrypted separate VM4709 provider
EOA `0xBbd4F07be80E1f4c40A1b470A180C0F38352bEaf`.
No app signing secret printed, funding, provider worker,
on-chain bid or physical SLA yet. Be precise: R234 provider
runtime currently uses UNPRIVILEGED per-request
`docker container inspect`; socket access is denied.
Root's one-off Docker listing does NOT make worker ready.
No Docker service, network, validators or blockchain node
changed by these checks. Actual public-only evidence:
`evidence/r273_vm4707_r271_and_vm4709_provider_wallet_created.json`,
details and next steps:
`docs/R273_REAL_VM4709_PROVIDER_WALLET_AND_VM4707_CONSUMER_EIGHT_BLOCK_FINALITY.md`.

---

# R272 — real consumer transfer canonical and funded at latest, 40 execution blocks short of finality; VM4709 has available real resources but Docker access blocked

Owner VM4707 R271 actual new 5/5 focused tests PASS,
live read-only exact consumer funding tx
`0x9f3a13cb295b5ba2f642804a30c391b9cce266784a83dd293d0dd7fb7d1f9fdd`
canonical receipt SUCCESS at included block **25564**,
consumer latest balance **0.01 TEST ETH**,
consumer finalized balance **0**,
execution head **25676**, finalized block **25524** (gap **40**).
Original Beacon genesis matched, head epoch **852**,
finalized epoch **848** (lag4); no R267 Monitor1
nonce2 or Monitor2 nonce3 send yet. Do not replay the
consumer nonce1 transfer or bypass real finality.

New real VM4709 owner's HOST inventory: **4 CPUs,
~10GiB available RAM, 92GiB free disk**, local Docker
CLI `docker ps` permission DENIED, system Python
`eth_account` absent. Existing Besu/Lighthouse node
containers may be running regardless of socket access;
not proven stopped. New `tools/sse_pos_r272_vm4709_provider_host_readonly_preflight.py`
and 7 focused offline mocked tests stage owner-only
read-only real Linux CPU/RAM/disk, nonroot Docker
Unix-socket ownership/permission/ps checks, Python
venv/eth_account detection, NEVER sudo, never start
or stop native PoS client. **R272 not yet tested
on actual VM4709.** Current owner host is a
candidate resource provider, but no real Docker
workload, provider EOA or WAN SLA yet.
Source/command: `docs/R272_REAL_CONSUMER_TX_40_BLOCK_FINALITY_GAP_AND_VM4709_PROVIDER_HOST_GATE.md`.

---

# R271 — user REAL R267 confirms consumer receipt successful+canonical, still pending FINALITY; no monitor send

User twice ran the owner-authorized R267 `--role monitor-1` checks
after the first actual chain31340 consumer test-ETH funding
nonce1 `0x9f3a13cb295b5ba2f642804a30c391b9cce266784a83dd293d0dd7fb7d1f9fdd`.
Both returned `R267_EARLIER_ROLE_FUNDING_PENDING_FINALITY_DO_NOT_RESEND`.
This R267 code only emits that stage AFTER actual tx and receipt
are verified exact successful/canonical, therefore the owner-observed
consumer transfer was successful and canonical **but not yet finalized**.
No monitor1 nonce2 or monitor2 nonce3 native transfer submitted, and
consumer one-time marker consumed; **NO resend, marker deletion, nonce
replacement, client restarts or finality-bypass**.

New `tools/sse_pos_r271_consumer_native_tx_finality_snapshot.py`
and five focused mock regression tests stage a **one-shot read-only**
real consumer nonce1 transaction inclusion-height versus EL finalized
height, latest/finalized recipient balance and live Beacon head/finality
epoch lag. No polling, signing, keystore reads, Docker, tx broadcast.
New code/tests **not yet owner VM-tested**. Full evidence:
`docs/R271_VM4707_CONSUMER_TX_FINALITY_AND_VM4709_REAL_ROLE_HOST_PREPARATION.md`.

VM4709 had genuine Besu+Lighthouse original-chain native peer/finality
evidence on Nov23, but its CURRENT resource availability is not known.
Candidate for REAL provider-host deployment after actual nonmutating
CPU/memory/disk/Docker inventory, and local encrypted provider EOA.
Do not treat VM4707's two monitor wallets as physically independent
operators; genuine independent monitoring and WAN access are not yet proven.

---

# R268 — actual VM4707 R267 9/9 tests and finalized consumer nonce1 funding PREVIEW PASS; waiting for NEW owner funding consent

At exact pinned Git SHA `8e10d74356fbfc33d493c103f7667d09d2f48c6f`, owner actually executed new R267 focused offline safety suite **9/9 PASS**, then actual VM4707 original-chain31340 read-only consumer native funding preview **PASS** with marker `R267_FUNDING_PREVIEW_ONLY_NO_SIGNING_NO_BROADCAST=true`. Actual latest finalized execution block **25396**, R206 native V2 finalized deployment verification **TRUE**. Already-funded separate app-only source `0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0` latest balance **999999993383597000 wei**, latest/pending nonce **1**. Consumer `0xD74A2aBC5a906BaFe39471CEe222c48BDD62DE3f` real EOA zero balance/nonce/no-code. Actual Besu basic native transfer gas estimate **21000**. Exact proposed consumer nonce1 transfer **10000000000000000 wei =0.01 TEST ETH**, gasLimit21000 gasPrice1000wei/gas, max single debit **10000000021000000 wei**. Remaining intended stages monitor1 nonce2 **0.005**, monitor2 nonce3 **0.005** testETH, total proposed across stages **20000000063000000 wei**, but **NO new TEST ETH transfer has been approved, signed, broadcast or finalized**. Public evidence `evidence/r268_vm4707_r267_consumer_funding_readonly_preview.json`. Wait for explicit user approval before ever suggesting --send; R267 sender remains user-local interactive + marker-gated, no silent sends. Existing deployer R257/R254 approval is consumed.

---

# R267 — FIRST native V2 contract deployment is ACTUALLY FINALIZED; one-by-one real role funding implementation STAGED, NOT authorized

Owner VM4707 REAL R265 focused regression **8/8 PASS**,
live original chain31340 public-only quote PASS and both
independent **R260 AND R206 FINALIZED** audited deployment
PASS at checked out SHA `72265cc545ca6cfc68ec91bbe60968ce2b4e465e`:
actual first market CREATE nonce0 tx
`0xe9187bd24d72d2dec11fc6a2758802ddf6fa46a2941edd306329173fe132d6b6`,
successful execution block **25339**,
finalized execution block **25364**,
actual fee **6,616,403,000 wei**, approved full initcode
SHA256 `22d5b3310ec9a9efc66015762ea3d78d152f0a52eb9d67a257f18e3470c171ec`.
Actual finalized R249-built market/ledger contract runtime
code SHA256, immutable-aware Solc parity and mutual links
all PASS with market minimumBond1e15 wei. **NATIVE V2
CONTRACT DEPLOYMENT MILESTONE COMPLETE.** No more R257
or R254 funding/deployment sends. No physical independent
SLA, unbiased VRF or global permissionless WAN onboarding
proven by this deployment.

Real R265 native role wallet funding quote observed existing
separately encrypted app-only EOA
`0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0`,
pending nonce1, actual latest balance
**999999993383597000 wei**. Three real owner-created
new VM4707 consumer+monitor EOAs all ZERO native TEST ETH,
pending nonce0, no code. Proposed **NOT APPROVED** lab
transfer values 0.01,0.005,0.005 TEST ETH with maximum
3*21000*1000=63,000,000 wei total transfer gas.
Source `evidence/r266_vm4707_finalized_v2_deployment_and_three_role_funding_quote.json`.

New `tools/sse_pos_r267_vm4707_one_by_one_role_funding.py`
is strict native role-funding sender SOURCE: default
read-only exact owner review, optional separate owner
authorization via `--send` and exact role/value/nonce
TTY consent+hidden existing app keystore password,
atomic non-retriable **per role** marker before
ONE raw tx RPC call, verified EIP155 legacy RLP,
fresh R206 finality, verified prior role tx **finalized**
before next one, original Genesis signer forbidden.
Exact nonces: consumer1, monitor1 2, monitor2 3.
New offline mocked/fake-signed tests included, but
**new R267 source/test NOT YET EXECUTED ON VM4707**.
**NO new funding tx authorized/sent**.
Evidence and safe review steps:
`docs/R267_FINALIZED_NATIVE_V2_AND_EXACT_ONE_BY_ONE_ROLE_FUNDING_RUNBOOK.md`.

---

# R265 — 3 actual VM4707 encrypted role EOAs CREATED; new native funding budget is only READ-ONLY PROPOSAL

Owner actually created and locally encrypted three distinct
application-only EOA keystore files on VM4707 (no keys
printed, no transaction): consumer
`0xD74A2aBC5a906BaFe39471CEe222c48BDD62DE3f`,
monitor1 `0xd63b2Ba14E8aD16Cf5f494259dAE05AD59fE0147`,
monitor2 `0xf8D4c882A7439507e2fc237DCBDf4A1c228F0FF8`.
These three accounts are at the same VM fault domain,
NOT independently operated physical monitors, and still
have NOT been actually funded/registered on chain.
Deployment receipt remains canonical successful at block25339;
last actual finalized block **25332** (7 short); R260/R206
formal finalized acceptance pending and R257 --send MUST
NEVER be retried.

New `tools/sse_pos_r265_vm4707_three_role_wallet_funding_quote.py`
and 8 mock regression tests prepare actual chain31340
strictly **READ-ONLY** proposed native transfers
from already-funded separate app-only VM4707 EOA,
not Genesis signer: consumer 0.01 and monitors0.005
each; proposed total **0.02 TEST ETH** plus maximum
three simple EOA transfer gas fees **63,000,000 wei**
at max1000 wei/gas. Quote checks correct chain/genesis,
actual canonical successful market CREATE, funder
nonce1/balance, recipient balance0/nonce0/no-code
and real node EOA gas estimates. NO wallet opens,
signatures or sends; amounts NOT YET authorized.
Tests/new code **not yet run on VM4707**.
Evidence `docs/R265_VM4707_REAL_THREE_NEW_ROLE_WALLETS_AND_GAS_BOUNDED_FUNDING_PREVIEW.md`;
public only `evidence/r264_vm4707_created_application_role_public_addresses.json`.
Next owner run: R265 focused tests then the real read-only
quote. Build exact per-recipient consent-gated
no-retry single native transfer only AFTER explicit
approval. Real roles / SLA remain unexecuted.

---

# R263 — Real V2 market healthy but has ZERO registered participants; finality only 7 blocks short

VM4707 actually ran the new R262 5/5 focused tests PASS,
then read the real chain31340 V2 market and ledger:
`R262_REAL_V2_LIVE_ROLE_READINESS_READONLY_NO_TX=true`.
Original canonical deployed contract block25339; at actual
latest head25476 execution finalized25332 (**7 blocks short**).
Both deployed actual runtime SHA256 hashes match R261 exact
public evidence; Solc nonimmutable-byte parity and
known constructor immutable values pass. Actual market
`activeMonitorCount=0`, `nextRequestId=1`,
`nextLeaseId=1`; service escrow, pending monitor
funding, monitor bonds, withdrawable credits and
market+ledger balances all =0. Real native contracts are
empty, financially solvent, no real resource requests or
leases; do NOT pretend a live marketplace SLA already ran.
No wallet keys accessed or signed transaction sent.

Next: run R260 and R206 exactly ONCE after finality
covers block25339; prepare genuinely separate consumer,
provider and four bonded monitor application-only
encrypted EOAs using existing `tools/sse_pos_test_wallet.py`
on their actual participating hosts, then per-role native
TEST ETH funding+registration and real provider
work with **separate new on-chain transaction approvals**.
Four EOAs on one machine are not four independent
hardware/operators. Evidence/plan:
`docs/R263_VM4707_REAL_V2_LIVE_MARKET_EMPTY_STATE_AND_ROLE_IDENTITY_BOOTSTRAP.md`.

---

# R262 — actual live post-deploy Solc runtime parity VERIFIED; one-shot native role-readiness added

Owner's actual VM4707 EVM runtime+compiler parity command
returned `LATEST_SOLC_BYTECODE_PARITY_VERIFIED=true`
for both real native V2 contracts, market 19,263 bytes,
SHA256 `aed48968f9b5ef4e8f238efaed8c539af5c8799de181f290b38a21803386c261`,
linked vote ledger 10,668 bytes,
SHA256 `3a14ac0cd120271c50ac31661b6080546477aa8218e9944e51dd89998b78622d`.
Solc compiler immutable slots market **27**, ledger
**12**; known real immutable values (market votes,
minBond=1e15 wei, ledger settlement) matched.
All nonimmutable EVM runtime bytes matched compiler source.
No transactions were submitted. This is REAL live latest-state
code parity, **NOT** finalized-state R260/R206 acceptance;
most recent owner execution finalized block25300 < deployed block25339.

New one-shot `tools/sse_pos_r262_native_v2_live_market_readiness.py`
and five focused mocked tests enable exact live market/ledger
code and immutable parity, actual active monitor roster,
real consumer/request and lease counters, real onchain
escrow/bond liabilities and contract balances, canonical
successful receipt and separate finality distance in
one READ-ONLY no-polling pass. NEW source not yet VM-tested.
Evidence `docs/R262_REAL_V2_DEPLOYED_CODE_PARITY_AND_NATIVE_ROLE_READINESS.md`.
Next state-changing actions require separately authorized
consumer/provider/monitor EOA ownership and funding;
R257 deployment approval is already consumed and does
not authorize role transactions.

---

# R261 — REAL native chain31340 market and linked vote ledger deployed at canonical latest state; 71-block finality gap

Actual VM4707 live Besu read-only observations from user:
deployment receipt block **25339**, status success,
gas used **6616403** (under owner-approved 8342601);
latest execution block **25424**, finalized **25268**;
**still NOT final** (needs 25339). The single R257
deployment tx must NEVER be resent.

Market is actual live EVM code at
`0x6C01dBd7aA336a96d8Ab09Ea631E209612224080`,
runtime **19263B**, SHA256
`aed48968f9b5ef4e8f238efaed8c539af5c8799de181f290b38a21803386c261`.
Real `market.votes()` points to on-chain ledger
`0x6635849b77f037fab611736612d7d3493dc650ff`,
runtime **10668B**, SHA256
`3a14ac0cd120271c50ac31661b6080546477aa8218e9944e51dd89998b78622d`.
`ledger.settlement()` returns exact market and market
`minimumBond()` returns **1e15 wei = 0.001 TEST ETH**.
All these are actual canonical **latest-state** observations;
R260 finalized compiled bytecode parity and R206 finalized
receipt/code/wiring still pending.

NEW public-only pinned candidate R206 manifest
`evidence/r261_vm4707_latest_state_v2_deployment_candidate.json`
enables direct R206 read-only finalized auditing of
the observed addresses/code hashes on VM4707 and VM4706
once execution finality >=25339. Do NOT claim candidate
manifest is finalized attestation. Documentation
`docs/R261_VM4707_REAL_LIVE_V2_MARKET_LEDGER_RUNTIME_ADDRESSES_AND_CANDIDATE_MANIFEST.md`.
Next: a single read-only R260/R206 run once finality catches up,
then actual independent role-wallet funding/registrations and
physical provider/monitor service evidence with separate
transaction authorizations.

---

# R260 — REAL one-time market+ledger contract-CREATE transaction submitted; finalized receipt/code linkage NEXT

Owner actual VM4707 at exact pinned R259 SHA
`08f383680db5647192643a5d9fa2df5170c8877a`
reported **14/14** new deployment safety unit tests PASS,
real original chain31340 read-only exact SHA-pinned preflight
PASS (R255 funding finalized, app wallet nonce0,
actual `eth_estimateGas=6,670,081`, approved gas cap
8,342,601 and 1000 wei/gas, full constructor SHA256
`22d5b3310ec9a9efc66015762ea3d78d152f0a52eb9d67a257f18e3470c171ec`).
Owner explicitly typed one-deployment TTY consent,
unlocked ONLY the new separate application VM4707
keystore privately, and **SENT EXACTLY ONE** signed
legacy nonce0 native contract CREATE with `value=0`.
Real Besu RPC acknowledged public txHash:
`0xe9187bd24d72d2dec11fc6a2758802ddf6fa46a2941edd306329173fe132d6b6`.
Private one-shot attempt marker consumed;
`R257_ONE_SIGNED_DEPLOYMENT_SUBMITTED_NOT_YET_FINALIZED=true`.
Expected market nonce0 CREATE address
`0x6C01dBd7aA336a96d8Ab09Ea631E209612224080`.
**DO NOT RESEND OR RERUN R257 --send.**
No successful receipt/finality, market bytecode or ledger
address have yet been owner verified.

New substantive `tools/sse_pos_r260_v2_readonly_finalized_deployment_audit.py`
and 11 mocked focused tests implement read-only exact
authorized contract-CREATE receipt, original genesis,
historical native funding canonical+finalized proof,
execution canonical/finalized inclusion, native actual gas
fee, actual on-chain market+ledger independent code
comparison vs R249-compiled runtime outside Solidity
compiler immutable patch slots, three known on-chain
immutable binding values (market votes, minimumBond,
ledger settlement), exact runtime SHA256 public manifest,
then existing R206 on-chain finalized code/wiring audit.
Tool must NOT require original finalized deployer
balance >=1 ETH after gas is paid. **New R260 source/test
NOT YET executed on real VM4707.**
No second transaction is authorized. Continue only with
the read-only real R260 audit and focus tests, then VM4706
cross-host public R206 manifest verification. Details
`docs/R260_VM4707_REAL_NATIVE_V2_CREATE_SUBMITTED_FINALIZED_ATTESTATION_NEXT.md`.

---

# R257 — First REAL native chain31340 TEST ETH transfer finalized; separate app deployer funded, one-shot V2 create prepared but NOT authorized

Actual R255 VM4707 real read-only audit returned
`R255_REAL_NATIVE_V2_DEPLOYER_FUNDING_FINALIZED=true`.
Exact tx
`0x07e3ff069936936b3daf17efc5cb484c1712e93dc6bd6040c55a5fae1b8d2a90`
sent 1 native TEST ETH from original VM4706 encrypted
Genesis EOA to new VM4707 separate app-only deployer
`0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0`.
Canonical successful inclusion block **24966**,
finalized execution height **25076**, actual fee
21,000 gas * 1,000 wei = **21,000,000 wei**.
Deployer **finalized balance exactly 1 TEST ETH**,
Genesis source finalized nonce **1**. No duplicate
funding send required or authorized.

R256 actual VM4707 passed 6/6 new mock policy tests,
`forge build -q`, real original Besu constructor gas quote
**6,670,081 gas** for exact compiled market+internal ledger,
padded proposed cap **8,342,601 gas** at observed
**1,000 wei/gas** = maximum scenario **8,342,601,000 wei**.
Quoted bond 1e15 wei (0.001 TEST ETH) is an illustrative
test parameter, NOT Sybil or economic-security proof.

Substantive new
`tools/sse_pos_r257_vm4707_one_time_v2_deployment.py`
adds a strictly **read-only default deployment preview** and
a DISTINCT `--send` owner-only interactive one-shot CREATE
sender requiring actual R255 finality, R249 original clean
source/ABI, live R256 quote, nonce0, bounded original-chain
gas, app keystore, local separate exact typed authorization,
and non-repeatable marker. **Neither sender nor mocked
R257 regressions have been VM-tested or broadcast;
the owner has NOT separately approved deployment.**
The current GitHub compare shows NO Solidity contracts,
Foundry config or vendored library change relative to the
fully VM-tested immutable R249 SHA.

Next run focused R257 mock tests and default **NO --send**
public preview on VM4707, inspect proposed immutable bond
and fee cap, obtain explicit one-deployment approval;
then independently verify any real deployment receipt and
contract runtime/wiring via R206. Evidence/commands
`docs/R257_NATIVE_FUNDING_FINALIZED_DEPLOYER_READY_AND_ONE_TIME_V2_DEPLOYMENT_PREVIEW.md`.

---

# R256 — VM4707 Beacon live and syncing normally, transfer included not yet final; quote real V2 deployment gas read-only

Owner actual VM4707 R141 captures 16:42:08Z and
16:42:32Z showed chain31340 original EL/CL genesis,
EL heads **24997→24999**, Beacon head slots
**26609→26611**, two native EL and CL peers,
no sync/optimism/offline, Beacon finality epoch **827**,
root `0xaf3a0dc5cc13527ea117952dc86bccc1467284a9f3c9318b18709827646a8861`.
Head epoch **831** vs finality epoch827 means a four-epoch
lag to watch, but identical finality over just 2 slots is
not a proven finality stall. Actual R254 1 TEST ETH
tx receipt included **24966**, verified canonical on
both VMs but `R255_FUNDING_NOT_FINAL_YET`.
**Do not resend, sign, or deploy.**

Implemented new `tools/sse_pos_r256_v2_readonly_native_deployment_quote.py`
for a genuine VM4707 Besu `eth_estimateGas` of the
actual R249-ABI-pinned compiled adaptive market constructor
(which internally creates vote ledger), verifying genesis,
code, balances and current gas price without signer or
transaction. Six new mocked regression tests; this code
and actual gas quote have **NOT YET run on VM4707**.
The optional 0.001 TEST ETH bond quote scenario is
**not** a protocol bonding/economic decision.
Next get real read-only deployment gas quote while
finality advances, then final R255 proof and **separate**
one-deployment authorization.
Evidence + exact instructions:
`docs/R256_FINALITY_PROGRESS_AND_NATIVE_V2_CONSTRUCTOR_QUOTE.md`.

---

# R255 — First actual one-time native TEST ETH funding tx submitted; receipt/finality NEXT

VM4706 owner at exact reviewed SHA
`c0e0d78f0be3f5816b146eb51cd07ee98c4d4c22`
verified fixed original chain/genesis, existing private
encrypted source EOA public signer, sender pending nonce0,
recipient zero balance/no code, authorized 21,000 gas at
fixed 1,000 wei/gas, then explicitly typed
`SEND-ONE-CHAIN31340-1-TEST-ETH`.
Owner ran exactly ONE signed `cast send --async` with local
hidden password and obtained RPC-submitted public hash:
`0x07e3ff069936936b3daf17efc5cb484c1712e93dc6bd6040c55a5fae1b8d2a90`.
`R254_SINGLE_CAST_SEND_RETURNED=true` and
the private one-shot attempt marker was consumed.
**DO NOT RERUN R254 OR RESEND**.

**Not yet proved:** actual mined receipt, canonical success,
execution finality, net gas fee, or actual post-transfer
VM4707 application EOA balance. New source
`tools/sse_pos_r255_v2_funding_finalized_audit.py`
performs ONLY read-only original-chain RPC verification
from VM4706 or VM4707. Targeted tests are newly added but
**not yet VM-tested**. R255 must show finalized receipt
before any separate owner-authorized V2 deployment.
Evidence `docs/R255_VM4706_ONE_NATIVE_TEST_ETH_SIGNED_SUBMISSION_AND_RECEIPT_GATE.md`.

---

# R254 — Owner approved exactly one bounded funding transaction; GitHub script staged, NOT broadcast

Owner explicitly authorized ONE native original chain31340
transaction transferring **1 TEST ETH** from existing
VM4706 encrypted Genesis execution EOA
`0x13fb73aace8A11Be2899D047635A757a224Ce00B`
to new VM4707 app-only V2 deployer
`0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0`,
with **at most 21,000 gas and 1,000 wei/gas**.
VM4706 `cast estimate` actually returned 21,000
and `cast gas-price` 1,000 wei; public owner EOA
balance was 1,000,007.984391109 TEST ETH, nonce0.

New `scripts/r254_vm4706_authorized_one_time_v2_deployer_funding.sh`
performs strict live original genesis/chain/wallet/address
and cap checks, requires an explicit local TTY phrase,
prompts encrypted wallet password privately, pins nonce0
and performs **only ONE** controlled Cast transmission.
It also creates an owner-private one-shot attempt marker.
**No transaction has yet been signed or broadcast by
GitHub or this assistant; new script is not VM-proven.**
See `docs/R254_VM4706_OWNER_APPROVED_SINGLE_ONE_TEST_ETH_FUNDING.md`.
Only after actual canonical/finalized receipt and VM4707
balance should separately authorized V2 deployment proceed.

---

# R253 — 0 native TEST ETH at V2 deployer; VM4706 Genesis owner EOA previously UNLOCKED successfully

Owner VM4707 read-only check: encrypted deployer file
permissions correct (0700 parent / 0600 file), RPC chain ID
31340, actual deployer public EOA
`0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0`
balance exactly **0 TEST ETH**. No transfer or deployment.

**Corrected historical custody evidence:** the actual
`docs/R28_PRESERVE_EXISTING_WALLET.md` recorded
successful OWNER-VM4706 pinned Cast decryption and
public-address match for the original Genesis-funded
execution EOA
`0x13fb73aace8A11Be2899D047635A757a224Ce00B`
on 2026-11-20. This disproves older broad phrasing
"Genesis custody never verified"; current file existence,
working password, fresh balance and spending authorization
have NOT been re-proven. Existing VM4706 keystore must
NOT be recreated, exported, moved or used without consent.

**Next:** one read-only VM4706 keystore-path/permission,
chain ID, public original balance+nonce check. Then ask
owner to explicitly approve one bounded TEST ETH transfer,
with no other automated key usage. See
`docs/R253_ZERO_BALANCE_AND_RECOVERED_VM4706_GENESIS_CUSTODY_PROOF.md`.
The complete marketplace source/compiled ABI/Foundry PASS
remains pinned to `6930c069b4e9738e63e2ce9d53b10d126053335e`.

---

# R252 — Owner-created app-only encrypted V2 deployer on VM4707; funding required

**Actual owner terminal output:** separate encrypted application
EOA created successfully on VM4707:
`0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0`,
role `adaptive-v2-deployer`. Tool reported
`walletCreated:true`, encryption/password prompts,
zero funds created, no signing or on-chain tx. The keystore and
password must stay PRIVATE and be safely backed up offline.
This is NOT a validator key and not the funded original
Genesis EOA.

**Current blocker: identify a genuinely spendable chain31340
TEST ETH funding EOA and obtain explicit transfer approval.**
The historical Genesis-funded public address had over
1,000,007 native TEST ETH, but its **private signing key
custody remains UNVERIFIED**. Do not fabricate a signer or
assume a public balance can be transferred. V2 remains
unverified deployed. No additional source tests needed at
already-green immutable SHA
`6930c069b4e9738e63e2ce9d53b10d126053335e`.

Public evidence + bounded-scope next steps:
`docs/R252_VM4707_ENCRYPTED_V2_DEPLOYER_PUBLIC_EOA_CREATED_FUNDING_BLOCKER.md`.

---

# R251 — Real chain31340 read-only preflight PASSED; next application wallet/deployment gate

Actual VM4707 RPC read-only R201 output on 2026-11-24:
**chain ID 31340 and original execution genesis verified**;
latest execution block **24840**, finalized execution block
**24692** (hash
`0xd00e0982d035f2c64fa7edcc7a01cfb4e9abf8ec1dce0c8b7667a16a4ccd0b44`),
block gas limit **30,000,000**, latest basefee **7 wei/gas**,
and original public Genesis funded EOA balance at finalized
**1,000,007.92902409 TEST ETH** (nonce **0**).
**No private key custody** or app keystore verified.

Full V2 source ABI/Foundry regressions are already green at
the immutable tested `6930c069b4e9738e63e2ce9d53b10d126053335e`.
No further test loops warranted without source change.
Next: explicit authorization to create owner-only encrypted
separate app deployer EOA (not Genesis), prove a legitimate
test ETH funding signer and bounded deployment budget, then
owner-authorized actual deployment with R206 finalized manifest.
The literal `marketV2Deployed:false` R201 field is NOT an
independent on-chain deployment scan. The full live network
resource SLA and independent Internet/validator experiments
remain outstanding.

Complete evidence/steps:
`docs/R251_ACTUAL_CHAIN31340_READ_ONLY_PREFLIGHT_AND_DEPLOYMENT_HANDOFF.md`.

---

# R250 — R249 real VM4707 full V2 source+compiled-ABI regression PASS

**Newest verified owner VM4707 source SHA**
`6930c069b4e9738e63e2ce9d53b10d126053335e`:
R249 and R235 full source gate success markers, 1,278
Python tests (1,275 PASS, 3 SKIP), R247 policy suite
10/10 PASS, real Solc ABI parity 21 actions/28 protocol
events + public getter structs PASS, adaptive V2 EVM
Foundry suite 21/21 PASS and whole `forge test -q`
exit 0. Marketplace runtime 19,263B; ledger 10,668B.

**R250 next step is NO MORE full-source retesting on the
same source SHA**: collect live chain31340 **read-only R201**
status from VM4707 and then, only on explicit owner approval,
prepare separate app wallet/funding and one deployment
transaction. This is not yet an actual live marketplace,
physical SLA, native public-Internet permissionless admission
or independent BLS-validator proof. Full evidence/plan in
`docs/R250_R249_ACTUAL_FULL_VM4707_SOURCE_GATE_GREEN_AND_LIVE_CHAIN_NEXT.md`.

---

# R249 — Compiler ABI parity: inherited EIP712 event repaired, RETEST REQUIRED

Actual VM4707 at SHA `c611ed1ff64059c642e30f0fc96f66d09feb057e`
executed **9/9 passing R248 R247 checker unit tests** and
successfully executed `forge build -q`.
Against the **actual Solc-built market artifact**, the first
R247 compiled event comparison stopped at the additional
**`EIP712DomainChanged()`**, inherited from OpenZeppelin
`EIP712`. This was not an SSE application event decoder mismatch
or native chain failure. Checks of ledger and compiled output
tuples were not reached.

R249 GitHub source now accepts ONLY the exact standard
inherited zero-field non-anonymous event; retains strict
event coverage for all SSE market/ledger application events
and rejects any other unexpected, malformed or duplicate event.
New regression covers both V2 contract roles and adversarial
schemas. **R249 revised code is committed but not yet
tested against actual compiler artifacts.**

Evidence: `docs/R249_VM4707_COMPILED_EIP712_ABI_EVENT_EXCEPTION.md`.
Prior R246 complete V2 source-only regression PASS at exact
SHA `6a25aa4aa86295cdac5d86596e95e18393e08b8f`
is unchanged; source test PASS is not live deployment or
independent physical SLA proof.

---

# R248 — R247 compiler-parity checker scalar/array return fix (NOT YET RETESTED)

Actual VM4707 at exact source `6e50557d30b9d7c6835b8a5927c5a90ec18f1bd6`:
38/38 R226–R229, 43/43 R231–R239, 6/6 R242,
5/5 R201 and 6/6 R206 all PASS. Full Python
1,275 run, **1 ERROR and 3 skipped**: a newly written
R247 ABI checker wrongly classified single `address[]`
return as nested Solidity struct, raising a tuple-unpack exception.
The fail-fast gate did NOT reach compiled-ABI checking or Forge.

R248 now distinguishes flat single/multiple scalar/array outputs
from nested Solidity struct returns, with two new regression
tests. **The new fix is committed but has not yet been
executed on VM4707 or tested against actual compiled Foundry
artifacts.** See
`docs/R248_VM4707_COMPILED_ABI_SINGLE_OUTPUT_REPAIR.md`.

Prior exact `6a25aa4aa86295cdac5d86596e95e18393e08b8f`
R246 full PASS remains valid (1,268 Python OK/3 skip,
21/21 adaptive Foundry, full Forge exit0 and market 19,263B).
No V2 deployment, real application TEST ETH transfer,
validator change or independent physical SLA yet.

---

# R246/R247 — New full VM4707 source PASS; compiled ABI parity gate not yet verified

**Actual owner VM4707 result on exact immutable source
`6a25aa4aa86295cdac5d86596e95e18393e08b8f`:**
38/38 R226–R229 Python PASS, 43/43 R231–R239 Python PASS,
6/6 R242 sender-policy PASS, R201 5/5, R206 6/6,
full Python **1,268 OK (3 skipped)**, Solidity **68 files
compiled** by Solc 0.8.24, adaptive V2 **21/21 Foundry PASS**,
complete `forge test -q` returned 0, and the genuine success
marker `R235_SOURCE_ONLY_GATES_COMPLETED=true` was emitted.
New market runtime **19,263B** (5,313B EIP-170 headroom),
vote ledger **10,668B** (13,908B headroom).
The updated R236 post-accept idle/bond-release adversarial cases
are included in the 21/21 passing tests.
See `docs/R246_VM4707_COMPLETE_R235_PYTHON_SOLIDITY_REGRESSION_PASS.md`.

**New further R247 compiled-ABI gate committed AFTER that verified
SHA, not yet executed on VM4707:** `tools/sse_pos_r247_v2_compiled_abi_parity.py`
checks Solidity compiler-emitted function signatures, every
on-chain event/indexed field, and public state tuple return types
against exact R226/R227/R229 Python readers. Added to
`scripts/r235_vm4707_v2_source_only_gate.sh` and source CI;
it is NOT yet a passing result. Exact new SHA must be pinned and
tested before live V2 use.

All new tool and contract source remains a draft, unmerged and
**not deployed to native chain31340**; no app wallet,
TEST-ETH funding, live lease transactions, independent physical
SLA, external-native peer admission or second independent
BLS validator is proven by the R235 source-only tests.

---

# R245 — Latest actual VM4707 integration evidence (2026-11-24)

On real VM4707, Python 3.12 isolated venv and source
`1c75859ae777d4b39a14071b37c4fb0b0c8a3af3`:

- **R226–R229: 38/38 PASS** (new adaptive V2 market/ledger ABI,
  public EIP-712 signature tests and read-only finalized mock policies).
- **R231–R239: 42/43 PASS**, 1 real-source ERROR: strict
  `type(path) is not Path` in R237 rejected the ordinary Linux
  `PosixPath` keystore returned by `Path(...)`.
- **R245 source correction committed**: use
  `not isinstance(path, Path)` while retaining encrypted
  keystore owner/permission/symlink restrictions, regression added.
  **R245 fix has not yet been retested on VM4707.**
- **No full Python source suite, R242 sender tests, new R236 contract
  compile/Foundry tests, or EIP170 deployed runtime-size acceptance
  yet**, due to fail-fast source gate. No live V2 deployed, signed
  or funded; no physical remote SLA proven.

This paragraph supersedes the historical R243 statement below that
none of the new Python source had been tested, as those tests have
since genuinely run on the actual VM. See
`docs/R244_VM4707_R235_FIRST_REAL_REGRESSION_SELECTOR_TEST_REPAIR.md`
and
`docs/R245_VM4707_R235_SECOND_PYTHON_GATE_KEYSTORE_PATH_TYPE.md`.

---

# R243 — Active draft R226–R242 real-role integration, SOURCE-ONLY (unverified)

As of 2026-11-23, new research integration work is on
`feature/r226-adaptive-v2-operator-runtime` draft PR #43,
**stacked on** `feature/r136-independent-observer-preflight`
draft PR #41; original `main`, VM4706 signing validator,
running VM4707/VM4709 observers, chain31340 genesis and wallets
have NOT been touched.

New source implements exact V2 unsigned ABI role actions, finalized
market+ledger event/runtime/lease audits, V2-specific EIP712
public signature tools and TTY consent-gated app-only signing,
V2 real HTTP Docker compute/provider/selected monitor evidence adapters,
public-DNS resource/SLA term commitments, per-node read-only status UI,
live-node actual gas/balance quoting, plus separately authorized
owner-local ONE-TX test ETH sender. R236 contract patch prevents
post-accept inactivity from indefinitely locking selected monitor
bonds; sealed no-quorum epoch fees remain escrowed for bilateral EIP712
resolution, and late consumer reactivation is rejected.

**CRITICAL:** NONE of R226–R242 sources, the amended R236 contract
or its added adversarial cases have yet been compiled/tested on
the user's VM. No source CI run reported PASS. The earlier R223
16/16 Foundry V2 success belongs ONLY to
`9a216518b3ea8c265f5186f6113987eb537d7949`, BEFORE
the new code. All new runtime/EIP170 sizes must be remeasured.
Explicit owner approval and a separate encrypted app wallet/funding
are required before any network transaction. No new native
testETH has been sent, no V2 market/ledger deployed, and no remote
physical independent SLA measured.

**Owner return:** see
`docs/R243_ADAPTIVE_V2_FULL_RUNTIME_INTEGRATION_AND_RETURN_GATES.md`
and `scripts/r235_vm4707_v2_source_only_gate.sh` at the exact
immutable branch commit provided in the return handoff.
If tests fail, correct through GitHub, not by patching a VM.

---

# R225 — New real two-node finalized checkpoint match, formal timing qualification

On 2026-11-23 the real VM4709 separately installed Besu+Lighthouse
observer reported the **same original chain31340 EL and CL genesis**
and **exact matching finalized Beacon epoch602/root**
`0x9d140067a9049103fc482221713f2f0c46cf7d0a89593bef4d6e19fb0dddecd7`
as VM4707. Both nodes independently reported 2 native EL peers and
2 native CL peers, no sync/optimism/offline flags; EL head17783 vs
17798, Beacon slot19394 vs19409. **Actual capture skew 181.223808s**
exceeded strict R141 180s compare requirement by 1.223808s. This is
**observed exact checkpoint agreement, NOT a formal same-window R141
`OBSERVED_CONSISTENT_CHECKPOINTS` result**. The earlier strict R192
epoch571 pair remains formally accepted. No live contracts, funding,
independent operators, external beyond-overlay P2P or physical SLA
were tested here. See
`docs/R225_VM4707_VM4709_FINALIZED_EPOCH602_MATCH_SKEW_RESTRICTION.md`.

---

# R224 newer actual network evidence — 2026-11-23 16:39:06 UTC

Original VM4707 **actual live two-layer R141 capture** (pinned source
`b02465bd6352bb87ae0f3109768a86aeed304141`): chain31340, correct
execution genesis **and Beacon validators genesis root**, EL head17783,
Beacon head slot19394, 2 native EL peers, 2 native CL peers, all
syncing/optimistic/offline flags false. **Finalized epoch602** with
root `0x9d140067a9049103fc482221713f2f0c46cf7d0a89593bef4d6e19fb0dddecd7`.
This is real live **VM4707-only** EL+CL health. VM4709 has NOT YET
been freshly checked at epoch602, and no contemporaneous two-host
finality match is claimed. Physical independent operators, global
Internet-native admission and V2 on-chain economics remain unverified.
Full observed report and restrictions:
`docs/R224_VM4707_LIVE_EL_CL_FINALITY_EPOCH602.md`.

---

# Current verified checkpoint — R223, 2026-11-23 (supersedes earlier 2026-11-21 source status)

On **real VM4707**, exact pinned source `9a216518b3ea8c265f5186f6113987eb537d7949`
was successfully compiled with Forge v1.9.0 / Solidity 0.8.24:
**68 Solidity sources; new adaptive V2 marketplace tests 16/16 PASS;**
full `forge test -q` returned exit 0 (full suite count not printed);
R201 mocked policy tests 5/5 PASS and R206 mocked audit policy tests
6/6 PASS. Observed operator gate ended with
`R222_SOURCE_AND_READONLY_GATES_COMPLETED=true`.
V2 runtime sizes: market 18,087 bytes; ledger 10,668 bytes.
Compiler/lint warnings remain and are **not** a security clearance.

The same VM4707 command independently queried the *original*
chain ID 31340 execution genesis and finalized EL block via localhost
JSON-RPC: EL latest **17751**, finalized **17621**, original genesis
`0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf`.
Original EOA `0x13fb73aace8A11Be2899D047635A757a224Ce00B`
at finalized state: **1,000,005.544827172 native TEST ETH, nonce 0**.
R201 did **not** read live Beacon root/peers and did **not** inspect V2
deployment addresses/code; do not construe its hardcoded
`marketV2Deployed:false` status as a chain-wide contract absence scan.

Historical real **VM4707+VM4709** cross-host EL/CL finality match
epoch571/root `0x48c1976b872c24b9fc00d8b7fd3c08e1b82a44534e3eb4034292c2621e25db63`
remains separately documented by R192. The later R223 EL-only probe
does not by itself refresh that cross-host proof.

**NOT YET VERIFIED:** current cross-VM CL finalized agreement after the
R223 time point; a new private application-only deployer EOA; funding
transactions; V2 market+ledger deployment receipts/runtime; live
provider/consumer/monitor SLA and payments; multiple independent
validator operators; outside-overlay globally permissionless admission.
No new genesis/validator, wallet import, broadcast or Docker changes
were performed by the R223 tests. Read
`docs/R223_VM4707_V2_SOURCE_GREEN_AND_LIVE_CHAIN_READONLY.md`.

---

# Verified state and gaps — updated 2026-11-21

## CURRENT chain31340 live evidence — supersedes older dated status entries below

**Live operator observations, 2026-11-21:** VM4706 runs original
Besu execution + Lighthouse Beacon and ONE original signing validator.
VM4707 runs separate real nonsigning Besu+Lighthouse peers.
On owner head slot 6549 (epoch 204) and observer head slot 6550
(epoch 204), both independently reported **previous justified epoch 201**,
**current justified epoch 202**, **finalized epoch 200**, identical
finalized root
`0x0e870e8687dd93737daf777c0a9c690a9ddc73bca03ac6b62fa44b3579a0a467`.
VM4707 Beacon `/eth/v1/node/syncing`: `is_syncing=false`,
`is_optimistic=false`, `el_offline=false`, sync distance 0.
Owner Beacon logs reported one native consensus peer, verified execution
payload hashes and advancing blocks. This is **REAL PoS FINALITY**;
historical entries stating that chain31340 has not launched are now stale.

**Limits of this milestone:** one BLS signing key/operator and two
same-cloud VMs, not multiple independent validator owners.
Dynamic Internet-wide P2P onboarding, outside-provider independent
connectivity, real third-party validator deposit/activation, authenticated
real cross-host resource leasing, monitor quorum and conservative SLA
settlement remain **NOT VERIFIED**. ZeroTier ad-hoc IPv6 is a public
controllerless overlay but still depends on ZeroTier underlay/root/relay
services; a VM overlay IP is not proof of ISP or physical independence.

**GitHub verification, 2026-11-21:** VM4707 tested R136/R137
targeted suites (6+7), corrected R54/R69 suites (11+6).
At integration revision `bb7d3db455231771a2b4eb5390aa185b77656070`
using isolated `.venv-tests`, full Python discovery ran
**920 tests, 1 failure, 0 errors, 3 skipped**. The sole failure was a
source-tree integrity conflict: obsolete `services/role-agent` existed
from a prior research restoration. New GitHub-only remediation moves
the legitimate non-signing monitor snapshot console to
`services/node-console`, updates its behavioral test and deletes
the obsolete `services/role-agent` path. **That remediation has not
yet been VM retested.**

**R140 current source-only:** finalized-chain31340 read-only marketplace
runtime/contract-binding audit tool and tests. No actual chain31340
marketplace contracts, bonds, leases or withdrawals are claimed.
The old `script/DeploySSEPos.s.sol` is explicitly chain31339;
`OpenMonitorCommittee` and `SSESettlement` still have fixed 4/3
committees. Adaptive and evidence-sound contract migration is a blocker
before the research-marketplace deployment.

Older entries below are retained as historical evidence of earlier stages
and MUST NOT be interpreted as current deployment status.

---


## Latest ACTUAL VM4706 checkpoint — 2026-11-20 Step40

- G1 actual: real pinned upstream binary successfully created 2,737,436-byte Beacon genesis.ssz (SHA256 8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82) from the one EXISTING real owner-derived BLS public validator. EL genesis SHA256 22eb6c58288113b9c3671970967151012665137b345237b5c24060dc988b1ee8 and CL config SHA256 839072fe3d4b2092b4867010ad01254145872969d89f66ecc86610700f381b13. Source R34 9/9 PASS. Exact SHA f8f36b0a9c2b696cfdd217c30f13e022831a8d6a. One real owner/physical fault domain. No active chain31340, real finality or Internet P2P verified by this step.
- R35 GitHub source only: native client exact artifact preflight, one-host Docker Besu+Beacon+existing validator client isolated startup, local read-only real health probe, seven source tests. NOT YET RUN ON VM. Do not claim signing/finality until owner reports actual results. See Entry055.

### Historical checkpoint context retained below
## Current verified checkpoint — 2026-11-20 (after previous R19 results)\n\n- **G1 Step39 ACTUAL 2026-11-20 VM4706:** owner ran SHA `447fa98292ba82b2c5966968d53fb67205a77bfb`, R33 pinned standard deposit source tests **7/7 PASS** plus R25/R30 genesis regression tests **19/19 PASS** (total 26/26); real existing R32 public-only contribution collector succeeded with EXACTLY 1 declared operator, 1 public BLS voting key, balance 32,000,000,000 Gwei and SHA256 `efc4d4d51c3acff8e8fa7238fb12428c6866c2d3d3d770f50ba6a98177a19140`. Output explicitly `blsProofOfPossessionVerified=false`, `executionGenesisVerified=false`, `consensusGenesisSszBuilt=false`, `readyToLaunch=false`. Owner-observed `== STEP 39 SOURCE AND PUBLIC CONTRIBUTION CHECKS COMPLETED ==`. **R34 new GitHub source only, NOT run on VM:** public-native EL/CL genesis input generator for this actual contribution, chain31340 TEST EOA funding and real Beacon SSZ builder preparation. Do not claim any new Genesis SSZ or live finality yet.\n

- **R33 current G1 SOURCE change after Step38 — NOT VM-tested:** The real `--build-single-operator-lab` path now requires the **standard ungated** Ethereum deposit runtime **and 31 constructor-initialized zero-hash storage entries**, from pinned upstream source commit `0b518636eec53e41e6d261f46ae07147d546a456`. Nonfunctional REVERT test fixture and arbitrary code do NOT pass the real-build preflight. Seven new tests in `tests/test_sse_pos_deposit_predeploy.py` and unchanged 19 genesis parser regression methods require **actual owner VM execution**; no passing result yet. No EL/CL artifacts built or tested by clients, and cross-layer forks / live deposit activation remain unverified. See `docs/R33_G1_REAL_DEPOSIT_PREDEPLOY.md`, Journal Entry053.
- **LATEST ACTUAL CHECKPOINT — VM4706 Step38 R32 REAL voting key derived, 2026-11-20:** At detached immutable `cc393edf498a7d552b7c9559c790e3dca0b55ee4`, source-only R32 derivation guards **8/8 PASS** plus shell syntax check. After independently entering `BACKUP-CONFIRMED` and `DERIVE-BLS-VALIDATORS`, the owner actually invoked the pinned offline Lighthouse v8.3.3 CLI against the **existing** EIP-2386 encrypted wallet to derive **one genuine EIP-2335 encrypted BLS validator voting keystore**. Real script reported `R32_REAL_OWNER_BLS_VOTING_KEYSTORES_CREATED=true`, `R32_BLS_VOTING_KEY_COUNT=1`, `R32_PRIVATE_SLASHING_PROTECTION_RETAINED=true`, `R32_PUBLIC_GENESIS_CONTRIBUTION_CREATED=true` and `R32_RECOVERY_BACKUP_ATTESTED_BY_OWNER=true`. Separate existing TEST-only withdrawal EOA is `0x13fb73aace8A11Be2899D047635A757a224Ce00B`. Backup is **human-attested**, not checked by source; exactly **ONE real operator fault domain**, not multioperator participation. **NEVER rerun R20/R27/R32 creators**. This actual event supersedes historical paragraphs below stating BLS keys absent/R32 unexecuted; retain those as historical snapshots only. **Still false/unverified:** BLS public subgroup/PoP, EL/CL chain31340 genesis and SSZ, actual PoS blocks/finality, native Internet P2P, independent peers, economic roles and real SLA/payout. The current genesis builder only checks EL deposit predeploy code **shape**, not functional contract bytecode or constructor-initialized deposit Merkle storage; generator/client interoperability and fork parity require real proof before launch. See journal Entry052.
- **VM4706 is a development/test VM, NOT a launched chain31340 node.** Last observed R24 pinned Git SHA `298518e51eeaf59477a92450fbec48bb8980eccd`: **31/31** adaptive funded-monitor Solidity tests PASS, **196/196** full Forge Solidity tests PASS across 22 suites, `forge build --sizes` shows R24 V2 runtime **10,675 bytes**. These are local EVM fixtures with simulated balances, NOT native PoS deployment or independently measured service.
- **G0 COMPLETE: Step31 Python source tests** actually passed at immutable VM4706 source `f1ddae763735fe365e49e7286ae83e5fb689ed3a`: **13/13** genesis builder preflight, **9/9** owner-private EIP2335 public-only metadata exporter, and **16/16** genesis contribution checks; **38/38 PASS**, zero errors, final completion marker observed. Expected negative file overwrite and unconfigured-build refusals were successful checks. These are source/security tests with **synthetic fixture keys**, NOT creation of any live BLS validator/SSZ/chain31340. Previous Step30 12/13 incorrect-test-exception result is resolved by this G0 rerun.
- **G1 PARTIAL REAL KEY CUSTODY VERIFIED:** On VM4706 at detached `ce31a21a13f68190c1f9478d67446e856694a21c`, the existing Cast encrypted TEST-only owner EOA was **successfully unlocked through a hidden keystore-password prompt by checksum-pinned Cast**, and the derived PUBLIC address matched `0x13fb73aace8A11Be2899D047635A757a224Ce00B`. Owner-private encrypted key was preserved, no secret output. Actual JSON field-name probe confirmed expected `crypto,id,version` with no embedded address; original R20 false rejection now understood/resolved. **DO NOT recreate wallet**; offline backup still the owner's responsibility. Updated Lighthouse v8.3.3 `--wallets-dir` offline CLI check **PASSED on VM** (`R27_PINNED_LIGHTHOUSE_OFFLINE_HD_WALLET_CLI_VERIFIED=true`). At separate HD-wallet creation prompt the owner entered an unrelated string rather than `CREATE-BLS-HD-WALLET`; script correctly **REFUSED without creating mnemonic/HD wallet/BLS signing validator**. Consent is absent, do not rerun automatically. Step33 wallet-report tests **10/10 PASS**, field-name probe tests **5/6 PASS, 1 incorrect test message expectation FAIL**; source-only assertion corrected R29, not yet VM-tested. Under set -e skipped recovery script 6-test and Lighthouse 8-test static suites. **No EL/CL chain31340 Genesis or SSZ, native TEST ETH/finality, P2P, VM↔laptop, or deployed roles exist.** Pinned Besu/Lighthouse/generator remain verified.
- **G1 source gate progress Step36 (ACTUALLY OBSERVED):** VM4706 at immutable SHA `47eeeb2785494b9ef56765c2884120f68e30cdd8` passed **6/6** safe encrypted Cast schema tests + **6/6** existing wallet recovery guards + **8/8** corrected Lighthouse wallet guards + **16/16** genesis builder safety checks = **36/36 Python tests** plus two `bash -n` checks; final Step36 marker observed. No new keys, wallets, chain or containers started. The owner-controlled BLS-wallet operation remains deliberately **REFUSED** at separate human confirmation. **R30 GitHub-only source AFTER Step36** adds explicit EL Shanghai/Cancun/Prague/Osaka ordering and CL Altair/Bellatrix/Capella/Deneb/Electra/Fulu fork epochs/version uniqueness, plus 3 NEW parser tests (builder suite now 19); **not yet VM tested**. These checks do NOT certify complete cross-layer fork parity or real deposit runtime.
- **G1 REAL owner-encrypted Lighthouse parent wallet now CREATED (new actual operator result):** At immutable SHA `891d49029968b4220d03974c5a5624027c8d023f`, VM4706 operator explicitly typed `CREATE-BLS-HD-WALLET` in private R27 script, which returned `R27_ENCRYPTED_HD_WALLET_CREATED_ON_OWNER_VM=true`, `R27_BIP39_MNEMONIC_WAS_NEVER_PRINTED=true`. Owner-local encrypted EIP-2386 HD wallet, 0600 random password file and 0600 recovery mnemonic file genuinely exist. No OFFLINE backup has been confirmed by the owner yet; user must back up before deriving staking keys. This newer SUCCESS supersedes older repeated refused attempts documented above; the old attempts remain historical facts. **No BLS validator voting keys are derived yet, no Genesis SSZ, Beacon duties or chain31340.** R32 GITHUB-ONLY script now allows creating actual owner-encrypted EIP-2335 voting keystores from that same parent wallet with separate `BACKUP-CONFIRMED` and `DERIVE-BLS-VALIDATORS` approvals; eight new static tests are source-only and NOT VM-tested. [R32 owner ceremony](R32_EXISTING_HD_VALIDATOR_DERIVATION.md), Journal Entries050–051.
- **R30 genesis fork tests ACTUALLY PASS (Step37):** VM4706 at detached `d3049cf1d1dd8178ea168d6e60f963bea2f1562a` executed `test_sse_pos_genesis_build.py` **19/19 PASS** and completion marker. This validates input schemas and ordering ONLY, not real/working deposit contract or EL/CL fork parity. Do not use the deliberate REVERT-stub test fixture as an authentic deposit runtime.
- **Role source, NOT live role deployments:** marketplace request/bid/fund/provider accept/monitor registration CLI and local provider/monitor agents exist as code; parts of legacy live-role scripts are **hardcoded for abandoned chain31339**. New `SSEAdaptiveVoteLedger` has 31 passing EVM tests for per-lease variable k/q, signed votes and real-contract escrow accounting (EVM fixture balances), but **not integrated** with honest permissionless election or V2 SSE service settlement. V1 still hardcodes 4 seats/3 votes; world-soundness counterexamples CE01–CE04 remain open.
- **Next real multi-VM work starts after first honest chain31340 native blocks and finality on VM4706, NOT after all contract/dashboards are done.** Second available VM is an actual EL+CL peer first, no validator keys or funds required; user's sole external laptop joins as first non-VM peer after real reachable P2P proof. Do not fabricate independent operators and do not impose fixed counts for any role. Exact acceptance gates and optional machines: [R26 execution roadmap](R26_EXECUTION_ROADMAP_AND_HOST_ROLES.md).
- Historical VM4705 DID operate real (but compromised-for-public-use) chain31339 with signed blocks/finality and SSE deployed; it cannot be repurposed for 31340 without clean independent genesis and key custody. R26 preserves separate experimental results rather than conflating VMs.

**Public network acceptance: NOT MET.**
The architectural target is defined in [ARCHITECTURE.md](ARCHITECTURE.md).
Do NOT confuse private single-host smoke data with a permissionless,
Internet-public deployment. Research claims require actual observations.

| Observation | Evidence and exact scope |
|---|---|
| Private PoS smoke VM | **Historical isolated chain31339** on VM4705, 4vCPU/11GiB, Besu EL+Lighthouse CL/VC, all operated on ONE host; **not public and not suitable for public reuse** |
| Consensus | Execution blocks increased to at least 1157; Beacon finalized checkpoint previously observed |
| Deployed source | SSE Solidity R16 commit `cd2fe67e3031d4f25c41bfc714c6539b7ca1ebef` |
| Committee | `0x9965bAC16C5Df538df0373a906e42eA0E0C327d9` |
| Settlement | `0x879878f7561F5a0a1f6dd22348FfdE81cD5fEe7F` |
| Board | `0xF1147CA8aC9e28F845529A6Ae5837873806C7788` |
| Deployment receipts | Seven canonical successful tx in blocks 953–959, 10,947,092 total gas; **finalized by execution block 1088**, verified by VM4705 R18 tool |
| Python tests | **51/51** targeted `test_sse_pos_*.py` passed at Git SHA `f846e770744fb18f3364801781d9075498eacc6b` |
| Foundry tests (historical) | **147/147** EVM Solidity tests passed at R16 on earlier historical source; superseded for current R19 validation by the separate VM4706 run below |
| Faucet | 1M genesis-allocated TEST ETH; no real ETH |
| User wallets | Faucet, consumer, provider and monitor01–05: eight encrypted local keystores on VM4705 |
| Local role funding | Attempt failed BEFORE broadcast in R18 due to EIP-55 checksum; R18b fix passed 51/51 Python tests, not yet retried live |
| Monitor bonds | **ZERO active registered candidates** in latest user-observed read-only plan |
| SSE real workload | **No real cross-host consumer/provider/monitor SLA execution witnessed** |
| Public PoS P2P | **No independent remote P2P peer or dynamically readdressing seed witnessed** |
| Public validator joining | **No new BLS deposit/activation from an independent host witnessed** |
| Genesis key security | First upstream PoS launch printed genesis consensus mnemonic and premine private keys. **Compromised for any Internet-public use.** |

**Chain identity and custody:** The preceding VM4705 chain was **31339** (historical, one-operator, leaked genesis mnemonic/private key material). It must never be published or repurposed as the independent public network. **31340** is a *proposed new chain ID*, not an already validated or deployed network; its genesis, independently generated validator identities, and Internet P2P remain outstanding. These chain IDs are not real Ethereum Mainnet and contain only worthless TEST ETH.

**Important distinction:** The successful ledger is genuine PoS and
the three SSE contracts genuinely exist there. But 32 genesis
validator BLS identities under one operator, and seven application
EOAs under one VM, do not represent independent operators. A quorum
of four SSE monitors on one VM is also not physical independence.

**New public system:** None of the entries above establishes the
fresh multi-operator public chain31340, public reachable P2P, or
permissionless external validator entry. It has to be launched with
independently created **non-exposed** genesis keys. No legacy
QBFT/Tailscale gate is acceptable as a substitute.

## R19 fresh-host source validation on VM4706 (latest observed)

**Verified from the operator's actual terminal outputs on 2026-11-19; NOT a deployed Internet-public network:**

| Check | Observed result and immutable revision |
|---|---|
| Fresh-host/architecture/public-manifest Python suites | **31/31 PASS** at `5fa84572f83bb58c0cddf97d59a5e381df8bc414`; exact checks 13 + 5 + 13 |
| Foundry v1.9.0 provenance | Official Linux amd64 release SHA-256 `8d17599b42e3139f1a9c171be3798c4ed8e743ae17b84cc3435e57bf2a51ae99` verified and installed on VM4706 |
| Solidity compile | **60 files compiled using solc 0.8.24** at Git SHA `c4acd52379710bec399e5af90ace3c9c31aa4a8c`; significant static warnings remain to audit |
| Faucet source EVM tests | **12/12 PASS**, included inside full EVM suite; test-only transfers, NOT live test-ETH distribution |
| Full EVM Solidity suite | **20 suites, 155/155 PASS, 0 failed/skipped** at `c4acd52379710bec399e5af90ace3c9c31aa4a8c` |
| Docker daemon and native client executable checks | Docker server 29.1.3 with cgroup v2; Besu **26.11.1** by digest `4fd2ba40f0d65917bcb3abd9af60673946f66dee2ecb1b87f7cdfa6a30fe458d` and Lighthouse **v8.3.3** by digest `53f9063d98c3d3a2d290207873f019ea2298cfc02f8cd58d87c33b04aab856d1`; version-only isolated runs at `2908450be6e3360d58ea35d64f7a72bcfa4f5f43`; **no native P2P** |
| Client diagnostics | Previously nonfatal Besu Log4j `UnknownHostException` **resolved by actual VM4706 offline by-digest retest** at `ef495d358462437a155e7689d7ea96f678303d77`; 7/7 image pin tests PASS |

**Critical blockers:** proposed new chain31340 execution/Beacon genesis is not built; independent owner-generated BLS/EOA keys and 32 worthless-test-ETH deposits are not activated; no unrelated remote EL/CL P2P clients joined; no production faucet, consumer escrow, bonded independent monitors, verified resource delivery or per-node public HTTPS UI; no final no-central-authority and entropy-security audit. Historical chain31339 remains unsuitable for public use. Repository is still private and the developer deploy key must never become public-network admission.

**More recent VM4706 milestones:** official Beacon genesis generator v0.0.8 installed with verified archive SHA-256 and actual binary SHA-256; **14/14** genesis contribution tests passed and checksum-verified existing tool reuse succeeded at `2eec47e0619c8b2fd0a28991fe33ac218f5ab2b0`. The later owner-wallet source suite at `a7955a2afbf7eb57f67d142bdb6069a88271dae1` ran **6 tests: 5 PASS, 1 FAIL**, caused by a false-positive test assertion matching the harmless `"privateKeyPrinted": false` status; source-only test corrected, **not yet VM rerun**. Because `set -e` stopped the command, **NO new operator wallet was generated**.

**Critical adaptive-role blocker (user reaffirmed 2026-11-19):** public network may not impose a fixed number of nodes in **ANY role**. Current `OpenMonitorCommittee.sol` and `SSESettlement.sol` still hardcode four monitors and 3/4 quorum, including selection/confirmation/escrow ABI. They are **NOT production-adaptive**. The new `AdaptiveMonitorQuorum.sol` and ten Foundry test methods are **source-only mathematical preparation** not yet integrated or VM-tested; actual variable committee/threshold contract migration, independent SLA samples and fault-domain checks are required (#38). Per-genesis security minimums are now explicit configurable inputs, not permanent network role-count defaults. See [R21 adaptive requirements](R21_ADAPTIVE_ROLES_AND_QUORUM.md).

**Testing accounting:** 31 Python and 155 Solidity tests passed in **separate runs on separate immutable Git source revisions**; do not claim a single complete 186-test run at one SHA or conflate Foundry test doubles with a public blockchain.

The full exact command/commit/failure ledger is [VM4706 experiment journal](experiments/VM4706_2026-11-19.md).

## Repository hygiene

The former `main` at `7e86edb9aff6a2e45eac940cf7ced3b2c88f2bea`
was 264 commits behind the R18b working integration branch and
incorrectly presented Anvil as the current runtime. The cleanup
work is reviewed on `refactor/permissionless-public-pos-mainline`
with a PR to `main`. Before merge, run Python/Foundry tests on a
clean checkout and review retained executable dependencies.
The snapshot branch
`archive/legacy-pre-public-pos-2026-11-19`
preserves the full previous integration tree for historic grading,
research reproducibility and potential migration.

CI/test status and current architecture MUST be refreshed from the
exact new GitHub commit: no static audit document or passing mock
unit test can prove live public Internet behavior.
