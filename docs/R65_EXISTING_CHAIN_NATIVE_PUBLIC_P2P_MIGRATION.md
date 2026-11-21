# R65 — controlled original chain31340 owner native open-overlay EL + Beacon P2P migration

**2026-11-21 status: GitHub SOURCE ONLY, no migration applied.** This is the FIRST reviewed migration implementation for enabling real native P2P on the **existing original live chain31340**, not an architecture mock or a second genesis. Previous G2 has one actual Lighthouse validator and remains on an IPv4-only Docker internal bridge with Besu `--p2p-enabled=false`. The original owner now has the same controllerless public ZeroTier transport as VM4707 and the outside laptop.

## Observed actual R65 first run and source correction — 2026-11-21

**Actual VM4706 evidence:** Corrected R59 17/17, R61 6/6 and R65 17/17 source tests all PASS (**40/40**). At immutable Git SHA `31bb642e9e15313a302e0aeab1087aca4095648b`, owner `--plan` passed original chain + shared PUBLIC overlay and absent migration resources, but REFUSED at original client Docker metadata with `custom entrypoint/environment requires separate source review`. There was **NO --apply** or interruption of EL/BN/VC; original chain still runs untouched.

**GitHub-only fix:** Normalize **only** Docker's `Entrypoint=None` versus `[]` (both absent) and Env list order when exact key/value mappings match. Strictly REFUSE custom entrypoint, duplicated/added/missing/changed Env values; do not print Env content or secrets. Controlled refusal now categorizes counts to diagnose the source of a real mismatch. Added six focused safety tests: **R65 now 23 tests**, source only until operator reruns. The corrected source does NOT permit arbitrary custom env/entrypoint; changed effective runtime behavior needs explicit review and safe preservation. No maintenance authorized.

**Important:** The R65 `--apply` mode, which can interrupt the only live validator, remains **NOT AUTHORIZED** until the corrected read-only plan passes, client effective Docker host ports and IPv6 bridge behavior are verified, actual original signer/chain databases have recoverable consistent backups, and rollback is independently reviewed. Its existence in GitHub is not a tested execution or successful public Ethereum bootstrap.

## R65 owner Docker entrypoint correction — actual evidence, 2026-11-21

**Observed on original VM4706 (read-only Docker inspect):** current original Besu `sse31340-g2-el-r40` container entrypoint `besu-entry.sh` is exactly the pinned Besu image entrypoint `besu-entry.sh`; both environments have **zero added/missing/changed variables**. Current original Lighthouse Beacon `sse31340-g2-bn` container has explicit entrypoint `lighthouse`, whereas its pinned Lighthouse image entrypoint is absent and its default image command begins `/bin/bash`; the environments likewise have **zero differences**. This explains the earlier R65 refusal `container_argv_count=1 image_argv_count=0` without implying any malicious override.

**GitHub-only fix, not VM-executed:** R65 now special-cases **ONLY the observed original BN's `["lighthouse"]` explicit entrypoint on a pinned image whose `Entrypoint` is empty**. It records the allowlisted override and adds `--entrypoint lighthouse` *before the immutable Lighthouse image reference* to the new Beacon-only `docker create` args, preserving original `bn` startup and existing exact JWT/Engine configuration. Besu still inherits the image's exact original `besu-entry.sh`. Any executable difference other than this verified BN case, or any environment-key/value difference, remains a hard refusal. Four unit tests cover the observed override, rejecting others, correct Docker option ordering, and failure without verified override; R65 regression suite is now **27** source/mock methods, NOT YET run on the VM at this revision.

Original chain/validator unaffected. Real Docker runtime readiness still subject to all remaining plan gates (original immutable images/hardening, preserved private mounts, original genesis, authenticated same-overlay networking, actual original API/finality and rollback). **DO NOT run `--apply` until the corrected plan returns successfully and backups/maintenance risks are reviewed**. This fix is not proof of external native peers.

## R65 owner WORKDIR refusal and next read-only correction — 2026-11-21

**Actually observed:** VM4706 fetched and detached `aa34d5a3a8164753775d8bc098ef676b389b2215`, ran **27/27 R65 tests PASS**, then `--plan` verified real chain and owner public overlay and stopped with **`custom working directory requires separate review`** during original Docker metadata inspection. No `--apply` or original-client restart occurred. The exact Docker `WorkingDir` values were not printed; no assumptions about their contents are warranted.

