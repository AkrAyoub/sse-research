# RFC R1/R2-01 — Service-specific SLA and native test-ETH economy

**Status:** DESIGN PROPOSAL / RESEARCH REFERENCE — NOT APPROVED AS A SETTLEMENT POLICY.
**Date:** 2026-11-15. **Working base:** WP09Q commit `75c2da3`, user-local 127/127 Foundry green.
**Scope:** R1/P1/P3 SLA semantics, R2 economic invariants, R4 evidence interface,
R7 service adapters, P2/P4/R9 evaluation. This RFC does not modify contracts,
deploy anything, create a token, or grant new evidence-based payout authority.
It is not a statement of production fairness or physical-service soundness.

## 0. Decision log: accepted facts versus this RFC's proposals

**Existing, verified source facts:**

- `OpenResourceBoard` accepts requests containing `resourceProfileHash`,
  `slaPolicyHash` and a maximum `epochFee`; providers bid an `epochFee`;
  consumer selection atomically funds a lease via `SSESettlement`.
- Marketplace leases store the hashes. The hash is a commitment to **bytes**,
  not a program for interpreting SLA metrics. The direct-lease path does not
  populate `slaPolicyHash` in this version.
- Service escrow is `epochFee * maxEpochs`. `reservationFee <= epochFee`,
  exposure budget, response/monitor/evidence windows and one epoch at a time
  are checked. Native-ETH `payable` / `withdrawable` implement settlement.
- N/F/S entitlements in `SSEBoundsPure`: `p(N)=r, p(F)=0, p(S)=f`.
  Separate `configureIncentives` deposits monitor/executor budgets; optional
  `fundVrfRequestFee` prepays a fixed bootstrapper reimbursement. Actual
  network gas is additional and paid by the transaction sender.
- Monitor `register` requires a native-ETH bond. The current contract has no
  general slashing for a wrong physical vote. No provider performance-collateral
  escrow or automatically enforceable external-service penalty exists today.
- The current on-chain three-of-four classification is a **research policy**.
  No generic cloud SLA interpreter or sound physical-delivery certificate
  verifier exists. `tools/sse_evidence_policy_v1.py` is off-chain reference
  research and does not establish evidence authenticity or truth.
- Only local Anvil / mock-VRF and selected Python/Foundry workflows have been
  tested; public-testnet operations are not part of this RFC.

**Proposed defaults FOR THE NEXT RESEARCH EXPERIMENT (review required):**

1. Start with `DETERMINISTIC_COMPUTE`, contractual mode
   `CONSUMER_CORRECT_RESULT_RECEIVED`, with a **separate receipt cutoff** and
   a **separate delivery deadline**. This is deliberately stronger than "worker
   calculated a digest" or "monitor got HTTP 200".
2. For this **new delivery-only SLA**, set reservation `r=0`. Do **not**
   reinterpret previous leases or erase the generic nonzero-reservation option.
   A reservation/availability promise must be separately purchased, justified,
   and versioned if we later allow `r>0`.
3. Keep **service escrow**, **monitor/executor budgets**, **VRF funding**,
   **monitor bonds**, and any **hypothetical provider collateral** as distinct
   accounting pots. No default slashing or provider penalty is approved.
4. Use the current `k=4, q=3` Solidity demo only until R3 introduces safe,
   configurable `k,q`. A majority vote is evidence of attributed statements,
   not proof of actual consumer delivery or execution.

These decisions may be approved for a research protocol version, but they
cannot be silently enabled in Solidity V1 or applied to already funded leases.

## 1. Service families and distinct proof obligations

| Service family | Purchased obligation | Example primary SLO/metrics | Necessary evidence / unresolved claim | Adapter status |
|---|---|---|---|---|
| `HTTP_CHALLENGE` | Correct response generated or delivered per named mode | Correctness, deadline, delivery | Consumer delivery needs separate qualification; monitor HTTP success alone is insufficient | Local prototype |
| `DETERMINISTIC_COMPUTE` | Specified job result + optionally actual execution / resources | Correct result, completion/delivery deadline, committed workload hash | A reproducible digest does not prove CPU reservation or execution on declared hardware | Local Docker lab |
| `OCI_CONTAINER` | Container environment with resource bounds over an interval | Uptime, image digest, reachability, CPU/RAM availability | Health endpoint does not prove allocation, isolation, duration | Planned |
| `OBJECT_STORAGE` | Persist an exact object and retrieve it on demand | Integrity, retention interval, availability, recovery latency | One successful GET does not prove retention across the whole contract | Planned |
| `GENERAL_API` | Correct and timely service on eligible calls | Success rate, p95/p99 latency, availability, error budget | A status 200 is not semantic correctness; define sampling and eligible denominator | Planned |

