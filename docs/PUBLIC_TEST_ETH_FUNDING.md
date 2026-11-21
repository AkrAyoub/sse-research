# SSE public test-ETH funding — permissionless, no master wallet

**Date:** 2026-11-19. **Status:** source-level *candidate implementation* and tests in PR #35; **NOT deployed, funded, or tested on new public PoS chain31340**. The no-central-admission policy is in `docs/DECENTRALIZATION_INVARIANTS.md`.

## What "automatic funds when joining" means

1. On a fresh Ubuntu VM, an outside-owned PC or independent host, the local installer obtains the network's exact public signed/hashed genesis/release **without a private GitHub account or SSE operator approval**. It independently generates its encrypted EOA wallet(s) and validator BLS keys as needed; private key material never leaves the owner's machine.
2. Requested role list selects *required* wallets and budget checks, not a role authorization service. `observer` and `full_node` can join and validate with **zero test ETH**. A validator funding wallet needs at least **32 valueless test ETH per BLS deposit** plus observed transaction gas; the Beacon protocol, not the faucet or SSE operator, determines activation. A monitor must cover the **actual on-chain `OpenMonitorCommittee.minimumBond()`** plus registration/probe gas; a provider needs transaction gas and any future chain-defined collateral; a consumer needs transaction gas plus its **actual chosen lease's escrow/incentives**. Sums must be queried/estimated from a pinned chain and actual transactions, not guessed constants.
3. A public ownerless `OpenTestEthFaucet` contract may provide initial chain-native funds from transparently provisioned reserves. No owner/pauser/admin/beneficiary. ANY participant with gas can call `claimFor(recipient, tier)` and submit the on-chain transaction, including as a volunteer sponsor on behalf of a zero-balance newcomer. The native ETH goes to the recipient; the sponsor never receives it.
4. If a malicious third party claims the small grant before a legitimate validator request, a later validator-tier request may top up the DIFFERENCE. A block-level throughput cap bounds instantaneous withdrawals. Configured grant amounts are immutable, public and must be computed/justified from expected **real** network gas and per-role obligations before launch, not copied from unit-test examples.
5. Joining a public P2P network must NEVER depend on receiving a grant. If no funded sponsor or faucet reserves are available, the node still syncs; funding-dependent on-chain actions remain **pending** with a truthful status/retry. Operators can receive valueless native test ETH from ANY account/donation/pool; a public faucet is convenience, not a gatekeeper. Do not substitute local balance edits, fake RPC responses or synthetic EVM deposits as real live-chain funds.

### The unavoidable Sybil and liveness limit

Valueless free test ETH has **no financial cost**, so even ownerless permissionless claims are vulnerable to unlimited cheaply created addresses exhausting finite reserves. Rate limits do not prevent a patient Sybil drain. No permissionless design can simultaneously guarantee unbounded instant free grants to every new unknown wallet from finite funds and prevent Sybil depletion with zero entry friction. This is a scientific threat-model constraint, not an invitation to install an identity-based central administrator.

Mitigations to design and empirically test **without creating admission authority**:
- permissionless deposits from independent donors; publicly auditable pool holdings and claims;
- multiple independently operated gas sponsors/relayers, no privileged caller rights, independent public discovery of sponsor endpoints, retry/failover;
- optionally multiple independent funded faucet instances or other voluntary native test-ETH transfers (no monopoly, and quantify cross-pool claim abuse);
- immutable per-address and per-block grant caps (partial throughput protection, not Sybil resistance), optional objectively enforceable proof-of-effort schemes if independently justified;
- on-chain grant exhaustion status, rate-limited retries and truthful pending state, no fabricated "funded" role;
- reproducible benchmarks of honest-join success, depleted-pool failure, adversarial wallet spam, independent sponsor outage, delayed activation and fees.

The Ethereum Beacon protocol's deposit contract must be real on our own chain; an invented SSE admin whitelist cannot stand in for its activation queue and validator registry. The standard 32 test ETH deposit (per validator key, on the specified configuration) is NOT a source of faucet funding; it is locked/staked through the actual consensus mechanism.

## Candidate contract boundaries

`contracts/OpenTestEthFaucet.sol` contains an **immutable** two-tier on-chain funding policy (`Application`, `Validator`), public reserve donations, outsider-callable sponsored claims, difference-only top-up and cross-wallet reentrancy guard. Its constructor rejects Ethereum Mainnet chain ID 1 and wrong intended chain ID. Genesis **hash** and final release must additionally be checked by the deployer/orchestrator, since chain ID alone is never a sufficient chain identity.

No privileged funding server, admin signature or shared faucet private key is required **by the contract**; a real funded and willing independent caller still has to submit the EVM transaction. This contract does NOT automatically install clients, generate keys, obtain funds from zero reserve, query the on-chain monitor bond, estimate gas, create consumer escrow, sign transactions, deploy itself or activate a validator. Those require later integration and external live verification.

## Source tests to run in correct GitHub checkout

```sh
forge test --match-contract OpenTestEthFaucetTest -vv
python3 -m unittest discover -s tests -p 'test_sse_fresh_host_probe.py' -v
```

Source tests do not prove an external user was funded. Full deployment acceptance requires:
- [ ] A fresh chain31340 with safe independent genesis custody, measured gas, properly funded reserve, immutable publicly agreed grant budgets, source-verified faucet code and multiple independently operated sponsors.
- [ ] A new *external* wallet with **zero** test ETH is funded on the actual network through a truly unrelated sponsor, with signed successful canonical/finalized transaction, receipt, transfer accounting and observed wallet balance.
- [ ] Validator BLS depositor transacts with 32 actual worthless TEST ETH (plus gas), Beacon sees deposit, activates, and attests. A monitor registers with real observed minimum bond; a consumer funds a real lease; provider truly executes work.
- [ ] Turning off the initial funder/sponsor does not block fresh P2P joining; independently funded alternate sponsors keep requests live where reserves and network participants exist; grant exhaustion remains a clearly diagnosed pending funding state.
- [ ] A Sybil/drain experiment and a third-party low-tier-griefing attempt demonstrate stated limitations and effect of top-ups, without equating per-address caps with human uniqueness.
- [ ] Per-node public HTTPS UI displays actual local wallet, on-chain grant, deposit, bond and escrow status, with locally authenticated consent for any transaction, never automatic key exposure.

**Do not replace the old genesis-funded private chain31339 `faucet` keystore as though that were a public funding solution.** The old code is historic. Contract test example grant amounts are NOT approved final chain policy or academically justified operating budgets.

Related: #32 master, #33 onboarding, #34 per-node UI, #36 no-central-control audit, PR #35 source.