**GitHub-only fix (NOT YET VM EXECUTED):** Normalize effective absent/empty Docker working directory to `/`, accept only a bounded normalized absolute in-container path (never traversal, untrusted relative paths or control characters), and **explicitly pass `--workdir` with the original live container's effective directory** to any proposed new Besu or Beacon container. This preserves runtime semantics instead of silently adopting a pinned image default, including for genuine nondefault original paths. The original running process and private host mount paths are untouched.

R65 `--plan` now constructs each complete proposed EL/BN `docker create` argument vector *in memory*, checks original Lighthouse explicit `--entrypoint lighthouse`, workdir match and size, but never runs `docker create`. This catches more launch inconsistencies before the only signing validator is interrupted. Strict original Env key/value equality, pinned image digest, mounts, Engine JWT and network hardening checks still apply. The R65 test suite now defines **33 tests** (previously 27), and corrected R59 source defines **19 tests** (previously 17), neither new suite run on VM yet.

**Peer-discovery safety improvement:** Lighthouse owner and observer CLI now pass `--disable-enr-auto-update` so an ENR configured for the public 6plane address is not overwritten by underlay peer observations; a stale `args.execution_seed_enr` R59 observer `--apply` reference was fixed to the actual `args.execution_seed_enode_v6` parameter. The latter would otherwise have raised `AttributeError` when eventually creating a second nonsigning observer. None of these source changes demonstrate native P2P peer handshakes or finalized-root equality across outside-provider nodes.

**Do not run R65 `--apply`** until corrected live `--plan` passes AND original EL/BN/VC recoverable backups and rollback can be independently verified. The owner VM must not use provider-private LAN for native P2P/bootstrap.

## Real R65 source gate now passed, and R66 local consistent recovery added — 2026-11-21

The operator's latest real VM4706 output at exact source SHA `ae5e780055f044d635d20cc33a5d426ca6e42e63` shows **33/33 R65 and 19/19 R59 tests PASS (52/52 total)**, followed by **SUCCESSFUL live R65 `--plan`**. The original EL advanced to execution block `0xd44` = 3396, Beacon to finalized epoch108. The plan verified current PUBLIC same-overlay `fca0:2328:776e:4750:395b::1`, no preexisting R65 migration resources, actual original Docker metadata, immutable image launch, preserved data/JWT and original workdirs. Proposed Besu IPv6 P2P `30404/tcp+udp`, Lighthouse `9000/tcp+udp` and `9001/udp`, all host-bound ONLY to actual owner 6plane; original localhost-only RPC/REST and no host-published Engine8551. No R65 `--apply` yet. This is original live chain health/read-only plan, not proof of external native peers.

**New mandatory in-apply consistent local snapshot (SOURCE ONLY, NOT VM-RUN):** the source-only R65 `--apply` path now calls `tools/sse_pos_r66_consistent_owner_recovery_snapshot.py` after **gracefully stopping original single VC, Beacon and EL** but BEFORE any original client rename/new container database opens. R66 verifies all exact three original Docker processes are stopped, requires source owner private `0700` directory, rejects symlinks, special files and path escapes, checks available disk space (≥2× original file sizes plus 64 MiB), and writes ONE uncompressed TAR under a new local owner-only `0700` recovery directory in the SAME VM with a `0600` archive. R66 checks every tar member against the still-stopped original file bytes using SHA256 and verifies full expected file count and byte total. Only on successful verification can R65 proceed to create new EL/BN processes with existing original databases. If backup fails, R65 attempts rollback and **does NOT rename/replace the originals**. R66 has **10 focused tests** using only tiny throwaway fixture data; R65 now **36 source/mock tests**, including staged failure rollback. All are NOT YET RUN ON VM in this revision.

**Restart policy gate:** Before any mutation, R65 now also rejects original EL/BN/VC restart policies that can revive preserved stopped processes on Docker daemon restart. Only original Docker `no` and `unless-stopped` policies qualify; `always` and unreviewed policies fail closed. This is necessary to avoid two processes accessing the same original EL/Beacon/validator databases after an unexpected daemon restart. The new revision defines **37 R65 tests plus 10 R66 snapshot tests** (47 focused tests), not yet VM-executed.

