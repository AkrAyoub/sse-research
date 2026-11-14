# R4 WP-08E — Signed external RPC checkpoint and portable evidence replicas

**Checkpoint:** 2026-11-14. Stacked draft PR #20, built on draft PR #19 and #18. Not merged. **All four CI jobs passed** (369 Python tests on Ubuntu, 369 on Windows, 52 Foundry tests, and the fresh Anvil live witness/replica/reorg scenario). Independent consensus finality remains open.

## Problem and scope

WP-08D anchors a monitor's observation to a block hash. WP-08E adds separately authorized checkpoint witness signatures and an independently re-verifiable portable archive. These witnesses still rely on their own RPC view; an RPC can lie, and different signing keys do NOT establish Ethereum proof-of-stake finality or independent organizations. The development experiment intentionally uses the same local Anvil RPC for both witness subprocesses.

## Technical implementation

1. **tools/sse_wp08e_witness.py** defines a new off-chain EIP-712 type SSECheckpointWitness, domain SSEExternalCheckpointWitness v1. It signs lease/epoch/evidenceId/blockNumber/blockHash/blockTimestamp and the fixed claimKind=1, meaning RPC_CANONICAL_OBSERVED_ONLY, never FINALIZED. evidenceId commits indirectly to the original monitor-signed observation and exact HTTP bytes.
2. **WitnessPolicy** requires 2–16 distinct out-of-band allowed identities, threshold >=2. Signers must be distinct from the lease provider and selected monitors. Duplicated, missing, unauthorized, forged or conflicting signatures fail closed.
3. **services/witness-agent/checkpoint_witness.py** runs as a separate process with a test-only signing key, checks the block by hash and number against loopback RPC, then emits its EIP-712 envelope. It never sends an on-chain vote or asserts physical fulfillment.
4. **EvidenceArchive** adds immutable witness_quorums records and store_witnesses/load_witnessed with full provenance and current canonical RPC re-verification. Missing witness records and attempts to replace a quorum are rejected. Legacy raw/anchored data cannot silently become externally witnessed.
5. **Portable export/import:** export_witnessed produces a bounded JSON/Base64 bundle containing unchanged provider response bytes, signed monitor report, signed snapshot anchor and witness signatures. import_witnessed verifies every statement, identity and current RPC block before populating another SQLite archive. The receiving archive independently re-verifies everything and rejects missing/reorganized source blocks.
6. **Anvil live test:** two additional witness CLI processes use separate keys, sign one block anchor, the original archive stores a two-of-two endorsement, a second SQLite archive imports the signed bundle, and both verify the exact raw bytes. After Anvil reverts the block, both strict archives reject the evidence even though the signatures remain cryptographically valid.

## Reproduction

Run the WP08E Python unittest, full unittest suite, forge build/test and the fresh disposable local Anvil runner tools/sse_wp08c_live_marketplace.py. The runner refuses to overwrite a nonempty .local/wp08c-live folder. GitHub Actions provides cross-platform test counts and publishes a short-retention evidence archive artifact.

## Verified CI checkpoint

[GitHub Actions run #43538865411](https://github.com/AkrAyoub/sse-research/actions/runs/43538865411) passed 4/4 jobs: **369/369 Python Ubuntu, 369/369 Python Windows, 52/52 Foundry Ubuntu**, plus fresh Anvil marketplace / HTTP / two-witness / portable second-archive integration marked **PASS**. The same live job saved both source and replica SQLite databases, two witness signatures and the signed portable bundle in the 14-day artifact. **R4 = 35% (+5 pp); engineering 24%, research 26%, overall 24%** under the original equal-phase-weight planning convention. These are phase estimates, not measured cryptographic or production security correctness.

## Unsolved trust and product requirements

- **NO independently authenticated finalized chain header.** Both lab witnesses currently read one Anvil node, not independent Ethereum consensus clients, and their EIP-712 attestations never prove PoS finality.
- **NO independently operated organizations/Sybil resistance.** Different keys do not prove different machines, network routes, financial ownership or physical distance.
- **NO automatic remote evidence availability.** A second verified local SQLite database and manually portable bundle do not replace TLS-secured cross-host replication, immutable externally committed hashes, or retention.
- **NO proof of physical SLA fulfillment or trustworthy clock.** Provider/monitor signatures cannot show consumer-side timely delivery or real CPU/storage work.
- **NO money release or contract change.** These signed checkpoint statements must never be treated as MonitorVote, QualifiedFact, slashing authorization or settlement evidence without an independently reviewed security policy.

## Next gate

WP-08F should implement a reviewed finalized-header/light-client or separately authenticated consensus-checkpoint model with explicit assumptions, then test conflicting RPCs, remote TLS/key pinning, independent peer operators, archive loss/replay and availability. R1/P1 physical-world soundness remains a separate payout blocker.
