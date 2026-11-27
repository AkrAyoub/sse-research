# R283 — VM4714 owner nonroot Docker access denied; separate, EXPLICIT sudo-only dedicated CPU worker trial

## Actual user evidence, 2026-11-24

On VM4714, exact source SHA `847f3196cedad92963e0854e628aa20a2ce4acca`,
R281 dedicated real CPU worker eight mocked source safety tests **PASS**.
The real no-effect `--preview` showed:
`sse-compute-vm4714`, 0.5 CPU, 256MiB memory+swap,
nonroot UID10001, read-only filesystem, PIDs limit32,
all Linux capabilities dropped, built-in seccomp,
no-new-privileges, bridge network and loopback-only
`http://127.0.0.1:8877` port. Actual local Docker
socket `/var/run/docker.sock` is
`srw-rw---- root:docker`, user
`ayoubakrvm4714` `docker --host unix:///var/run/docker.sock ps`
returned **permission denied**. Neither `--run`
nor a real Docker compute worker was started.
The guessed Ubuntu rootless script path
`/usr/share/docker.io/contrib/dockerd-rootless*.sh`
was NOT present on this actual VM4714.
Do NOT add VM4714 owner to Docker group or chmod
the daemon socket; Docker group membership has
root-equivalent privilege on the host.

Separately on VM4707 the owner ran new R282
six offline tests PASS and actual one-shot read-only
quote. Actual returned
`MONITOR2_NOT_FINALIZED_NO_STANDBY_FUNDING_QUOTE`;
therefore exact previously approved Monitor2
nonce3 was still not finalized at that R282 read.
No extra RPC recipient quote, new approved funding,
signing or transaction occurred.
The exact preceding Monitor2 tx is
`0x0c6b2e79f930b8e23e5ee9b32bd151733bb09d88a7ecbc8c145cec091cdb389a`,
included successfully/canonical at block26008
with 132-block finality lag in the PREVIOUS
R278 observation, but R282 did not give new
finalized height. Preserve the original R267
marker and never resend.

## R283 GitHub source-only change: explicit dedicated-rootful Docker test escape hatch

Because VM4714 is a DEDICATED 2-vCPU compute-only
lab VM — **not the original live PoS Docker host**
— the existing `scripts/r281_vm4714_real_compute_worker.sh`
now allows a THIRD strictly explicit
`--run-sudo` option. It is not the default.
The original `--preview` remains read-only; the
original `--run` remains nonprivileged and
automatically refuses on Docker permission denied.
`--run-sudo` requires:

- Exact nonroot OS owner `ayoubakrvm4714`,
  exact clean reviewed Git SHA pinned in command,
  existing source, actual interactive human terminal.
- Owner types the distinct exact authorization
  `START-ONE-R283-DEDICATED-VM4714-SUDO-DOCKER-COMPUTE`.
- Real `sudo -n` privilege must ALREADY be
  configured and passwordless. **No** sudoers
  edits, user group changes, new password,
  daemon installation or restart. If unavailable,
  the script fails closed before creating a
  container. `sudo -n docker` is a root-equivalent
  action on that ONE host and should be regarded
  as experimental only, not a permanent,
  unattended rootless worker deployment.
- Exact `/var/run/docker.sock` root-owned
  local UNIX socket; explicitly
  `sudo -n docker --host unix:///var/run/docker.sock`.
  Remote `DOCKER_HOST`, `DOCKER_CONTEXT`,
  `DOCKER_TLS_VERIFY`, `DOCKER_CERT_PATH` disabled.
- **Refuses if any Docker containers already exist**
  on VM4714. Never kills or alters any
  unrelated containers. Docker image build,
  run and later per-request inspect can
  operate only on dedicated VM4714.
- Builds existing `Dockerfile.sse-compute`,
  measures real sha256 image ID AFTER building,
  starts exactly one container named
  `sse-compute-vm4714`.
- Strict container runtime limits: 0.5 CPU,
  256MiB memory+swap, 32 PIDs, UID10001
  nonroot worker, read-only rootfs, all
  Linux capabilities dropped, no-new-privileges,
  built-in seccomp, isolated bridge networking,
  only host binding `127.0.0.1:8877:8877`.