**Sensitive data warning:** R66 recovery TAR includes original EL+BN data, confidential Engine JWT, and the original VC signing/slashing material. It is **NOT ENCRYPTED**; directory 0700 / tar 0600 restrict local access but do NOT provide encryption-at-rest. It must NEVER be pasted, uploaded, stored in public GitHub or shared with other nodes, and operator should encrypt/offline-backup the archive separately. R65 still requires `--backup-attested` as an independent owner assertion that recoverable offline backup/recovery is already prepared; a local TAR is an additional safeguard, not sufficient substitute for an offline recoverable backup. The new local TAR is NOT deployed as a second validator and does not launch a second signing key. There is no verified external backup or restore test to claim until owner reports one.

**New status:** NOT SAFE TO DECLARE successful native P2P; original signer never stopped in actual latest user output. We will not bypass owner maintenance approval, safe recovery backup or actual Docker IPv6 post-publication and chain health gates. Any future `--apply` is disruptive to original single-validator finality during local snapshot; no native provider-private-LAN bootstrap or side-channel transfers allowed. The operator must understand the backup's local sensitive-unencrypted status.

## What the original VM actually proved

At immutable Git SHA `ada6cf9bc84a1fd6944e6c7a40b1feff2901ef7c`, VM4706 operator ran R64 **10/10 source tests PASS** and real original R64 network/state audit. Output verified owner actual ZeroTier `ff2328775f000000` `OK PUBLIC`, assigned `fca0:2328:776e:4750:395b::1`; original single EL/BN/VC running; same isolated internal Docker trust network `sse31340-g2-internal`; exact pinned image IDs and immutable original genesis/JWT metadata; EL P2P explicitly false, actual native peers `0x0`. EL/BN each bind-mount **exactly three owner-private paths** at `/data` (writable), `/testnet` and `/jwt/engine.jwt` (readonly), no extra original attached Docker networks; VC has four existing private mounts and **must never be recreated**. Real in-namespace EL execution chainId31340 block `0xc62` = **3170**; Lighthouse head **slot 3388**, finalized **epoch 101**, finalized root `0xf30b621acbfda2ee5ebaef9e0dd26c516481f27c545a49fb78f81f94484ddf85`. These advance from R62 EL3029, BN head3247, epoch97. They do not prove ongoing multi-peer finality or native P2P beyond the single owner host.

## Implemented migration source (NOT YET OPERATOR-RUN)

`tools/sse_pos_r65_original_chain_native_public_p2p_migration.py`, `tests/test_sse_pos_r65_original_chain_native_public_p2p_migration.py` (**35 mocked/source tests**, not executed on VM), and this document. Source is GitHub-only in feature branch. The implementation has two mutually exclusive modes:

**`--plan --expected-commit SHA`** reads the exact original G2 + owner overlay state through R60/R62/R63/R64, checks that exactly one original execution+Beacon pair is running, normal image digest and private mount layout, preserved Engine JWT metadata, hardening and trusted Docker network, current canonical execution/Beacon health. It checks no old `-r65-preserved` containers or R65 P2P bridge exist. It builds a minimal proposed public IPv6 P2P publication list:
- Besu existing client: primary *internal IPv4* `30303` (NOT host-published, NOT private provider-LAN advertised), **secondary IPv6 30404 TCP+UDP** published ONLY to owner `[fca0:2328:776e:4750:395b::1]` (computed dynamically from current ZeroTier host membership). Besu v26.11 IPv6 options `--p2p-enabled=true`, `--p2p-host=127.0.0.1`, `--p2p-host-ipv6=<actual6plane>`, `--p2p-interface-ipv6=::`, `--p2p-port-ipv6=30404`, `--p2p-discovery-port-ipv6=30404`, IPv6 outbound preference and discovery BOTH. Host EL JSON-RPC only `127.0.0.1:18545:8545/tcp`; **NO Engine8551 host publication**.
- Original Lighthouse BN: existing state/genesis/execution JWT, IPv6 `--listen-address=::`, `--enr-address=<actual6plane>`, TCP+UDP9000, QUIC UDP9001 published ONLY to same actual owner IPv6; Beacon REST only `127.0.0.1:15052:5052/tcp`. Original BN→EL Engine endpoint remains on the trusted local bridge via alias `sse31340-g2-el` (exact original R40 alias). The same original VC→BN local DNS name is retained.
- **Original VC:** is stopped only during owner-approved maintenance then the exact same container restarted unchanged, with all existing signing/slashing files and original key custody. Never cloned, imported, regenerated or placed on the new public Docker bridge. Only EL+BN receive a second dedicated `--ipv6` non-internal Docker bridge `sse31340-g2-r65-public-p2p`, while their PRIMARY original trusted Docker bridge remains. Docker host publications and local original chain API are checked before restarting the signer.
- All original EL+BN Docker containers are renamed to `-r65-preserved` and retained STOPPED, not deleted. New EL/BN processes use **the same exact original Docker bind-mounted databases/testnet/JWT** and image ID/version, with restrictive uid, readonly root filesystem, no-new-privileges, capability drop, original tmpfs/memory/pid limits and Docker restart policy. They share the same one original chain, not a copy, fork or new genesis.
- Health gates use genuine local original-chain JSON-RPC chain ID/head and Beacon genesis/head from existing running process namespaces. Before claiming host-exposed P2P, inspect **effective** Docker port bindings and the exact host IPv6; if wrong, fail. Peer handshakes, signed seed EnodeV6+Beacon ENR, outside-provider WSL native two-layer synchronization, matching finalized roots and reboot recovery remain **NOT VERIFIED until independent real measurements**.
- If later `--apply` fails *after* stopping clients, safeguarded rollback must remove only newly created process containers, restore original stopped EL+BN container names and start original EL, BN, then exact original VC if health checks pass. On incomplete rollback, **do not restart signer automatically**, and retain original private data for manual diagnosis. The dedicated newly created P2P bridge may persist after partial failure; never blindly rerun.
- **Maintenance risk**: one active original validator means temporary outage may prevent chain finalization until it recovers. Backup of original signer key/slashing data and execution/Beacon databases must be independently recoverable; source requires explicit `--backup-attested` plus a separate typed owner-approval token before `--apply`. This is not evidence of tested restoration. On network mutation, firewall and host published P2P behavior require actual independent verification. No immediate `--apply` is authorized by this document.

