# WP-09L — Consumer-prepaid VRF requests and bounded subscription exposure

**Research-only; 2026-11-14. Local files only. No GitHub writes, Actions, cloud CI, deployments or RPC calls.** This increment builds on **WP-09K**, which itself is an uncompiled offline patch on top of the **WP-09E draft branch**. WP-09G/H/I remain separate offline research components, not collectively verified EVM code.

## Core problem and engineering choice

In the WP-09K interim VRF integration, only the deployment bootstrapper could dispatch coordinator requests. This blocked straightforward permissionless depletion of the *sponsor's* Chainlink VRF subscription but also gave the bootstrapper discretionary control of when monitoring elections occur. Fee incentives and timing were not linked to a specific consumer's request.

**WP-09L enables third-party triggering only after the lease consumer prepays a *fixed native-ETH service fee* and the provider has accepted the lease.** The fee is recorded separately from service-epoch escrow and is earned by the sponsor only when the adapter's coordinator-request transaction succeeds. A one-time immutable fee schedule and **lifetime request-count cap** bound the number of new sponsored purchases. The design preserves one request per frozen assignment and bans seed rerolls. No caller earns money for triggering the request; there is no per-callback incentive or ability to redirect sponsor credits.

Crucially, **this is not a provable upper bound in ETH on actual Chainlink charges**. The coordinator might bill a LINK-denominated subscription at variable network cost, or native tokens depending on configuration; the protocol does NOT know those charges. The bootstrapper intentionally assumes fee-conversion, gas surge, liquidity, misconfiguration, and insufficient-subscription risks. A flat ETH fee and an upper bound on purchase *count* cannot prove zero sponsor loss, full market pricing, or anti-Sybil identities. A real sponsored service requires authenticated price/credit policy, monitored charge estimates and auditable reconciliation. The only strict financial property of this design is settlement's **native-ETH fee conservation** under the specified acceptance/close/purchase paths.

## Contracts and invariants

`SSESettlement.sol` (patched through `apply_wp09l.py`):

- **One-way policy** `configureVrfFeePolicy(feeWei, maxLifetimeRequests)`: bootstrapper-only, before any lease or VRF adapter binding; both values strictly positive. This fixes fee/cap terms for that deployment and prevents repricing pending consumer deposits. `bindRandomnessAdapter` now requires the configuration. Non-adapter legacy deployments are unaffected.
- **Consumer-funded reserve** `fundVrfRequestFee(leaseId) payable`: only the lease consumer, provider already accepted, exact native-ETH price, no prior fee reserve or purchase, still-open matching assignment, global cap not exhausted. Repeated/cross-account funding fails. Service escrow balance and epoch fee remain unchanged.
- **Permissionless request** `requestLeaseRandomness(leaseId)`: succeeds only with a one-time funded reserve, nonclosed/accepted lease, unchanged original snapshot, remaining global quota and coordinator request readiness; *any address* may trigger. Before external coordinator invocation, mark the fee as spent, clear reservation, increment `vrfRequestsUsed`, credit `withdrawable[bootstrapper]`, and enter `vrfPurchaseEntered` reentrancy lock. If coordinator rejects, **the EVM reverts all state and sponsor credit atomically**; the consumer may later trigger again within the same original deadline (not a seed reroll, because no order succeeded).
- **On closure**: if a fee is **still reserved but never spent**, add it to `withdrawable[consumer]` before the original escrow refund/committee cancellation. If a request succeeded, the sponsor keeps the fee even if the proof arrives late, is withheld, or the lease closes. This prevents a payer from deliberately imposing subscription costs and requesting a fee refund. The consumer receives any uncommitted service escrow per the preexisting close path.
- **Hard lifetime quota**: once `vrfRequestsUsed == vrfLifetimeRequestCap`, new coordinator purchases revert. Previously funded but unspent fees can be refunded on ordinary lease closure. There is no automatic quota reset, fee update, retry after an accepted coordinator request, or administrative reseeding.
- **Reentrancy**: the settlement-level guard blocks nested purchases across **other funded leases** as well as the adapter's per-assignment reentrancy guard. There is no native-ETH transfer on request; sponsor and consumer compensation uses the existing pull-payment `withdrawable` ledger.

