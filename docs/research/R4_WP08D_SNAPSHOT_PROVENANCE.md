# R4 WP-08D — Monitor-signed, block-hash pinned evidence provenance

**Status:** implementation branch, draft stacked PR #19 (depends on WP-08C PR #18). CI revalidation must be recorded after final source commit. **No production or research-acceptance finality claim.**

## Purpose

WP-08C used an authenticated monitor identity drawn from a local chain-state read, but RPC reads were selected by a **block number**. At a given height an unfinalized chain can reorganize. Without preserving the observed block hash, the archive cannot even tell which block the authorization snapshot claimed.

This WP-08D increment **does not provide a light client or external finality proof**. It improves local provenance and makes signed raw observations detectably tied to a historical block under the configured node's canonical view.

## Scope of the implementation

1. `sse_chain_read.inspect_chain(..., pin_block_hash=True)` obtains the block header and its nonzero 32-byte hash, then executes all `eth_getCode` / `eth_call` contract-state queries using EIP-1898 `{"blockHash": ..., "requireCanonical": true}`. It checks that the numeric-height canonical hash remains the same after the reads. An incompatible RPC fails closed. Unpinned inspection remains available for existing B1 demos.
2. `sse_wp08c_chain_binding.bind_capture_to_chain(..., pin_block_hash=True)` only accepts a resulting report explicitly marked hash-pinned and carrying a canonical nonzero block hash. The prior checks for lease, provider, SLA/profile/request/endpoint, four confirmed monitors, and monitoring window remain.
3. In chain-bound `evidence_capture.py --rpc-url` mode, the monitor creates **two separate EIP-712 signatures**: the existing off-chain `SSEObservation` about the exact provider HTTP bytes and a new `SSEChainSnapshot` over `(leaseId,epochId,evidenceId,blockNumber,blockHash,blockTimestamp)`, domain `SSEChainObservationAnchor` / version 1 / `chainId` / verifying settlement address. `evidenceId` is the existing cryptographic observation-record commitment, so the anchor transitively covers the scoped raw bytes. The independently verified HTTP provider signature remains unchanged.
4. The SQLite `chain_anchors` table is created if missing. An anchor is authenticated *before* insertion and stored **atomically in the same transaction** as the raw provider bytes and monitor envelope. Nonce collision / duplicate evidence with conflicting anchor is rejected; existing WP-08B records are not retroactively pronounced chain-pinned.
5. Strict `EvidenceArchive.load_anchored(..., rpc)` rechecks the provider and monitor signatures and bytes, validates the separate monitor-signed anchor and expected authorization context, and fetches the old block by **number and by hash** from the current trusted RPC. It refuses missing, corrupted, reorged or mismatched blocks. Legacy `load()` remains a raw-evidence API and is explicitly **not** a chain-provenance check.
6. The existing CI Anvil runner tests full marketplace funding, selection, signed HTTP capture and artifact reload. It now creates a local `evm_snapshot`, mines a block, captures hash-pinned evidence, then `evm_revert`s to the earlier state. Even though the archived monitor signature is cryptographically intact, **anchored retrieval must fail** when its block has disappeared.

## Verification commands

From the source root with pinned dependencies, Forge and Anvil installed:

```bash
python -m unittest discover -s tests -p 'test_sse_wp08d_provenance.py' -v
python -m unittest discover -s tests -p 'test_chain_read.py' -v
python -m unittest discover -s tests -v
forge build
forge test -vv
python tools/sse_wp08c_live_marketplace.py
```

The final command is destructive **only to its own disposable Anvil instance** and preserves evidence in `.local/wp08c-live/`; it refuses to replace a nonempty output folder. The test uses the widely known Anvil test mnemonic, not real funds.

## What this achieves — and does not

**Achieved:** a signed reference to a concrete block hash; EIP-1898 state read pinning; an atomic signed observation-to-block linkage; strict replay/tamper checks; detection of missing/replaced blocks **as reported by the same trusted RPC**. Observations are still raw, and the code does not authorize monitor votes or escrow transfers.

**NOT achieved:**

- Independent header/consensus/light-client verification; an adversarial single RPC can fabricate its own consistent history.
- A finalized-epoch validity proof. A current canonical block is **not** necessarily finalized. Anvil `evm_revert` only models one local class of reorg.
- No cross-node archive replication, external immutable checkpoint, proof-of-availability or crash/restart checkpoint notarization. Disk operators can delete evidence.
- No guarantee that the intended consumer received a correct physical response on time, that monitors are independent, or that local wall clocks are truthful.
- No accepted `QualifiedFact`, on-chain monitor vote, settlement change, slash or payment rule.

## Next target

WP-08E must separately design and test **authenticated canonical chain-finality provenance** (e.g. independent consensus/EL header or defensible trusted checkpoint model) and remote/offsite evidence availability, including RPC equivocation tests. R1/P1 must still justify truthful physical SLA certificates before adapting on-chain monetary policy. R3 scalable/unbiased monitor selection remains open.
