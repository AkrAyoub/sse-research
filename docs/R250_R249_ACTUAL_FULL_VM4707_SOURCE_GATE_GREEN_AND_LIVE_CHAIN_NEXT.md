# R250 — Verified R249 exact-source full pass; next gate is real live chain preflight

## Actual operator evidence (2026-11-24)

**Fully tested immutable Git SHA:**
`6930c069b4e9738e63e2ce9d53b10d126053335e`.

- `R249_ALL_SOURCE_GATES_COMPLETED=true`
- `R235_SOURCE_ONLY_GATES_COMPLETED=true`
- `R247_COMPILED_V2_ABI_PARITY_COMPLETED=true`
- Whole Python suite: **1,278 executed, 3 skipped, 1,275 passed, 0 failed**.
- R247 parity unit suite: **10/10 passed**.
- Actual Foundry-generated compiled ABI parity: **PASS** for
  **21** operator actions (market 17, ledger 4),
  **28** SSE protocol event schemas (market 16, ledger 12), and the
  decoded public state/return tuple ABI layouts; only the exact
  zero-argument inherited EIP712DomainChanged event is tolerated.
- Compiler-emitted ABI SHA-256:
  - Market: `e7ad167851a912a52d30ef1a08f6fdeedad24fa06c9fb99b8bc2ef2385faadb0`
  - Ledger: `f94b65c8dfda90c52b4aede0c96e16110b663868bd8dce4a79039523f6c64d8e`
- Compiled `SSEAdaptiveMarketV2`: **19,263B** runtime, **31,577B** initcode;
  EIP170 margin **5,313B**, EIP3860 margin **17,575B**.
- Compiled `SSEAdaptiveVoteLedger`: **10,668B** runtime, **11,400B**
  initcode; EIP170 margin **13,908B**, EIP3860 margin **37,752B**.
- Adaptive V2 Foundry suite: **21/21 passed** incl. R236 idle-lease
  bond unlock, reserve conservation, no-quorum and expiry behavior.
- Whole Foundry `forge test -q` successfully returned (the source
  script printed both final success markers under `set -euo pipefail`).
- Foundry emitted nonfatal lint warnings. They are not proof that the
  affected code is safe; any materially relevant V2 issue warrants review.

**These are verified source-only regressions**, not chain-native
resource marketplace tests. No application EOA created or funded,
no V2 contracts deployed, no user-signed tx broadcast and no
remote independent physical SLA demonstrated.

## Stop repeating the regression gate without a source change

The current source is pinned and passed. Instead of more offline
test cycles, obtain the current real VM4707 **read-only R201**
chain status from `http://127.0.0.1:28545`:

```bash
cd /tmp/tmp.Ridv9nIavf/repo
test "$(git rev-parse HEAD)" = "6930c069b4e9738e63e2ce9d53b10d126053335e"
export PATH="/tmp/tmp.Ridv9nIavf/testvenv/bin:$HOME/.local/share/sse-r19-toolchains/foundry-v1.9.0:$PATH"
python3 -B tools/sse_pos_r201_v2_readonly_live_chain_gate.py --rpc http://127.0.0.1:28545
```

This prints current verified chain ID, genesis hash, finalized
execution height/hash, current block gas limit, base fee, and the
original genesis-funded public TEST ETH account balance/nonce.
It has **NO private key, signing, wallet, Docker, or mutating RPC**.
It does NOT verify a contract deployment, finality from independent
consensus clients, a wallet custodian, or real SLA.

## Actual live deployment is the NEXT separate gate

1. Confirm live original chain ID 31340/genesis/finalized
   execution head + available gas via R201, without touching keys.
2. Confirm the owner approved the role-wallet and funding plan.
   The **original genesis EOA MUST NOT be used as the marketplace
   app EOA**. Separate owner-controlled encrypted app keys must be
   generated only after explicit authorization, kept local and
   offline-backed up. A test ETH funding path to app EOAs requires
   separate explicit consent and public tx receipt verification.
3. Deployment Foundry script `script/DeploySSEAdaptive31340.s.sol`
   accepts positive bond and creates ONE market and its immutable
   vote ledger on the actual chain. **Do not run with broadcast or
   any key until a separate owner-approved, bounded-scope runbook
   is reviewed**. Pin exact bytecode and receipts.
4. Use R206 to verify receipt, finalized runtime code SHA-256,
   V2 mutual wiring and bond at original-chain finalized block
   from VM4707, then separately from VM4709 if compatible.
5. Run real on-chain registrations, requester bid, funding,
   committee election, provider execution, independent monitor
   signed votes, finalization and payout, preserving public tx hashes
   and private physical evidence. Mark no-quorum as inconclusive.
6. Independent BLS signing validator, true external Internet
   nodes (not overlay-dependent) and real independent physical
   provider/monitor are still research deliverables. Single-node
   validator authority and blockhash selection bias are fundamental
   security limitations; no source unit test resolves them.

## Evidence boundaries and branch

This pass applies only to tested SHA
`6930c069b4e9738e63e2ce9d53b10d126053335e`.
The active feature branch and PR #43 remain **draft / unmerged**;
this R250 document is metadata after the verified SHA, not an
additional code-test claim. The original VM4706 signing validator
and observers stay untouched.
