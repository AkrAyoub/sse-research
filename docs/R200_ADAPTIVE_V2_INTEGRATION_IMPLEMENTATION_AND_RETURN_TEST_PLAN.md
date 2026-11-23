# R196–R200 — Adaptive marketplace integration implemented in GitHub; NOT YET LIVE TESTED

**Observed live network evidence before source changes (2026-11-23):**
VM4707 original local Besu RPC chain31340, original on-chain EOA
`0x13fb73aace8A11Be2899D047635A757a224Ce00B`
had **1,000,005.319709155 test ETH**, transaction count nonce **0**,
finalized execution block **16822**. Public immutable genesis allocation
for the same EOA is 1,000,000 test ETH. The extra 5.319709155 may be
fee-recipient credits or incoming transfers; provenance NOT attributed.
The wallet's encrypted custody was previously verified LOCALLY on VM4706,
not available as a keystore on VM4707 and must NEVER be pasted or
automatically transferred to VM4707. No fresh EOA, funding or signed
transaction yet. Genesis and both EL/CL clients unchanged.

## New source implemented in this branch

- `contracts/SSEAdaptiveMarketV2.sol`: real chain-compatible Solidity
  marketplace request/bid/escrow, bounded and explicit permissionless
  bonded monitor registry, frozen per-lease eligibility commitment and
  post-commit future-block selection, variable funded committee and
  `k`/`q` chosen by existing AdaptiveMonitorQuorum math, actual
  `SSEAdaptiveVoteLedger` bound immutably to the new settlement,
  confirmed monitor assignments, real EIP-712 signed provider responses,
  separate report reward escrow, evidence hashes, quorum-based
  success/failure payouts, zero imaginary payouts for inconclusive
  outcomes and joint EIP712 residual allocation, withdrawal guards,
  escrow refunds on expired random draws, missing committee confirmations,
  and non-accepting provider. Global monitor enrollment is not capped:
  rotating gas-bounded selection window up to 64 participants per
  lease; this is NOT a statistically uniform global election.
- `foundry/test/SSEAdaptiveMarketV2.t.sol`: Foundry simulation tests
  for variable seats/threshold, actual escrow bookkeeping, false/no
  success payment absent quorum, signed response, expired entropy
  seed cannot be rerolled, denied provider and monitor expiry
  refunds, and >64 active monitor registration. TEST SOURCE ONLY,
  not physical SLAs.
- `script/DeploySSEAdaptive31340.s.sol`: separate chain ID 31340-only
  V2 market+ledger creation with required explicit bond policy.
  **NOT BROADCAST**, no code/address/receipts verified on chain.
  Existing V1 deployment script is obsolete for the adaptive target
  and should NOT be broadcast as final design.

## Important limitations and security model

1. Enrollment is address+collateral based, WITHOUT true physical
   Sybil resistance or proof of independent operator/control/domain.
   Multiple EOAs can all be one machine. If that independence is
   required, design/measure independently auditable resource
   credentials and avoid claiming Byzantine fault bound from
   address count.
2. Draw from future Ethereum `blockhash` is **proposer-biasable**,
   not VRF. The frozen roster and delayed entropy limit naive
   user chosen committee but cannot meet unbiased-sortition claims.
   A real verifiable unbiased randomness source still remains a
   scientific production requirement.
3. Bounded rotating MAX_ELIGIBLE=64 scan per lease is for EVM gas
   boundedness, NOT a global lifetime/active registration cap.
   It is not uniform global sampling. Adversarial churn/front-run
   and fair independent global election need further study.
4. Provider-signed EIP-712 hashes authenticate an EOA and response,
   not whether arbitrary compute actually ran. Monitor votes commit
   evidence digest, but no external physical SLA is established by
   a hash or vote alone. Off-chain real Docker compute, signed
   receipts, independent measured resources, and credible SLA
   verification are still required.
5. R196–R199 source has **not been compiled, Foundry tested,
   statically analyzed nor audited on the operator's VMs**.
   DO NOT broadcast deploy script before tests pass and critical
   security review. Source integration is progress, not completed
   end-to-end delivery.
6. Escrow associated with unresolved inconclusive outcome deliberately
   remains held until both parties sign allocation; this is a
   liveness/loss-of-funds tradeoff. It must be disclosed, not hidden
   or replaced by invented success/failure.
7. Existing V1 code is untouched and current original chain
   31340 unaffected. No permissioned enrollment authority added.
8. This V2 model is one bounded, research architecture candidate,
   not yet an end-to-end final system.

## WHEN RETURNING: first test the exact pinned branch

VM4707 already has Foundry v1.9.0 and actual source checkout in
`/tmp/tmp.khSXftvQs8/repo` (OLD SHA).
Obtain a NEW immutable reviewed branch SHA and fresh separate
`git clone --no-checkout` from GitHub, then `git switch --detach SHA`
and assert SHA exactly. No code edit on VMs. Export
`PATH="$HOME/.local/share/sse-r19-toolchains/foundry-v1.9.0:$PATH"`.

1. `forge build --sizes`: reject compile errors, EIP170 runtime
   size excess, and constructor EIP3860 initcode overflow.
2. `forge test --match-contract SSEAdaptiveMarketV2Test -vv`:
   inspect every test; no mock test counts as actual chain
   activation. Correct via GitHub if issues.
3. `forge test -q`: full source regression.
4. `forge script script/DeploySSEAdaptive31340.s.sol:DeploySSEAdaptive31340 --rpc-url http://127.0.0.1:28545`
   only after setting required `SSE_V2_MIN_MONITOR_BOND_WEI`,
   **without --broadcast**; needs an authorized test-only keystore
   for any true broadcast, not currently staged on VM4707.
5. Read-only chain31340 checks original genesis hash, CL finality
   and public EOA balances, deployment existence and verified code.
6. Do not execute any `--broadcast`, `cast send`,
   EOA wallet creation or transfer without owner consent
   and a complete live-deployment check. Do not use VM4706
   original BLS validator key, VM4707 Engine JWT, or recovery
   mnemonic as signing material.

## Remaining project

- Source compile/test failures or security vulnerabilities;
- Adaptive unbiased publicly verifiable committee sortition and
  independently evidenced monitor eligibility;
- User-controlled signed test-only EOA, test-ETH funding and real
  deployed runtime hashes/receipts verified from both hosts;
- Real public resource discovery, provider jobs, independent
  monitors, time/evidence protocols and genuine SLA payments;
- Internet-wide dynamic IP admission outside current overlay,
  independent operator/validator launch + real validator economics;
- Measured gas/perf/resource SLA and documented outcomes.

This artifact intentionally distinguishes actual verified PoS
network from unverified V2 source, and forbids fake
`FINAL_IMPLEMENTATION_COMPLETE` signals.
