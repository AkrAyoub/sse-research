# WP-09O engineering findings — completed local WP-09N measurements

**Evidence:** user-provided `optimizer_sweep.csv` (4 successful compiler profiles) and `success_call_gas.csv` (16 successful-call `gasleft()` deltas). Earlier local WP-09M report: 117 Foundry tests passed, and a settlement deployment-size listing of 23,661 bytes. No new Solidity execution was possible in the ChatGPT container in this package. The WP-09N withdrawal-reentrancy regression was reported by the user as passing locally before these CSVs were uploaded.

## 1. Compiler optimization sweep

| Optimizer runs | Runtime code bytes | EIP-170 headroom | WP-09N status |
|---:|---:|---:|---|
| 1 | 22,259 | 2,317 | room_available |
| 50 | 22,317 | 2,259 | room_available |
| 200 | 22,400 | **2,176** | room_available |
| 500 | 22,598 | 1,978 | low_headroom |

The EIP-170 runtime-code limit is 24,576 bytes; a **2,048-byte discretionary buffer** was defined by the WP-09N local tool as an engineering warning threshold, **not** a chain rule. All four optimizer profiles meet EIP-170, but 500 fails the buffer target.

**Default recommendation:** Keep optimizer runs=200, since this is the existing repository `foundry.toml` setting and measured headroom satisfies the discretionary threshold. Runs=1 provides only 141 additional bytes, and no matching 1-versus-200 successful-operation gas comparison is provided. Do not optimize for bytecode alone.

**Reconciliation blocker:** WP-09M listed 23,661 bytes with what was described as the default profile, but WP-09N's isolated default-200 sweep lists 22,400 bytes. The 1,261-byte difference is **not established as a source-code improvement**. Check source Git blob SHA, resolved compiler settings, exact optimizer runs, Forge version, `via_ir`, library dependencies and whether a stale gas-report/build artifact was used. The bundled `verify` runner measures the isolated bytecode and a gas-report deployment-size table in the SAME compiler profile.

## 2. Gas results, *gasleft* deltas (successful internal call)

| Operation | n=4 | n=16 | n=64 | n=160 |
|---|---:|---:|---:|---:|
| Legacy registration | 131,436 | 131,436 | 131,436 | 131,436 |
| Global-Merkle registration | — | 382,541 | — | 399,661 |
| Legacy lease creation | 579,503 | 975,492 | 2,559,465 | 2,579,365 |
| Global-Merkle lease creation | — | 472,682 | — | 472,994 |
| Global committee finalize (10 sampled proofs) | — | 544,367 | — | 568,910 |

At 16 active monitors, global-mode lease creation is **51.54% cheaper than legacy lease creation alone**. At 160, the comparable reduction is **81.66%**. Global creation increases by just **312 gas (0.066%)** from n=16 to n=160. These outcomes demonstrate a lease-creation scalability benefit, NOT complete protocol gas or throughput superiority.

Global registration grows about **4.48%** from n=16 to n=160 while registration at 160 costs about **3.04x** the legacy registration in the same fixture. Global finalization grows about **4.51%** and requires off-chain preparation of 10 Merkle paths.

Legacy lease creation reaches approximately **2.56M gas at n=64** and **2.58M at n=160**. Its scan is bounded, so the near-plateau is consistent with a capped snapshot window—not evidence that it treats all 160 identities equally.

The sum of global lease creation + 10-proof finalization is **1,017,049 gas at n=16** and **1,041,904 gas at n=160**. These partial sums are **not apples-to-apples full-election costs**, because legacy/randomness finalization differs from the global flow and neither sum includes all required transactions.

For the single VRF fixture, the request purchase measured **451,106 gas**, and applying VRF randomness measured **656,963 gas**, both as successful local EVM call deltas (not intrinsic transaction gas). The VRF application has **no roster-size label in the CSV**, so do not extrapolate its scaling from this file.

## 3. Engineering next steps, in priority order

1. **Verify the 1,261-byte settlement-size discrepancy using exact same-profile artifact and gas-report output.** A default-200 source+artifact+compiler snapshot must agree before size-optimization claims are made.
2. **Retain optimizer_runs=200** for now. Do not change production contracts or default config based solely on the bytecode sweep.
3. **Benchmark complete successful workflows** (including registration amortization, fee funding, coordinator request, VRF apply, 10-proof finalize, confirmation, epoch and withdrawals) using transaction receipts in a local Anvil instance, at 16, 64 and 160 monitor sizes. The 16 CSV deltas are a first-stage microbenchmark, not an end-to-end cost model.
4. **Target the global-registration write cost** and proof-finalization cost with adversarial roster-churn experiments; test WP-09G's proposed 40-index batched recovery separately before integration. Registration and proof finalization are the main added costs of global election.
5. **Continue security review** of settlement↔pool cancellation and external-call ordering. The passing single withdrawal-reentrancy test does not establish full security or real coordinator trust.

## 4. Explicit nonclaims

- No on-chain deployment, paid VRF call, real VRF proof or public-chain benchmark is part of these measurements.
- A smaller bytecode measurement under an isolated compiler run is not automatically a deployability proof for a different profile.
- The earlier gas-report function medians mixed successful/reverting calls; this new file deliberately measures successful-call `gasleft()` deltas.
- 16 test cases / 16 measured samples do not establish statistical confidence or production throughput.
