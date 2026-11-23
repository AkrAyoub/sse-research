# R210 — Return-time exact-source V2 verification runbook

**STOP BEFORE LIVE TRANSACTIONS.** This branch now has SOURCE-ONLY R196–R209
adaptive SSE V2 implementation. **No VM has compiled it yet**, no GitHub Actions
test run is asserted, and no runtime addresses, wallets or receipts exist.
The ONLY real chain acceptance is earlier R192 matching finalized epoch571
on VM4707 and VM4709. The previously compiled legacy contracts and
full local source tests are proven on VM4707, but not these changes.

## Source files to review/test

- `contracts/SSEAdaptiveMarketV2.sol`: bonded monitor participation,
  resource requests, bids, strictly escrowed test ETH, bounded rotating
  candidate snapshot, locked pre-entropy candidate bonds, future entropy
  draw into true V2 adaptive ledger, per-lease k/q, EIP-712 verified
  provider responses, actual monitor vote credits, conservative no-quorum
  freeze and bilateral allocation, preserved refunds and pull payment.
- `contracts/SSEAdaptiveVoteLedger.sol`: existing R22 EIP-712 genuine
  per-lease flexible committees and funded monitoring.
- `contracts/AdaptiveMonitorQuorum.sol`: existing objective budget/
  seat/quorum calculation, given explicitly modeled independence f.
- `foundry/test/SSEAdaptiveMarketV2.t.sol`: added new adversarial
  Foundry simulated EVM tests, NOT real SLA proof.
- `script/DeploySSEAdaptive31340.s.sol`: intended ONLY after
  reviewed source tests, independent test-only signer and owner consent.
- `tools/sse_pos_r201_v2_readonly_live_chain_gate.py`: independently
  check exact pinned original chain31340, native finalized execution
  state, original 0x13fb.. owner-public address balance/nonce.
- `tools/sse_pos_r206_adaptive_v2_deployment_audit.py`:
  only AFTER a real approved broadcast has a public signed-tx receipt,
  independently pinned actual market+ledger runtime code SHA256,
  and bidirectional immutable market.votes/ledger.settlement.
- `tests/test_sse_pos_r201_v2_readonly_live_chain_gate.py`,
  `tests/test_sse_pos_r206_adaptive_v2_deployment_audit.py`:
  pure mocked policy tests.

## On VM4707: safe first action after returning

Use a fresh, exact pinned GitHub checkout in a new temp directory,
never overwrite the running `~/sse-research` or either VM's Docker.
Replace `FULL_SHA` below with the **latest exact 40-character commit
given in ChatGPT's terminal answer**, not with the old
a2481958 checkout. Verify it is the expected SHA.

```bash
(
  set -euo pipefail
  SHA="FULL_SHA"
  DIR="$(mktemp -d)"
  git clone -q --no-checkout https://github.com/AkrAyoub/sse-research.git "$DIR/repo"
  cd "$DIR/repo"
  git fetch -q --no-tags origin feature/r136-independent-observer-preflight
  git switch -q --detach "$SHA"
  test "$(git rev-parse HEAD)" = "$SHA"
  export PATH="$HOME/.local/share/sse-r19-toolchains/foundry-v1.9.0:$PATH"

  echo "== NEW V2 FOUNDRY BUILD AND EIP170 LIMITS =="
  forge build --sizes
  echo "== ADAPTIVE REAL-ESCROW SOURCE TESTS =="
  forge test --match-contract SSEAdaptiveMarketV2Test -vv
  echo "== WHOLE SOURCE REGRESSION =="
  forge test -q
  echo "== LOCAL READ-ONLY POLICY UNIT TESTS =="
  python3 -B -m unittest discover -s tests \
    -p 'test_sse_pos_r201_v2_readonly_live_chain_gate.py' -v
  python3 -B -m unittest discover -s tests \
    -p 'test_sse_pos_r206_adaptive_v2_deployment_audit.py' -v
  echo "== ACTUAL ORIGINAL CHAIN TEST-ETH SOURCE, NO SIGNING =="
  python3 -B tools/sse_pos_r201_v2_readonly_live_chain_gate.py \
    --rpc http://127.0.0.1:28545
  echo "== SOURCE / STATUS =="
  git rev-parse HEAD
  pwd
)
```

