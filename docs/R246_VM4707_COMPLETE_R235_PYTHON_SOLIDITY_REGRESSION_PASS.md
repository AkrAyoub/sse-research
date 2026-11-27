# R246 — REAL VM4707 full R235 source-only Python + Foundry regression PASS

**Captured from operator-supplied VM4707 terminal output, 2026-11-24 UTC.
Immutable source `6a25aa4aa86295cdac5d86596e95e18393e08b8f`.**
This is the owner test, not a GitHub CI run nor a remote live deployment.

## Verified exact source and toolchains

- Fresh isolated checkout retained at
  `/tmp/tmp.Ridv9nIavf/repo`, with Python 3.12 isolated virtualenv
  `/tmp/tmp.Ridv9nIavf/testvenv`; Foundry 1.9.0 pinned at
  `6056c5845d34205a83cf7108042adb137325c9df`.
- Exact `git rev-parse HEAD` printed
  `6a25aa4aa86295cdac5d86596e95e18393e08b8f`.
- R226–R229 targeted Python: **38/38 PASS**.
- R231–R239 targeted Python (including R237 path correction):
  **43/43 PASS**.
- R242 protected signer/broadcast policy unit tests:
  **6/6 PASS**; mocked; no actual EVM transaction submitted.
- R201 read-only policy: **5/5 PASS**.
- R206 deployment-attestation policy: **6/6 PASS**.
- Whole Python source suite: **1,268 tests run, OK, 3 skipped**.
  This means **1,265 passed, zero failed** and 3 skipped.
- `forge build --sizes`: **compiled 68 Solidity files using
  Solc 0.8.24**, successful with warnings.
  **New** runtime/constructor sizes:
  - `SSEAdaptiveMarketV2` **19,263B runtime**,
    **31,577B initcode**; under EIP-170 by **5,313B**
    and under EIP-3860 by **17,575B**.
  - `SSEAdaptiveVoteLedger` **10,668B runtime**,
    **11,400B initcode**; EIP-170 margin **13,908B**,
    initcode margin **37,752B**.
- `forge test --match-contract SSEAdaptiveMarketV2Test -vv`:
  **21/21 PASS, 0 fail**, including 5 new R236
  permissionless timeout, no-quorum fee conservation,
  bond unlock and late consumer revival tests.
- `forge test -q`: returned exit **0** (the script continued
  and emitted the terminal success marker). Do not invent a
  total count for the quiet full Forge run.
- **`R235_SOURCE_ONLY_GATES_COMPLETED=true`** observed.
- Warnings include expected compiler mutability/shadowing,
  Foundry lint including timestamp trust, ERC EVM calls
  and reentrancy patterns in **legacy V1** and some V2
  event ordering; passing tests alone do not discharge the
  security-review requirement.

## Explicit evidence boundaries

- Real source test PASS on a separate observer VM **does NOT**
  prove V2 deployed to the actual original chain31340.
- No `eth_sendRawTransaction`, private application signer,
  new BLS validator, live market escrow, actual provider
  CPU machine, independent monitor, remote SLA measurement,
  live role-reward payout or public no-overlay P2P admission
  has been verified by R235.
- R231–R239 role integration tests include **mocked RPC**
  and actual **local loopback HTTP socket** tests, not
  Internet-native independent provider or monitor evidence.
- Original VM4706 validator, original genesis, synchronized
  VM4707/VM4709 clients, historical finality and owner wallet
  remain unchanged by this source-only test.

## Next gates after the source freeze

1. Strict cross-check tool action signatures, event topics, fields,
   tuple/struct layouts and actual Solidity `forge`-compiled ABIs
   rather than comparing only test fixtures constructed from
   our own Python definitions. This MUST pass before any
   owner-authorized broadcast.
2. Live read-only original-chain EL/CL + owner-only app wallet
   custody and estimated actual TEST ETH funding requirements,
   with the exact current finalized hash/genesis.
3. Explicit owner permission before creation of new app wallets,
   transfer of test ETH, V2 deployment, or any actual service
   lease or monitor stake. V2 deploy only ONCE on original chain31340,
   then independently attest finalized deployment/runtime/wiring
   across VM4707 and VM4709.
4. Real independent provider workload and independent monitor
   probes, test-ETH-native accounting, full SLA/no-quorum/
   malicious behavior experiments and external-native P2P joins
   remain uncompleted.

Research branch `feature/r226-adaptive-v2-operator-runtime`,
draft PR #43 remains unmerged and experimental.
