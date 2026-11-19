# R21 — Adaptive permissionless roles, committee membership and monitoring quorum

**Status 2026-11-19:** binding nonnegotiable target, from user clarification. **NOT YET IMPLEMENTED IN THE LIVE SSE CONTRACTS.** The original PoS31339 is historical and unsuitable. Target fresh chain31340 has no independent network, Genesis or real distributed SLA deployment yet. GitHub issue [#38](https://github.com/AkrAyoub/sse-research/issues/38) is a mandatory release gate.

## The rule: count of nodes performing ANY role is not fixed

Any independent operator, on any infrastructure, may launch one or more of the following roles according to objective protocol requirements. Role count rises and falls from zero to arbitrary physical/network/chain resource capacities. No SSE administrator, allowlist, invitation, central scheduler, fixed RPC, shared Docker host or fixed public IP is a requirement for membership.

| Role | Eligibility and active state | Does an SSE owner get to fix how many may participate? |
| --- | --- | --- |
| Observer/full node | Public Genesis + compatible EL/CL + real native P2P; zero TEST ETH to observe or sync | NO |
| PoS validator | Locally controlled BLS key, actual 32 worthless TEST ETH deposit, Beacon activation; genuine attestation and staking constraints | NO — Beacon validator registry grows and shrinks through deposit/exit |
| Consumer | Local wallet, gas, real escrow/lease terms | NO |
| Provider | Local wallet, independently observed real CPU/memory/network capacity, price and objective bids; optional declared collateral | NO |
| Monitor | Bonded eligible independent candidate, verifiable sampling and evidence; cannot be the observed consumer/provider for the same task | NO |
| Multi-role operator | Any combination whose separate protocol requirements hold; one physical operator may not be treated as multiple independent votes | NO |

**Finite snapshot is not a network cap:** Genesis must have an exact finite initial set and Beacon's actual minimal genesis conditions. Research operators publish independent public-key contributions before genesis; post-genesis anyone can join by actual on-chain deposit. `tools/sse_pos_genesis_contributions.py` now requires *explicit, per-genesis* `--min-operators` and `--min-validators`, with no built-in 4/64 defaults. These thresholds are stated experiment fault-domain assumptions, **not lifetime role limits** or scientific evidence of independence. A per-file 64-KiB limit and bounded number of entries protect a parser, not chain membership; handling a single initial operator with more than that parser budget requires future paginated input support **without inventing additional operator identities**. This local input limit must not be mistaken for a PoS protocol validator or role-membership cap.

## Adaptive quorum per REAL task, not a global fixed 3/4

For each actual lease/monitoring assignment at election time:

1. Identify the complete objectively eligible and bonded candidate snapshot (excluding the consumer, provider, and any provable shared/colluding control). Declare the eligibility rules, snapshot hash, consensus-supported entropy and sampling algorithm. Monitor addresses alone or valueless TEST ETH bond **do not prove physical independence or defeat Sybils**.
2. Before randomness, freeze the terms: threat tolerance `f`, actual eligible population `N`, maximum permissible committee seats for one assignment from measured EVM gas `G`, actual reserved monitoring incentives `B`, guaranteed paid reporting epochs `E` and per-report reward `R`. No post-outcome increase/decrease of quorum by consumer, provider, deployer or monitor.
3. Choose a finite **per-lease** committee `k=min(N,G,floor(B/(E*R)))`, requiring `k>=3f+1`, `f>=1` and actual candidate eligibility/custody. **No amount of budget alone proves independence.** Any failure (too few distinct candidates, budget, gas limit or secure randomness) is an explicit pending/rejected/inconclusive state, not fake additional monitors or quietly lowered threshold.
4. Proposed equal-weight strict supermajority `q=floor(2k/3)+1`. For example `k=4→q=3`, `k=5→q=4`, `k=7→q=5`, `k=10→q=7`. Strictly require the same signed outcome/evidence and prohibit duplicate votes. An outcome becomes final only after the assigned `q` unique monitors provide valid observations inside windows; conflicting, absent, stale or mismatched evidence remains *inconclusive* and follows the previously agreed dispute/escrow path.
5. Deterministic/unbiased-enough sortition must scale to large rosters without central agent approval, include fair open registration/exit, and be resistant to censorship, byzantine withholding and proposer-biased entropy. Independently measure and report physical operator fault domains; bound economic payouts and O(n) calls with on-chain batched processing.
6. The policy's `G` is a gas/transaction bound for **one selected committee**; it must never become an enrollment cap for the **total monitor population**. Public role count is not `k`.

**Mathematical caution:** `k>=3f+1` and `q>2k/3` have useful quorum-intersection properties for an assumed maximum of `f` Byzantine committee seats. They do not establish a Byzantine fault bound in a permissionless costless/Sybil-prone TEST ETH system. Treat as proposed fault model, not a validated scientific security guarantee. Must analyze actual sampling probability against observed diversity/stake/independence, missing reporters, epoch-level retries and budget. Check the real threat model and parameter choices before production.

## Current source reality — RED release blockers

- `contracts/OpenMonitorCommittee.sol` has constant `COMMITTEE_SIZE=4`, `address[4] committee`, `GLOBAL_MERKLE_CAPACITY=1<<20` and fixed proof/snapshot/recovery draw limits. The latter are gas tradeoffs, but one-million-active-candidate capacity in global mode is a **hard pool ceiling**, not acceptable as a global network admission cap. Audit dynamic/scalable roster structures and gas upper bounds.
- `contracts/SSESettlement.sol` has `COMMITTEE_SIZE=4`, `QUORUM=3`, `address[4] monitors`, confirmation/rotation and reward formulas depending on exactly four. Therefore current V1 is **4-seat/3-threshold**, not adaptive despite permissionless candidate registration.
- `contracts/AdaptiveMonitorQuorum.sol` (new R21) and `foundry/test/AdaptiveMonitorQuorum.t.sol` (new R21) are the initial **pure on-chain math and unexecuted EVM unit tests**. They are **NOT YET WIRED** to live allocation, voting, settlement, monitoring agents or escrow. Do not claim public adaptive committee behavior from these tests.
- Solidity migration has to change both contracts' storage and events/ABI together; recompute monitor funding and EIP-712 vote accounting for variable committee size and locked q; maintain fairness, timeouts, standby rotation, honest evidence, fraud-proof/inconclusive conditions, gas, and payout invariants. A one-line change to the `4` or `3` constants is not a safe fix. Review and test new ABI carefully; do not expose a partly upgraded contract to public funds.
- Dynamic per-lease selected `k` is an economic/security model, not the right to unilaterally change active quorum because monitors go offline. Insufficient votes -> no automatic success/failure; genuine inconclusive handling and bounded fund locking are required.
- Validator Beacon quorum and native PoS finality remain the **actual Ethereum protocol**, not an SSE-written voting or PoW mining substitute. Genesis count and network throughput must be experimentally measured, not asserted optimal from an arbitrary number.

## Required tests and actual measured acceptance

- Foundry tests: committee `k` across multiple values, `q` thresholds, proof paths, bounded gas, snapshot freeze, double votes, consumer/provider exclusion, one operator with multiple EOAs, dropout, conflict, equivocation, censorship, malicious entropy source, reward accounting, exact escrow/withdrawal invariants and on-chain actual evidence windows.
- Cross-host: at least two different operators on distinct infrastructures, open native P2P, actual validator deposits/activation, real SLA probes with independent physical monitoring, peer loss and recovery, variable open eligibility, benchmark gas/latency against population and selected `k`. Example test networks may temporarily use finite observed participants; they do **not** impose protocol-wide caps.
- Do not claim success until new contract deployed to actual fresh chain31340, user-run tests pass and independent unprivileged external nodes behave as expected.

## Change-tracking discipline

Every source change via GitHub PR, all VM4706 observed commands/outputs and failures in `docs/experiments/VM4706_2026-11-19.md`, public repo/release installation for outside operators, never uploading EOA/BLS secrets or unmasked logs. Source contract math can be unit tested with synthetic **test inputs only**; **real workload and SLA data may never be invented or simulated**.
