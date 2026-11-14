# R3 WP-09C — Opt-in future-block entropy over a frozen committee snapshot

**Status:** 2026-11-14 · stacked draft PR #24 built on WP09B PR #23 (itself stacked on #22 → #18). No production deployment, merge, VRF or Ethereum PoS light client. All claims below distinguish observed local EVM tests from assumptions.

## Motivation and realistic gain

V1 accepted any integer seed sent by a single immutable `randomnessSource` EOA, **after** a selected lease's eligible snapshot was already known. That party could deliberately choose a favorable seed (or withhold fulfillment). WP09B removed the 32-lifetime-registration ceiling but its 64-entry rotating candidate window is predictable. Simply declaring the seed "random" did not establish a fair committee.

WP09C adds an **optional** different path: the monitor pool itself binds the exact eligible snapshot to a commitment **before** a particular future block is mined, and anybody can derive/apply a deterministic entropy value from that future block hash. An authorized arbitrary-seed callback is disallowed **when this mode is enabled**.

This eliminates the one-EoA arbitrary-seed selection step *in opt-in mode*, but is **not** a securely unbiased Ethereum VRF or global selection guarantee. A validator/sequencer can bias a hash; a proposer can influence inclusion, chain forks and timestamps; a user can time requests; and the rolling candidate window remains predictable. Do not use this as proof of honest-majority monitor assignment.

## New public contract interface

`OpenMonitorCommittee` adds:

- `enableDelayedBlockEntropy()`: callable only by the deployment bootstrapper **once, before** `bindSettlement`. The change is one-way; there is no post-binding admin switch. Legacy (disabled) mode stays available to preserve V1 prototypes and test/deployment compatibility.
- `delayedBlockEntropyEnabled()`: query which mode was fixed before the pool was bound.
- `assignmentRequestedBlock(id)`, `snapshotCommitment(id)`: record the request block number and a SHA3/Keccak commitment `keccak256(abi.encode(block.chainid, poolAddress, requestId, requestBlockNumber, eligibleAddressArray))`, calculated during the **bounded** WP09B snapshot. The snapshotted candidate array is also frozen in storage and protected by pending-selection bond locks. Later joins do not affect it.
- `DELAYED_ENTROPY_BLOCKS = 4`, `DELAYED_ENTROPY_DOMAIN = keccak256("SSEDelayedBlockEntropyV1")`.
- `fulfillDelayedBlockEntropy(id)`: permissionless after block `requestBlock + 4` has been mined, while the existing randomness timeout has not expired and the target is no older than 256 blocks. It uses `blockhash(target)`, refusing a missing/zero hash. The derived on-chain seed is `uint256(keccak256(abi.encode(domain, chainId, poolAddress, requestId, snapshotCommitment, entropyTargetBlock, targetBlockHash)))`.
- `EligibilitySnapshotCommitted` and `DelayedEntropyApplied` events: publish the frozen commitment, chosen target, observed future block hash and applied seed for auditable local replication.
- In opt-in delayed mode, `fulfillRandomness(id, seed)` **always rejects**, even when invoked by the formerly authorized randomness source. In unchanged legacy mode, only that source may fulfill the snapshot.

## Selection and financial invariants

Both modes call exactly the **same** bounded seed-based pool permutation and reuse WP09A's committee and standby accounting. The successful assignment is still four selected monitors; three monitor votes remain the reporting quorum, four actual confirmations are still necessary to begin any epoch. A successful delayed fulfillment still releases pending snapshot locks and increments selected active assignment locks, and later recovery and release use the unchanged paths. No monitor can infer an EIP712 physical delivery fact from this entropy event. There are **no changes** to Solidity lease escrow, rewards, slashing or evidence verification rules.

In delayed mode, the original `expire(id)` remains permissionless only after the timeout and clears pending locks. If target hash becomes too old (>256 blocks), unavailable, or the reporter doesn't fulfill before the timeout, the request **fails closed**; funds and pending locks can be recovered through the existing expiry and consumer refund path. `releaseCommitteeAfterEvidence` is appropriate **only for Assigned** pools, not an expired pre-selection request whose pending locks were already released.

## Tests / independent reproduction

Foundry adds `foundry/test/DelayedBlockEntropy.t.sol`:

1. Unauthorized, repeated or post-binding activation is rejected.
2. Existing authorized arbitrary-seed callback is rejected in delayed mode; permissionless fulfillment before/at the target block is rejected.
3. Full eligible roster and request scope hash are frozen before entropy exists; late registration has no effect on an already requested assignment.
4. Known future block hash plus typed domain, chain ID, pool, request ID and snapshot hash reproduce the derived selection exactly using the original Fisher–Yates-style permutation.
5. Four selected monitor confirmations are still necessary before epoch admission, and the previous three-of-four failure vote economic path is unchanged.
6. Expired, zero-hash, too-old block (>256) and duplicate fulfillment attempts fail; pending bonds are released by expiry, and uncommitted escrow can be refunded; no phantom committee release.
7. Legacy seed mode remains behaviorally compatible when the new mode is not activated.

The fresh local Anvil marketplace E2E now explicitly enables the new one-way mode before binding settlement, creates and funds an actual marketplace lease, captures the pre-entropy commitment, mines the later target block, and uses an **unprivileged outsider** to fulfill. It then runs the full WP09A 3-of-4 no-show rescue, real provider/monitor signed HTTP capture, witness replication, post-capture reorg refusal, and simulated Beacon REST ancestry checks.

Reproduce (fresh directory for `tools/sse_wp08c_live_marketplace.py`):

```bash
forge build
forge test -vv
python -m unittest discover -s tests -v
python tools/sse_wp08c_live_marketplace.py
```

### Research limits — never call this a VRF

- The future block is an **unfinalized consensus-execution block**, not a cryptographically validated beacon finality certificate. Anvil uses a controlled test miner; it demonstrates only EVM semantics, not independently operated Ethereum validators.
- Block proposers can conditionally choose/block/censor transactions and may influence block contents, choosing among admissible blocks. Users can front-run or schedule leases to target desirable entropy blocks, and a chain reorg may change the entropy before canonical finalization.
- This method does **not** protect against Sybil identities (one operator controlling multiple bonds), window manipulation, proposer collusion, adversarial selective cancellation or liveness denial.
- This method does **not** produce uniform global eligibility across all active monitors. WP09B's 64-candidate rotating window is the entire sample domain; weighted and globally uniform election are out of scope.
- The future block target is four blocks later for **lab reproducibility**, not a production risk parameter justified by empirical block production/reorg data. Timeouts are anchored to `block.timestamp`, not an independent physical clock.
- For production and a paper proof of randomness security, design an independently verified VRF/coordinator or other assessed randomness beacon, frozen eligibility commitments covering the desired *global* sample space, honest-majority/Sybil assumptions, and adversarial withholding/proposer-grinding experiments.

**Acceptance statement:** WP09C proves reproducible, opt-in on-chain **future-block seed derivation for a previously frozen bounded snapshot**, with explicit economic and liveness nonclaims. The global-randomness/fairness phase gate remains open.
