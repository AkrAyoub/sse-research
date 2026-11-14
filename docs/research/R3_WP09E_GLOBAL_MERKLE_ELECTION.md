# R3 WP-09E — Authenticated global active-roster elections with bounded proofs

**Status:** 2026-11-14 · stacked **draft PR #26** atop WP09D #25 → #18. No merge, existing-contract upgrade, public key ceremony, audited VRF, distributed infrastructure or live-chain release.

## What changed

WP09B could enroll far more than 32 lifetime identities but sampled a **predictable rolling window of at most 64 currently active identities per lease**. Even an RSA proof (WP09D) or future-block entropy (WP09C) could only permute within that window. Registration/exits could manipulate which part of the pool was sampled.

WP09E introduces a separate, one-way deployment option `enableGlobalMerkleElection()` that must be enabled **before any monitor registers and before settlement binding**. It maintains an authenticated Merkle commitment to *every currently active monitor address* with **O(log N) roster update**, freezes the entire roster's root and cardinality on each lease request in **O(1) snapshot time**, and later requires index-by-index Merkle proofs for a deterministic **bounded draw across all N active identities**, not a local 64-address window. The ordinary fixed committee (four selected; three vote quorum; four required confirmations) and the WP09A seeded standby/no-show recovery remain unchanged.

**This is conditional global sampling, not cryptographically proven unconditional fairness.** The draw inherits its entropy mode's security: legacy EOA still allows seed grinding, WP09C future-block may be proposer-biased, and WP09D's RSA private-key holder can withhold outputs (and uses an unstandardized custom representative scheme). Adversarial churn after the snapshot, Sybil registrations, correlation among physical operators, time/abort manipulation and selection availability remain open.

## Contract interfaces

- `GlobalRosterMerkle.sol`: sparse binary Merkle tree of depth 20, capacity **2^20 simultaneous active slots**. The leaf for slot `i` and address `a` is `keccak256(0x01 || uint32_big_endian(i) || address20(a))`; empty leaves are zero. Internal parents hash left/right packed 32-byte nodes, treating double-zero as an empty subtree. On every `register`, the new dense active slot is written. An authorized unlocked exit uses the existing swap-and-pop roster, updates the moved address's leaf (if any), and deletes the vacated last leaf. At most 20 ancestors are recomputed per update, independent of N. The **maximum simultaneous** population exists because the fixed tree must have a bounded depth; there is still **no lifetime enrollment identity ceiling**. Address-only leaves do not prove physical operator independence or future bonded availability.
- `GlobalRosterSampler.sol`: an **O(k²), k≤10** sparse partial Fisher–Yates permutation over integer indexes **0..N−1**, with a Keccak seed/domain linked to request ID. Exactly `min(N,10)` distinct indexes are deterministically sampled, with no full-roster shuffle and no unbounded loop. Modulo reduction introduces theoretically negligible bias assuming an ideal seed, but it is not strictly zero-bias, and no global uniformity exists if the seed source is manipulable.
- `OpenMonitorCommittee.enableGlobalMerkleElection()`: opt-in before binding, initially empty candidate list; compatible with **one of** the original three entropy modes (legacy trusted EOA, WP09C future block, WP09D RSA proof).
- `globalRosterRoot()`: current root. `GlobalRosterLeafUpdated` and `GlobalRosterRootUpdated` events allow independent observers to replay the tree. Off-chain clients need a historical indexer or archive snapshot, not just `candidateAt()` at today's mutable roster state.
- `requestAssignment(consumer,provider)` in global mode: requires at least four active identities **excluding** lease parties, freezes `globalSnapshotRoot[id]`, `globalSnapshotCount[id]`, `assignmentRequestedBlock[id]` and `snapshotCommitment[id] = keccak256(abi.encode(chainId,pool,id,block.number,root,count))`. No 64-entry scan and **no pending-selection lock over the global roster**. Emits `GlobalEligibilityCommitted` and `AssignmentRequested`.
- `fulfillRandomness / fulfillDelayedBlockEntropy / fulfillRSAProofEntropy`: the selected mode derives/stages a fixed `pendingGlobalSeed[id]`, and sets `pendingGlobalSeedReady[id]`. It **does not immediately assign a committee** in global mode because proof of the global leaf addresses must follow. A second seed submission is prohibited. Existing non-global selection paths remain unchanged.
- `globalDrawIndexes(id)`: publicly recomputes the first `min(globalSnapshotCount,10)` distinct global indexes from the immutable seed.
- `finalizeGlobalCommittee(id, accounts[], siblingPaths[][])`: any caller must submit **exactly one 20-element historical Merkle proof per deterministic index, in the required order**; there is no caller-controlled skip list. The contract recomputes each leaf against the previously frozen root. Forged address, wrong index, reordered proofs, changed leaf, omitted index, or wrong snapshot all fail. Lease consumer/provider and candidates **no longer active/bonded at finalization** are skipped only after their historical proof is verified. The first four currently eligible accounts become the committee, the remainder (up to six) become standby entries in the same seeded order. Fewer than four valid current candidates fails closed, without changing escrow or assignment locks.

