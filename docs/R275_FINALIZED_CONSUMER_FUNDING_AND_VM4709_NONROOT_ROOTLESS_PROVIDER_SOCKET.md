# R275 — Actual original chain31340 consumer funding FINALIZED; R234 provider now has explicit private-rootless Docker inspection mode

## Genuine owner VM4707 R271 evidence (2026-11-24)

Actual VM4707 user command `tools/sse_pos_r271_consumer_native_tx_finality_snapshot.py`
(one-shot, no send) proves:

- Original chain31340 + Beacon genesis verified.
- Consumer actual native nonce1 TEST ETH TX
  `0x9f3a13cb295b5ba2f642804a30c391b9cce266784a83dd293d0dd7fb7d1f9fdd`,
  included block **25564**, now **SUCCESSFUL_CANONICAL_FINALIZED**.
- Actual EL finalized **25588**, head **25728**; finality gap **0**.
- Consumer EOA `0xD74A2aBC5a906BaFe39471CEe222c48BDD62DE3f` holds actual 0.01 native TEST ETH
  both `latest` AND `finalized` (10000000000000000 wei).
- Beacon head slot27340 epoch854, finalized epoch850 (lag4); real PoS finality
  advancing, no reset, patch or synthetic block.
- The user has separately approved three *specific* role EOA funding
  transfers; so **Monitor1 nonce2** recipient
  `0xd63b2Ba14E8aD16Cf5f494259dAE05AD59fE0147`
  with value `5000000000000000 wei`, exact gas 21000
  at 1000wei/gas can now be proposed to R267 **once**
  with real fresh preflight and each terminal approval.
  **No actual Monitor1 send has yet been observed.**
  Monitor2 nonce3 must await Monitor1 finalized receipt.
  Never resend consumer nonce1.

### Exact already-tested VM4707 owner R267 command

On **existing VM4707 checkout pinned to commit**
`4eafadae5e27a6bc5ff6467c3a76996858dbdcb5`
at `/tmp/tmp.Ridv9nIavf/repo`, operator may run
the previously granted **ONE** Monitor1 transfer
using default R267 independently reverified R206 and prior
consumer finalized eligibility and existing app-only keystore:

```bash
(
  set -euo pipefail
  cd /tmp/tmp.Ridv9nIavf/repo
  SHA="4eafadae5e27a6bc5ff6467c3a76996858dbdcb5"
  test "$(git rev-parse HEAD)" = "$SHA"
  /tmp/tmp.Ridv9nIavf/testvenv/bin/python -B \
    tools/sse_pos_r267_vm4707_one_by_one_role_funding.py \
    --source-sha "$SHA" --role monitor-1 \
    --rpc http://127.0.0.1:28545 --send
)
```

Never blindly rerun after the single-attempt marker is consumed
even if node response is ambiguous. Preserve hash.

## VM4709 actual R274 readiness

Owner R274 seven actual focused tests PASS on VM4709.
Actual owner runtime directory private 0700, subuid/subgid
each have 65536 distinct subordinate IDs starting165536.
**Rootless Docker not installed yet**:
`dockerd-rootless-setuptool.sh`, `dockerd-rootless.sh`,
`rootlesskit`, `slirp4netns`,
`newuidmap`, `newgidmap` absent.
`/run/user/1001/docker.sock` NOT CREATED. Rootful
Docker CLI exists but unprivileged owner is denied access
to rootful Docker socket; separate `sudo -n docker ps`
did show the 2 actual running original Besu and Beacon
PoS containers. Leave the ORIGINAL rootful Docker daemon
and PoS containers alone.

Already-created encrypted VM4709 provider EOA:
`0xBbd4F07be80E1f4c40A1b470A180C0F38352bEaf`,
key private on VM4709. It remains UNFUNDED; no provider
bid, Docker physical worker, HTTPS endpoint or SLA yet.

## R275 — actual V2 provider agent rootless-only source functionality

The existing audited `tools/sse_compute_docker.py` now accepts
an **optional, explicitly selected** `docker_socket` for
`inspect_container(..., strict_hardening=True,
docker_socket=...)`; this is a backwards-compatible
source interface. When explicitly enabled it:

