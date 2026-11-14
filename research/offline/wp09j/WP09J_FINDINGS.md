# WP-09J — Local-only VRF coordinator-to-SSE integration, failure paths and security boundaries

**2026-11-14. Experimental, prepared offline.** Not a public network deployment; not a cryptographically verified VRF in the local mock; **no Solidity compilation or EVM tests have been executed** in this environment. No GitHub Actions or GitHub writes were used.

## Why WP09I draft was not directly deployable

The earlier WP09I adapter draft needed the settlement address in its constructor. Yet the monitor pool needs the adapter as its immutable `randomnessSource` in its constructor, and settlement needs the monitor pool's constructor address: `adapter → pool → settlement → adapter`. The new WP09J contract instead keeps the coordinator pinned in the adapter constructor and provides an **immutable-in-practice one-way pool/settlement binding**, verified against the pool's configured randomness source and settlement's pool pointer. It rejects changing the adapter after the first lease.

WP09I also needed an explicit settlement hook to initiate a randomness request **after** the pool had frozen the snapshot. WP09J adds an opt-in `requestLeaseRandomness(leaseId)`, permissionless for an already-created Offered/Accepted lease. Unlike automatic VRF requests inside lease creation, a temporarily unavailable coordinator does not automatically block lease creation, and historical V1/other modes retain default behavior when no adapter is bound.

## Component-by-component lifecycle

**`SSESettlement` (patched via `apply_wp09j.py`):**

- Adds `ISSEVRFAdapter public randomnessAdapter`, governance-only `bindRandomnessAdapter()` once **before any lease**, checking adapter points to this settlement and the same monitor pool. It further checks pool's immutable `randomnessSource` equals adapter and that delayed-block and RSA proof modes are off.
- Adds permissionless `requestLeaseRandomness(leaseId)` for a lease in Offered or Accepted, with zero monitors finalized and the matching assignment still AwaitingRandomness. It does not change escrow amounts, evidence admission, vote quorum, confirmation requirements, or payout allocation.

**`OpenMonitorCommittee` (patched):** adds read-only `assignmentRequestedAt(id)` to expose the immutable request timestamp used by the adapter to enforce the same randomness timeout as the pool. Existing randomness seed acceptance, global snapshot roots, proofs, no-show recovery and bond accounting are not rewritten.

**`SSEVRFV25Adapter` (new):**

- Pins `coordinator`, `keyHash`, `subscriptionId`, `confirmations`, `callbackGasLimit` and `nativePayment` as immutable deployment configuration. Supports Chainlink VRF **v2.5 subscription request ABI** and its `extraArgs` V1 tag. No mutable coordinator migration method, no dynamic key/signer swapping.
- `requestSeed(assignmentId)` can be called **only** by the linked settlement, at most once per assignment forever. Reads `snapshotCommitment` and `requestedAt + pool.randomnessTimeout`; cannot choose a fresh, requester-controlled deadline. Fails closed if request is missing or already timed out. The official v2.5 coordinator would verify a VRF proof; local mock does not.
- `rawFulfillRandomWords(vrfId, words)` checks **exact pinned coordinator**. Unknown request, duplicate, malformed words or late callback are **ignored** without pool calls; spoofing reverts. This avoids consuming a coordinator's one-shot callback in a failed downstream selection. A locally simulated coordinator can nonetheless choose arbitrary outputs—it is a test double.
- `apply(assignmentId)` is permissionless but only for Ready, unexpired request; it rechecks assignment state and frozen snapshot hash. Seed domain includes chain ID, pool, assignment ID, external VRF request ID, snapshot hash and coordinator output. The pool accepts the result only because its immutable randomness source is the adapter. Failure is atomic, so the Ready state reverts as well.
- `expire(assignmentId)` after deadline transitions Requested/Ready to Expired, **with no retry, no reseeding and no blockhash fallback**. Pool expiry releases pending locks in legacy mode, or clears global staged seed; consumer refunds unused service escrow by closing uncommitted lease. A VRF subscription fee already charged is **not refunded** by the SSE contract.

