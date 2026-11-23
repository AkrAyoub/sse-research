# SSE blockchain: complete participant roles, permissionless invariants, scaling, and eight-VM experiment

**Research teaching/engineering reference — 2026-11-21.**
**Network:** independent Ethereum-compatible Proof-of-Stake chain, chain ID **31340**, with **worthless TEST ETH**, never Ethereum Mainnet.
**Classification:** the architectural requirements below are normative *targets*. Verified implementation and remaining gaps are explicitly distinguished. This document does not claim that a new validator, paid cloud lease or independent WAN monitor has been activated.

## 1. Three separate layers, never conflated

1. **Native blockchain layer:** Besu execution clients (EL), Lighthouse Beacon consensus clients (CL), optional Lighthouse validator clients (VC), devp2p/discovery/discv5/libp2p peer networking, execution and Beacon state, block proposals, attestations, fork choice, justification, finality, protocol rewards and penalties. This is real Ethereum PoS, not proof-of-work mining and not an SSE-invented consensus protocol.
2. **On-chain SSE marketplace layer:** EVM contracts for resource requests/bids, eligible bonded monitor pool and committee selection, escrow, EIP-712 authorization/evidence references, voting, bounded financial rights and withdrawal accounting. Contracts do not execute rented CPU workloads: every verifying EVM node deterministically executes *contract* transitions.
3. **Off-chain physical service/evidence layer:** independent provider-hosted workers and storage/HTTP services, consumer-signed requests, real measurements and result delivery, monitor probes, signed raw evidence, durable append-only provenance and appropriately sound qualification. Physical fulfillment is not established by an on-chain event or a majority vote alone.

**Terminology:** a host is a machine or VM; a node is a running blockchain client stack; a validator is an activated consensus staking identity/key, which can be one among many on one node; a wallet/EOA is a transaction actor, not a human identity; a provider/consumer/monitor is an application role, not a consensus role; an operator is an actual controlling entity/fault domain, which cannot be inferred from EOA count or VM count.

## 2. Participant role matrix