HTTP probes and compute Docker jobs are **experimental implementations**, not
audited physical SLA validators. Future types are reserved; missing policies
must fail closed rather than default to HTTP semantics.

Commercial model comparisons: AWS EC2 defines separate instance and region
uptime objectives with bill-credit tiers; Google Compute Engine and Cloud
Storage use service/location-dependent monthly uptime and future-bill credits.
ISO/IEC 19086-2 supplies a metric model but does not mandate one universal
metric set. We use these as **comparators**, not as SSE promises.

## 2. First agreed-on-paper SLA proposal: compute result delivered

**Service identifier (proposed, not current contract enum):**
`COMPUTE_CONSUMER_DELIVERY_DRAFT_V0`.

**Contractible inputs before provider accepts:**

- Chain ID and intended `SSESettlement` verifying contract; consumer and
  provider addresses; lease / epoch reference, nonce and version;
- Canonical `resourceProfileHash`, `serviceEndpointHash`,
  `workloadManifestHash` (input/result algorithm and workload identity);
- Whether correctness means output equality only, execution by a real CPU,
  fixed reserved vCPU/RAM, or end-to-end correct **consumer receipt**. The first
  experiment uses **correct consumer receipt**; CPU reservation and hardware
  attestation are explicitly out of scope for its success predicate;
- Deadline `D_r` for qualifying *physical provider receipt* and `D_f` for
  qualifying *physical consumer result receipt*, with `D_r <= D_f`, and named
  time authority, clock error and transport assumptions;
- Fee `f`, optional reservation `r`, maximum epochs, exposure cap, evidence
  retention and settlement/refund/reward/dispute rules;
- Explicit evidence policy `policyId`, version and rejection behavior for
  contradictory, late, absent and unverifiable reports.

**Physical world semantics (in the simulator, not automatically observable):**

- **N:** no qualifying physical request receipt by `D_r`.
- **F:** qualifying physical receipt occurred, but correct result did not reach
  the contracted consumer by `D_f`.
- **S:** qualifying physical receipt and correct consumer delivery both occurred
  by their respective deadlines.

The complete physical event trace is stipulated in research simulations only;
see `tools/sse_service_trace_reference.py`. A signed provider ACK is not itself
physical receipt; signed result is not consumer delivery; a monitor timeout is
not proof of no delivery. Even all four monitors can be partitioned together.
`block.timestamp` determines EVM windows, not external packet delivery time.

**Evidence qualification rules TO IMPLEMENT before any real payout upgrade:**

| Incoming information | Authentication proves | What can be excluded in physical N/F/S model? |
|---|---|---|
| Provider EIP-712 ACK / result hash | Which key signed these bytes | None by default |
| 3/4 success or timeout votes | Attribution + lease-specific vote majority | None by default |
| Sound physical provider-receipt certificate | Receipt before agreed `D_r` under stated trust/clock assumptions | N, leaving F/S |
| Sound correct-and-timely consumer-delivery certificate | Consumer received qualifying result by `D_f` | N and F, leaving S |
| Sound universal nonfulfillment certificate | Excludes **every** timely qualifying delivery | S, leaving N/F |
| Contradictory qualified claims | Rules or assumptions conflict | HALT; no further irreversible automatic payout |

A certificate type must include signer/key authority, immutable bytes,
anti-replay binding, verified chain scope, timestamp uncertainty, availability
of underlying raw observations, validity windows and a documented soundness
argument. A consumer can withhold a receipt; a provider can lie; network
partitions make absolute non-delivery difficult to prove. No certificate
mechanism here is declared secure just because it has a digital signature.

