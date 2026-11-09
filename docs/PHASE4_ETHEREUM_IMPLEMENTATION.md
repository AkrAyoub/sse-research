# Ethereum-Based Implementation: Technical Source Register and Research Exposition

**Scope:** current source snapshot derived from `SSE (2).zip` and a *new*, separate Phase 4 research extension. The new extension is source-level only until compiled and executed in Foundry; its presence does not establish deployment or operational validation. The long-term, permissionless network described in the SSE reference is a system specification, not a running Ethereum deployment.

## 1. Ethereum execution, consensus and node responsibilities

1. **Production architectural target:** Public, permissionless Ethereum, whose network state is secured by proof-of-stake. Consensus is supplied by Ethereum's execution, consensus and (for validators) validator clients. SSE neither implements a blockchain consensus algorithm nor elects validators.
2. **Development environment:** Locally running Anvil EVM with chain ID 31337 in the recorded experiment. Anvil processes transactions and changes simulated block time, but it is not independent proof-of-stake consensus and does not establish permissionless validator participation.
3. **SSE node:** A machine running an application client/agent capable of reading chain state and signing/submitting transactions via RPC. Its consumer/provider/monitor/executor roles are application roles, not blockchain-validation roles. A machine may optionally run its own Ethereum execution/consensus clients, but no SSE role requires a validator.
4. **Monitor quorum:** The 3-of-4 monitor classification threshold is **outside** blockchain consensus. The current committee is contract-managed and uses a trusted `randomnessSource`, unlike the approved verifiable-selection target.
5. **Future distributed packaging:** Versioned GitHub monorepo, automated Ubuntu installation, role selection, outbound discovery/NAT traversal, provider-specific plugins, node console and central read-only observatory are described in the approved target. They are not implied to exist by the current contracts.

## 2. Keys, authentication and registration

- Ethereum externally owned accounts use secp256k1 cryptographic keys and address-based authorization. An account is free to act as a consumer for one lease, provider for another, monitor candidate for others, and/or settlement executor.
- Provider and monitor messages use EIP-712 typed structured signing. In the contract `EIP712("SSESettlement", "1")`, the signing domain includes chain ID and verifying contract address; the message additionally includes lease/epoch identifiers and request/evidence commitments.
- **Acknowledgment:** `ProviderAck(uint256 leaseId,uint256 epochId,bytes32 requestHash)`; it can remove `N` only when accepted before `evidenceClose`.
- **Response authentication:** `ProviderResponse(uint256 leaseId,uint256 epochId,bytes32 requestHash,bytes32 responseHash)`; it authenticates the deterministic expected response commitment, not historical HTTP receipt or timing. Current submission is permitted through monitoringClose, which may be after responseDeadline.
- **Monitor report:** `MonitorVote(uint256 leaseId,uint256 epochId,bytes32 requestHash,uint8 outcome,bytes32 responseHash,bytes32 evidenceHash)`; signer recovery must identify a confirmed selected monitor. The report signature authenticates attribution, not the physical truth of the observation.
- **New residual agreement:** `ResidualAgreement(uint256 leaseId,uint256 epochId,uint256 unresolvedAmount,uint256 providerShare,uint256 consumerShare,uint256 nonce,uint256 expiry)` requires both consumer and provider EIP-712 signatures. The contract enforces equal funds, authorization, and a one-shot terminal flag. The `nonce` is an agreement identifier; the terminal flag is the operative replay barrier for one resolution per epoch.
- A traditional CA-based PKI is not required to create Ethereum application identities. TLS certificates can separately authenticate HTTP endpoints; private keys must remain off-chain. The code does not deploy a PKI or verifiable clock oracle.
- Monitor registration in `OpenMonitorCommittee.register()` is open to any address depositing the minimum bond while lifetime capacity remains. Candidates cannot exit while selected or pending. A provider/consumer cannot monitor its own lease. This contract presently caps lifetime-registered identities at 32, which is **not** the approved scalable membership design; no organizational-independence guarantee exists merely from distinct wallet addresses.

## 3. Deployment bootstrap and contract boundaries

Deployment order and one-time bindings:

1. Deploy `OpenMonitorCommittee(randomnessSource, minBond, exitDelaySeconds, randomnessTimeoutSeconds)`.
2. Deploy `SSESettlement(committeeAddress)`.
3. Deploy `OpenResourceBoard()`.
4. Bind `committee.bindSettlement(settlementAddress)`.
5. Bind `settlement.bindResourceBoard(boardAddress)`.
6. Bind `board.bindSettlement(settlementAddress)`. This latter binding confirms that settlement has already registered the board.