## Security, exit and liveness boundaries

**Global roster root is authentic conditional on EVM execution**, but root truth does not establish independent operators, anti-Sybil eligibility, or a qualitative credential. The tree is index-address scoped and authenticated by its mutation path, not supplied by an external administrator. It is also **not an immutable global participation snapshot of bonds**: it freezes membership indexes, while the system checks live `Candidate.active` and bond at assignment time. The absence of global pending bond locks is deliberate to bound request gas but introduces a **post-request exit window**. Exits after root commitment (and before selection) can force the top candidate to be skipped or, with enough coordinated exits, cause insufficient candidates and timeout/refund. This is **not resolved** by a Merkle proof or a VRF. An indexer that fails to reconstruct historical tree data can also delay committee selection.

A snapshot with N≥10 and at most two lease parties has at least eight eligible slots among the first ten draws **if there are no exits**: four initial monitors and up to four standby monitors. When party addresses are absent, ten eligible slots yield four initial monitors and six standbys. For N<10, all N slots are drawn. Standbys remain independently allowed to exit after assignment, and WP09A's recovery verifies their current bond/activity.

The seed can be staged but not finalized before the randomness timeout; on failure, the existing permissionless `expire(id)` transitions AwaitingRandomness → Expired, resets staged-seed state, and the consumer can refund uncommitted escrow via the pre-epoch close path. No phantom bond locks are released for a global snapshot because **none were created until committee assignment**; the four selected members still acquire and later release their active-assignment locks normally.

**Global fairness, independent verifiable randomness and guaranteed committee liveness are not established**: WP09D RSA signing can be selectively withheld, the key setup is trusted and its private key in the test fixture is **public and insecure**. In non-RSA modes the legacy EOA/proposer influence caveats also remain. Adaptive Sybil split, malicious operator churn and selective abort need adversarial measurement. Global population cap is a fixed 2^20 active *slots*, not an unbounded proof of scalable storage cost.

## Evidence and reproducible tests

- `foundry/test/GlobalMerkleElection.t.sol`: independent-on-chain historical tree, **80 registered monitors with sampled indexes >63**, uniqueness, proof-completeness and no caller-chosen index, wrong address/sibling/order rejection, immutable historical proof after swap-pop exit, former member exclusion, selected bond locks, consumer/provider exclusion, WP09A 3-of-4 confirmation timeout/replacement and retained epoch activation, insufficient-eligible atomic revert, expiry and escrow refund. The 80-candidate test proves **functional selection beyond 64**, not a measured gas ceiling for a 2^20-identity deployment.
- `tools/sse_wp09e_global_merkle.py` + `tests/test_sse_wp09e_global_merkle.py`: independent Python root, proof, swap-pop, commitment and sparse global permutation implementation. Tests cover a **96-candidate** roster, tampered paths, proof reuse against a changed root, full small-permutations, diverse candidate counts up to 1,000 and sample reach beyond the former window.
- `tools/sse_wp08c_live_marketplace.py`: fresh Anvil starts with RSA proof-verified entropy **and** global-Merkle opt-in, registers five real bonded actors, funds a marketplace lease, freezes global root/count, independently rebuilds it and the chain-/lease-bound commitment in Python, submits a **real RSA proof** to the on-chain verifier, checks staged seed, compares global sampled indexes independently, submits real **20-sibling EVM inclusion proofs for all five deterministic indexes**, finalizes committee, exercises 3-of-4 no-show replacement and the established provider/monitor signed evidence integration. No mocked proof in this scenario. Existing EIP712 authorization and post-capture fork/replica/Beacon mock caveats remain.

Source CI reference: [WP09E GitHub Actions run #43548406416](https://github.com/AkrAyoub/sse-research/actions/runs/43548406416). Final branch-head CI must also be green after documentation updates.

```bash
forge build
forge test -vv
python -m unittest discover -s tests -v
python tools/sse_wp08c_live_marketplace.py
```

## Next requirements

1. **Withholding-resistant audited entropy**: standard, independently verified VRF/coordinator with explicit key authenticity, availability and timeout/retry/grinding analysis.
2. **Membership churn & snapshot locks**: safe bounded mechanisms for willingness-to-monitor at snapshot time, nonresponse penalties only for independently provable offenses, bounded reserve exhaustion and cancellation policy.
3. **Empirical global fairness**: compare selection frequencies, conditional bias and concentration across 64-window WP09B vs global proof-based WP09E, for varying N, adversarial registrations and churn.
4. **Scale measurements**: gas per 20-level register/exit, verify ten proofs, select k=4, standby turnover and concurrent assignments at hundreds/thousands of identities. The 2^20 upper bound is not itself an empirical deployed gas/cost guarantee.
5. **R1/R2 safeguards**: physical SLA evidence soundness and robust economic authorization are independent of elected EOA membership; global committee selection is not proof of honest service evaluation.

**Tracking proposal if full CI passes:** R3 **33% → 38% (+5pp)**, engineering aggregate **26% (309/1200)**, research **26% (180/700)**, overall **26% (489/1900)** by equal-phase planning estimates. Not a security assurance figure.