**Release gate:** R1 and P1 must approve these predicates and assumptions;
R4 must implement/verify certificate qualification; R2 must implement new
on-chain policy checks using a distinctly versioned contract. Today the live
Solidity 3-of-4 policy remains unchanged and must be described as conditional.

## 3. Monetary mechanics: preserve two different notions of money

- **In the laboratory:** Anvil's prefunded balances are simulated ETH.
- **In public integration experiments:** native **testnet ETH** funds real
  transactions on the test chain but has no intended monetary value. It is NOT
  ERC-20, not a custom SSE credit, and not real Ethereum mainnet ETH.
- **In an economic paper model:** use integer wei/notional prices and report
  outcomes normalized by contract value. Test ETH has no meaningful market
  price, so successful testnet execution does **not** demonstrate that monitor
  bonds economically deter corruption or that a real provider would accept bids.

Do not merge gas cost with escrow: network gas belongs to each transaction
sender, separate from service charges, optional monitor rewards and VRF fee.
No oracle payment cost should be inferred from the adapter's fixed policy fee.

### 3.1 Current implemented service escrow

For one epoch with service fee `f>0`, reservation `0<=r<=f`, admissible
nonempty histories `H subset {N,F,S}`, define provider entitlement
`p(N)=r`, `p(F)=0`, `p(S)=f`:

```
L = min(p(h) for h in H)
U = max(p(h) for h in H)
provider guaranteed credit = L
consumer guaranteed refund = f - U
unresolved service escrow = U - L
```

Then `L + (f-U) + (U-L) == f`. An evidence refinement is acceptable only
if the new histories are a **nonempty subset** of the previous histories,
and cumulative payouts never decrease. Money is released by crediting deltas;
no prior recipient is forced to repay. Soundness requires the true world
remain among admitted histories.

The new delivery-only proposal chooses `r=0`. Example `f=25` wei (small
numbers for arithmetic; **not market prices**):

| Qualified admissible histories | Provider credit | Consumer refund | Service escrow unresolved |
|---|---:|---:|---:|
| N/F/S (no qualified fact) | 0 | 0 | 25 |
| N/F (qualified nonfulfillment) | 0 | 25 | 0 |
| F/S (qualified physical receipt) | 0 | 0 | 25 |
| S (qualified fulfillment) | 25 | 0 | 0 |
| F (qualified receipt + nonfulfillment) | 0 | 25 | 0 |
| N (qualified absence of receipt) | 0 | 25 | 0 |

**Legacy V1 contrast:** For `f=25,r=5,H={N,F}`, provider credit 0,
consumer refund 20, unresolved 5. That legacy result remains correct under
its own original contractual semantics. No policy may retroactively change it.

### 3.2 Funding and participants — current, separate obligations

```
service escrow           = epochFee * maxEpochs
monitor reward reserve   = maxEpochs * k * monitorRewardPerReport
executor reward reserve  = maxEpochs * (seal + settle + evidenceClose) + release
optional VRF prepayment  = configured fixed fee (subject to on-chain quota/state)
consumer funding         = service escrow + rewards + optional VRF prepayment
consumer gas             = separately paid by tx sender (estimate, varies)
monitor registration     = each monitor separately bonds at least minimumBond
provider performance bond = NOT IMPLEMENTED
```

The reward budgets are optional and must be configured/prepaid using the
current contract's legal lifecycle. `k=4` in today's deployed type. Existing
VRF fee is reimbursement to a configured sponsor, not demonstrated actual
external coordinator billing. Executor bounties are not assumed to prove
physical service truth.

Providers may bid a `fee` subject to the consumer's price cap, but current
`OpenResourceBoard` bids encode only `epochFee` (not a verifiable cost
curve or SLA-specific penalty). A future quote should show the service fee,
expected monitoring cost, VRF cost, the payer of gas, optional collateral
requirement, deadlines, and all-in projected expense **before acceptance**.

### 3.3 OPTIONAL FUTURE: separately prefunded provider collateral

Not implemented in Solidity and **not an approved penalty**. In a limited
research model, let provider deposit `B>=0`, with a **strictly bounded**
penalty `0<=P<=B` for *independently qualified* physical history F.
No penalty is payable for N or S. This tests a possible service-breach
deposit without slashing for a mere unfavorable monitor vote.

