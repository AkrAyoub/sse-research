# R243 — Adaptive SSE V2 real-role application integration / return-time gate

**Scope:** GitHub-only source work R226–R242 on
`feature/r226-adaptive-v2-operator-runtime`, draft PR #43 stacked
on existing DRAFT PR #41 `feature/r136-independent-observer-preflight`.
**Source status: NEW, UNTESTED on actual VM at the time of this document.**
Do not treat unexecuted authored tests as PASS. There has been NO VM
change, package installation, wallet creation, transaction, contract
deployment, Docker lifecycle action, key disclosure or other on-chain
state mutation by this development batch.

## What is now implemented, not yet executed

| Increment | Sources | Concrete function |
| --- | --- | --- |
| R226 | `tools/sse_pos_r226_adaptive_v2_transaction_planner.py` + tests | Exact versioned V2 contract ABI action plans, including dynamic EIP712 signed calldata, strict full 9-field Terms tuple, explicit required native TEST ETH escrow, R206 read-only on-chain bid fee match; now includes `forceCloseIdle` |
| R227 | `tools/sse_pos_r227_v2_finalized_event_audit.py` + tests | Finalized native execution logs from BOTH actual V2 contracts; immutable R206 runtime/receipt gate, exact topic/ABI decoding, 256-block batches, verified canonical event block hashes, no lost/duplicate/reorg logs accepted |
| R228 | `tools/sse_pos_r228_v2_typed_data.py` + tests | Three exact V2 EIP-712 schema/domain builders and public EOA signature verification for provider response, vote, and bilateral residual. V1 `SSESettlement` typed domains are NOT reused |
| R229 | `tools/sse_pos_r229_v2_finalized_lease_snapshot.py` + tests | One-real-finalized-block market Lease/Epoch, dynamic committee and vote Ledger/Epoch, bonded monitor roster, escrow coverage and adaptive q/f invariants; includes R236's new `lastProgressAt` ABI field |
| R231 | `tools/sse_pos_r231_v2_compute_wire.py` + tests | Deterministic work digest bound to real lease/request, resource policy and provider-signed exact V2 response. A correct digest alone is NOT proof of CPU use |
| R232 | `tools/sse_pos_r232_v2_monitor_probe.py` + tests | Selected/confirmed actual on-chain monitor can request real bounded HTTP/HTTPS work from lease-committed origin, independently check signed provider reply and measure monotonic elapsed time. Private create-only raw body and observation archives. Timeouts remain UNKNOWN; never auto-votes |
| R233 | `tools/sse_pos_r233_public_v2_compute_terms.py` + tests | Public dynamic-DNS HTTPS origin, image digest, CPU/RAM profile and SLA hash commitments; negotiates funding, k/f and declared finality safety margins. Does not enforce or certify physical resource delivery |
| R234 | `services/provider-agent/v2_compute_response_server.py` + tests | On real provider host: loopback-only service only releases an operator pre-signed V2 response AFTER strict Docker inspect and actual CPU-worker HTTP execution. Does not have private keys, create containers or prove independent hardware |
| R235 | `scripts/r235_vm4707_v2_source_only_gate.sh` | Exact immutable SHA guard, targeted+full Python unit suites and actual local Foundry compile/contract test. NO live RPC, transactions, Docker, wallet or validator changes |
| R236 | `contracts/SSEAdaptiveMarketV2.sol` + Foundry tests | Fixed distinct previously unprotected scenario: post-accept idle owner could strand selected monitor bonds indefinitely. Permissionless `forceCloseIdle`, non-revivable idle deadline, secure refund, unresolved service fee stays escrowed; emitted audit event |
| R237 | `tools/sse_pos_r237_v2_approved_local_eip712_sign.py` + tests | Typed EIP-712 actual signatures ONLY after R206 finalized source integrity, R229 finalized lease/role evidence, separate owner-only encrypted app EOA, hidden password and explicit terminal approval. Original genesis EOA forbidden; no blockchain send |
| R238 | `services/node-console/v2_status_app.py` + tests | Per-node read-only HTML/JSON UI with real local R141 EL+CL health and optional R206/R229 finalized V2 lease info, no master admission server; binds loopback ONLY until separate HTTPS proxy authorization |
| R239 | `tools/sse_pos_r239_v2_real_gas_quote.py` + tests | Quotes *real* node `eth_estimateGas`, `eth_gasPrice`, finalized app-wallet balance and latest block gas limit under explicit maximum native test-ETH spend; source-only until R206 live contracts |
| R242 | `tools/sse_pos_r242_v2_owner_local_send.py` + tests | No-send default. A single actual V2 role transaction ONLY when owner explicitly runs `--send`, passes exact prompt approval, separate encrypted app wallet and local gas/recipient/signing/nonce gate. Checks real receipt/canonical block/finality without pretending remote Beacon/physical proofs |
| CI | `.github/workflows/sse-adaptive-v2-source.yml` | Full source-level Python and Foundry gates with pinned dependencies, no deploy key, signer or live VM changes; **no successful workflow run asserted** |

