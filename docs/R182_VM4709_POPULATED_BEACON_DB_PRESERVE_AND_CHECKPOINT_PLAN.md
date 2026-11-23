# R182 — VM4709 populated Lighthouse DB, preserve state and use owner-verified SSZ checkpoint

Date: 2026-11-23. Actual VM4709 diagnostic result, 3 R181 tests PASS.

## Evidence, not a simulation

The operator's read-only R181 metadata inventory of the original
`/root/.local/share/sse-r137-node-8be265272c35f3d8c3a0/beacon`
reported 30 entries, 24 regular files (159080 aggregate file bytes)
and six directories, including actual RocksDB files in
`beacon/chain_db`, `beacon/freezer_db`, `beacon/blobs_db`.
It also showed `beacon/network/key` (64 bytes), the new node's
local P2P identity, and log files. Original Docker containers both
still `Restarting (1)`. DO NOT read or export the P2P private key
or Engine JWT, remove the DB, or attempt an in-place
`--checkpoint-sync-url` or `--purge-db` without an approved
recovery plan.

Lighthouse Book (official):
https://lighthouse-book.sigmaprime.io/advanced_checkpoint_sync.html
states checkpoint syncing requires an empty existing Beacon DB.
Official CLI:
https://lighthouse-book.sigmaprime.io/help_bn.html
documents local `--checkpoint-state` / `--checkpoint-block`
SSZ files as an alternative to a remotely exposed Beacon API.
A future per-node install should retrieve a finalized state+block
from the already-verifiable chain31340 native owner and verify
genesis, slot, finalized block root before startup. This need not
expose a public authenticated Beacon API or use a paid GitHub REST
service; the operator can transfer validated SSZ blobs via a
separately authenticated transport.

VM4707 owner demonstrated exact original genesis root
`0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd`;
finalized checkpoint epoch 560 / slot 17920,
block root `0x166faa9e332bbe4ff749d486e88de74bec3339efcc38dfb3659cb149f89954dd`,
and both finalized SSZ state and block endpoints returned
HTTP 200 application/octet-stream on localhost only.

## Recovery constraints

- Preserve the old original Beacon data, network identity, native
  genesis, Engine JWT and existing pinned Docker image/ports.
- Do not restart the existing R147/R151/R137 create-once deployment.
- Prepare a separate empty Beacon data location and verify it
  remains empty before local-SSZ checkpoint import; do not
  overwrite existing data or keys.
- Need an authenticated, constrained SSZ transport from actual
  owner VM4707 to VM4709; hash full files and compare checkpoint
  Beacon block root/slot on VM4707 before import. A matching
  SSZ file hash alone does not prove consensus validity; verify
  using pinned client and exact original genesis network.
- Any actual Docker container replacement requires explicit
  operator action, exact image/ports/security preflight,
  preserved original configuration and rollback plan. Avoid
  image entrypoint wrapper by using tested native Besu
  `/opt/besu/bin/besu`; do NOT disable caps/read-only mounts.
- Prove VM4709 native EL+CL peers, sync and finalized checkpoint
  with R141/R153, then compare fresh R141 reports against owner
  VM4707. Until then implementation is NOT proven to have
  independent synchronized nodes.

## Next non-mutating checks

- Check actual dynamic ZeroTier IPv6 connectivity on VM4709 to
  VM4707's currently advertised public native EL (30404/tcp)
  and CL (9000/tcp) ports. TCP reachability does not prove native
  ETH handshake or UDP discovery connectivity.
- Check VM4707 available disk and state SSZ size for a safe
  transfer, but never expose its Engine API or original signing
  keys. Prefer operator-authenticated direct SSH or similarly
  encrypted transfer to new node, not a GitHub comment.
- Inspect existing VM4709 Docker port and pinned volume settings
  read-only and calculate an exact reversible migration; no
  automated purge, renaming, deleting or force-stopping clients.

This document records actual observed evidence and next required
verification, not a claim that the client recovery is finished.