| Role | Actual responsibility | Eligibility, wallet/stake or capacity | Is it a separate blockchain node? | Permissionless admission and restrictions | Present state |
|---|---|---|---|---|---|
| **Full node / verifying peer** | Execute and validate EVM blocks/transactions, follow Beacon consensus, independently check chain data, propagate protocol traffic | Exact public EL + Beacon genesis/fork identity; compatible Besu/Lighthouse or equivalent clients; storage, CPU, RAM, TCP/UDP and valid peers. **No TEST ETH needed** | Yes, EL + CL | Any compatible honest outsider; no inviter, whitelist, fixed IP or admission token | VM4706 and VM4707 real EL/CL, matching checkpoints observed; outside-ISP joining not proven |
| **Independently verifying observer** | Inspect state and finality without signing | A nonsigning full-node stack; 0 TEST ETH | Usually yes for truly independent verification | No separate role approval; observer can later add another role | VM4707 live; R141 real API capture verified |
| **RPC-only observer / wallet client** | Query a remotely operated node for balances/events/state | RPC access and optional verification; often no local EL/CL, no staking | No | Can use any honest endpoint or change providers; a single RPC is a data-availability/trust dependency | Source/API usage exists; independently verified remote service not proven |
| **PoS validator** | When active, perform assigned BLS attestations; propose blocks when selected; contribute to fork choice/finality; earn protocol rewards, incur penalties/slashing where applicable | Independent, encrypted BLS signing key, secure VC/slashing protection, synchronized Beacon, actual standard **32 worthless TEST ETH** deposit per validator in present chain configuration, activation via Beacon rules | VC normally connects to a CL; can share an EL/CL node with other keys | No SSE admin validator whitelist; objective deposit, protocol entry/exit and stake rules; never duplicate one live signer | One original validator on VM4706 signing. Fresh independent deposit/activation not yet verified |
| **P2P discovery / bootstrap peer** | Publish fresh public enode/ENR discovery *hints*, answer native peer connections; may gossip discovered peers | Publicly reachable actual TCP/UDP endpoint or appropriate transport, current peer metadata and appropriate network capacity | Typically an existing EL/CL full node offering discoverability | Directory membership is neither chain membership nor an allowlist; seeds replaceable; no single permanent owner peer | Native VM-to-VM peers verified; R142 source obtains multi-mirror hints, but real public mirrors/address re-advertisement unverified |
| **Relay / NAT helper** | Transport peer traffic when direct reachability fails | Real network connectivity/relay throughput and applicable provider terms | No inherent consensus requirement | Optional/substitutable infrastructure; cannot authorize or censor entry by design | ZeroTier public controllerless overlay used; dependency on its root/relay infrastructure remains |
| **Public RPC gateway** | Serve readonly chain API, relay already signed raw EVM transactions and relevant event queries | Synced full node, controlled HTTP API permissions, rate limits, uptime and bandwidth | Yes if self-hosted; clients can use it remotely | Optional and replaceable; Engine API, signer APIs and keystores must remain private | Loopback-only RPC exists; public hardened deployment not established |
| **Consumer** | State desired resources and price/SLA, fund escrow, select provider bid, submit real lease-bound work, verify results | Own EOA and gas, actual escrow and incentive reserves; potentially no local full node | No | Any wallet satisfying public request/funding rules; no operator approval; cannot rewrite funded SLA retroactively | Resource board and consumer software exist; real 31340 funded end-to-end lease not verified |
| **Resource provider** | Advertise honestly measured available CPU/RAM/disk/network capability, price; bid; isolate/execute real workloads, sign receipts, uphold agreed SLA and keep logs | Own wallet and transaction gas, actual deployable host capacity, authenticated reachable service; any required collateral | No | Any provider meeting objective bid/profile requirements; not automatically truthful merely from advertisement | Contracts and real HTTP/compute adapters exist; independent live 31340 service not verified |
| **Monitor candidate** | Register as eligible auditor/prober and bond funds | Separate EOA; actual on-chain `minimumBond()` and gas, healthy probe endpoint, sufficient measurement capability | No | Anyone may register if economically eligible; candidate pool not a centrally approved roster | `OpenMonitorCommittee.register/topUpBond/requestExit/withdrawBond` coded/tested; real 31340 bond registration not verified |
| **Selected lease monitor** | Confirm an elected seat, probe actual provider against precommitted policy, sign canonical evidence, cast authorized EIP-712 application-level observations/votes | Registered and valid *selected* seat, provider/consumer independence for that lease, lease/epoch hash binding, current admissible window | No | Selected by verifiable publicly committed policy, **not** administrator assignment; may not attest own lease; timeout alone not physical nonfulfillment | Fixed 4-seat/3-quorum V1 code and multiple evidence labs; adaptive live system not complete |
| **Committee/election executor** | Trigger public callable lease committee selection, recovery, expiry and reassignment transitions | EOA gas, contract state and allowed call constraints | No | Anyone where contract entrypoint is public; contract validates state; cannot force arbitrary winners | Legacy and V2 experimental selections tested; trust-minimized current-chain deployment pending |
| **Settlement keeper / epoch closer** | Submit permitted finalize/seal/close transitions and withdraw eligible credits | Gas and preconditions; may receive explicitly budgeted executor incentives | No | Open eligible calls where allowed; no one discretionary operator may seize escrow; some role-only functions necessarily enforce caller authorization | V1 accounting and experimental V2 implementations exist; sound on-chain live settlement not verified |
| **TEST ETH donor / sponsor / faucet participant** | Provide valueless on-chain gas/stake grants and sponsor newcomers' transactions | Already funded wallets; transparently limited reserves/immutable claim rules | No | Sponsor must not become a gateway to P2P participation. Faucet exhaustion doesn't prevent node sync, only funding-dependent actions | Candidate ownerless faucet and tests exist; no live 31340 deployment or outsider grants verified |
| **Independent research auditor** | Reproduce chain genesis/finality, logs, gas, resource measurements, failure cases and soundness claims | Accessible sanitized evidence and suitable computation; ideally separate operator/control domain | Optional | Anyone may audit without SSE admin permission where artifacts are public; audit reports do not authorize funds | R140/R141 audit tools, journals and laboratory provenance exist; distributed dataset incomplete |
| **Multi-role operator** | Combine any technically compatible responsibilities on one host or across machines | Must meet each role's *separate* objective rules; different local signers where appropriate | Optional | No global one-role-per-host limit, but strict lease conflict and operator-independence analysis | Local role policy enforces distinct wallets and same-node counterparty exclusions; shared human-control detection not solved |

