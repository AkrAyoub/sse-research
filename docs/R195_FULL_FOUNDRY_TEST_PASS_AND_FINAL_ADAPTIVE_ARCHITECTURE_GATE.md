# R195 — Full Solidity suite passed on real VM4707; deployment architecture gate

Real user VM4707 command reported on 2026-11-23:
- `NO_FOUNDRY_KEYSTORE_DIRECTORY` at `~/.foundry/keystores` (does NOT prove no wallets or no test ETH anywhere).
- actual `cast chain-id` original localhost RPC **31340**.
- actual `cast block finalized --field number` **16790**.
- `forge test -q` returned exit 0 under `set -e` and control advanced to next command. **Full local Foundry test command completed successfully.** Exact case count not observed from -q; do not invent a count.
- source `script/DeploySSE31340.s.sol` exists and has enforced 31340 chain constant.
- `R194_FULL_TEST_PREFLIGHT_COMPLETED=true`.
- no live deployments, token transfers or signed transactions executed.

## Critical architecture reconciliation before live transactions

This project already identifies V1 limitations in
`docs/R140_CHAIN31340_MARKETPLACE_DEPLOYMENT_GATE.md`:
`SSESettlement` has fixed `COMMITTEE_SIZE=4`, `QUORUM=3`,
and `OpenMonitorCommittee` fixed four-seat election. The later
`SSEAdaptiveVoteLedger` contract has actual dynamic-size
committee, precommit quorum and genuine report funding, but
its own source states that it is NOT YET integrated with V1
`SSESettlement` or an audited independent election/selection
mechanism; its constructor restricts calls to one designated
future settlement.

The new `script/DeploySSE31340.s.sol` was correctly adapted
to the ORIGINAL network chainId31340, but it still deploys
these old fixed-quorum SSE V1 contracts. It is ONLY a
**legacy compatibility demo script**. It does NOT satisfy
the final dynamic-fault-tolerant SSE requirements. Do not
broadcast it as the final research application simply
because 12 targeted tests and full local suite passed.
Prior R193 wording implying it was ready for final
deployment must be read with this explicit restriction.
No live chain31340 contracts have been deployed.

The codebase also has `OpenTestEthFaucet.sol`, documented in
`docs/PUBLIC_TEST_ETH_FUNDING.md` as an un-deployed,
un-funded candidate on actual chain31340. Its public
sponsorship model CANNOT generate funds ex nihilo; no known
public faucet reserves or independent gas sponsors have
been empirically verified. A genuine chain31340 test-only
deployer must be funded by a real valueless test-ETH transfer,
and the source of native balances must be checked on-chain.

## What must be implemented before claiming final marketplace

1. Build and test a FINAL versioned SSE settlement/marketplace
   that actually invokes the existing adaptive per-lease
   ledger, rather than leaving it standalone. Freeze justified
   `k`, `q`, objective eligibility/root+selection proof,
   funded monitor report reserves and conservative
   inconclusive outcomes per lease. Verify real independent
   physical monitor assumptions rather than count wallet IDs.
2. Preserve consumer resource requests, bids, service
   endpoint/resource policy commitments, EIP-712 provider
   signature checks, actual monitor evidence and escrow
   conservation from the submitted contracts. Fix or
   explicitly constrain security-relevant lint findings.
3. Run full Foundry adversarial/gas tests; label them
   simulated local EVM execution, never real external compute.
4. Identify authorized non-validator TEST ETH deployer
   through private local keystore/address and independent
   funding. Do not print secrets. Preserve original
   genesis and validators; no new genesis.
5. Only deploy exact reviewed V2 contracts when actually
   compiled and run against live chain31340; verify receipts,
   code, mutual bindings and finalization from both VMs,
   followed by real provider/consumer/monitor SLA flow.

## Current truthful completion

PASS: original live two-VM PoS network synchronized and
common finalized epoch571 root; one VM4707 real Foundry
full local test suite returned success.
NOT COMPLETE: final adaptive SSE settlement integration,
test-only deployer/funding, live contracts, real leases,
physical service SLA, independent Internet admission and
permissionless PoS validator economics.

Do not expand the legacy static deployment script again
or imply the network's healthy EL/CL validates the final
application protocol.