- Newly extended generic inspection in
  `tools/sse_compute_docker.py` accepts an
  explicitly opted-in
  `dedicated_vm4714_sudo_docker=True`.
  It REFUSES root caller, any other VM account,
  wrong container name, wrong endpoint,
  rootless socket mix or non-strict hardening.
  It restricts the actual privileged command
  to **read-only** `sudo -n docker --host
  unix:///var/run/docker.sock container inspect
  sse-compute-vm4714` and validates exact
  image digest, CPU/RAM, security and loopback
  binding before independently probing the real
  SHA256 workload from localhost.
- One fresh OS-generated 32-byte challenge
  is passed to actual 8192-round CPU worker.
  Strict actual Docker inspection and independently
  recomputed result must BOTH succeed before
  claiming real pre-lease CPU run. If either
  fails, remove ONLY newly created worker's
  exact container ID; no PoS clients or
  foreign containers affected.
- It never loads the VM4714 encrypted app
  private key or changes any native chain31340
  funds, validator, keystore or contract state.

Eight new mocked tests:
`tests/test_sse_pos_r283_vm4714_explicit_sudo_compute.py`
cover true explicit local-only host, wrong user,
root denial, rootless mix denial, unhardened
inspect rejection, forbidden container identity,
insecure worker policy refusal and source script
non-TTY refusal BEFORE invoking any privileged
command. They are authored but **not yet actually
executed on VM4714**.
All previous R281 8 focused tests and R275
Docker16/V2 provider5 focused suites should
continue to pass (verify on owner VM).

### Owner command: first check tests and sudo Docker access

```bash
(
 set -euo pipefail
 SHA="<NEW_EXACT_GIT_SHA_FROM_CHAT>"
 cd "$HOME/sse-v2-standby-source"
 git fetch --no-tags origin feature/r226-adaptive-v2-operator-runtime
 git switch --detach "$SHA"
 test "$(git rev-parse HEAD)" = "$SHA"
 python3 -B -m unittest discover -s tests \
   -p 'test_sse_pos_r283_vm4714_explicit_sudo_compute.py' -q
 python3 -B -m unittest discover -s tests \
   -p 'test_sse_pos_r281_vm4714_real_compute_worker.py' -q
 PY="$HOME/.local/share/sse-v2-app-only/pyvenv/bin/python"
 "$PY" -B -m unittest discover -s tests \
   -p 'test_sse_compute_docker.py' -q
 echo "== PRIVILEGED READ-ONLY DOCKER INVENTORY; NO INSTALL =="
 if sudo -n docker --host unix:///var/run/docker.sock \
   ps -a --format '{{.Names}} {{.Status}}'; then
   echo "VM4714_LOCAL_SUDO_DOCKER_ACCESS_READONLY_VERIFIED=true"
 else
   echo "VM4714_LOCAL_SUDO_DOCKER_ACCESS_DENIED=true"
 fi
)
```

If all safety tests pass, sudo -n Docker works,
and no existing containers appear in the
inventory, the owner MAY CHOOSE to explicitly
start the experiment locally:

```bash
(
  set -euo pipefail
  cd "$HOME/sse-v2-standby-source"
  SHA="<SAME_FULL_GIT_SHA>"
  test "$(git rev-parse HEAD)" = "$SHA"
  bash scripts/r281_vm4714_real_compute_worker.sh "$SHA" --run-sudo
)
```

Only the second command builds and starts
an actual rootful-daemon-hosted but nonroot-worker
Docker container. The owner TTY confirmation
is mandatory. If sudo inspection is unavailable
or other running Docker workloads are present,
**do not run the second command**; review
separate rootless options instead.

## Security and research reporting

This is genuine CPU instruction execution and
local Docker containment, NOT a trusted hardware
attestation, real pre-funded lease, onchain monitor
measurement, proof of independence from cloud
infrastructure, or public signed SLA. The R234
finalized-lease provider response remains
separately gated. Permanent offchain provider
service should use rootless or least privilege,
not a broadly privileged Docker API. No
new standby funding is authorized by the
R283 changes; R282 remains a read-only quote.