**Critical distinctions:** A *selected monitor* is not a validator; monitor EIP-712 vote is not Beacon attestation. A *resource provider* sells host resources, not consensus block production. A *bootstrap node* is a directory/networking convenience, not an admission controller. A *smart contract* is code executed by the EVM, not a special network node or a server that measures CPU/latency. An EOA address alone is not an independent participant or fault domain.

## 3. Full-node and observer responsibilities, and their scaling

Each independently verifying host runs compatible execution and consensus clients. Besu enforces transactions, gas, balances, account/code state, contract execution and execution payload validity. Lighthouse Beacon tracks validator commitments, slots, fork-choice, protocol votes and finalized checkpoints. They communicate via an authenticated private Engine API. The privileged JWT, Beacon key-manager and validators' private keys stay private; external clients see only permitted P2P and carefully limited RPC.

Peers can join with **zero TEST ETH** if they have exact genesis/fork data and working native P2P. Full-node count may grow without an SSE protocol-set roster. Practical disk and bandwidth requirements increase as history/state grows; if all peers relay to a single bottleneck, liveness/throughput can worsen. Extra nonvalidating replicas do not increase the Beacon attestational stake.

Observer may mean a real nonsigning EL/CL host (trust-minimized observation) or a lightweight application that trusts some remote RPC (lower cost, weaker independent data verification). Do not conflate these proof levels.

### PoS validators, slot competition and finality

PoS **does not mine SHA puzzles**. For each slot, the protocol chooses a proposer among active validators using consensus rules, with attestations from other selected validators. Validators submit signed messages and face protocol rewards/penalties and applicable slashing for violations. More machines or wallet addresses do not automatically earn more proposer rights; those relate to active stake/validator identities. Present configured research chain has a 32-TEST-ETH deposit per validator, a real deposit contract and Beacon activation protocol target. New operators must create their own BLS custody and recoverable slashing protection; never clone VM4706 signer state or genesis.

Finality is fundamentally stake-weighted (roughly >2/3 active attesting stake for Casper-FFG transitions). Ten validators controlled by one human do not prove independent operators. Several VMs with one VC signing key copied to all of them is dangerous double-signing, **not** ten independent validators. An independent host may sign several distinct BLS validator keys but that is still a single operator/fault domain.

Numbers of full nodes, active validator identities, operator organizations and wallets are separate dimensions. We must record them independently.

## 4. Consumer-provider leasing lifecycle

1. **Consumer request:** consumer commits resource profile, SLA policy hash, maximum epoch fee and bidding close under `OpenResourceBoard.requestResource`. Terms must clearly distinguish CPU compute, storage, public-chain publication and delivered physical service; the physical meaning of each SLA is essential.
2. **Provider bid:** any eligible provider submits price with `placeBid`; provider has real measured resources and capacity to honor advertised commitments. A contract cannot prove physical capacity merely by accepting the bid.
3. **Selection and funding:** consumer selects a permitted bid and funds a lease/escrow, such as the board's `chooseBidAndFundLease`, with economically sound monitoring reserves. Avoid counting unsubmitted/off-chain plans as actual transactions.
4. **Lease activation:** provider accepts the exact contractual terms, monitoring committee is eligible/selected/confirmed, and agreed service epochs are admitted. The owner EOA cannot retroactively lower monitoring requirements.
5. **Actual work:** consumer signs a request bound to lease/epoch, provider executes a real worker/container/storage operation on its independently controlled host, records resource consumption, returns signed response/result and any required consumer delivery receipt. No synthetic success or fake latency measurement counts as fulfillment.
6. **Monitoring:** selected independent monitors perform actual probes from their vantage points. Evidence records protocol versions, signed requests/responses, timestamps with clock uncertainty, network/probe failure, resource metering and provenance hashes. One vantage point's timeout is not necessarily provider nonfulfillment.
7. **Outcome and finances:** monitor votes are scoped application claims. Only sufficiently *qualified* evidence can safely reduce physical-world uncertainty. Contract transitions accrue bounded entitlements; unqualified or conflicting evidence stays inconclusive with retained residual funds and documented dispute/timeout rules.
8. **Withdrawals:** provider, consumer, monitors and eligible keepers withdraw their own ledger credits through on-chain transactions, with receipt, gas, block hash, finality and observable balance changes. A source test/mock balance is not a settled real lease.