The bootstrapper has one-time wiring powers, not a general ability to move arbitrary user escrow. The randomness source remains a privileged **evidence-selection** dependency and is not permissionless in the current implementation. All roles communicate with contracts via EVM transactions/RPC. The contract deployer is not a network validator by virtue of deploying contracts.

### Contract inventory

| Source | Status | Responsibility |
|---|---|---|
| `contracts/OpenResourceBoard.sol` | Active | Requests, bids, consumer choice and atomic lease funding through `chooseBidAndFundLease` |
| `contracts/OpenMonitorCommittee.sol` | Active | Bonded candidate roster, snapshot-based four-member selection, timeouts, bond locking and release |
| `contracts/SSESettlement.sol` | Active | Escrow, epochs, EIP-712 provider/monitor reports, three-history bounds, exposure, withdrawable credits, and Phase 4 opt-in extensions |
| `contracts/SSEBoundsPure.sol` | Reference model | Pure `N/F/S` lower/upper/refund/retained calculation; not imported into the active settlement function |
| `contracts/OpenMonitorBondPool.sol` | Legacy | Earlier standalone bond pool; not used by the active committee path |

The active system is three primary contracts. `SSEBoundsPure` is a separate calculation reference, not an additional on-chain consensus authority; the legacy bond pool should not be drawn as an essential current component.

## 4. Lease creation, admission, evidence, and settlement

### 4.1 Resource marketplace and lease commitment

1. Consumer `requestResource(profileHash, slaPolicyHash, maxEpochFee, biddingClose)`.
2. Any other account `placeBid` while bidding remains open; no global provider whitelist.
3. After close, consumer `chooseBidAndFundLease` and supplies a `LeaseConfig`; `OpenResourceBoard` assembles `LeaseTerms`, and forwards exactly `epochFee*maxEpochs` wei to `SSESettlement.createLeaseFromBoard`. This is atomic: on failure, bid selection reverts too.
4. A development-only direct `createLease` path exists. It does not populate a nonzero SLA-policy hash (unlike marketplace-funded leases) and was used by the historical monolithic local E2E controller. Do not describe that demonstration as having exercised the full marketplace.
5. `_createLease` rejects zero identities, same-address self-leases, invalid commitments, `reservationFee > epochFee`, excessive epoch count (>64), insufficient exposure budget, and underfunding. It requests committee selection through the bound pool.

### 4.2 Committee setup

Provider `acceptLease`; trusted randomness source `fulfillRandomness`; any caller `finalizeMonitorCommittee`; each of four selected monitors `confirmMonitorAssignment`. The contract requires all four confirmations before Ready, even though only three matching votes are required later. This is an availability limitation. The current selection takes a fixed-size snapshot from a maximum of 32 lifetime identities. The selection seed is trusted, not cryptographically verified. The proposed target replaces this with a scalable registry and verifiable randomness.

### 4.3 Epoch admission and deadlines

Only the consumer may `admitEpoch(leaseId,requestHash)`. It checks lease readiness, unique nonzero request, available uncommitted service escrow, maximum epochs, and the conservative exposure reserve:

`lease.currentExposure + lease.epochFee <= lease.exposureBudget`.

It admits the next epoch, debits uncommitted escrow, reserves the **full** epoch fee in exposure, sets a deterministic expected response commitment, and derives `responseDeadline`, `monitoringClose` and `evidenceClose` sequentially from blockchain time. This is not an independent proof of external network timing.

### 4.4 Evidence ingestion and quorum

The provider can relay a signed acknowledgement until evidence close and a signed expected-response digest until monitoring close. Selected monitors report Success or Failure with a nonzero commitment to their off-chain evidence; reports must be signed or submitted directly from a confirmed monitor. Failure votes cannot be submitted before `responseDeadline`; success voting requires a registered provider response signature. Reports are unique per monitor and epoch. Any caller can relay up to four EIP-712 signatures in one transaction.

After `monitoringClose`, anyone can `sealMonitoring`. At least three Success votes yields Success; otherwise at least three Failure votes yields Failure; otherwise the outcome is None. These are accepted classifications **under an assumed monitor model**. None leaves all contractual histories possible absent further authenticated provider evidence. Signatures and a quorum do not establish independent organizations or guarantee the truth of external observations.

### 4.5 Three-history computation

Let `mask= N|F|S`, with bits N=1, F=2, S=4. A valid provider ACK eliminates N. Success eliminates N and F. Failure eliminates S. If the mask is empty, settlement reverts rather than arbitrarily paying. The provider is entitled to:

- `F(N)=reservationFee`,
- `F(F)=0`,
- `F(S)=epochFee`.

