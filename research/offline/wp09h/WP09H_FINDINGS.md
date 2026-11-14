# R3 WP-09H — Offline threshold-entropy withholding and quorum research

**Date:** 2026-11-14  
**Execution:** Local Python only. **Zero GitHub Actions, zero GitHub writes, zero paid hosted runners, zero test-network calls.**  
**Project context:** Follows stacked draft WP09E (#26) and the entirely offline WP09F / WP09G research packages. **This is not merged contract code and is not a production-ready threshold VRF.**

## Outcome

- **28/28** independent offline tests passed, including real Ed25519 signature authentication for request-scoped *participation receipts* and integration with the WP09G 40-index batched election state machine.
- **400,000** offline simulated committee elections (eight scenarios × 50,000); analytic exact probabilities cross-checked against Monte Carlo, deterministic RNG seed 20261114 + scenario index.
- **Core result:** A uniquely verifiable threshold output eliminates arbitrary *subset-dependent seed choice* **only if a proper threshold cryptographic protocol is implemented**. It does **not** eliminate selective withholding whenever malicious shares are required for liveness. A simple "first t signers / hash signatures" design is unsafe because different signer subsets yield different outputs.

### Threat model and measured math

All scenarios model N=160 bonded *identities* (not independent physical operators), 40 attacker-controlled identities, and k=4 committee seats sampled **ideally without replacement**. The ideal probability of at least one attacker seat is:

`1 - C(120,4)/C(160,4) = 0.6875919398684738` (68.7592%).

A genuinely *unique* threshold-VRF output is **assumed by the model, not implemented**. For n signers, quorum t, f colluding malicious signers, and independent honest signer online probability p:

- `H ~ Binomial(n-f, p)` counts timely honest shares.
- `P_forced = P(H >= t)`. In this case honest shares suffice and attackers cannot censor an otherwise publishable unique output, assuming network liveness.
- `P_optional = P(t-f <= H < t)`. Here malicious shares are necessary to achieve the threshold; attacker may conditionally publish only favorable results after seeing enough honest shares.
- `P_publish = P_forced + P_optional * P_hit` under this **maximally selective** withholding strategy.
- `P(attacker seat | published) = P_hit * (P_forced + P_optional) / P_publish` when `P_publish > 0`.

| Scenario | Proof publishes | At least one attacker among published |
|---|---:|---:|
| Ideal unbiased selection baseline | 100.00% | 68.76% |
| One fully malicious signing authority | 68.76% | **100.00%** |
| **2-of-3 all honest**, p=0.95 | 99.28% | 68.76% |
| **3-of-5 all honest**, p=0.95 | 99.88% | 68.76% |
| **3-of-5 with one malicious**, p=0.95 | 99.53% | 69.05% |
| **3-of-5 with two malicious**, p=0.95 | 95.54% | **71.96%** |
| **3-of-5 with three malicious**, p=0.95 | 68.76% | **100.00%** |
| **4-of-7 with three malicious**, p=0.90 | 89.25% | **77.03%** |
| **4-of-7 with four malicious**, p=0.90 | 68.76% | **100.00%** |

*Numbers are analytical model outputs. The independent seeded Monte Carlo estimates are in `threshold_bias_metrics.csv` and generally agree within simulation error. The table is not a deployed-network measurement.*

### Why a naive backup can be worse

A signer choosing opportunistically between a primary and a secondary independent candidate output can prefer whichever has an attacker seat: `P(favorable in either) = 1 - (1 - 0.68759194)^2 ≈ 90.24%`. A "fallback randomness" button does not automatically cure withholding; it may **add a new grinding option**. Pure fail-closed expiry preserves authorization but cannot ensure availability and can still make successful results conditionally biased.

## Implemented files and test boundaries

- `wp09h_policy.py`: strict chain-/pool-/request-/root-/count-/deadline-scoped request digest, **real Ed25519** authenticity validation for fixed signer IDs, duplicate/unknown signer prevention, exact deadline and expired-state cleanup. Receipt subset/order never enters output seed. It has an **injected verifier callback for a unique proof**. **That callback is a test-only ideal oracle; it is not an implementation of RSA threshold key splitting, BLS threshold aggregation, DKG, or an Ethereum VRF precompile.**
- `wp09h_experiments.py`: exact binomial and hypergeometric conditional-publication bias model and deterministic 50k-election Monte Carlo for each of 8 scenarios.
- `wp09g_recovery.py`, `keccak.py`: copied read-only prior local WP09G recovery and Keccak reference required for integration and reproducibility.
- `test_wp09h.py`: 28 tests of Ed25519 scope, replay, quorum, duplication, proof abstraction, expiry, WP09G bounded batches/locks, exact math and simulation.
- `results.json` and `threshold_bias_metrics.csv`: machine-readable experiment records; `experiment_stdout.json`: concise human-facing scenario values.

**What's real**: participation receipts use `cryptography` Ed25519 verification; WP09G election reference is executed; math and simulations execute locally.  
**What's not implemented**: a genuine distributed threshold-VRF key ceremony, secret shares, aggregation, slashable operators, reliable message dissemination, real blockchain operations, Solidity compile or gas measurements, external witness independence, service-delivery truth.

## Production design gate — WP09I recommendations

1. Select a **standard, reviewed, unique-output threshold VRF or other assessed beacon**. Require an authenticated public key, audited share verification and threshold proof reconstruction where **every valid t-subset produces the same final proof/seed**. Do not derive the seed from the choice/order/identities of signers.
2. Quantify availability under *actual honest quorum*, not merely `t of n` participants. Protocol threat assumption should specify an honest responsive lower bound, network delays, corruption budget, outage distribution and minimum availability target. With 5 signers, t=3, two malicious refusing to cooperate requires **all 3 honest signers online**.
3. Introduce bounded submission / proof deadlines and **fail-closed** expiry, with exact consumer refund and monitor-bond unlocking. Avoid discretionary early retries, re-sampling, fallback sources and manual override after an unfavorable result.
4. Design a verifiable incentive mechanism and dispute procedure for signer absence; nonresponse on-chain can be observed but cannot alone distinguish intentional malice from outage or censorship. Penalties only help economically if credible, collectible and larger than incentives to censor.
5. Keep WP09G’s deterministic 40-index batched Merkle proof sequence. Never permit relayers to skip an index or restart with a fresh seed after unfavorable outcomes. Preserve lease 4-of-4 confirmations vs. 3-of-4 evidence vote quorum and exact escrow accounting.
6. Prepare distributed, independent-host experiments on network partitions, adaptive withholding, correlated operator compromise, randomized failure recovery, backlog and gas. **No new test runner bills should be incurred: run locally or on already-owned machines with consent.**

## Reproduce (strictly offline)

```bash
cd WP09H_offline
python -m unittest discover -s . -p 'test_wp09h.py' -v
python wp09h_experiments.py --trials 50000 --output .
```

Requires Python 3.11+ and the local `cryptography` package for Ed25519 receipts. No public RPC, GitHub API, cloud services, or GitHub Actions are involved. Output paths are local to this folder.

## Progress accounting

- Latest recorded repo tracker remains **R3 38%, engineering 26%, research 26%, overall 26%**. R4 38%, P4 20%.
- WP09F, WP09G, WP09H are **offline research/prototypes**, not compiled/merged Solidity or deployed decentralized entropy infrastructure. They are evidence for future protocol decisions, **not additional verified on-chain completion points**. Thus no percentage bump.
- Next on-chain integration will require **local Foundry/Anvil**, a real threshold-verifier implementation, security review and user-authorized repository workflow changes only **after disabling Actions**.
