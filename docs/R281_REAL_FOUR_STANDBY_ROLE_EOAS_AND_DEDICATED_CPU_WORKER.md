# R281 — VM4707 Monitor 2 real canonical pending-finality; 4 encrypted standby EOAs created; VM4714 real Docker CPU worker staged

## Actual owner logs on Nov 24, 2026 — NOT synthetic

### VM4707 last of three approved funding transactions

Owner `R267 --send --role monitor-2` (pinned previous R267 source)
actually typed the exact owner terminal phrase and entered the hidden,
existing VM4707 app-deployer keystore password. R267 records one-time
attempt and reported actual single RPC raw transaction ACK. Hash:

`0x0c6b2e79f930b8e23e5ee9b32bd151733bb09d88a7ecbc8c145cec091cdb389a`

Actual original native chain31340, existing VM4707 source
`0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0` nonce3,
recipient `0xf8D4c882A7439507e2fc237DCBDf4A1c228F0FF8`,
value **5000000000000000 wei / 0.005 TEST ETH**,
21000 gas *1000wei/gas max 21000000wei fee.
R267 checked finalized original R206 contract deployment,
original genesis and BOTH prior consumer+Monitor1 funds
canonical/finalized before send.

Owner then ran R278 5/5 focused tests PASS and
actual strict single-shot public-only transaction forensic
at Git SHA `52033d7099a9981d6652de27d5e23cb3f20388e4`.
Exact `MATCHING_TX_SUCCESSFUL_CANONICAL_PENDING_FINALITY`,
canonical successful inclusion block26008, EL head26011,
finalized EL25876 (**132 blocks gap AT THAT OBSERVATION**),
recipient latest balance 0.005 TEST ETH, finalized balance0;
sender latest+pending nonce4.
**R278 is read-only**; `allThreeApprovedRoleTransfersFinalized=false`
at that time. Later finality not yet submitted by owner.
DO NOT resend Monitor2 nonce3 or delete its one-time marker.
Use same owner VM4707 R278 read-only tool to check finality
until it reports `MATCHING_TX_SUCCESSFUL_CANONICAL_FINALIZED`.

### Four REAL separate standby VM encrypted EOA wallets

Four uploaded owner terminal logs `Pasted text.txt` through
`Pasted text (4).txt` on separate observed VM sessions:
each pinned source SHA52033d709..., ran R279 seven
focused tests PASS, owner interactive exact role TTY
consent and encrypted wallet password entry and confirmation.
Existing `requirements.txt` dependencies actually
installed into private owner venv, new individual encrypted
keystore files created once 0700/0600, no secret printed.

| Host | Actual app-only role | Actual new EOA |
| --- | --- | --- |
| VM4711 | adaptive-v2-monitor-vm4711 | `0x1a89D81288522912643e15D8e06a2a7D9dc4bc08` |
| VM4712 | adaptive-v2-monitor-vm4712 | `0x30dc70daA83B2D4199B98Cf1b93f31f1BA80f0Aa` |
| VM4713 | adaptive-v2-monitor-vm4713 | `0x001f529E8d17A243078631100CA7Ad93c001Ea2d` |
| VM4714 | adaptive-v2-provider-vm4714 | `0x016B91ED50Ec350e600327C4287F2ED882E0Cf66` |

No TEST ETH funded into these four wallets;
no market registration, monitor bond, CPU worker, SLA,
public HTTPS service, external P2P admission or onchain
paid job proven yet. Separate app wallets on separate
VMs support a distributed-role test but do NOT prove
separate organizations/ISPs/hypervisor fault domains.
Shared patch template hostnames should NOT be confused
with separate OS usernames or actual network independence.

Public-only original factual evidence:
`evidence/r280_vm4707_monitor2_canonical_pending_and_four_distinct_standby_role_wallets_created.json`.

## Next actual physical CPU work on dedicated VM4714

The existing real `Dockerfile.sse-compute` implements a CPU-bound
8192 SHA256-round challenge worker. New
`scripts/r281_vm4714_real_compute_worker.sh`
stages two explicitly different modes:

**`--preview`**:
- Requires source Git HEAD exact 40-hex SHA, original clean tracked source,
  exact nonroot user `ayoubakrvm4714` (not an onchain protocol role limit),
  expected existing application sources.