If a command fails, paste failing output, **DO NOT switch to
--broadcast or manually patch files on a VM**. Send compile errors,
unexpected runtime EIP-170 sizes, Python test failures and Forge
individual tests so the fix is through GitHub. A code compile
or EVM test pass is still not a real SLA or external user run.

### Security and economics review BEFORE any transaction

* Check `forge build --sizes` for EIP170 runtime and EIP3860
  constructor code limits. If default compile has stack-too-deep,
  run `FOUNDRY_VIA_IR=true forge build --sizes` and similarly tests
  as a separate explicit artifact; record compiler mode rather than
  pretend bytecode identical.
* Audit all Solidity reentrancy/timestamp warnings and externally
  supplied policy parameters. Re-run adversarial tests for rational
  malicious parties and escrow conservation. No production claims.
* Existing chain31340 genesis EOA `0x13fb73aace8A11Be2899D047635A757a224Ce00B`
  at previous read-only check had 1,000,005.319709155
  TEST ETH, nonce0, at finalized EL16822. The **private
  encrypted wallet remains local to VM4706** and was previously
  verified, NEVER copied/pasted or put into GitHub.
* Create an owner-authorized, encrypted application-only wallet
  privately at the chosen owner host, independently confirm public
  address. Transfer ONLY a limited agreed research test-ETH amount
  from original owner wallet through locally authenticated Cast
  after explicit user approval. Capture signed tx hash and actual
  finalized block. No permissionless grant/faucet funded on
  this network is assumed. Do not prompt for any passwords in chat.
* Separate consumer, provider, and monitor EOAs must be genuinely
  independent roles. Different EOAs do not prove different
  physical operators. Real host credentials and resource measurements
  must be independently audited.
* The draw uses **proposer-biasable Ethereum blockhash**, not
  cryptographic VRF. Global gas-bounded selection is rotating,
  not statistically globally uniform; enumerate this limitation
  in experiment results and never call it production Sybil-safe.

## End-to-end live acceptance (NOT YET DONE)

1. Source tests and verified code size PASS.
2. Authorized test-only EOA and native test-ETH funding proven
   on original genesis with live canonical/finalized receipts.
3. Source-attested V2 deployment to chain31340 approved
   manually, with actual tx receipts and runtime hashes; R206
   audit PASS **independently on VM4707 and VM4709**.
4. Register real monitor EOA bonds (k>=4), consumer resource
   request, provider bid, consumer chooses funds market
   escrow and locked monitor report reserve, snapshot
   commitment published as event.
5. Real delayed draw after exact future block, list selected
   committee, confirm real distinct monitors; inspect
   bond locks, immutable k/q and reward pool.
6. Provider actually runs bounded Docker workload on a
   host; independently observe real CPU/memory/Docker digest,
   request response, signatures and measurement evidence.
   Local Docker configuration is NOT proof of independent
   provider physical infrastructure.
7. Provider EIP712 signs verified actual response hash,
   eligible independent monitors independently observe
   and sign on-chain scoped Success/Failure votes.
   Failure vs timeout, physical false reports, and
   inconclusive outcomes must be experimentally distinguished.
8. Actual Beacon-finalized market transactions,
   monitored evidence hashes, escrow payouts, monitor reward
   credits and withdrawal receipts. Compare both real nodes.
9. External Internet dynamic-IP, native P2P outside ZeroTier,
   independent host/operator and validator onboarding/economics
   independently verified, scientific gas/resources/cost
   metrics collected without synthetic SLA measurements.

All of (1)–(9) are acceptance gates, NOT claims of current completion.

**Avoid rerunning VM4709 R188 recovery, rerunning any genesis creator,
removing original databases, or setting up another unrelated
blockchain instance.** Existing two real nodes must remain intact.
