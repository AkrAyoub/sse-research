# R285 — VM4714 actual Docker inventory: ONLY three five-month-old exited hello-world containers; preserve all, permit one isolated real worker only under strict proof

## Actual owner results on 2026-11-24

VM4714 ran pinned R284:
- **R283 8/8 focused safety tests PASS** after prior fake-shebang test fix.
- **R281 8/8 real worker wrapper source safety tests PASS**.
- **SSE Docker inspector 16/16 tests PASS**.
- Total owner test assertions **32/32 PASS**.
- `sudo -n docker --host unix:///var/run/docker.sock ps -a --no-trunc`
  returned **only 3** containers, all image `hello-world`,
  all `Exited (0) 5 months ago`:
  - ID `0736e142f5d925c8a63771d6ce08d02cc2723509e06f9d3b638f35d306f88084`
    name `serene_sammet`
  - ID `dc71dc02b5e4375535c2fc69e90c0dc62322e72a4550b46e0c7f6d90f6e9434c`
    name `friendly_saha`
  - ID `ff494d7657a18a7f0a6ecce74ceb9edf97250c8ae64cacaa23aa166d8524aade`
    name `zealous_wilson`
- No running Docker containers appeared. Do not confuse
  exited hello-world leftovers with live native EL/CL PoS nodes.
  These are still owner-existing objects and **MUST BE PRESERVED**
  (no rm, stop, prune, rename or restart).
- No actual new compute Docker container or CPU benchmark
  has been owner VM4714-executed yet. Unit tests and
  preview are not physical SLA proof.

Separately, actual owner VM4707 R278 independently confirmed
all THREE original authorized native chain31340 funding transfers
FINALIZED. R282 actual read-only four newly generated
VM4711/4712/4713/4714 EOA funding scenario verified real
RPC gas, chain, exact clean recipients and sender nonce4.
It proposes **0.005 TEST ETH to each** (total value0.020,
maximum debit **0.020000000084 TEST ETH** including gas)
but the owner has NOT separately authorized these four
new native transfers, and no onchain registration, staking
or provider bond is authorized.

## New R285 strict read-only existing-container preservation gate

New GitHub
`tools/sse_pos_r285_vm4714_preserve_existing_docker_readonly_gate.py`
has **ONE mode only** `--audit`, and requires real nonroot
VM4714 OS username `ayoubakrvm4714`. It executes
only bounded fixed:
- `sudo -n docker --host unix:///var/run/docker.sock
  ps -a --no-trunc --format '{{.ID}}'`
- `sudo -n docker --host unix:///var/run/docker.sock
  container inspect <exact three full public IDs>`
- repeat the same read-only full-container-ID listing to
  detect intervening creations/removals.

The gate requires EXACTLY the three public observed full
IDs in the original owner's inventory, each with its
individually observed name, `Config.Image=hello-world`
or `hello-world:latest`, `State.Status=exited`,
`Running=false`, `Paused=false`,
`Restarting=false`, integer `ExitCode=0`.
Unexpected fourth container, changed name, different
image, live/exited-nonzero status, wrong owner,
root process, malformed JSON, unavailable privileged
read-only inspection or changed inventory all REFUSE.
The daemon host is explicit fixed local UNIX socket,
never a Docker context/TCP/remote. No `docker rm`,
`start`, `stop`, `run`, `build` or OS mutation
in this audit module. Its stdout is only a public
evidence report; no keys or wallets opened.

New `tests/test_sse_pos_r285_vm4714_preserve_existing_docker_gate.py`
contains **9 mocked safety tests**. Neither these tests
nor R285 live audit have yet been run on VM4714.
They are staged source-only.

## Single-owner explicit real compute worker invocation

Existing R281 strict trial script now checks the R285
read-only gate (only when owner's EXPLICIT `--run-sudo`
is chosen) before proceeding past its original
no-existing-container protective guard. It allows
**ONLY three exact old benign exited hello-world
containers**, leaves them untouched, refuses other
present containers. Nonprivileged `--run` retains
no-existing-containers requirement.