The contract calculates `lower=min F(H)`, `upper=max F(H)` on remaining histories, then targets provider credit `lower`, consumer credit `epochFee - upper`, and unresolved escrow `upper - lower`. It credits **deltas only**, requires that previously credited amounts do not exceed the targets, and decreases `lease.currentExposure` by the reduction in unresolved exposure. Credits are accumulated in `withdrawable` (pull payments, no external call in `settleEpoch`).

With `epochFee=25`, `reservationFee=5`, and accepted Failure without ACK, `mask=N|F`: provider=0, consumer=20, unresolved=5. Subsequent authenticated ACK before evidence closure narrows to `F`, creating an additional consumer credit of 5. After evidence closes, normal ACK refinement is not available.

### 4.6 Evidence closure and ordinary lease closure

Any caller `closeEpochEvidence` after evidence close, sealing/settling if needed and marking closure. The consumer can `closeLease` to refund unused *uncommitted* service escrow; admitted epochs and disputed portions remain financially accountable. `releaseCommitteeAfterEvidence` allows anyone to unlock monitor bonds once the lease is closed and all admitted evidence windows are closed. It does not distribute retained disputed service funds.

## 5. Phase 4 addition: consent-based residual settlement

`resolveResidualByAgreement(leaseId,epochId,allocation,consumerSignature,providerSignature)` is a candidate source extension. Preconditions:

- The epoch exists, has closed evidence, has positive unresolved exposure, and has not already been resolved by agreement.
- Agreement expiry has not passed; provider and consumer shares sum to **exactly** the current residual amount.
- Both EIP-712 signatures verify against the current lease counterparty identities under this chain ID and settlement contract address.
- The digest binds the lease/epoch, **current** residual amount, split, nonce and expiry; a terminal per-epoch flag forbids reuse.

Effects: set `residualResolved`, clear epoch residual, decrement lease exposure, increase both historical credited amounts, and credit each party's `withdrawable`. No ETH is sent during the transaction. The caller can be anyone with the signed authorizations. Agreement-derived credits are **not** mislabeled as guaranteed SSE entitlements. Subsequent `settleEpoch` on that epoch is disallowed to prevent recomputing evidence-only targets over agreement-derived credits.

If either party refuses to sign, the residual remains in escrow indefinitely; this is an explicit safety/liveness tradeoff, not an omitted fallback policy.

## 6. Phase 4 addition: separately funded protocol incentives

`configureIncentives` is a consumer-only, optional opt-in extension available **once** while the lease is Offered (before provider acceptance). The funded rates are per accepted monitor report, first seal, first settlement, evidence close and committee release. With `m=maxEpochs`, fixed `n=4`, monitor rate `r_m`, seal bounty `b_s`, settlement bounty `b_t`, evidence-close bounty `b_c`, and committee-release bounty `b_r`:

`D_monitor=m*n*r_m`;

`D_executor=m*(b_s+b_t+b_c)+b_r`;

`msg.value` must equal `D_monitor+D_executor` exactly. This is **in addition to** `m*epochFee` already escrowed in service funds. It is not a gas reimbursement mechanism: Ethereum transaction fees are separately paid by transaction senders under the chain protocol.

A selected monitor earns exactly one fixed reward when its authorized vote is accepted. All accepted outcomes—including dissent—are paid equally. Each epoch's first successful `sealMonitoring`, `settleEpoch` and `closeEpochEvidence` transition earns its corresponding one-time executor bounty, provided that bounty was funded. One-time committee release pays a separate bounty. The caller can be any account; the contract—not the caller—selects whether the action is executable.

After the lease is Closed, all admitted epoch evidence is closed, and committee selection is Released or has timed out to Expired, anyone may invoke `refundUnusedIncentives`. The contract credits all unearned monitor and executor reserves back to the consumer **without touching residual service escrow**. The refund is permitted once. A committee-release bounty must have been paid or become inapplicable before refund; this prevents later unfunded claims.

These are opt-in extensions to keep older lease creation, existing test harnesses and user interactions compatible. The fully approved target design would integrate mandatory reward provisioning directly into a versioned lease agreement and make committee size configurable; those are *not* represented as completed here.

### Example complete value conservation

For `maxEpochs=2`, service fee 25, and incentive rates monitor=2, seal=3, settlement=5, close=7, release=11:

- Service escrow: 50 wei.
- Monitor budget: `2*4*2=16` wei.
- Executor budget: `2*(3+5+7)+11=41` wei.
- Initial contract funding: 107 wei.
- If the first epoch has four valid reports and an ambiguous N/F Failure, while the second epoch is never admitted, the payouts before withdrawal are: consumer guaranteed refund 20 + unused service 25 + unearned reward budgets 23 = 68; monitors 8; executors 15+11=26; provider 0; residual held 5. This satisfies `68+8+26+5=107`.

