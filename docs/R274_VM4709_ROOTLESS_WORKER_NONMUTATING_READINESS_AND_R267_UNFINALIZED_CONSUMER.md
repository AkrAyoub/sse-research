# R274 — consumer funding already succeeded/canonical, now blocked only by native EL finality; VM4709 dedicated rootless worker prerequisites

## Actual continuing owner state on original chain31340

User invoked existing R267 Monitor1 --send on VM4707 **after** the
previous R271 actual one-shot measured the canonical successful consumer
nonce1 transfer in block **25564**, finalized EL block **25556**
(**8 blocks short**). Actual new output again:

```
R267_EARLIER_ROLE_FUNDING_PENDING_FINALITY_DO_NOT_RESEND:
previous role funding not yet finalized; DO NOT RESEND
```

This confirms R267 again stopped **before** monitor1 keystore unlock,
interactive transfer authorization or raw send; prior included
canonical consumer tx and successful receipt still passed validation
before the finality check. It does **NOT** establish current specific
EL finalized height or exact remaining block gap — those were 8 at
the earlier R271 measurement, not at this later CLI run.
There was **no new Monitor1 nonce2, no Monitor2 nonce3 transfer**.
Do not rerun consumer nonce1 or delete its private one-use marker.
Do not use R267 --send as a finality status-poll tool.

Current safe one-shot observation (on VM4707 existing checked-out
4eafada... R271 code, with no Git checkout required):
`/tmp/tmp.Ridv9nIavf/testvenv/bin/python -B tools/sse_pos_r271_consumer_native_tx_finality_snapshot.py --rpc http://127.0.0.1:28545`.
Only when this returns `SUCCESSFUL_CANONICAL_FINALIZED` can
R267 monitor1 nonce2 be attempted, after the owner terminal prompts.
There is no chain restart or finality bypass, and no automated
retry/backoff loop. One can advance independent work on VM4709.

## VM4709 real provider status

VM4709 R272 actual 7/7 focused PASS; CPU4, >=10GiB free RAM
and >=90GB disk; two real existing original-chain31340 Besu
and Lighthouse containers were independently verified running
via owner-authorized `sudo -n docker ... ps`.
New VM4709 provider application-only EOA
`0xBbd4F07be80E1f4c40A1b470A180C0F38352bEaf`
was created and encrypted under owner-local 0700/0600;
the project-pinned app Python dependencies are installed
in its separate venv. The provider remains **UNFUNDED**
and no Docker CPU worker or real SLA has been executed.

**Problem:** unprivileged VM4709 cannot access rootful Docker
Unix socket (uid root, 0660). The existing R234 provider
wrapper runs strict `docker container inspect` per HTTP
request, and would fail when run as owner nonroot.
Granting root-equivalent `docker` group membership, opening
rootful Docker socket, or restarting existing PoS clients is
not an acceptable automatic workaround.

## New R274 — rootless provider worker readiness ONLY

The new `tools/sse_pos_r274_vm4709_rootless_compute_readiness.py`
does ONLY NONMUTATING owner-local checks on actual VM4709:

- Exact nonroot owner `ayoubakrvm4709`.
- Presence of `dockerd-rootless-setuptool.sh`,
  `dockerd-rootless.sh`, `rootlesskit`, `slirp4netns`,
  `newuidmap`, `newgidmap`, `docker` binaries.
- Public local `/etc/subuid` and `/etc/subgid` entries for
  owner with at least 65,536 IDs each.
- Expected `XDG_RUNTIME_DIR=/run/user/<uid>`;
  actual /run/user/<uid> 0700 private owner dir.
- Existence/ownership/symlink status of LOCAL
  `/run/user/<uid>/docker.sock` without connecting.
- Structural prereq readiness only. Even an owner-owned
  socket is NOT proof Docker daemon is responsive or the
  worker runs; a later separately authorized, fixed
  local `docker --host unix:///run/user/<uid>/docker.sock
  info/inspect` is needed.

**R274 NEVER installs or starts rootless Docker, calls sudo,
changes the original rootful Docker daemon, starts/stops
the PoS containers, reads any wallet, creates an EOA,
submits a transaction or asserts real SLA.** Missing
rootless prerequisites must be reviewed by actual host
owner before any setup. This rootless approach is
a separate worker daemon, not a blockchain architecture
change. Existing R234 worker inspection will need
an **explicit known local Docker socket** for full
independent execution; no source change to R234
was made in R274.

New source-only mock tests at
`tests/test_sse_pos_r274_vm4709_rootless_compute_readiness.py`.
**Not yet executed on VM4709.**

Safe VM4709 owner invocation after fetching exact pinned
commit from chat:

```bash
python3 -B -m unittest discover -s tests \
  -p 'test_sse_pos_r274_vm4709_rootless_compute_readiness.py' -q
python3 -B tools/sse_pos_r274_vm4709_rootless_compute_readiness.py \
  --inventory-only
```

Do not run any `dockerd-rootless-setuptool.sh install`,
sudo installers, group mutation or compute worker run until
the results and operational isolation are reviewed; VM4709
continues serving real native PoS nodes safely.