All new code remains in the draft branch for operator-controlled testing.
The previous actual VM4707 **V2 16/16 PASS and 68-source compile**
was from **OLDER** exact source
`9a216518b3ea8c265f5186f6113987eb537d7949`;
those results do NOT validate R236 or any new source. R236 adds five
Foundry lifecycle tests to the old 16; authorship ≠ observed passing tests.
Do not reuse the previously reported 18,087-byte V2 market runtime
size as if it were the NEW post-R236 build.

## R236 contract-level failure and bounded fix rationale

Previously, after a consumer funded a lease, committee was drawn and
confirmed, and provider accepted, the consumer could disappear without
starting another epoch or closing. The original V2 locked each selected
monitor's test-ETH bond until ordinary lease close; absent the consumer,
there was no external actor able to release those honest locked bonds.

Revised V2 stores `uint64 lastProgressAt` in the fixed Lease struct
and tracks acceptance, started work, successful finality-based epoch
settlement or bilateral signed allocation. The already negotiated and
bounded `confirmationSeconds` is reused as the post-accept maximum
idle interval. This is a research policy choice to be reviewed against
actual observed chain finality and SLA durations; do not quietly call
it a universal objectively optimal timeout.

At idle expiry any actor can `forceCloseIdle(leaseId)`, only if the
provider accepted and the lease is Assigned/Active. It cannot falsify
Success/Failure; every opened epoch must already have been sealed.
When no epoch is pending it returns the unused service escrow, has
ledger refund unused monitoring rewards and unlocks all chosen bonds.
When a sealed epoch is **None/no quorum**, it preserves exactly
the unresolved epoch fee in settlement escrow, refunds only unused
future fees, closes reporting and unlocks monitor bonds. The original
consumer and provider can still supply the bilateral EIP712 allocation
after the lease's idle close. A sealed Success/Failure quorum must first
be finalized with the original rightful payout. `startEpoch` now
refuses late revival after the negotiated idle deadline.

These invariants are unit tested as *source-only authored tests*,
not yet contract-compilation or live-chain evidence. They do not
solve indefinitely stalled **unresolved service fee**, untruthful
monitor EOA collusion or proposer-biased random selection.

## Exact VM4707 return gate — NO live effects

Use **a fresh temporary checkout** (do not overwrite the running
`~/sse-research` or any Docker container). Insert the immutable
full SHA reported in the handoff message:

```bash
(
  set -euo pipefail
  SHA="<PINNED_FULL_GITHUB_SHA_FROM_HANDOFF>"
  DIR="$(mktemp -d)"
  git clone -q --no-checkout https://github.com/AkrAyoub/sse-research.git "$DIR/repo"
  cd "$DIR/repo"
  git fetch -q --no-tags origin feature/r226-adaptive-v2-operator-runtime
  git switch -q --detach "$SHA"
  test "$(git rev-parse HEAD)" = "$SHA"
  git submodule update --init --recursive
  # Python 3 must have pinned requirements; use an ISOLATED user-space
  # venv if absent, never install system-wide without review.
  export PATH="$HOME/.local/share/sse-r19-toolchains/foundry-v1.9.0:$PATH"
  bash scripts/r235_vm4707_v2_source_only_gate.sh "$SHA"
)
```

