# R3 WP-09G — Offline batched global recovery prototype

**Date:** 2026-11-14  
**Repo:** `AkrAyoub/sse-research` (prior draft PR #26, branch `research/r3-wp09e-global-merkle-election`)  
**Execution:** Strictly local Python; **zero GitHub Actions runs, zero remote commits, zero network usage by tests**. The existing GitHub Actions settings were **not** changed because repository Actions administrative/cancellation permissions were unavailable. **Do not push until Actions has been disabled at repository settings.**

## 1. The precise defect targeted

WP09E freezes a global Merkle root over the entire active candidate registry, but finalization only ever uses the **first ten deterministic global indexes**. After the snapshot, these candidates can exit, because the global request does not lock the entire roster. Even if enough other monitors exist outside the first ten, four active monitors may be unavailable among the first ten. Re-rolling the entropy seed or letting the relayer skip an index would create unacceptable selection grinding.

WP09G **prototypes** a different approach: keep the **exact original seed and deterministic global index order**, but extend the ordered draw to at most **40** distinct indexes and prove them across **batches of eight**. It still verifies the historical Merkle inclusion of **every** processed index, not merely a caller-chosen set.

This is a **liveness improvement conditional on available correct proofs, at least four currently eligible monitors among the 40, and no adversarial denial of transactions**. It is **not** an unbiased VRF, an anti-Sybil mechanism, or a production security guarantee.

## 2. Implementation candidate included (uncompiled)

The offline ZIP contains:

- `wp09g_recovery.py`: executable deterministic partial Fisher–Yates, 40-index bounded draw, 8-index proof-batch model, first-four provisional bond locks, no arbitrary seed replacement, immutable historical proof sequence, expiry/refund state modeling.
- `test_wp09g.py`: invalid proof/seed guards, replay, full draw vs independent dense shuffle, compatibility with WP09E's first ten indexes, early candidate exits, retained bond locks, failure cleanup, timeouts, adversarial 37-of-40 exits, and randomized safety invariants.
- `run_experiments.py`, `metrics.json`, `liveness_comparison.csv`: exact finite-population mixing of two possible lease-party addresses plus independent exit events; **not** chain or gas measurements.
- `apply_wp09g.py`: **non-networking, anchor-checked local patch generator** for precisely two prior-PR26 Solidity source files (`OpenMonitorCommittee.sol` and `GlobalRosterSampler.sol`). Its default mode only prints a diff. `--apply` writes local files with backups. The new Solidity code is **NOT COMPILED OR EVM TESTED** because Foundry and solc were not installed in this environment. Solidity review, local build, tests and gas benchmarks are explicitly needed before merging.
- `test_patch_tool.py`: checks that patch anchors, key guards and state-release logic are present and refuses mismatched branches/double application; this is **NOT a Solidity compiler or verification oracle**.

### Proposed on-chain path

1. During a **new deployment's initial configuration**, select the already-existing global Merkle election mode and additionally enable `enableGlobalBatchedRecovery()`. This requires no historical registrations and must happen **before** the settlement contract binding.
2. `requestAssignment` commits global root and roster size as before. The selected entropy mode (legacy / delayed block hash / experimental RSA) stages one immutable seed; WP09G **does not** silently change that mode or the seed.
3. The relayer reads the first `min(40, snapshotCount)` deterministic indexes from `globalRecoveryDrawIndexes(id)` and reconstructs historical Merkle inclusion proofs from the frozen root.
4. `advanceGlobalRecovery(id, accounts, siblingPaths)` accepts **one to eight consecutive proofs**, in exact order. A wrong index, forged address, tampered proof or skipping previously due indexes reverts atomically. Every sampled membership leaf is authenticated before live bond and exclusion checks.
5. The first four currently bonded/active non-party candidates are assigned provisional seats and **immediately lock their own bond** (`activeAssignments++`). Additional eligible proven candidates are standbys in deterministic order. These reservations can last at most the pre-existing `randomnessTimeout` while the request remains pending. An already selected monitor cannot voluntarily exit until it is released.
6. **Only after all 40 (or N if smaller) indexes** are proven can the contract mark the assignment `Assigned`. There is no relayer-controlled early finalization that could suppress standbys. If fewer than four eligible members remain, it instead marks `Expired`, **releases every provisional lock** and clears partial standbys; the pre-epoch consumer refund path remains available. A permissionless timeout also releases provisional locks.
7. The original 4-confirmations / 3-monitor voting quorum, WP09A standby recovery, reward/escrow and physical evidence rules are unchanged.

The proposed maximum is five transactions for N ≥ 40, each carrying at most eight × twenty 32-byte sibling elements (about 5 KiB of proofs plus ABI overhead). **This is a structural bound, not a measured EVM gas or block limit**. Recomputing a 40-index partial draw in every batch and storing 36 standbys may be costly; local `forge snapshot` is mandatory before adoption.

## 3. Exact availability comparison (independent exit model)

160 identities, 2 registered lease parties, ideal uniform drawn indexes, and independent equal post-snapshot voluntary exit probability p among nonparty monitors. Event counted: at least 4 usable monitors exist somewhere in the first D distinct drawn indexes.

| Exit probability | WP09E D=10 | WP09G D=40 | Improvement |
|---:|---:|---:|---:|
| 0% | 100% | 100% | 0 pp |
| 10% | 99.998% | ~100% | +0.002 pp |
| 20% | 99.884% | ~100% | +0.116 pp |
| 40% | **93.956%** | **~100%** | **+6.044 pp** |
| 60% | **60.514%** | **99.99943%** | **+39.486 pp** |
| 80% | **11.649%** | **96.912%** | **+85.263 pp** |

The 40-proof approach is valuable **only if the prover submits all required proofs before expiry**. The probability model is not an adversarial guarantee and does not account for gas/relayer cost, delayed confirmation, physical operator correlation, targeted censorship, or fail-open physical SLA claims.

### Worst-case targeted exits

If the 40 distinct drawn identities all start eligible, **37 targeted exits** leave at most three available, still forcing fail-closed expiry. The prior 10-proof limit could be defeated by **seven targeted exits** in the corresponding all-eligible case. Registered consumer/provider identities reduce both counts. Coordinated targeted churn remains entirely possible.

### Withholding persists

The signer still observes a selected committee before deciding to publish a valid proof in the experimental RSA mode. With 40 attacker addresses among 160 active identities, ideal global 4-seat sampling has approximately **68.76%** probability of at least one attacker; a signer that reveals only such outcomes can still make **100% of published committees** include an attacker, withholding approximately **31.24%** of proofs. Proving 40 Merkle leaves cannot fix this. A standardized, availability-analyzed beacon/fallback design and an anti-Sybil/independent-operator trust model remain needed.

## 4. Security/accounting review checklist before integration

- **Staged bond lock griefing:** A malicious request proposer or proof relayer can provisionally lock four candidates by publishing the first batch and never completing. They auto-unlock only after the current `randomnessTimeout` (if someone calls permissionless expiry). Rate limits, request fees, concurrent lock ceilings, and keeper incentives need research before public deployment.
- **Selectively incomplete proofs:** Relayers may withhold later batches when they dislike the provisional committee. That converts liveness into another selective abort vector, even with a unique seed. Any fairness claim must condition on all requests being completed, not just accepted assignments.
- **Missing historical proofs:** An on-chain root alone doesn't make proof data available. Indexers, logs, snapshots and independent relayers must be demonstrated under reorgs and outages.
- **Churn between batches:** First-four provisional seats cannot voluntarily exit. Later sampled standbys are not locked and can leave before assignment/replacement.
- **Gas and contract size:** Nothing here establishes EIP-170 24 KiB bytecode fit, real calldata/gas budgets, or correct EVM compilation. **No Solidity-related tests were executed**. Mandatory local `forge build`, `forge test`, `forge snapshot` and fresh local Anvil after applying.
- **Operator identity and physical truth:** Attestation/signature validity does not imply physical SLA fulfillment or independently run monitors.
- **Economic conservation:** Full settlement invariants must be retested in EVM before deployment. The Python state machine only models selection locks, not EVM escrow storage.

## 5. Reproduce without Github Actions

Offline Python now:

```bash
cd WP09G_offline
python -m unittest discover -s . -p 'test_*.py' -v
python run_experiments.py
```

When repository Actions is **disabled by the owner**, apply to a fresh LOCAL checkout of stacked draft PR #26:

```bash
python WP09G_offline/apply_wp09g.py --repo /path/to/sse-research --check
python WP09G_offline/apply_wp09g.py --repo /path/to/sse-research --apply
cd /path/to/sse-research
forge build
forge test -vv
forge snapshot
```

The patch tool does **not** run `git push` or `gh workflow run`. Running local `forge`/`anvil` does not use GitHub-hosted Actions. **Do not push or merge until Actions is disabled and the Solidity integration passes local compile/tests.**

## 6. Recorded progress

Latest remote repository tracker (WP09E): **R3 38%, R4 38%, engineering 26%, research 26%, total project 26%**. WP09F adversarial experiments and this WP09G offline recovery prototype are additional local work only; no increase in project completion percentages has been recorded because Solidity is uncompiled, not integrated, not security-audited and not merged. WP09G verified offline subtask: **23/23 Python tests passed**; 40-candidate liveness calculations complete. Real protocol liveness/entropy hardening: **OPEN**.
