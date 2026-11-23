# R183 — native VM4707↔VM4709 ZeroTier TCP verified, startup recovery prerequisites

2026-11-23 real owner VM4709 command result:

- ZeroTier 1.16.2 `ONLINE` and network `ff2328775f000000`
  `OK PUBLIC`, dynamically assigned VM4709 `fca0:2328:77e5:740c:ce60::1/40`.
- TCP connect from actual VM4709 to actual VM4707 previously observed
  `fca0:2328:77b8:6578:a55::1:30404`:
  `BESU_EL_TCP TCP_REACHABLE`.
- TCP connect to same VM4707 `:9000`:
  `LIGHTHOUSE_CL_TCP TCP_REACHABLE`.
- No Docker, chain, package or files mutated by this check.
- Both VM4709 containers still `Restarting (1)`; no native ETH
  handshakes, genesis/network-wide sync or finality confirmed.

This proves direct cross-VM TCP reachability over genuine ZeroTier
transport and removes basic TCP overlay routing/firewall from the
immediate blockers. It does NOT prove UDP discv5 reachability,
native EL/CL P2P handshake, public Internet access without ZeroTier,
independent infrastructure, PoS validation/finality on VM4709 or
final permissionless-discovery readiness.

## Already observed and preserved state

- VM4707 original chain31340 Lighthouse recent finalized epoch560 root
  `0x166faa9e332bbe4ff749d486e88de74bec3339efcc38dfb3659cb149f89954dd`
  and both finalized SSZ state and block endpoints return 200 on
  owner **localhost**. Do not expose owner Beacon/Engine APIs to
  arbitrary network clients.
- VM4709 Docker original selected observer + pinned non-signing EL/CL,
  root-owned original archive, Engine JWT and a populated
  Lighthouse DB holding `chain_db`, `freezer_db`, `blobs_db`
  and network identity file; do not delete or reuse it for
  checkpoint import.
- Besu default entrypoint `besu-entry.sh` causes chown/chmod/su
  failures under hardened Docker flags. Separately validated
  pinned `/opt/besu/bin/besu --version` with read-only rootfs
  and writable tmpfs reported `besu/v26.11.1`. Disposable
  --network none hostname warning did not block it.
- Lighthouse refuses stale genesis under correct weak subjectivity
  protection. `--allow-insecure-genesis-sync` did not bypass
  it, and `--ignore-ws-check` is NOT approved.
- No existing container migration has yet been attempted.

## Next safe gates before changing anything

1. On VM4707 read-only inspect:
   - Existing native P2P container status and owner localhost
     checkpoint state/block endpoints; owner checkpoint identity.
   - Whether an authenticated transfer (SSH/SFTP over the already
     working ZeroTier dynamic IPv6 network) is possible, without
     assuming credentials or publishing privileged REST.
   - Full byte sizes of finalized SSZ state and block, with bounded
     streaming and no secret-key access. Snapshot must be
     consistently paired at ONE immutable finalized block ROOT:
     use /eth/v2/debug/beacon/states/{finalized-root} and
     /eth/v2/beacon/blocks/{finalized-root}, not two moving
     'finalized' aliases across a checkpoint rollover.
2. On VM4709 inspect the exact existing two Docker objects,
   root-owned data dir and ports, then prepare separate **empty**
   Beacon data root with explicit owner authorization for the
   next recovery phase; retain network identity and previous
   populated Beacon DB untouched.
3. Checkpoint transfer must be authenticated, integrity-checked
   and scoped to publicly shareable Beacon SSZ only; do not
   transfer Engine JWT, validator keys, private node identity or
   the owner's full chain database.
4. Recover existing Besu through a reversible exact-container
   migration, using verified native executable and unchanged
   security settings. Recover Lighthouse from trusted checkpoint
   and empty new DB, preserve old DB and peer ID. Stop old
   restart loops ONLY as part of operator-authorized controlled
   migration, never `docker rm -f` or global cleanup.
5. Verify actual native EL peers `net_peerCount`, Lighthouse
   peer count, syncing=false and finalized epoch+root on VM4709
   and VM4707 through independent read-only R141/R153 capture.

## Reusable future-node requirements

Original R147/R151/R137 deployment is a non-idempotent create-once
experiment. The final onboarding system needs a declarative,
stateful, resumable release with signed dependencies, direct hardened
Besu binary entrypoint, bounded owner-verified checkpoint import,
dynamic peer discovery without GitHub REST or static IP, real
startup readiness, safe rollback and independent-provider test.
Every failure and repair from VM4709 is preserved in R173-R183
docs on GitHub. Do not claim these are completed already.