Current `OpenResourceBoard.sol`, `OpenMonitorCommittee.sol`, `SSESettlement.sol` and provider/consumer/monitor Python services implement parts of these steps. The fixed `SSESettlement` quorum does **not** currently implement the full adaptive research target and the contracts are not verified as a funded 31340 application.

## 5. Registered monitors versus selected committees

Let:
- `N` be registered *eligible candidate* count (not number of VMs or wallets under one operator).
- `k` be selected committee size for a particular funded lease.
- `q` be the precommitted same-outcome, unique-seat voting threshold.
- `f` be an explicit maximum Byzantine-seat assumption.
- `B` be funded monitoring budget, `E` paid epochs, `R` per-seat per-epoch reward and `G` the practical gas/cost-bounded seats for one committee.

The proposed **research design**, not currently deployed production behavior, uses:

```text
k = min(N, G, floor(B/(E*R)))
require k >= 3*f + 1, f >= 1, objectively eligible independent seats
q = floor(2*k/3) + 1
```

Examples: k=4→q=3; k=5→q=4; k=7→q=5; k=10→q=7. The selected committee is finite for each lease; total registrations are **not** capped at four, seven or any fixed selected size. Budget and transaction gas may bound one task without requiring a protocol-wide membership ceiling. Do not lower `q` after seeing a missing vote or outcome to force settlement. An absent, late, conflicting or misbound report is inconclusive; same-outcome quorum does not magically establish physical delivery.

Byzantine-intersection properties assume distinct faults/actors and a true bound `f`. A valueless TEST ETH bond plus many EOAs cannot establish economic anti-Sybil strength or independent human fault domains. Sampling randomness must be publicly verifiable, robust to withholding/proposer bias and operationally available on *our chain*, not merely present as a mocked Chainlink coordinator. Independent contract-side selection, freeze, recovery, incentives and loss-of-quorum behavior are central open engineering/research tasks.

**Present code fact:** `OpenMonitorCommittee.sol` hardcodes `COMMITTEE_SIZE=4`, `address[4]` and a bounded global Merkle population; `SSESettlement.sol` hardcodes `QUORUM=3`. `SSEAdaptiveVoteLedger.sol` and `AdaptiveMonitorQuorum.sol` provide experimental variable-seat accounting and math, but are not a complete wired marketplace replacement. Editing only constants would be incorrect.

## 6. Physical evidence, time and financially safe uncertainty

Three provisional physical histories:
- **N:** no meaningful service delivery/receipt;
- **F:** some receipt or work occurred but the contractual success conditions were not met;
- **S:** successful delivery and fulfillment of agreed obligations.

Signed raw observations, producer acknowledgments, monitor timeouts and EIP-712 votes can be authentic statements about *what was observed* without proving which physical world actually occurred. Distinguish: (a) valid signature, (b) signer eligibility at the correct historically pinned chain block, (c) timing within an honestly bounded interval, (d) objective physical success/failure. These require different proofs and assumptions.

The conservative financial reference treats evidence E as defining lower and upper allowable payment bounds `L(E)` and `U(E)` for contract value `V`:

```text
L(E) <= P <= U(E)
P = L(E)       safely releasable provider portion
C = V - U(E)   safely refundable consumer portion
X = U(E)-L(E)  unresolved exposure held pending qualification/dispute
P + C + X = V
```

These are *research model* variables requiring justified service semantics. A reporter can be honestly mistaken; monitor quorum does not logically imply `World.S`. Unsupported clock assumptions, untrusted RPC finalized labels and same-host tests cannot certify physical-world truth. Do not claim automatic payouts are safe until source/chain/physical evidence integration is reviewed and adversarially validated.