The WP-09K pool cancellation and closed-lease adapter checks are retained. The adapter continues to use a coordinator-only, original-request-ID-bound callback, with no contract-side cryptographic VRF verification. The bundled mock verifies **NO** real randomness proof.

## Model ledger accounting

For the simplified research model before any epoch admission, at every step:

```
total ETH deposited
  = escrow still held for open leases
  + prepaid-but-unspent VRF fees
  + sponsor/consumer withdrawal credits
  + ETH already withdrawn
```

The model checks this invariant after each of 36,000 deterministic adversarial action steps (500 sequences × 72 steps), including fee underpayment/overpayment, caller impersonation, repeat orders, forced coordinator failure, nested order attempts, quota exhaustion, closure and withdrawals. This does **NOT** prove the real Solidity escrow accounting across all epochs or the external LINK/native VRF subscription's solvency.

## Tests and reproducibility

Actually executed locally:

- `python -m unittest discover -s WP09L_offline/tests -v`: **24/24 tests passed**: source-patch anchors, one-time policy, prepayment, refund, atomic failure, quota, cross-lease reentrancy and conservation state machine.
- `python -m unittest discover -s WP09L_offline/policy_reference/tests -v`: **19/19 WP09K regression tests passed** (legacy standalone reference behavior; these do not test WP09L Solidity).
- `(cd WP09L_offline/policy_reference/WP09I_offline && python -m unittest -v test_wp09i.py)`: **25/25 WP09I model tests passed** (these do not test live VRF).
- Total: **68/68 local Python/reference tests**; 36,000 modeled actions are inside one test and are *not* blockchain transactions.

Authored but **NOT compiled or executed**: `foundry_test/VRFFeePolicy.t.sol` (two suites for basic fee funding, lifetime cap, refund/close, cross-lease mock reentrancy, coordinator revert, and WP09E global-Merkle staged-seed closure). Local Foundry/Solidity 0.8.24 dependencies are missing from this environment; `logs/local_evm_probe.log` verifies the offline runner refuses to download compilers or start services.

`apply_wp09l.py` is a **read-only, exact-anchor WP09E → WP09K → WP09L generator**. Its output goes to a separate directory and contains the modified `OpenMonitorCommittee.sol`, `SSESettlement.sol`, copied `SSEVRFV25Adapter.sol`/`MockVRFV25Coordinator.sol`, the new Foundry test file, and a unified diff. `verify_wp09l_locally.sh` copies a preinstalled WP09E checkout and its existing Foundry libs into a disposable directory, applies the patch and runs `forge build/test --offline`. It does **not** download/install or execute GitHub workflows. Inspect all generated Solidity before deployment.

## Remaining issues (not solved)

1. **Real coordinator/VRF proof assurance**: use an authentic reviewed consumer and a coordinator that actually validates VRF. The mock's arbitrary output is not a VRF proof.
2. **Payment reconciliation**: ETH fee differs from subscription cost asset, pricing and max charge. Verify actual sponsor exposures, cap exhaustion effects, and external subscription failure; do not claim economically risk-free permissionless VRF.
3. **Selection fairness**: a sponsor with control over quota/funding setup, and a coordinator with callback discretion, can withhold or delay requests/results. Snapshot manipulation, post-request exits, Sybils and observer availability persist.
4. **WP09G recovery**: at most 10 global candidates remain in the current EVM-tested **WP09E source**; the separate 40-candidate batched WP09G patch is still not integrated/compiled with WP09L.
5. **Onchain compile/gas/EVM**: the code has not been compiled or executed here. Do not merge or deploy until fully run locally, reviewed and tested under concurrency/adversarial coordinator conditions.
6. **Original SSE evidence**: Merkle membership, randomized selection, and funded VRF orders do not prove physical SLA fulfillment, operator independence, consensus finality, or correctness of provider payouts.

## Progress / CI policy

R3 **38%**, R4 **38%**, P4 **20%**, engineering **26%**, research **26%**, overall **26%**, unchanged. WP09L's model tests are not a sign-off on uncompiled Solidity. No GitHub Actions, PR creation, pushes or deployments have been performed.
