# SSE R1 WP-05 — asynchronous monitoring and clock/Byzantine source-traced mapping

**2026-11-09. STATUS: local research artifact authored and tested; source files not yet integrated on GitHub or hosted CI.**

## Reproducible artifact

Downloadable package: `SSE_R1_WP05_Async_Clock_Contract_Research_2026-11-09.zip`. It contains `tools/sse_async_contract_reference.py`, `tools/sse_wp05_demo.py`, `tests/test_sse_async_contract_reference.py`, and documentation + test logs. Extract into the local SSE repository root to add the files.

**Local Python 3.13 tests:** 45/45 new tests, and 120/120 combined reference tests (19 WP-02 + 26 WP-03 + 30 WP-04 + 45 WP-05). Source-check tests used a copy of the existing `SSESettlement.sol` source, not EVM execution. **Existing original project 106 Python cases / Foundry 35 tests have not been rerun with WP-05; expected total Python 226, not yet verified.**

## Contract-derived conditions and conditional counterexamples

Inspected existing `SSESettlement.sol` branches: `admitEpoch`, `submitAcknowledgment`, `submitProviderResponse`, `_recordAuthorizedVote`, `sealMonitoring`, `settleEpoch`, and `closeEpochEvidence`. Formal shadow demonstrates:
- Three authorized, honest *local timeout* votes at eligible chain timestamps can exclude a stipulated physically successful consumer-delivery history S: with V=25/r=5, contract-derived model credits consumer 20, retains 5.
- With a provider-authenticated ACK, same timeout quorum filters to F and credits consumer 25, given actual S.
- A provider-authenticated expected response hash and three eligible Success votes can filter to S even when consumer delivery has not occurred (actual F), crediting provider 25.
- Success may also be sealed for a response signature included **after responseDeadline but before monitoringClose**. If physical fulfillment first happened after the contracted deadline, the outcome can be unsound; *late inclusion alone does not establish late physical completion*.
- Local timestamp 110 with stipulated bounded clock error ±2 around physical deadline 110 => physical event time in [108,112], so timing is unknown.
- With four distinct selected monitors and at most one vote each, opposing quorums of three simultaneously are arithmetically impossible; quorum consistency is not physical-truth soundness.

These are **counterexamples against conditional source-traced state transitions**, NOT EVM-executed vulnerabilities, verified cryptographic attacks, or real cloud-delivery observations.

## Scientific provenance

- Dwork, Lynch, Stockmeyer (1988), partial synchrony: https://research.ibm.com/publications/consensus-in-the-presence-of-partial-synchrony
- Chandra, Toueg (1996), failure-detector completeness/accuracy: https://research.ibm.com/publications/unreliable-failure-detectors-for-reliable-distributed-systems
- IETF RFC 5905, NTPv4 clock uncertainty concepts: https://www.rfc-editor.org/rfc/rfc5905
- EIP-712 typed signing and domain separation: https://eips.ethereum.org/EIPS/eip-712
- Project source: `contracts/SSESettlement.sol`

Nothing above establishes a publishable novelty claim.

## Integration gates and next research work

1. Extract package to original repository checkout on this branch.
2. Run `python -m unittest discover -s tests -p test_sse_async_contract_reference.py -v`, full Python discovery, `python tools/sse_wp05_demo.py`, `forge build`, `forge test -vv`.
3. Commit source/test/docs and push, open draft PR; review Python Windows+Ubuntu and Solidity Ubuntu CI results.
4. **WP-06 R1/R2:** real Foundry bytecode transition/differential tests with EIP-712 fixtures for the four counterexample scenarios, plus documented physical clock/network assumptions. No production monetary rule changes until safe evidence policy is specified and reviewed.

## Provisional completion estimates

R0 100%, R1 **50% (+7pp)**, R2 20%, R3 15%, R4 10%, R5 10%, R6 5%, R7 15%, R8 10%, R9 5%, R10/R11 0%. P0 **35% (+3pp)**, P1 **46% (+6pp)**, P2 **20% (+5pp)**, P3 **30% (+5pp)**, P4 **12% (+2pp)**, P5/P6 0%.

Rounded equally weighted averages: engineering **20%**, research **20%**, overall **20%**. These percentages count local formal-model progress, **not deployed protocol acceptance**.