## 7. Permissionless does NOT mean rule-free

Every participant can *attempt* a public protocol action. The network accepts it **only** when deterministic public conditions are satisfied. This is the essence of open, rule-governed participation.

| Action | Valid condition | Invalid central control |
|---|---|---|
| Join full-node P2P | Correct genesis/forks, protocol messages and reachable peers | Owner approval, cloud tenancy whitelist, mandatory SSE signup |
| Activate validator | Locally held BLS identity, valid 32-test-ETH deposit, Beacon queue/activation, protocol duties | Deployer selecting a permanent validator roster |
| Offer compute | Real capacity, valid on-chain bid, compatible service | Project admin manually designating the only sellers |
| Buy compute | Defined policy, wallet, funded escrow | Central operator authorizing buyers |
| Register monitor | Objective bond and registration rules | Private monitor invitation list |
| Selected monitor report | Correct selected seat, eligible lease/epoch, signed bound evidence and open window | Admin supplying desired outcome |
| Settle | Valid admitted evidence, fixed conditions, justified financial bounds and call permissions | Administrator seizing escrow or forcing successful result |
| Query RPC/publish peer hints | Appropriate service functionality | One irreplaceable gateway controlling network existence |

Local role tags and an owner UI only express preferences; they do not grant on-chain committee membership or consensus staking rights. Provider/consumer/monitor on a single host must use distinct locally controlled signers where required and **never count their own resource lease as independently witnessed**. Our current local role policy enforces same-node wallet conflicts; hidden common control across VMs/EOAs remains an explicit research assumption.

Bootstrap resources, public software release mirrors, DNS, ZeroTier relays and third-party Internet infrastructure may be needed for discovery/transport, but no one publisher or relay is entitled to approve network membership. Current R142 automatically retrieves untrusted peer *hints* from multiple HTTPS directories once published; it does **not** implement zero-touch first-boot, cryptographic publisher provenance or verified independent WAN reachability.

## 8. Separate scaling variables; never impose a global role count

```text
F = full EL/CL nodes
V = active PoS validator keys
O = independently controlled operators/fault domains
P = providers with actual capacities
C = consumers
M = bonded eligible monitor candidates
k = selected monitors for one lease
q = threshold for that lease
T = simultaneous live service tasks or leases
```

No requirement `F=V=O=P=C=M=k`. Example illustration only: 50 full nodes, 15 validators, 10 providers, 100 consumers, 30 registered monitors, but per-lease `k=7,q=5`. Neither example counts nor audit report parser quotas are blockchain membership caps.

| Growth | Main resource costs | What to measure |
|---|---|---|
| F grows | Replicated state/storage, EL/CL CPU and native P2P gossip, bandwidth | Peering, finalized agreement, synchronization, disk and propagation latency |
| V grows | Deposits, key safety, attestations/proposals, consensus gossip | Activation lag, missed duties, finality delay, operator/active stake distribution |
| P grows | Real offered CPU/RAM/disk/network, service orchestration | Verifiable committed and available capacity, utilization, isolation, SLA fidelity |
| C and T grow | Contract gas, funded escrow, provider throughput, monitoring | Admission latency, job latency, cost, throughput, exhaustion |
| M grows | Bond/registry cost, public candidacy snapshot and selection proofs | Eligibility fairness, proof size, sampling gas, Sybil pressure |
| k/q grow | Frozen incentive funding, voting gas, evidence verification, outage sensitivity | Cost-versus-failure model, gas, quorum delay, inconclusive frequency |
| Operators/ISPs grow | Coordination complexity, real networking heterogeneity | Genuine failure-domain independence, censorship/partition effects |
| Discovery/RPC grow | Serving bandwidth, public HTTPS/ENRs, outage failover | Newcomer success after original seeds/mirrors disappear |

More full nodes do not automatically increase chain gas throughput; more validator keys under the same owner do not increase independence; more wallet addresses do not prove more honest monitors. Each protocol transaction is gas-bounded but no permanent membership ceiling is accepted as an SSE project design.

## 9. Current machines and immediate allocation