- Prints immutable planned CPU worker and bound loopback resources:
  **0.5 CPU**, **256MiB memory+swap**, **32 PIDs**,
  UID10001, read-only filesystem, all capabilities dropped,
  seccomp=builtin, no-new-privileges, isolated bridge network,
  local only `127.0.0.1:8877`.
- **NO Docker, network, wallet, EVM, BLS or host changes.**

**`--run`**: optional genuine pre-lease physical worker trial,
one actual owner-TTY typed authorization per execution.
This mode WILL build an actual Docker image and start exactly one
named Docker container **only on dedicated VM4714** (not the
native EL/CL VM4706/4707/4709), and:
- Requires nonroot owner local Docker `unix:///var/run/docker.sock`
  permission. No sudo, docker group change, remote contexts,
  network daemon exposure or privileged root fallback.
- Refuses to touch a VM with any existing Docker containers
  (`docker ps -a -q` nonempty). This is deliberately more
  restrictive than generic resource-provider node onboarding;
  only for this first dedicated host test.
- Uses existing source `Dockerfile.sse-compute`,
  builds actual image, captures real post-build sha256
  image ID, then launches exactly named
  `sse-compute-vm4714` with resource/security caps above.
- Uses strict existing `tools/sse_compute_docker.py`
  real `docker container inspect` of the exact
  image/CPU/RAM/security/port config, and calls existing
  actual local HTTP compute service using cryptographically
  random per-test challenge, independently reproducing
  its real 8192-round result with elapsed CPU timing.
- If startup or strict live probe fails, removes **only
  the newly created exact Docker container ID**, and
  does not kill/restart unrelated services. If success,
  one pre-lease worker stays running on localhost only.
- Never touches keys or sends transactions; this run
  does NOT prove trusted hardware, 3rd-party monitoring,
  onchain service/lease or financial SLA. Real workload
  is not a fabricated CPU utilization claim.

New 8 mocked script preview/source-syntax regression
tests in `tests/test_sse_pos_r281_vm4714_real_compute_worker.py`
are staged **not yet owner VM4714 run**.
R281 `--run` has **not yet been performed** by the owner.
An actual Docker socket access check MUST be performed
before deciding to use `--run`; user may have insufficient
unprivileged Docker permissions as on VM4709.
The project original application wallets must NOT be
copied or replaced for this worker trial.

### VM4714 safe FIRST test and Docker permissions discovery

After GitHub checkout at the newest exact pinned SHA:

```bash
(
 set -euo pipefail
 cd "$HOME/sse-v2-standby-source"
 SHA="<EXACT_CURRENT_SHA_FROM_CHAT>"
 test "$(git rev-parse HEAD)" = "$SHA"
 python3 -B -m unittest discover -s tests \
   -p 'test_sse_pos_r281_vm4714_real_compute_worker.py' -q
 bash scripts/r281_vm4714_real_compute_worker.sh "$SHA" --preview
 echo "== NONMUTATING LOCAL DOCKER SOCKET =="
 ls -l /var/run/docker.sock || true
 echo "== CURRENT OWNER DOCKER ACCESS =="
 docker --host unix:///var/run/docker.sock ps \
   --format '{{.Names}} {{.Status}}' 2>&1 || true
 echo "== ROOTLESS UBUNTU SCRIPTS EXISTENCE =="
 ls -l /usr/share/docker.io/contrib/dockerd-rootless*.sh \
   2>&1 || true
)
```

No sudo and no actual Docker start. If rootful Docker owner
permission is denied on VM4714, DO NOT automatically add
user to Docker group (equivalent to root on that host);
instead separately review a dedicated rootless engine,
or an explicit limited owner-approved rootful worker
setup on this **dedicated** compute-only VM.
Ubuntu package may provide rootless scripts in
`/usr/share/docker.io/contrib` even though R274
`command -v` found none; no automatic package install
or daemon migration is authorized.

Once a real pre-lease CPU worker is proven on VM4714,
next user-approved steps are public HTTPS with
authenticated transport, resource profile hashed by
R233, actual finalized provider/consumer onchain
request/bid/escrow and a committee of bonded eligible
monitors. Existing R234 provider wrapper correctly
refuses to issue signed onchain service responses
until the real finalized lease+epoch prerequisites
are satisfied. The 0.5CPU/256MiB worker example is
a resource-constrained first *real* measurement,
not a product SLA promise.
