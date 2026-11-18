# SSE handoff — Project Dev 3 recovery (2026-11-18)

Source of truth: repository AkrAyoub/sse-research at main commit
7e86edb9aff6a2e45eac940cf7ced3b2c88f2bea (2026-11-14).
This is a *reconstruction* from retained project conversation excerpts,
GitHub commits, reports and source. It is NOT a verbatim chat transcript,
not an independent runtime inspection of the user's VM, and not evidence
that any command proposed after the last user terminal output was run.

## Research goal

SSE Intercloud explores SLA-backed resource leasing across independently
operated cloud providers. A consumer advertises CPU/RAM/workload/SLA/budget;
providers bid; an accepted lease escrow-funds service. A provider agent
instantiates an image/digest-bound compute or HTTP workload. Selected bonded
monitors submit signed observations and hashes of raw evidence. Contracts
validate authenticated roles, applicable deadlines, committee threshold,
residual claims and payout/escrow accounting. The on-chain consensus layer
orders/finalizes transactions; it cannot establish the off-chain physical
truth of delivered compute or HTTP responses without additional assumptions.

## Layers and roles — KEEP DISTINCT

1. Ethereum consensus nodes: run EVM blockchain; participate in finalization.
2. Consumer, provider, resource board: negotiate, create/fund/accept leases.
3. Monitors, committee, bond pool: independent identities selected for
   per-lease SLA evidence; a 3-of-4 monitoring threshold is NOT consensus.
4. Service agents: launch containers/HTTP workloads off-chain; collect facts.
5. Witnesses/evidence archive: signed HTTP evidence, block-hash binding,
   anchored snapshots; do not imply external fact attestation.
6. Control-plane UI/role agents: convenience orchestration, not authoritative
   payout ledger or proof of independent machine control.

## Published source modules

- contracts/SSESettlement.sol: leased epoch lifecycle, signed provider
  responses/monitor votes, settlement, credits, fixed reward/residual policy,
  plus experimental VRF-fee extensions needing EVM validation.
- contracts/OpenMonitorCommittee.sol: registry, assignment, confirmations,
  quorum committee lifecycle, no-show recovery, global election research.
- contracts/OpenMonitorBondPool.sol: monitor economic membership bonds.
- contracts/OpenResourceBoard.sol: marketplace bids and funded lease creation.
- contracts/GlobalRosterMerkle.sol and GlobalRosterSampler.sol:
  full-active-roster root and proof-checked bounded global sampling.
- contracts/RSA2048EntropyVerifier.sol: research-only RSA 2048 verifier.
- contracts/SSEVRFV25Adapter.sol, MockVRFV25Coordinator.sol:
  draft VRF v2.5 integration with insecure mock, NOT real Chainlink proof.
- services/provider-agent, services/monitor-agent, services/witness-agent,
  services/role-agent, apps/control-plane and tools: off-chain service,
  evidence, operator, read-only chain and settlement helpers.
- foundry/test and tests: Solidity and Python references/unit/adversarial
  experiments. See module-level docs for input assumptions and test logs.

## Historically demonstrated local development

Early SSE Milestone III used a local Anvil RPC at 127.0.0.1:8545, chain
31337, with a prior SSESettlement address
0x0DCd1Bf9A1b36cE34237eEaFef220932846BCD82. Demo identities included
the Anvil consumer 0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266. The
sprint path created a *fresh* direct funded lease, acquired an authorized
committee seed, confirmed four monitors, admitted an epoch, signed EIP-712
provider response and three monitor votes, settled and released bonds;
that baseline was local, with unlocked dev RPC accounts, same-host probes,
and artificial evm_increaseTime. The optional Docker CPU worker bound a
canonical image/CPU/memory/endpoint profile and nonce-bound computation to
a new lease and evidence hashes. Local compute != remote cloud provisioning.
The user earlier reported passing tests for their old local setup; that
does NOT mean the newest 2026-11-14 research contracts were deployed.

## Research methodology

- Keep high-level physical histories and service-property semantics
  separate from evidence and the evidence-policy decision procedure.
- Specify failure, success, nonresponse and inconclusive outcomes; avoid
  equating a monitor signature with a physical certificate.
- Use adversarial negative tests, independent Python reference models and
  real-EVM Foundry/Anvil runs, then progressively cross-host measurements.