**Actually observed current network:** VM4706 = one original live Besu EL + Lighthouse BN + **one signing VC**; VM4707 = one real nonsigning Besu EL + Lighthouse BN. On 2026-11-21 the VM4707 R141 capture observed chain 31340, EL genesis `0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf`, Beacon validators root `0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd`, execution block 5072, head slot 6682, finalized epoch 204 root `0xfd294df66b8e51553fefba2f3458ffea98f9c1301f5d98162051994bf5f057ed`, 1 EL peer, 1 CL peer, no reported sync/optimistic/offline state.

**Provisioned by operator:** two additional larger VMs (~4 vCPU, 12–16 GB RAM, suitable disk as provisioned), four smaller Ubuntu 24.04 VMs (**2 vCPU, 4 GB RAM, 40 GB disk, CPU only**). Provisioning is **not** proof any blockchain/app software has been installed.

| Host | Intended initial experiment job | Why |
|---|---|---|
| VM4706 | Preserve existing full node + sole live signing VC | No changes or duplicate original BLS signer |
| VM4707 | Preserve existing nonsigning full node, independent observational audits | Existing real finality baseline |
| New large A | Start with independent nonsigning EL+CL; later fresh locally keyed validator after deposit | Test independent native joining before expanding stake |
| New large B | Start with independent nonsigning EL+CL; later fresh locally keyed validator after deposit | Second joining/validator case and failure-domain trials |
| New small C | App-layer monitor candidate and real probe worker | Reduced memory/disk burden; tests remote monitoring |
| New small D | Separate app-layer monitor and timeouts/fault-injection observer | Failure/partition experiments |
| New small E | Real limited-capacity compute provider, own metering | Cannot honestly promise entire 2 vCPU/4 GB to lease while OS runs |
| New small F | Consumer plus distinct-monitor-role capability only for *other* leases | Real workload and counterparty checks |

One smaller machine can later become a full node **if measured capacity supports it**; 4 GB RAM is not a safe blanket promise for Besu+Lighthouse plus app workloads, particularly where current Docker per-container memory limits are each 4 GB. All roles can be reassigned/combined given objective eligibility. Eight VMs are a first experiment size, not an admission limit. Eight VMs under one cloud account/provider are *not* eight independent physical networks or human operators; add outside-ISP hosts for stronger decentralized claims.

## 10. First-boot and dynamic peer-discovery workflow (intended vs actual)

**Target**: a new independent host obtains open-public authentic software/genesis through multiple interchangeable mirrors, performs one local OS authorization, automatically configures its own EL/CL node identities and appropriate transport, reads regularly refreshed publicly discoverable native P2P hints, joins without central permission, verifies ongoing finality, and can independently choose funded roles. Changing or shutting down original VM4706/VM4707 must not require reconfiguration/approval for every newcomer.

**Present**:
- R136: safe independent observer preflight, pinned original archive, actual overlay IPv6 inspection.
- R137: guarded create-once genuine nonsigning Besu+Lighthouse installer, requires local manifest/archive/images/ZeroTier/Docker, one interactive consent; never run on the original two machines.
- R140: read-only real contract deployment runtime/wiring audit on actual 31340 finalized state (no app deployment claimed).
- R141: per-host real EL/CL evidence and offline variable-size fleet comparison.
- R142: two-source dynamic *peer-hint retrieval* into R137, but **no actual public directories have yet been published**, directory provenance/peer identity are not fully authenticated, and dynamic ENR refresh/complete cloud-init installation is absent.

**Not yet**: independently published public release/archive, cryptographically validated rotating discovery, unattended first-boot with reproducible packages, third-host native joining proven, fresh independent BLS deposit and activation, live 31340 economic contracts with adaptive committees, actual remote workloads, independent monitor evidence and safe payout.

No new node is automatically authorized to spend a wallet, sign validator duties or claim role eligibility by local configuration alone. Fresh validator creation must be explicit, secure, recoverable, and protected from double-signing. All old historical chain31339 deploy scripts are *incompatible* with current chain31340 without reviewed migration.

## 11. What tests prove and do not prove