**Mock coordinator:** `MockVRFV25Coordinator.sol` records the subscription-format request and permits its test operator to deliver arbitrary words. It is **NOT Chainlink**, **has no VRF proof verification**, and does not establish cryptographic unpredictability. Do not deploy as a trusted randomness source.

## Work verified vs not verified

**Actually run in this environment:**

- `17/17` WP09J Python integration-patcher/guard tests (source-anchor uniqueness, idempotence rejection, separate output generation, no changes to local source tree, duplicate/malformed state guards, expected EVM test cases). These are *structural* checks and do **not** prove that Solidity compiles.
- `25/25` prior WP09I Python state-machine tests (request ID scoping, no rerolls, fake coordinator callbacks, key rotation policy, timeout/fallback, signer/model tests). These are **policy model** tests and do **not** execute EVM code.
- Verified output file creation and offline package construction.

**Authored but not run:** two Foundry test contracts with **seven EVM-oriented test functions** for request/callback integration, abuse resistance, VRF expiry/refund and global Merkle selection after a mock callback. Needs Forge/solc present locally, with the existing SSE/Foundry libraries installed. No compiler or Anvil present; sandbox cannot resolve external downloads.

**Not verified:** v2.5 official coordinator compatibility on a supported network, actual Chainlink proof-verification, real subscription gas charges, VRF latency, deployed coordinator authenticity, reorg/finality assumptions, and concurrency or gas at large monitored populations. All of these remain release gates.

## Critical risk and threat model

1. **A fixed coordinator address is not a VRF proof verifier.** Only a known genuine coordinator can check the cryptographic proof. The standalone local adapter uses a minimal raw callback with an exact sender guard, whereas official Chainlink security guidance recommends inheriting their audited `VRFConsumerBaseV2Plus`. For a production implementation, use the official base or security-reviewed pinning extension—not this bare adapter in isolation.
2. **Withholding is not fixed.** A real VRF operator/coordinator failure can leave a request unfulfilled; the no-reroll policy prevents an assignment from trying again but cannot promise assignment completion or erase selection bias conditional on which assignments finish.
3. **Repeated lease creation is still a grinding surface.** The adapter blocks one lease from re-requesting; it does not stop a well-funded user from abandoning one lease and creating another. Production research needs bounded cancellation/fees and an external fairness definition.
4. **Membership can change after snapshot.** In WP09E global mode, exits can invalidate readiness despite an authenticated historical root, and Merkle availability depends on a functioning proof indexer. WP09G's 40-candidate offline batch proposal remains separately uncompiled and not combined with this patch.
5. **Timeout must account for actual VRF service latency.** If coordinator fulfillment normally exceeds the configured pool timeout, user may pay for a request that will be ignored and expire. Verify service-level limits before a public deployment.
6. **Payment and key setups are external.** No real subscription was created/funded, and no LINK/native payment occurred; the mock does not reproduce subscription billing. Network addresses and keyHash MUST come from official chain-specific sources at deployment time.
7. **The real SSE fairness problem remains.** Even perfect VRF only randomizes bonded addresses. It does not prove independent operators, physical SLA facts, legitimate votes, resilience to correlated partitions, or fairness of fee split.

## Recommended next action

Run the provided Foundry tests **locally on a machine with Foundry installed**, after applying the patch in a disposable working tree. Compile the whole existing SSE suite and measure gas. Resolve any compilation/integration errors before changing project completion estimates. Explicitly disable GitHub Actions in repository settings before any accidental remote push; no hosted CI is required.

A separate security-reviewed design phase should replace the bare callback with official VRF v2.5 consumer base, define coordinator migration/deployment lifecycle, harden lease-cancellation economics and connect proven bounded no-show recovery before any production claim.

### Project progress bookkeeping

| Measure | Last verified recorded estimate | Change from WP09J |
|---|---:|---:|
| R3 – monitor registry and election | 38% | 0 pp |
| R4 – signed evidence SDK | 38% | 0 pp |
| P4 – experiments and baselines | 20% | 0 pp |
| Engineering aggregate | 26% | 0 pp |
| Research aggregate | 26% | 0 pp |
| Project overall | **26%** | **0 pp** |

No increase because no EVM execution or production-hardening review was completed.
