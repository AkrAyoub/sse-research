# R251 — Actual chain31340 VM4707 live read-only preflight passed; deployment handoff

**Owner-supplied live VM4707 output, 2026-11-24, using the immutable
source-only-verified Git SHA
`6930c069b4e9738e63e2ce9d53b10d126053335e`.**

## Observed live RPC facts (NOT simulated)

- Actual chain ID: **31340**
- Pinned actual execution genesis:
  `0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf`
  with `executionGenesisVerified: true`.
- Finalized execution height **24692** and canonical block hash:
  `0xd00e0982d035f2c64fa7edcc7a01cfb4e9abf8ec1dce0c8b7667a16a4ccd0b44`.
- Observed latest execution height **24840**.
- Live block gas limit **30,000,000**.
- Latest observed base fee **7 wei per gas**, **not** a verified
  all-in transaction gas price; an owner-authorized tx requires a
  fresh gas quote.
- Known genesis-funded public EOA
  `0x13fb73aace8A11Be2899D047635A757a224Ce00B`
  had at finalized height:
  `1000007929024090000000000` wei =
  **1,000,007.92902409 worthless native TEST ETH**.
  Its finalized nonce was **0**.
- `accountPrivateKeyAccessVerified: false` —
  no signer has been unlocked or custody proven.
- `newAppDeployerKeystoreCreated: false` —
  independent application wallet remains uncreated.
- `marketV2Deployed: false`, `contractRuntimeVerified: false`,
  and `physicalSlaVerified: false` are literal R201
  source-reported NON-VERIFIED state flags, not independent scans
  showing non-existence of every possible deployment.
- `transactionSignedOrSubmittedByThisTool: false`.
- The R201 tool does not query Beacon state, so it reports the
  pinned Beacon genesis root as expected, **not independently read**.

## Source integrity / deploy program

At exact SHA `6930c069b4e9738e63e2ce9d53b10d126053335e`,
R249/R235 full source gates PASSED (1,275/1,278 Python PASS,
3 SKIP, R247 real compiled 21 actions and 28 protocol events,
21/21 V2 Foundry + whole Forge suite).
`script/DeploySSEAdaptive31340.s.sol` is the V2 source deployment
path: constructor `new SSEAdaptiveMarketV2(minimumBondWei)`
creates one immutable `SSEAdaptiveVoteLedger`, and verifies
bidirectional binding. Required env `SSE_V2_MIN_MONITOR_BOND_WEI`
must be positive and protocol-economically justified from actual
role funding. **It calls `vm.startBroadcast()`, so do NOT run
with private key, keystore, `--broadcast` or wallet commands
without separate explicit owner authorization.**
Do not use legacy 31339/V1 deployment scripts.

## Operator handoff — minimizing unused regression cycles

**No further R235 unit/Forge loops for unchanged SHA.**

1. Owner may run **non-mutating wallet plan** from an exact
   pinned GitHub checkout on VM4706:
   `python3 -B tools/sse_pos_test_wallet.py --role adaptive-v2-deployer --output-dir /some/owner-private-path`.
   Omitting `--apply` is strictly a plan, creates no key;
   the output directory is not accessed in plan mode.
2. Only after explicit owner authorization, owner can create
   new **separate application-only encrypted UTC-V3 EOA** on
   their own VM4706, under existing private owner-controlled
   `0700` directory using
   `tools/sse_pos_test_wallet.py --apply` with two
   private password prompts; never print/commit keystore or
   passphrase, never use original Genesis/BLS/withdrawal keys
   as new application account.
3. Establish the actual authorized and accessible native TEST ETH
   funding source **without assuming** the Genesis public
   address has its owner signing key available (R201 explicitly
   says custody unverified). Do not sign from the Genesis
   account unless separately approved and controlled. A
   public faucet contract is NOT claimed live funded.
4. Record the intended test-only minimum monitor bond in wei
   and a bounded max deployment budget, then do actual read-only
   deployment sender balance/gas estimation using freshly
   observed chain base/gas price. Source runtime sizes alone do
   not guarantee deploy gas affordability.
5. After a distinct positive authorization for actual transfer
   and V2 creation, deploy only once via the
   `DeploySSEAdaptive31340.s.sol` path, recording actual
   tx hash, gas, canonical and finalized receipt, market and
   ledger addresses and actual SHA256 runtime digests.
   R206 public deployment manifest is:
   `{schema,chainId,executionGenesisHash,deployer,deploymentTxHash,minimumBondWei,market:{address,runtimeSha256},ledger:{address,runtimeSha256}}`.
   Values must originate from real finalized RPC receipt/code,
   not guessed addresses.
6. Verify R206 against original finalized VM4706 or VM4707
   RPC; repeat independently across compatible observer.
   Then run actual native TEST ETH role/stake/escrow/compute/
   monitor/settlement experiments and external validator/native
   peer admission before calling the project complete.

## Current project claim boundaries

Original chain31340 is real and read-only reachable;
V2 source is thoroughly tested. V2 is **NOT verified deployed**,
no marketplace escrow or monitor fee transfer proven,
no physical independent service SLA proven, and independent
external-node/validator public-network admission remains open.

Current GitHub PR #43 remains draft; documentation-only R251
does NOT invalidate the exact earlier R249 source gate PASS.