For possible penalty amounts `d(N)=0,d(F)=P,d(S)=0`:

```
collateral consumer guaranteed = min(d(h) for h in H)
collateral provider guaranteed return = B - max(d(h) for h in H)
collateral unresolved = max(d(h) for h in H) - min(d(h) for h in H)
```

These sum exactly to B. They are **a separate pot from the fee**; no
double-counting fee refunds, monitor bonds or unspent incentive reserves.
For `B=6,P=4`: H={F} gives customer additional 4, provider returned 2;
H={N,F} gives customer 0, provider safely returned 2 and 4 remains held;
H={S} returns all 6. These numbers are research inputs, not SLA defaults.
A wrong/absent quorum must not trigger automatic slashing. Proven EIP-712
equivocation by a monitor is a separate monitor-bond security question.

The accompanying `tools/sse_sla_economy_reference.py` and
`tests/test_sse_sla_economy_reference.py` model both pots and exhaustive
subset-refinement conservation **without authorizing any actual transfer**.

**Critical open item:** how to terminate permanently ambiguous funds fairly.
The current EIP-712 two-party residual agreement gives one consensual way to
split an unresolved closed epoch; it does not ensure agreement or economically
fair termination. Do not silently burn, release to provider, release to consumer
or grant an administrator unilateral authority after a timeout.

## 4. A proposed versioned SLA manifest — schema contract, not yet a hash

Before designing a canonical byte representation and domain-separated Keccak
hash, the following fields require a documented, fixed encoding:

```yaml
schema: SSE_COMPUTE_CONSUMER_DELIVERY_DRAFT_V0
serviceKind: DETERMINISTIC_COMPUTE
fulfillmentMode: CONSUMER_CORRECT_RESULT_RECEIVED
binding:
  chainId: <target testnet chain ID>
  settlement: <deployed verifying contract address>
  consumer: <20-byte address>
  provider: <20-byte address>
  marketplaceRequestId: <uint>
  leaseId: <uint>                 # if known when signed
  epochId: <uint>                 # for epoch-specific amendment
  nonce: <unique bounded value>
resourceProfileHash: <bytes32>
serviceEndpointHash: <bytes32>
workloadManifestHash: <bytes32>
slaSemanticsVersion: <immutable version>
evidencePolicyVersion: <immutable version>
timing:
  receiptCutoff: <D_r and validated time authority>
  deliveryDeadline: <D_f and validated time authority>
  uncertaintyPolicy: <versioned rule, NO default guessed clock>
economics:
  epochFeeWei: <uint>
  reservationFeeWei: 0
  maxEpochs: <uint>
  exposureBudgetWei: <uint>
  reportRewardBudgetWei: <uint>
  executorRewardBudgetWei: <uint>
  optionalVrfPrepaymentWei: <uint>
  optionalProviderCollateralWei: 0   # NO live contract support
  penaltyPolicy: NONE                # NO live contract support
evidencePolicy: <named certified-fact transition rule>
unresolvedPolicy: BILATERAL_AGREEMENT_OR_HELD
```

**This is intentionally NOT a canonical JSON/hash/signed transaction.**
It has unresolved placeholders, no agreed EIP-712 type hash, and is not
compatible by itself with `SSESettlement` V1. The exact off-chain/chain
binding and pre-lease versus post-lease identifiers must be resolved before
R4 implements serialization and authenticated negotiation. Never hash this
illustration and claim the contract is enforcing its contents.

## 5. Metrics and experimental economic calibration (R7, R9, P4)

| Dimension | Compute first experiment | Later services |
|---|---|---|
| Fulfillment | Correct bytes delivered to consumer by D_f, with qualified proof | Storage retention / container uptime / API correctness |
| Reliability | Fraction of eligible jobs with qualified on-time delivery | Availability and valid request ratio |
| Timing | Request/receipt/delivery intervals, skew, partitions | Latency percentiles, outage windows, retrieval time |
| Evidence security | False exclusion rate vs simulation ground truth | Certificate falsifiability, correlated monitor failures |
| Cost | Escrow released/held, gas per phase, witness fees | Per-unit storage/runtime/API expenses |
| Liveness | Completion, timeout, honest-vs-Byzantine withholding | Recovery time with n monitors and configurable k/q |
| Economics | Auction bid, bounded loss, capital locked duration | Collateral efficiency and pricing sensitivity |

