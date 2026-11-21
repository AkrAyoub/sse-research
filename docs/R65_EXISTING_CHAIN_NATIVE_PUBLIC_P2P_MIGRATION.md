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

## What the original VM actually proved

At immutable Git SHA `ada6cf9bc84a1fd6944e6c7a40b1feff2901ef7c`, VM4706 operator ran R64 **10/10 source tests PASS** and real original R64 network/state audit. Output verified owner actual ZeroTier `ff2328775f000000` `OK PUBLIC`, assigned `fca0:2328:776e:4750:395b::1`; original single EL/BN/VC running; same isolated internal Docker trust network `sse31340-g2-internal`; exact pinned image IDs and immutable original genesis/JWT metadata; EL P2P explicitly false, actual native peers `0x0`. EL/BN each bind-mount **exactly three owner-private paths** at `/data` (writable), `/testnet` and `/jwt/engine.jwt` (readonly), no extra original attached Docker networks; VC has four existing private mounts and **must never be recreated**. Real in-namespace EL execution chainId31340 block `0xc62` = **3170**; Lighthouse head **slot 3388**, finalized **epoch 101**, finalized root `0xf30b621acbfda2ee5ebaef9e0dd26c516481f27c545a49fb78f81f94484ddf85`. These advance from R62 EL3029, BN head3247, epoch97. They do not prove ongoing multi-peer finality or native P2P beyond the single owner host.

## Implemented migration source (NOT YET OPERATOR-RUN)

`tools/sse_pos_r65_original_chain_native_public_p2p_migration.py`, `tests/test_sse_pos_r65_original_chain_native_public_p2p_migration.py` (**27 mocked/source tests**, not executed on VM), and this document. Source is GitHub-only in feature branch. The implementation has two mutually exclusive modes:

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
 SHA="aa34d5a3a8164753775d8bc098ef676b389b2215"
 git switch --detach "$SHA"
 test "$(git rev-parse HEAD)" = "$SHA"
 python3 -B -m unittest discover -s tests -p 'test_sse_pos_r59_native_ipv6_observer.py' -v
 python3 -B -m unittest discover -s tests -p 'test_sse_pos_r61_common_public_p2p_policy.py' -v
 python3 -B -m unittest discover -s tests -p 'test_sse_pos_r65_original_chain_native_public_p2p_migration.py' -v
 echo "R65_SOURCE_SUITE_PASSED=true"
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
