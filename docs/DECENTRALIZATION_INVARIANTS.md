# R19 architecture invariant — NO central admission or control

**Status:** user-confirmed nonnegotiable requirement, 2026-11-19. This is a **design/audit gate**, NOT a statement that the retained Solidity and onboarding code already satisfies it.

SSE is an open, independently operated, Ethereum-compatible Proof-of-Stake test-ETH network. Anyone, including an arbitrary PC outside the developer's university/cloud VM infrastructure, must be able to join and independently verify the chain using public protocol data, without needing an SSE account, a VPN/tailnet invitation, a centrally approved device, a privileged signer, a single network administrator or a static public IP. If a participant runs several roles, only the **objective requirements of each role** determine eligibility.

## Hard prohibition: no central "god control" at any layer

| System boundary | Permitted | FORBIDDEN as mandatory join/control path |
| --- | --- | --- |
| P2P | Native EL devp2p + CL discv5 gossip, any compatible peer, multiple interchangeable bootstrap peers/mirrors | Operator whitelist, tailnet enrollment, permissioned validator list, registry owner approving peers, reliance on one seed remaining live |
| Genesis | One explicit reproducible genesis, checksummed, independently cached and mirrored; independent node chooses which chain to join | Hidden mutable genesis or coordinator able to rewrite history; treating release-signing key as blockchain signing key |
| Consensus | Independently held BLS keys, standard deposit and Beacon activation, on-chain rewards/penalties/exit | One fixed validator roster, shared mnemonic, central approval to become validator, operator forcing consensus votes |
| Network/discovery | Public static artifacts across multiple mirrors; independent peer discovery afterwards, DDNS/ENR update; optional relays | A required API/broker to grant every new node membership, hardcoded one RPC, static IP requirement, one central routing hop for all P2P |
| Software | Reproducible verifiable clients, signed releases from accountable publishers, hash-pinned immutable versions and several distribution mirrors | Mandatory GitHub personal account/token; private repo invitation; remote forced update; one publisher key deciding who can join |
| Test ETH | Disclosed distributed genesis allocations and/or independently replaceable permissionless faucets; deposit is ordinary consensus transaction | One discretionary faucet operator approving all validator deposits or arbitrarily blocking entry by identity |
| Resource market | Public resource advertisements and bids, consumer escrow, independent provider execution, public verifiable settlement contract | One marketplace owner selecting winners, giving role permissions or unilaterally reallocating escrow |
| Monitoring | Permissionless bonded registration; verifiable unbiased-enough committee election under documented threat model; independent evidence and bounded votes | One VRF/seed operator controlling committees, one required evidence server or monitor administrator approving monitor membership |
| Node UI | Every node serves **its own** public HTTPS browser UI with owner-authenticated controls, data locally derived from chain/agent | One central dashboard/agent that hosts or controls all node functions, or browser-exposed raw wallet/validator signer APIs |
| Recovery | Local node decisions, independently reproducible state and evidence, fail-closed behavior | Single kill switch, master signing key, central role configuration or owner-controlled rejoin broker |

**Nuance:** every chain has a known genesis and some initial network discovery information. A genesis-creation ceremony and public artifact publishers are unavoidable coordination activities; neither may retain the authority to approve subsequent validators, peers, app operators, votes, upgrades or withdrawals. DNS registrars, public CAs, transit providers and optional relays are outside dependencies; distribute and allow alternatives, document outages honestly. Absolute absence of any Internet infrastructure or third-party coordination is not technically claimable.

**Dynamic IP:** No participant must buy or own a static address. Outbound-only peers may still synchronize and validate. At least some P2P peers must be discoverable/reachable; DDNS does not bypass CGNAT. Each node UI must have an Internet-accessible HTTPS URL, using a substitutable relay/reverse tunnel if necessary, but that relay must not become an authority over blockchain membership or consensus.

## R21 explicit open-ended role counts and adaptive monitor quorum

No maximum number of `observer`, `full_node`, `validator`, `consumer`, `provider`, `monitor` or multi-role participants may be imposed by SSE operator signup, static contract arrays, per-role allowlists or a permanent Genesis roster. Network capacity, actual gas and registration economics still impose physical/operational limits; transparent bounded **per-transaction** work is allowed, but not a hard protocol-wide enrollment ceiling.

**CURRENT PUBLIC RELEASE FAILURE:** `OpenMonitorCommittee.sol` still hardcodes `COMMITTEE_SIZE=4`, `address[4]`, global active Merkle pool capacity `1<<20`, and fixed selection/snapshot sizes; `SSESettlement.sol` hardcodes `COMMITTEE_SIZE=4`, `QUORUM=3`, `address[4]`, fixed confirmations and reward formulas. These are historical executable constraints that contradict the user's adaptive-committee requirement. They cannot be cured safely by editing a constant alone.