- requires nonroot caller, exact `/run/user/<os.geteuid()>/docker.sock`,
  private owner-controlled mode0700 non-symlink runtime
  directory, existing real Unix socket owned by same
  user, owner read+write access;
- rejects `/var/run/docker.sock`, `tcp://` URL,
  remote, symlink, wrong user, missing rootless daemon;
- calls ONLY `docker --host unix:///run/user/<uid>/docker.sock
  container inspect <safe-container-name>`, no shell,
  no Docker start/stop, remote host or socket exposure;
- strips inherited `DOCKER_HOST` and
  `DOCKER_CONTEXT` environment variables for
  this rootless CLI invocation;
- still validates every immutable worker property
  already required by R234: exact image digest,
  NanoCpus and memory/swap caps, read-only root,
  nonroot UID10001, only loopback worker port8877,
  `bridge` network, no capabilities/devices/host
  namespace/mounts, PIDs cap, no-new-privileges,
  seccomp and auto-remove.

The real V2 finalized-lease provider wrapper
`services/provider-agent/v2_compute_response_server.py`
now has opt-in `--rootless-docker`; only during
actual `--serve` is the exact owner private socket
selected for the worker's **per-request** strict Docker
inspection. The existing no-effect dryrun and legacy
default behavior remain unchanged. It still REQUIRES a
real funded and finalized lease, elected/confirmed
monitor committee, provider EIP712 signed reply,
actual CPU Docker worker and authenticated HTTPS
for outside monitoring. No code assumes a completed
lease, signs or sends any transaction, or runs a
container merely because this option exists.

New `tests/test_sse_pos_r275_rootless_worker_inspection.py`
has **9 authored mocked regression tests**, including
malicious Docker environment host/context overrides,
rootful/remote socket rejection, source fallback
prevention, and R234 strict per-request opt-in.
**These 9 tests have NOT YET been run on VM4709**.

### VM4709 source test — no effects

Use exact HEAD SHA published in chat and owner existing
private checkout at `$HOME/sse-v2-provider-source`:

```bash
PY="$HOME/.local/share/sse-v2-app-only/pyvenv/bin/python"
"$PY" -B -m unittest discover -s tests \
  -p 'test_sse_pos_r275_rootless_worker_inspection.py' -q
"$PY" -B -m unittest discover -s tests \
  -p 'test_sse_compute_docker.py' -q
"$PY" -B -m unittest discover -s tests \
  -p 'test_sse_pos_r234_v2_compute_response_server.py' -q
```

The older test suites include a user-namespace in-process
HTTP server using OS loopback; these ARE source/unit tests
and do NOT start Docker, broadcast transactions or
establish a paid SLA.

### VM4709 distribution/package selection — READ-ONLY

```bash
(
 set -euo pipefail
 echo "== OS / DOCKER PACKAGE SOURCES =="
 cat /etc/os-release
 dpkg-query -W 'docker.io' 'docker-ce' 'docker-ce-cli' \
   'containerd.io' 'uidmap' 'rootlesskit' \
   'slirp4netns' 'fuse-overlayfs' 2>&1 || true
 echo "== ACTUAL APT CANDIDATES — NO INSTALL =="
 apt-cache policy docker-ce-rootless-extras rootlesskit \
   uidmap slirp4netns fuse-overlayfs
 echo "== APT SIMULATION, NO DOWNLOAD/INSTALL =="
 apt-get -s install uidmap rootlesskit slirp4netns fuse-overlayfs \
   2>&1 || true
)
```

Do **not** run real `apt install` until reviewing
the candidate package and solver output: package
transactions can replace/restart Docker or containerd,
which is unacceptable while the real PoS chain operates.
In particular, **NEVER** follow generic docs steps
to `systemctl disable --now docker.service docker.socket`,
remove `/var/run/docker.sock` or restart the existing
Besu/Lighthouse native nodes. Official Docker docs
document a rootless `--force` installation path
while retaining an existing rootful daemon, but the
right package, script and service isolation must be
checked on THIS existing VM before actual authorization.

Upstream reference:
https://docs.docker.com/engine/security/rootless/

The intended next state is one separate nonroot
worker daemon with its own private socket, fixed
privilege limits and actual physical CPU measurement,
not a fresh blockchain or an infrastructure rewrite.
Source authored is not a deployed or tested workload.