Pre-register fair comparison cases: (a) binary pay-or-refund,
(b) hold-all-until-unambiguous, and (c) SSE guaranteed-partial-release,
**under identical true histories, evidence and costs**. Vary arrival
times, partitions, dishonest witnesses, resource availability, admission
exposure, relative price, bond collateral and testnet fees. Avoid claiming
statistical economic incentive compatibility from free test ETH alone.

No automatic 99.9% target, 30% service credit, or penalty multiplier is
authorized here. Choose thresholds for each service from workloads and
stated customer contract assumptions, then version them and evaluate.

## 6. Ownership and acceptance order

| Phase | Next artifact | Acceptance criterion |
|---|---|---|
| R1 / P1 | Final signed compute SLA semantics, event and clock threat model | Complete unambiguous N/F/S physical predicates |
| P3 | Versioned message/manifest specification | Fixed bytes/encoding, roles, time units, compatibility |
| R4 | Evidence validator and qualified certificate verifier | Positive, negative, partition, forged, replay tests; trust boundary |
| R2 | Policy-aware settlement V2, if justified | Conservation, monotone credits, collateral separation, dispute closure |
| R7 | Remote compute adapter; then OCI, storage, API | Each adapter proves only its approved metrics |
| R3 / R5 / R6 | Scalable independently operated monitor and VM infrastructure | Multi-host key and viewpoint separation, testnet integration |
| R9 / P4 / R10 | Registered scenario matrix, real distributed evaluation | Replicable cost/safety/liveness datasets |
| P0 / P2 / P5 / P6 | Prior art, proofs, final paper/release | Source-grounded novelty, conditional theorems, replication |

**Immediate decisions to review and approve:**
1. Is the *first* purchased good "correct job result received by consumer",
   or only "correct result generated by provider"? These cannot share the
   same SLA version.
2. Is `r=0` acceptable for the initial delivery-only experiment?
3. Should penalty collateral remain disabled until a sound physical
   breach verifier exists? This RFC recommends **YES**.
4. What trust assumptions or external certificates can establish correct
   consumer delivery without enabling fraudulent refund claims?
5. How do we fairly close permanently unresolved service and collateral
   funds if consumer and provider cannot reach a bilateral agreement?

Approval of this RFC's first three defaults allows us to finalize an R1
versioned *research* SLA; approval of Q4/Q5 and implementation/testing is
necessary before irreversible physical-SLA payout changes.

## 7. References and constraints

- Project source: `docs/research/R1_WP03_SERVICE_CONDITIONS_AND_TRACES.md`,
  `ADR-001_WP08_HTTP_SERVICE_SEMANTICS.md`,
  `ADR-002_WP08_EVIDENCE_TRUST_BOUNDARY.md`,
  `ADR-003_WP08_SCALABLE_MONITOR_DESIGN_TARGET.md`.
- Project formal models: `tools/sse_formal_reference.py`,
  `tools/sse_evidence_policy_v1.py`,
  `tools/sse_service_trace_reference.py`.
- Solidity: `OpenResourceBoard.sol`, `SSESettlement.sol`,
  `SSEBoundsPure.sol`, `OpenMonitorCommittee.sol`.
- Shi et al. (2022), *AWESOME: an auction and witness enhanced SLA model for
  decentralized cloud marketplaces*, Journal of Cloud Computing 11:27.
  https://doi.org/10.1186/s13677-022-00292-8
- ISO/IEC 19086-2:2018, metric model: https://www.iso.org/standard/67546.html
  (terminology and framework, not mandatory particular metrics).
- AWS Compute SLA: https://aws.amazon.com/compute/sla/
- Google Compute SLA: https://cloud.google.com/compute/sla
- Google Storage SLA: https://cloud.google.com/storage/sla

**Paper claim boundary:** Auctions, monitors, credit tiers and collateral are
not novel by themselves. The SSE research question is whether *world-sound
admissible-history interpretation* plus guaranteed partial release yields
quantifiable benefits under explicitly realistic service and network
assumptions. The RFC does not establish those assumptions or novelty.
