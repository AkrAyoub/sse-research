# P0 WP-07 — Prior art, adaptations and limitations

**Research posture:** source-based and focused primary-paper comparison. NOT a systematic literature review or proof of scientific novelty.

| Source / mechanism | Established prior-art claim | What SSE can adapt | What SSE must not claim |
|---|---|---|---|
| Basin–Klaedtke–Zălinescu 2015, https://doi.org/10.4230/LIPIcs.FSTTCS.2015.590 | Sound runtime-monitoring verdicts with knowledge gaps, out-of-order observations | Explicit unknown/incomplete verdicts, avoid irreversible release before adequate evidence | Inventing three-valued knowledge or proving missing messages mean false |
| Chandra–Toueg 1996, https://www.cs.cornell.edu/info/people/sam/FDpapers.html | Failure detectors characterized by completeness and accuracy | State which failure-detector assumptions allow what guarantees | Claiming 3/4 failures imply physical failure under arbitrary delay |
| EIP-712, https://eips.ethereum.org/EIPS/eip-712 | Typed structured signing and domain separation; specification does not provide replay protection itself | Canonical signer/domain/chain/contract/lease/epoch/service binding for R4 | Claiming a signature proves the off-chain statement is true |
| Asokan–Shoup–Waidner 1998, https://research.ibm.com/publications/asynchronous-protocols-for-optimistic-fair-exchange | Optimistic fair exchange with exceptional trusted-party termination | Compare explicit dispute/risk allocation and residual liveness in R2 | Describing all evidence-based settlement as new; calling arbitrated outcome trustless |

**Our own proposal:** separate immutable service semantics, raw signed observations, explicitly qualified claims, admissible physical histories and generic financial bounds. This exact combination needs comprehensive closest-work novelty evaluation. The chain-publication profile is a scope-limited demonstration of how redefining the product can change provability; it must not be marketed as cloud resource attestation.

**Key negative result for our research:** no unconditional algorithm receiving identical observations for physically different contractual outcomes can choose a nonzero irreversible payout safe under both outcomes unless the contract itself allocates that ambiguity/risk. This is a simple indistinguishability argument (not a claim of original impossibility theorem).