### VM4706 — source tests and read-only plan FIRST (no restart)

```bash
(
 set -e
 cd "$HOME/sse-research"
 export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/sse_vm4706_readonly -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o BatchMode=yes"
 git fetch --no-tags origin feature/r19-fresh-external-node-preflight
 SHA="a65253b4300282e81356a17ac4a41605ee111785"
 git switch --detach "$SHA"
 test "$(git rev-parse HEAD)" = "$SHA"
 python3 -B -m unittest discover -s tests -p 'test_sse_pos_r65_original_chain_native_public_p2p_migration.py' -v
 python3 -B -m unittest discover -s tests -p 'test_sse_pos_r66_consistent_owner_recovery_snapshot.py' -v
 echo "R65_R66_SOURCE_GATE_PASSED=true"
 sudo -v
 python3 -B tools/sse_pos_r65_original_chain_native_public_p2p_migration.py --plan --expected-commit "$SHA"
)
```

`--plan` does NOT create the new Docker network, stop or rename containers, modify existing data, change client flags, or enable P2P. Original owner/source checks may REFUSE an unexpected existing security config, additional mount, image/env mismatch, or ZeroTier state rather than guessing. Diagnose first, do not weaken the guard without actual VM evidence.

### Separately approved controlled maintenance (NOT YET TO RUN)

Only after the actual R65 source tests and **real read-only plan** have been reviewed, backup/recovery attested, Docker version+bridge IPv6 host publication verified, and the operator explicitly approves a temporary original validator outage:

```bash
# NOT AUTHORIZED HERE; future separately reviewed owner maintenance only.
# python3 -B tools/sse_pos_r65_original_chain_native_public_p2p_migration.py \
#   --apply --backup-attested --expected-commit "<exact-reviewed-SHA>"
```

This actual migration stage needs *no provider-private LAN*, VM-to-VM SCP, new genesis, duplicate signer, VM4707 original-key copy or static public IPv4. VM4707 R59 observer itself is still not deployed; its earlier proposed port30303/enr design was corrected to IPv6 Besu30404 and Besu enodeV6 vs Lighthouse ENR in GitHub, but remote instance must be sourced from a public immutable release rather than copying old scripts over SSH.

**Sources:** Docker publish/bridge docs https://docs.docker.com/engine/network/port-publishing/ ; IPv6 Docker bridge https://docs.docker.com/engine/network/drivers/bridge/ ; Besu https://docs.besu-eth.org/public-networks/reference/options ; EL enodeV6 https://docs.besu-eth.org/public-networks/concepts/node-keys ; Lighthouse https://lighthouse-book.sigmaprime.io/advanced_networking.html ; no private provider-LAN / third-party relay acceptance `docs/ARCHITECTURE.md`.