After R285 owner tests and actual read-only audit pass,
the owner can separately choose `--run-sudo` again.
The script requires its own exact typed consent
`START-ONE-R283-DEDICATED-VM4714-SUDO-DOCKER-COMPUTE`,
rechecks local Docker inventory, invokes R285 again
before building. Then it builds the existing project
Dockerfile, measures real sha256 image ID and starts
only `sse-compute-vm4714`:
- **0.5 CPU** and **256MiB memory+swap**
- strict actual measured `NanoCpus`, `Memory`,
  `MemorySwap`, PIDs limit32
- read-only rootfs, UID10001 (nonroot),
  drop ALL capabilities, seccomp=builtin,
  no-new-privileges, auto-remove
- Docker isolated bridge network with only
  localhost `127.0.0.1:8877` host port.
- Actual strict `sudo -n docker --host unix:///var/run/docker.sock
  container inspect sse-compute-vm4714`, only
  under VM4714 nonroot owner and opt-in,
  rejecting wrong names/ports/daemon.
- Actual bounded local HTTP `/healthz`
  readiness check (up to 12 attempts at
  0.25s intervals; no synthetic status).
- Actual fresh OS random requestHash and **8192 SHA256
  rounds** performed inside actual Docker CPU container
  plus independent local recomputation and real
  observed elapsed time.
- It removes **only the newly created exact
  worker container ID** if start/probe fails.
  It NEVER deletes/starts/changes any of the
  three original stopped hello-world containers.

This trial is an actual resource-controlled local
CPU workload, NOT paid SLA, trusted hardware
attestation, independent outside-ISP provider
reachability or onchain settlement. The worker
stays localhost-only until a separately reviewed
authenticated HTTPS ingress is actually established.
No native TEST ETH, encrypted EOA, BLS consensus
keys, native EL/CL clients or deployments are touched.
Privileged Docker access is root-equivalent on this
DEDICATED VM4714, and is accepted only for a bounded
first research proof under explicit owner TTY
authorization, not production permissionlessness.

### VM4714 read-only first command after GitHub update

```bash
(
 set -euo pipefail
 cd "$HOME/sse-v2-standby-source"
 SHA="<NEW_EXACT_SHA_FROM_CHAT>"
 git fetch --no-tags origin feature/r226-adaptive-v2-operator-runtime
 git switch --detach "$SHA"
 test "$(git rev-parse HEAD)" = "$SHA"
 python3 -B -m unittest discover -s tests \
   -p test_sse_pos_r285_vm4714_preserve_existing_docker_gate.py -q
 python3 -B -m unittest discover -s tests \
   -p test_sse_pos_r283_vm4714_explicit_sudo_compute.py -q
 "$HOME/.local/share/sse-v2-app-only/pyvenv/bin/python" -B \
   tools/sse_pos_r285_vm4714_preserve_existing_docker_readonly_gate.py --audit
)
```

If R285 actual test+audit passes AND the owner
still chooses to perform this physical CPU
experiment, invoke **separately**:
`bash scripts/r281_vm4714_real_compute_worker.sh "<SAME_SHA>" --run-sudo`.
This does actually build a real image/start
a resource-controlled new worker; user must
type local explicit consent. NEVER run the
worker script on VM4706, VM4707 or VM4709
original PoS containers, and never delete
existing hello-world containers.

## Future roadmap gates

After actual local CPU work succeeds, next are:
public DNS/HTTPS authenticated provider ingress
from independent monitor machines VM4711-4713,
real EOA funded/registered market participants,
actual bonded eligible monitor committee,
funded finalized lease, real onchain challenge,
signed provider response bound to the real
CPU Docker output, offchain votes/evidence
and finalized payouts/refund/inconclusive.
Any new native grants to the four new wallets
and their eventual onchain bond/stake tx
need separate exact owner authorization.