- **Unit/source tests:** protect schemas, signatures, state transitions, guard behavior and EVM logic; do **not** prove a new independently controlled VM is running or delivering real resources. Last operator run at R142 SHA `32a5a768c460cb5ab1bb93f2784834141fc9969f`: **951 Python tests ran, OK, 3 skipped**, no errors/failures.
- **Historical EVM/Anvil and Docker TLS research experiments:** demonstrate actual local EVM transactions, signed HTTP and network-namespace fault cases with explicit lab trust assumptions; do **not** establish Internet-wide permissionlessness or physically trustworthy delivery.
- **Live VM4706/4707 evidence:** real Besu/Lighthouse P2P, chain identity/finality, one original signing validator, not multiple independent validator operators.
- **Needed research acceptance:** (1) unrelated outside-cloud node discovers, joins and verifies correct chain; (2) fresh BLS deposit activates and attests; (3) real public TEST ETH grants with no mandatory owner sponsor; (4) provider and consumer independently fund/perform/receive workload under SLA, with actual CPU/RAM/latency logs; (5) genuinely independent bonded monitors, multiple real `N,k,q` levels, signed evidence with time/provenance; (6) contract accounting of safe payouts/refunds/residuals and actual withdrawals; (7) loss, partition, churn, withheld entropy and malicious participants; (8) no bootstrap owner, registry, RPC, identity service or VRF owner becoming a permanent approval authority.

## 12. Research contribution framing

Our proposed novelty is **not Besu, Lighthouse, EVM or standard PoS consensus**. Candidate contributions:
- conservative uncertainty-aware service settlement that distinguishes raw reports from soundly qualified physical facts;
- adaptive pre-funded committee sizing, evidence-bound voting and explicit inconclusive handling with open monitor registration;
- chain-bound signed evidence and historically pinned provenance under clock uncertainty;
- actual distributed resource leasing/monitoring with empirical fault-domain, latency, gas, throughput and failure analysis.

Some reference models, EIP-712 checks, on-chain settlement/monitor incentives and Anvil/HTTP/TLS labs already exist. Important soundness counterexamples and operational centralization/randomness gaps remain. **Do not claim solved Sybil resistance, unbiased sortition, physically sound automatic payments or better performance than prior work without independent proof and benchmark comparison.**

## 13. End-to-end acceptance example, without synthetic shortcuts

An unrelated consumer with an independently generated wallet joins/accesses chain 31340 and transparently obtains enough TEST ETH for gas and escrow; a distinct provider advertises measured real capacity and accepts a funded lease; at least `k` objectively eligible, bonded, independently controlled monitoring candidates are selected under precommitted verifiable terms; actual requests and results are sent across real host boundaries; each monitor records its own raw signed observations and clock limitations; the policy only qualifies externally justified facts, leaving uncertain residual funds locked; public transactions update accounts and successful withdrawals appear in finalized blocks. Then repeat with different actual `N,k,q`, budgets, failures, and independently controlled operators.

**If any stage is not observed on real machines and final chain receipts, the entire full-stack implementation remains incomplete.**

### Related source files and design references

- `docs/ARCHITECTURE.md` — binding architecture and nonnegotiable permissionless target.
- `docs/DECENTRALIZATION_INVARIANTS.md` — current privilege, source audit, open role rules.
- `docs/R21_ADAPTIVE_ROLES_AND_QUORUM.md` — proposed dynamic `k/q` and limitations.
- `docs/R140_CHAIN31340_MARKETPLACE_DEPLOYMENT_GATE.md`, `docs/R141_REAL_MULTI_VM_FLEET_EXPERIMENT.md`, `docs/R142_DYNAMIC_PUBLIC_PEER_DISCOVERY_AND_VM_SCALE.md`.
- `contracts/OpenResourceBoard.sol`, `contracts/OpenMonitorCommittee.sol`, `contracts/SSESettlement.sol`, `contracts/SSEAdaptiveVoteLedger.sol`, `contracts/OpenTestEthFaucet.sol`.
- `tools/sse_node_role_policy.py`, `tools/sse_pos_r136_independent_observer_preflight.py`, `tools/sse_pos_r137_independent_observer_create_once.py`.
