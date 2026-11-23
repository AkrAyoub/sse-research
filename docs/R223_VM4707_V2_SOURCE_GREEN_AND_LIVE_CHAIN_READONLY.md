# R223 — VM4707 adaptive V2 tests GREEN; real original-chain read-only evidence

**Evidence date:** 2026-11-23 (operator-pasted terminal transcript).
**Reviewed exact source:** `9a216518b3ea8c265f5186f6113987eb537d7949`, branch `feature/r136-independent-observer-preflight`.
**Location:** VM4707, separate `/tmp/tmp.K0G8uJowW1/repo` checkout.
**This is source and read-only local-chain evidence, NOT V2 on-chain deployment.**

## Actual observed local compilation and tests

The operator's command ran in `set -euo pipefail` and printed
`R222_SOURCE_AND_READONLY_GATES_COMPLETED=true`; therefore all commands
in that gated sequence returned exit code zero.

- `forge build --sizes`: PASS, 68 Solidity sources, solc 0.8.24.
  Fixed original stack-too-deep compilation failure; compiler emitted
  warnings and lint findings, **not an audit/security clearance**.
- `SSEAdaptiveMarketV2`: 18,087 runtime bytes, 30,387 initcode bytes;
  EIP-170 runtime margin 6,489 bytes, EIP-3860 initcode margin 18,765 bytes.
- `SSEAdaptiveVoteLedger`: 10,668 runtime bytes, 11,400 initcode bytes;
  EIP-170 runtime margin 13,908 bytes.
- `forge test --match-contract SSEAdaptiveMarketV2Test -vv`: **16 PASS,
  0 FAIL, 0 SKIP**. All new adaptive V2 cases passed, including bilateral
  EIP-712 residual signing and the genuinely signed late-response rejection.
- `forge test -q`: exit **0**, no case count printed; **do not invent a
  full-suite test count**.
- R201 mock-only Python policy suite: **5/5 PASS**.
- R206 mock-only Python runtime-audit policy suite: **6/6 PASS**.
- This is not a real provider Docker workload, monitor measurement,
  live settlement receipt, public external admission or validator activation.

## Real original chain31340 live read-only evidence (VM4707 only)

`python3 -B tools/sse_pos_r201_v2_readonly_live_chain_gate.py --rpc http://127.0.0.1:28545` returned:

- Exact chain ID: `31340`.
- Execution genesis hash verified:
  `0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf`.
- Latest execution block: `17751`.
- Finalized execution block: `17621`, hash
  `0xeaabcce7d5b8c20b532f311cd2a8ff0c9c28388c3ce9512a209ce5b4aebe0904`.
- Block gas limit: `30000000`; observed base fee: `7 wei/gas`.
- Original public-only genesis funded address:
  `0x13fb73aace8A11Be2899D047635A757a224Ce00B`.
- Balance at finalized: `1000005544827172000000000 wei`
  (= 1,000,005.544827172 native TEST ETH); nonce at finalized: `0`.
- This tool does **not** read a Beacon genesis root; its expected
  `beaconGenesisValidatorsRootExpectedNotReadHere` field is **not a CL
  verification result**. Previously proven R192 cross-VM finality is a
  separate, older measurement.
- The R201 schema's `marketV2Deployed:false` and
  `contractRuntimeVerified:false` describe the tool's *lack of deployment
  verification*, **NOT an exhaustive absence proof** (no code scan).
- `accountPrivateKeyAccessVerified:false`,
  `newAppDeployerKeystoreCreated:false`,
  `transactionSignedOrSubmittedByThisTool:false`,
  `physicalSlaVerified:false`.

## Security, correctness and deployment boundary

1. **No broadcast authorized.** Do not deploy, import original validator
   signing keys/Engine JWT, fund a new signer or touch original genesis
   or existing VM4706/4707/4709 clients based on tests alone.
2. Read-only audit still required on the actual node for current CL
   sync/finality/peers and EL peer health; R201 checks EL finalized state
   only. Repeat on VM4709 before and after any later deployment.
3. Source review of V2 economics: bonded EOA identities are not independent
   physical monitors, proposer-biasable future-blockhash is not VRF, rotating
   64-address candidate windows are not globally unbiased; evidence hashes
   are not actual remote CPU/latency/SLA proof. Inconclusive outcomes can
   lock service escrow until bilateral signed allocation.
4. Compiler warnings include EVM time conditions, uninitialized-local lint
   and reentrancy-events warnings. Individual warnings are not confirmed
   exploits; inspect V2 paths and conservative settlement invariants
   before approving the owner-signed experiment.
5. Before any live deployment obtain explicit owner approval, independently
   owned encrypted **application-only** test EOA (not BLS signer), limited
   real native test-ETH funding, immutable source/bytecode commitment and
   original-chain preflight. Verify actual finalized deployment tx/contract
   runtime hashes and cross-binding using R206 on two independent nodes.
6. V2 deployment is a **research experiment**, not proof of completed
   public permissionless network or end-to-end provider/consumer/monitor
   SLA. No code was deployed by any R222/R223 test command.

**Next operational gate:** read-only two-layer network/finality health
and local public-address-only signing-custody inventory. No private
keys or wallet JSON in logs. Prepare an explicit separate application
EOA funding/deployment proposal before requesting transaction consent.
