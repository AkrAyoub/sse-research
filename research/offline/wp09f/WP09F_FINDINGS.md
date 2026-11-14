# R3 WP-09F — Offline adversarial committee election and liveness results

**Date:** 2026-11-14. **Cost:** no GitHub Actions workflow triggered; experiments ran in a local container with Python standard library only. **Repository status:** previous draft PR #26 remains the latest known remotely stored WP09E implementation; this WP09F report and code have NOT been committed to GitHub.

## Question and model

WP09E made every active member eligible through a frozen authenticated global root with a 10-index proof limit. A valid inclusion proof says an address was in a historical active roster; it does **not** guarantee fair entropy, independent operators, a responding monitor, or unalterable physical service observations.

This offline experiment isolates three remaining attack classes:

1. **Predictable window targeting (WP09B vs WP09E):** 160 registered addresses; first 40 controlled by an adversary; an eligible committee has 4 members; WP09B has 64-wide rotating windows starting at 0, 64, 128, 32, 96; WP09E samples the full 160-person roster.
2. **Selective proof withholding:** a cryptographic proof holder privately sees the selected committee before deciding whether to reveal a valid proof. Because one holder can refuse to sign/reveal, deterministic proof uniqueness does not guarantee unbiased *published* outcomes.
3. **Post-snapshot churn and nonconfirmation:** WP09E can prove up to ten distinct historical leaves, but it does not lock all candidate bonds during the entropy stage. Voluntary exits, actual nonresponses, and proof availability may cause fewer than four usable current monitors.

All probabilities use an **ideal unbiased randomness source** unless stated otherwise; this assumption intentionally gives the design the benefit of the doubt. The current V1/VRF alternatives have *additional* entropy and authentication caveats.

## Exact results

### 1. Predictable 64-window vs global roster

With 40 adversarial addresses among 160 (25% concentration), exactly 4 distinct committee seats and no exits/party exclusions:

| Scheme / initial window | Attacker IDs inside sampling population | P(at least 1 attacker in 4) |
|---|---:|---:|
| Global 160-identity uniform draw (WP09E ideal model) | 40 of 160 | **68.76%** |
| Window start 0 | 40 of 64 | **98.33%** |
| Window start 64 | 0 of 64 | **0.00%** |
| Window start 128 (wraps) | 32 of 64 | **94.34%** |
| Window start 32 | 8 of 64 | **42.19%** |
| Window start 96 | 0 of 64 | **0.00%** |

In a *static* five-request cursor cycle, each identity appears in 2 of the 5 windows, so its marginal per-request election rate is 4/160=**2.5%**, the same as under ideal global sampling. **Do not mistakenly claim the static five-cycle marginal probability is biased.** The crucial danger is that the **next individual lease's window and candidate population are transparent**, and adversaries can time participation, enrollment/exits, or target which lease they attack. The event probability of at least one attacker varies sharply (0% to 98.33%) depending on the current predictable window. WP09E removes that 64-window restriction, but not entropy-withholding attacks.

### 2. Withholding changes the sample of *published* outcomes

Using ideal full-roster selection (40/160 attacker identities):

| Private signer publication policy | Requests that produce a proof | Unresolved requests | Attacker in published committee |
|---|---:|---:|---:|
| Publish all proofs | 100.00% | 0.00% | 68.76% |
| Publish only when >=1 attacker in first 4 | **68.76%** | **31.24%** | **100.00%** |
| Publish only when >=2 attackers in first 4 | **26.04%** | **73.96%** | **100.00%** |

The last column means **at least one attacker**, not an attacker majority. For policy >=2, it additionally guarantees two or more attacker seats among the published committees. Unresolved attempts are not counted as successful assignments; timeout/close/refund paths must handle them. An operator needs only **the ability to withhold**, not the ability to forge a second RSA proof, to create this bias among *completed* assignments. A truly autonomous verifiable randomness beacon or an incentive/fallback policy must address this separately.

### 3. Liveness under post-snapshot exits

WP09E samples up to ten distinct global indexes, chooses 4 currently available eligible monitors, and excludes consumer/provider. In this model, exactly two lease-party addresses are among the 160 registered identities, so an expected fraction of the ten draws is ineligible. Remaining monitor identities exit independently after the global root is frozen with probability `p`. The probability of **at least four usable current monitors** before activation is:

| Per-monitor post-snapshot exit probability p | P(at least 4 eligible among 10 drawn) | P(all initial 4 confirm without standby replacement) * |
|---|---:|---:|
| 0% | **100.00%** | **100.00%** |
| 10% | **99.998%** | **65.61%** |
| 20% | **99.884%** | **40.96%** |
| 40% | **93.956%** | **12.96%** |
| 60% | **60.514%** | **2.56%** |

*Last column uses the *same numeric p as an independent no-show probability* for four already selected monitors. It is a separate simplified mechanism from exits; it does not reflect WP09A replacement availability or real turnaround time. If all ten candidates were independently callable, a perfect sequential replacement policy could theoretically obtain four confirmations with probability much higher than the four-initial-confirmations probability, but it requires renewed one-hour timeout windows and excludes adversarial churn/censorship.

**Worst-case adaptive exit:** if 7 of the 10 provably drawn identities were initially eligible but exit before finalization, only 3 remain: the contract must fail closed and the assignment must eventually expire/refund. This is a *safety-preserving liveness failure*; a Merkle membership proof cannot solve it. Party exclusions can reduce usable members even without any exits, although with at most two registered lease-party identities among ten draws there remain at least eight if all others stay active.

### 4. Reproducibility and cross-checks

- Exact Keccak-256 WP09E sparse sampler for `seed=1234`, `requestId=1`, `n=160` produces **[42, 10, 22, 78, 37, 128, 82, 118, 93, 145]**. These are distinct global indexes, including values above the old 64-address selection limit.
- The sparse implementation matched an independently written dense Fisher–Yates reference across 44 size/seed combinations.
- 50,000 seeded ideal-source Monte Carlo samples gave **69.076%** of global 4-member committees containing >=1 of the 40 attackers, close to the exact theoretical **68.759%**. Expected sampling error near this size is about 0.21 percentage points (one standard error).
- `python -m unittest discover -s . -v`: **11/11 offline tests passed**, zero GitHub Actions cost.

## Design and evaluation decisions for the next work

1. **No production qualification yet.** RSA signature/root verification and Merkle inclusion are distinct from a reviewed VRF, a proof of entropy availability, operator independence, physical SLA truth, and settlement safety.
2. **Explicit withholding policy:** Specify a bounded proof deadline, deterministic error/abort state, responsibility for fees/timeout and an entropy fallback that cannot be manipulated by one malicious actor. Do not immediately fall back to a seed controlled by the same adversary; and do not equate lack of a proof with independently attributable slashable misconduct without censorability assumptions.
3. **Exit/withdraw policy:** A dynamic global roster cannot simply lock every monitor on every request (gas- and denial-of-service risk). Analyze a short-lived per-selected-candidate acceptance reservation, advance availability commitments with reasonable expiries, or a bounded snapshot epoch and safety-preserving lock management. Any policy must prevent one spam lease from locking every operator forever.
4. **Fairness evaluation beyond toy assumptions:** Include seed grinding/censorship, strategic consumer selection/aborts, correlated multi-address organizations, 10-draw cap, party exclusion, geographic/protocol anti-correlation, and the time and cost of each standby-replacement round.
5. **Measure real gas locally:** Use Foundry/Anvil on the project owner's machine: `forge test`, `forge snapshot`, EVM gas receipts. Those tools by themselves are local/free and do not require GitHub Actions. This environment did not have Foundry installed, so **no new Solidity contract execution was performed here**.
6. **No remote commits until Actions disabled.** Owner: repo Settings → Actions → General → Disable Actions → Save; optionally set a metered GitHub Actions budget with **Stop usage when budget limit is reached**. These are account-side protections the assistant cannot confirm or toggle using the connected GitHub tool.

## Project progress accounting

Previously recorded (stacked WP09E draft): **R3 38%, R4 38%, engineering 26%, research 26%, overall 26%**. This local WP09F artifact is an additional verified *experiment*, but **not merged into the repository or verified against EVM**, so the repository tracker percentages are **intentionally left unchanged** pending a controlled, no-CI local integration and review. WP09F local research experiment status: completed; WP09F production liveness hardening: still open.