A committee is a **finite set per actual lease**, with size and strict supermajority derived from objective precommitted risk, real eligible independent candidates, incentive escrow and measured EVM gas limits. Proposed `k=min(eligible, gasBoundSeats, floor(monitorBudget/(epochs*rewardPerMonitor)))`, with `k>=3f+1` and `q=floor(2k/3)+1`; never silently reduce `f` or quorum because budget/reports are missing. Distinguish mathematical BFT assumptions from observed independence of individual real operators—bonded EOAs on a valueless TEST ETH chain are Sybil-prone. Inconclusive outcomes must not become unilateral slashing or false SLA success. `contracts/AdaptiveMonitorQuorum.sol` is only a candidate pure math helper; **not yet wired to runtime**. See [R21 design](R21_ADAPTIVE_ROLES_AND_QUORUM.md) and [#38](https://github.com/AkrAyoub/sse-research/issues/38) (blocking).

The initial Genesis is necessarily finite, but `--min-operators` and `--min-validators` are now mandatory explicit ceremony inputs, not hidden 4/64 defaults. This is NOT an admission gate for post-genesis validator deposits.

## Existing SOURCE-LEVEL centralization findings — BLOCK public release

Audit current retained code by its exact interfaces and deployment bytecode; do not infer decentralization solely from comments.

1. `contracts/SSESettlement.sol`: immutable `bootstrapper` sets one-time VRF fee policy, binds resource board/adapter, receives prepaid VRF reimbursement; `vrfLifetimeRequestCap` can exhaust. `requestLeaseRandomness` currently has NO `msg.sender == bootstrapper` check, so its comment saying only bootstrapper can dispatch appears **stale/inconsistent**. Need inspect gas/cost/liveness, clarify why bootstrapper fees and caps exist, and remove any residual privilege inconsistent with open operation.
2. `contracts/OpenMonitorCommittee.sol`: immutable `randomnessSource` and pre-binding deployment switches, including proof operator and delayed-block entropy modes. A configured source can censor/withhold or bias assignments; delayed blockhash is proposer-biasable, experimental RSA signer can withhold, and neither is proven permissionless/unbiased at deployment. Need define and benchmark a trust-minimized, robust sortition/entropy policy, including fallback/penalties/liveness and honest operator-independence assumptions.
3. `contracts/SSEVRFV25Adapter.sol`: `pinnedCoordinator` is fixed at deployment and must exist and remain available. A Chainlink coordinator is NOT automatically present on our fresh custom chain. Never silently install a test/mock coordinator as the live mechanism or call this decentralized.
4. `contracts/OpenResourceBoard.sol`: `bootstrapper` performs one-time settlement binding. Must verify there is NO continuing admin path affecting consumer/provider bids and escrow, and prove binding is immutable/correct.
5. SSE PoS scripts and role wallets still hardcode private historical chain31339 and one machine's named wallets. A fresh chain31340 must use locally generated identities, independently downloaded authenticated config, public P2P, not a coordinator's seven-wallet file.
6. Earlier role-agent/portal/mesh enrollment used Tailscale, admin invitations, localhost-only UI; they are archived, **not** public network dependencies. The first new source preflight and signed public manifest validator are NOT full node onboarding.
7. The future TEST ETH distribution mechanism must not grant discretionary individual admission to validators. Because test ETH is valueless, real Sybil cost/security assumptions are weaker than Ethereum mainnet. State this limitation in scientific claims.

## Evidence-based acceptance: mandatory independent adversarial checks

- [ ] An outside operator who never communicated with the project owner obtains exact public chain configs/release from an **independent mirror**, syncs via native EL+CL P2P after original seeds go offline, and gets the same canonical chain.
- [ ] An outsider with locally created keys and enough public TEST ETH deposits 32 test ETH and becomes active under Beacon rules; all operator-specific eligibility is verifiable on chain, no invitation or whitelisting.
- [ ] No service held by the original deployer can block honest peer admission, transaction inclusion, payouts, monitor candidate registration, resource bidding, or validator exits simply by being turned off. If any liveness limitation exists, it is measured, documented and fixed before acceptance.
- [ ] No privileged production functions remain that allow arbitrary admin freeze, role denial, roster replacement, contract fund seizure, arbitrary seed injection or unilateral selection overriding objective protocol rules.
- [ ] Open monitoring works under loss or malicious behavior of a randomness/faucet/discovery publisher, including explicit inconclusive outcomes, economically bounded penalties, and transparent security assumptions.
- [ ] Anyone can inspect node-specific public HTTPS UI, while only the node owner with its own keys can authorize node changes. Nodes need neither shared central account nor global controller.
- [ ] All actual claims backed by independent-host measurements and chain receipts. Unit/mock/test manifests and same-owner multiple VMs are never substituted for actual decentralization.

## Implementation discipline

Every change must be committed to GitHub through an isolated branch/PR with evidence, reproducible steps, precise ref, tests, security/failure observations, and a tracked explanation of any bug and fix. Record manual actions as **automation gaps**. First experiments may involve manual provisioning; final onboarding must require only a trusted one-time install consent and selection of role(s), with explicit owner consent for transactions and custody.

Related issues: #32 overall; #33 new VM/external onboarding; #34 each node's public UI; PR #31 historical cleanup; PR #35 first fresh-host probe. **Do not merge a declared "decentralized" runtime without the above gate.**