## 7. Storage, ETH transfer, and gas auditing

| Layer | Data and authority | Explicit limitation |
|---|---|---|
| Ethereum transaction history | Signed transactions, gas, logs, transaction receipts, external/internal value movement | Network records do not attest external HTTP truth |
| EVM contract state | Lease terms, monitor addresses, bonds, vote counts, commitments, epochs, service escrow, credits, outstanding exposure, separately funded reward reserves and agreements | Does not contain complete raw service observations |
| Off-chain immutable/retained evidence | Signed HTTP request/response records, probe measurements, Docker output, service policy and resource descriptors, witness traces | Requires availability, integrity verification and privacy controls |
| Off-chain indexer/UI | Queryable read-only financial and operational view; VM/node status; research metrics | Never authoritative for transfers or quorum decisions |

A monitor's evidence hash commits to an off-chain record but does not prove its accuracy, timestamp, or retention. The contract does not duplicate network-level gas charges in its `withdrawable` ledger. Ether value is withdrawn by the beneficiary using the checks-effects-interactions pattern with a reentrancy guard.

## 8. Limitations and readiness register

| Topic | Inspected baseline | Phase 4 source extension | Approved design still outstanding |
|---|---|---|---|
| Contractual SSE bounds | Implemented with N/F/S mask | Preserved | General history sets and richer SLA predicates |
| Exposure-based admission | Full next fee reserve | Preserved | Tight upper bounds for correlated obligations |
| Open monitor registration | Bonded; 32 lifetime identities | Unchanged | Scalable unbounded candidate lifecycle |
| Lease-specific monitoring | Four selected/confirmed monitors, 3 votes | Unchanged | Configurable n/f/q and bounded acceptance recovery |
| Selection randomness | Authorized unverified seed | Unchanged | Proof-verifiable, bias-resistant selection |
| Protocol rewards | Absent | Separately funded optional fixed rewards | Mandatory policy-bound funding and gas/cost experiments |
| Residual escrow | Can remain locked forever | Requires bilateral signatures for optional release | Arbitration-free liveness cannot be assured absent agreement |
| Provider response | EIP-712 digest authenticated on-chain | Unchanged | Provider-signed HTTP receipt and trusted timing policy |
| Ethereum consensus | Anvil local EVM | Unchanged | Deployment on an actual permissionless Ethereum network |
| Distributed VMs | Local orchestrator; Docker compute | Unchanged | Automated SSH-free bootstrap, NAT traversal, modular role agents |

**Compiler/validation boundary:** Current isolated execution environment has no Foundry/Solidity compiler. Eleven new Foundry test cases were created but cannot be compiled or run here. Four new Python typed-message tests and the existing Python suite were exercised with a *temporary test-only* Keccak fallback after verifying it against standard Keccak-256 vectors. A real local `forge build && forge test -vv` is mandatory before claiming the new Solidity extension is verified. The fallback is not packaged as a runtime dependency.

## 9. Source-backed submission pseudocode candidates

**Algorithm A — `admitEpoch`:** Verify consumer and lease readiness; require unique request; ensure uncommitted escrow and exposure capacity; create fee-bound epoch; assign challenge commitment and three deadlines; reserve fee in unresolved exposure; emit `EpochAdmitted`.

**Algorithm B — `settleEpoch`:** Require monitoring sealed; start with {N,F,S}; filter with signed ACK and monitor outcome; reject empty set; compute lower and upper; prohibit decreases in previously guaranteed credits; credit only deltas; update retained exposure; emit `SettlementUpdated`; issue at most one separately funded executor bounty (new extension).

**Algorithm C — `resolveResidualByAgreement` (new extension):** Require closed evidence and positive unresolved; validate exact split and expiry; verify both EIP-712 signatures; mark terminal, move exact residual to authorized credits, and clear exposure. Explain that this step is contractual resolution and **not** SSE-guaranteed settlement.

## 10. Validation and research traceability

Research results from earlier local Anvil + Docker runs are retained only as evidence for the original protocol: a local successful compute epoch and an ambiguous-failure settlement. The new economic and consent extensions have not been included in those historical experiments. A publication-quality empirical claim must distinguish the different source versions and provide reproducible contract addresses, transaction hashes, evidence digests and experiment parameters.

**External authoritative specifications:** EIP-712, <https://eips.ethereum.org/EIPS/eip-712>; Ethereum node architecture, <https://ethereum.org/developers/docs/nodes-and-clients/node-architecture/>. They should enter the article bibliography when cited. Existing cloud and SSE prior-work references retain their separate research roles.