If `Crypto`, `eth_account` or `eth_abi` is missing, use an isolated
local test venv, `python3 -m venv "$DIR/testvenv"`, then
`"$DIR/testvenv/bin/pip" install -r requirements.txt`
(which accesses external pinned PyPI distributions and is a separate
user-approved source-dependency download; review hashes and environment
before running). Activate via
`PATH="$DIR/testvenv/bin:$PATH"` for source tests. Never upload wallet
private files, copy BLS keystores or run `forge script --broadcast`
to "fix" a failed unit test.

**Accept only actual pasted test logs** with exact Git SHA,
targeted V2 contract tests and full source suite passing, observed
new runtime sizes under EIP-170/EIP-3860, and local no-effect marker
`R235_SOURCE_ONLY_GATES_COMPLETED=true`. If failing, correct through
GitHub and issue a NEW exact immutable SHA rather than ad-hoc VM edits.

## Separate live deployment acceptance gates — owner must approve

1. Confirm original VM4706 encrypted owner **PUBLIC EOA only**, untouched
   original genesis, and current canonical finalized EL/CL state;
   preserve original validator, Docker, Beacon storage/slashing history.
2. Owner independently creates/preserves distinct private encrypted
   **application-only** EOAs on each actual role host. No passwords
   or private keys in chat, PRs, environment, CLI flags or GitHub.
3. Before ANY fund, transaction or deployment obtain explicit
   separate consent and a measured bounded test-ETH budget.
   Original owner must actually send a real limited native TEST ETH
   transfer from VM4706; newly joining zero-balance observers should
   still join without a wallet. The public faucet remains **unfunded,
   undeployed**, so there is no autonomous universal gas subsidy yet.
4. Only after source/adversarial security review, owner deploys the
   exact reviewed `script/DeploySSEAdaptive31340.s.sol` ONCE on
   original chain31340; no legacy fixed-4/3 V1 deployment.
   Audit finalized creation receipt, unique addresses, runtime SHA-256
   and mutual market↔ledger immutable bindings with R206
   **independently on VM4707 and VM4709**.
5. Real monitor registration bonds and confirmations, chosen consumer
   resource request/actual provider bid, on-chain full service+monitor
   escrow, future block committee draw (still NOT VRF), acceptance and
   epoch start with realistically long chain-finality-aware deadline.
6. Run REAL pinned CPU Docker worker on actual provider host and
   independently measure/report from actual monitor hosts over
   authenticated public HTTPS; monitor signatures attest their
   observations, not proof of independent resources or SLA truth.
7. Owner-approved per-role R242 ONE tx at a time, with real gas
   estimate/receipt/finality from actual node and independent cross-VM
   checkpoint audit. Validate Success/Failure/no-quorum, withdrawals,
   refunds, nonresponse, honest and malicious timeouts, bond unlock
   and actual test-ETH conservation. R227 audit and R229 snapshot
   should agree at a single canonical finalized state.
8. Multi-operator validators with independent BLS keys/deposits,
   actual unrelated infrastructure and dynamic public-IP peer
   onboarding independent of ZeroTier and GitHub rendezvous,
   reliable public HTTPS per-node UI, multiple monitors with actual
   independent fault domains and economic Sybil resistance remain
   **unverified** and are not silently "completed" by source tools.

### Project evidence preserved

- R223 original real VM4707 V2 source 16/16 PASS at old source.
- R224 VM4707 genuine EL+CL healthy epoch602.
- R225 VM4709 genuine original EL+CL head state with identical
  finalized epoch602/root as VM4707, but capture separation was
  **181.223808sec** vs formal 180-second R141 threshold;
  older R192 epoch571 actual two-node formal strict match remains passed.
- No changes in this branch affected the real chain31340 owner validator,
  VM4707/VM4709 running clients, original genesis or funded wallets.

**All draft work stays unmerged until verified.** Script/source authorship
does not imply actual installation, gas spend, finality or SLA operation.
