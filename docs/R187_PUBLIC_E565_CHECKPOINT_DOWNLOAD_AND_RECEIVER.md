# R187 — real e565 public checkpoint receiver without API authentication

VM4707's real R186 exported and published public Release
`chain31340-checkpoint-e565-86fdc98df47d641a`:
`https://github.com/AkrAyoub/sse-research/releases/tag/chain31340-checkpoint-e565-86fdc98df47d641a`.

The user-observed owner output:
- original Beacon genesis validators root
  `0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd`
- actual finalized epoch 565, slot 18080, block root
  `0x86fdc98df47d641a27fbc95eb3229dfc0e24553d1dc57bfbe2599e161b60a259`
- checkpoint-state.ssz 2,859,760 bytes, sha256
  `8c03cdec390bb9442d7ac8d98a01a1d6dc03861602bf085d95553554ea5a1d41`
- checkpoint-block.ssz 1,417 bytes, sha256
  `9e2859ca4e57bf1228d010bd7958483ee111b4ec10d39c5d5aa82f691c702373`.
- actual GitHub release API confirmed EXACTLY these three public
  asset names and sizes, release published (not draft).

`tools/sse_pos_r187_verified_public_checkpoint_receiver.py` now downloads
from the exact release download paths using public HTTPS with
no account, paid API or SSH. It first checks exact manifest
schema/genesis/epoch/slot/block root and explicitly pinned SHA256
and sizes, downloads and verifies both SSZ assets fully in memory
before creating exclusive fresh 0700 output directory with 0600
files. It refuses any pre-existing target and malformed/tampered
assets. It does not touch existing Docker containers, original
genesis, populated Beacon database, Engine JWT, or network identity.
Tests mock malformed manifest and tampered asset; tests are NOT
proof that VM4709 actually downloaded it.

Next VM4709 run narrow R187 unit tests then `--out` to NEW user-owned
private temp directory; preserve location if verified. The downloaded
checkpoint is a *trusted owner supplied* checkpoint for experimental
network: SHA256 ensures transport integrity relative to operator
observations, but does not independently check consensus SSZ
hash-tree-root. Lighthouse must still accept it on exact original
chain31340 using a fresh Beacon database, and actual cross-node
native EL/CL peering/finality must subsequently pass.

As of this R187 commit, VM4709 original Besu and Lighthouse
containers STILL restart. No successful checkpoint import or
end-to-end SSE marketplace transaction was demonstrated. Next
migration must be an explicit reversible exact Docker migration
preserving original populated Beacon DB, network identity, JWT and
data; no `--ignore-ws-check`, DB deletion or blind rerun of
R147/R151/R137. Avoid claiming final project complete.