- Freeze versioned source, chain ID, contract address, immutable parameters,
  environment versions, test manifests, raw signed evidence and tx receipts.
- Report limitations of trusted randomness, fake laboratory keys, time
  manipulation, collusion, evidence withholding, Sybil identities,
  centralized RPC, single-host observations and missing finality proof.
- Do not increase claimed scientific progress on tests not yet executed;
  do not treat source test definitions as observed results.

## R0–R11 engineering tracks

R0 canonical reproducible source baseline: accepted in tracker.
R1 physical-service evidence truth/soundness: open.
R2 financial conservation, residual policy, governance: open.
R3 bounded scalable monitor registration, seed, fairness, liveness: open.
R4 signatures, archive, chain provenance, trusted finality: open.
R5 autonomous roles, wallets, UI: open.
R6 reproducible Ubuntu onboarding and discovery: open.
R7 remote compute, storage, HTTP, OCI/API workloads: open.
R8 read-only chain observatory and reconciliation: open.
R9 multi-VM and adversarial test campaigns: open.
R10 quantified comparisons and publishable analysis: open.
R11 independently reproduced research release: open.
Separate P-series (P0–P6) cover novelty, theory and manuscript work.

The published 2026-11-14 tracker cited planning estimates approximately
R0=100%, R3=38%, R4=38%, overall engineering/research/project=26%.
These are **internal project planning percentages**, not security scores.
Later WP09F–WP09L code was merged into main on 2026-11-14; stale branch
README headers written before merge must not override actual Git history.

## Monitor/entropy research

WP09A: pre-epoch confirmation timeout and standby replacement.
WP09B: no 32-lifetime-identity ceiling, bounded live roster/window.
WP09C: delayed blockhash seed, not an ungrindable VRF.
WP09D: lab RSA root verified using EVM modexp, insecure public key; 
withholding and custom-encoding proof concerns remain.
WP09E: global active roster root/20-level Merkle proofs, at most 10
deterministic sampled leaves for four selected monitors and standbys.
Not Sybil-resistant, not fully churn-robust, nor an audited VRF.
WP09F–WP09I: offline randomness, liveness, policy, reroll modeling.
WP09J–WP09K: simulated VRF v2.5 adapter with callback authentication,
subscription-spend, closed-lease and reentrancy protections.
WP09L: consumer-prepaid native-ETH fee, bounded request quota, atomic
refund/credit/purchase paths. Fee is NOT a proven bound on real
LINK/native VRF coordinator charges. Integrated Solidity was authored
but still needs a fresh **manual local Foundry build/tests/EVM experiment**;
do not claim those source paths have passed from Python-only results.

Historical tracker records assorted hosted and local tests; these are
past results, not authorization to run Actions again. The newest merge
commit #27 is 7e86edb9 on 2026-11-14. No real 4-validator QBFT network
is confirmed from that merge.

## Last user-state constraints (2026-11-15)

The user requested realistic multiple blockchain nodes and consensus,
research-backed block interval/block capacity, miner/validator roles and
incentives, not just one Anvil mining engine. They were at an Ubuntu VM
under the working directory named sse-r7-onboarding, reporting private
address 10.50.56.8/24 and Docker interfaces. The user explicitly said
the latest terminal commands had **not** been run. Treat network and
deployment state as unverified. Do not assume git remote, branch, Docker,
Anvil, contracts, key files, or RPC still match an old experiment.

New explicit instruction: **DO NOT USE GITHUB ACTIONS**. GitHub is the
source for reviewed files/commits/branches only; all tests and chain
processes are manually initiated on the user's own Ubuntu VM.

## Decision for the next increment

Implement a separate *manual* four-validator Besu QBFT localhost/Docker
laboratory. It models real distributed consensus messaging and BFT
one-node fault tolerance, but does not provide PoW mining competition,
block rewards, public permissionless consensus, physical independence
or production network security. Values 3s target block period,
6s timeout, 10M gas/block are provisional hypotheses and must be
measured against SSE transaction workloads and network performance.

This lab MUST NOT replace existing Anvil until local genesis,
all-validators block production, fault injection, real contract
re-deployment, cross-node read agreement and wallet integration
are independently evidenced. After that, separate VMs, keys, RPC,
economics and governance are independent work packages.
