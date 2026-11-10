# R1 WP-05 — Asynchronous monitoring, clock uncertainty, Byzantine reports and Solidity mapping

**Status:** provisional research / source-traced shadow model. 2026-11-09. Not a Solidity bytecode test, not a cryptographic prover, not an attack deployed against a network. **Production contracts remain unchanged.**

## 1. Precisely what was inspected in the existing source

Inspected GitHub `main` `contracts/SSESettlement.sol` at 2026-11-09 and compared named transition predicates with an archived WP-01 source copy. The Solidity contract was unchanged between these snapshots for the inspected rules. See in-repo contract at lines approximately 320–511 (line numbers may move in later revisions):

| Solidity transition | Existing explicit guard / action | WP-05 reference implementation |
|---|---|---|
| `admitEpoch` | `block.timestamp + responsePeriod` => `responseDeadline`; then monitoring grace => `monitoringClose`; then evidence window => `evidenceClose` | `EpochTerms` deadlines; assumes admitted epoch and preselected confirmed 4-member committee |
| `submitAcknowledgment` | provider EIP-712 signature; block timestamp <= evidenceClose and evidence not closed; one ACK | `EpochShadow.acknowledgment(authenticated=True)`; `authenticated` is a **stipulated cryptographic verification result** |
| `submitProviderResponse` | provider EIP-712 response signature; block timestamp <= monitoringClose, monitoring not sealed; one response | `EpochShadow.provider_response(authenticated=True)` |
| `_recordAuthorizedVote` | committee member, confirmed monitor, one vote; nonzero evidence hash; <= monitoringClose; failure only when block timestamp >= responseDeadline; success requires provider responseAuthenticated | `EpochShadow.monitor_vote` includes the listed predicates; `authorized` and `evidence_present` are stipulated, not verified cryptographically |
| `sealMonitoring` | block timestamp strictly greater than monitoringClose; 3 success => Success, else 3 failures => Failure, else None | `EpochShadow.seal` |
| `settleEpoch` | mask `{N,F,S}`; ACK removes N; Success removes N/F; Failure removes S; lower=min entitlement, upper=max; only credit deltas; no increase in unresolved exposure | `EpochShadow.admissible_after_contract_filters()` and WP-02 generic `evaluate()`; no transfer, no gas or contract runtime simulation |
| `closeEpochEvidence` | block timestamp strictly greater than evidenceClose; seals if needed, settles, closes | `EpochShadow.close_evidence` |

**What the source already does correctly:** checks identity and cryptographic signature recovery, binds signed data to domain-separated lease/epoch/request and response hash, prevents duplicate monitor votes, requires a verified provider response before positive votes, enforces inclusion windows, retains partial uncertainty where quorum is missing, and avoids re-crediting previous settlement amounts.

**What source guards do not establish:** physical provider request arrival; correctness of the underlying service, consumer delivery, monitor vantage independence, honest off-chain reports, or external wall-clock accuracy. A timestamp evaluated by the contract is the timestamp of an included on-chain transaction, not a cryptographically proven timestamp of a remote HTTP event.

## 2. Network fault model

A monitor can send a probe at real time `t_send`, set a local timeout threshold `t_timeout`, and receive a valid response only at `t_arrival`, possibly after its timeout or never. It may truthfully report a local timeout when `t_arrival > t_timeout`. This does **not** imply the consumer did not receive the contracted result before its own contractual deadline.

The WP-05 `Probe` records these stipulated physical times. The contract observer sees only the monitor's authorized vote, its evidence commitment hash, and the transaction inclusion timestamp. Signature correctness makes a report attributable, not physically correct. An adversary can also control a subset of signed monitor votes without violating the contract's selected-member checks, if those members act Byzantine.

Our toy model enumerates four selected monitors and a three-vote quorum. This is the existing prototype committee shape, **not** an open scalable monitor infrastructure or a proof of committee fault tolerance.

### Counterexample C1 — honest timeouts, physical fulfillment S

With `admitted_at = 100`, `responsePeriod = 10`, `monitoringGrace = 5`, `evidenceWindow = 8`, the chain deadlines are 110, 115, and 123 respectively.

1. Assume the agreed SLA is consumer-delivery fulfillment. The service executes and the consumer receives a correct result at simulated physical time 108: the true physical world is `S`.
2. Three monitors send probes at 103, time out locally at 109, and would get a valid delayed response only at 113. The monitors are not dishonest; their timeout **observations** are true.
3. Each selected monitor's Failure vote is included at chain timestamp 110, satisfying `>= responseDeadline` and `<= monitoringClose`. The fourth monitor may abstain.
4. At chain timestamp 116 (`> monitoringClose`) `sealMonitoring` sets Failure because there are three such votes.
5. `settleEpoch` excludes S. With no ACK its remaining history set is `{N,F}`, and for `fee=25`, `reservation=5` the consumer receives 20 and 5 remains unresolved.
6. But under the stipulated actual S, the consumer's legitimate refund is 0. Therefore 20 is an *overcredit relative to the physical SLA* — not an arithmetic conservation failure.

**Conditions required for a real reproduction:** the specified SLA fulfillment must actually be met; the provider service/network must permit consumer delivery while three selected monitors time out; authorized monitor votes and transactions must satisfy exact chain gates. WP-05 proves only this **conditional model execution**, not that the production deployment has been attacked.

### Counterexample C2 — ACK + honest timeout

If the provider also submits an authentic EIP-712 ACK, the current contract removes N. A three-vote failure outcome then retains `{F}` only. The consumer is credited all 25 although the stipulated physical history is S. The signature authenticates the provider statement; it does not change the fact that monitor timeouts may be a communication failure. This makes the potential error *larger*, contingent on the consumer-delivery SLA.

### Counterexample C3 — positive quorum and consumer nonreceipt

Suppose the provider signs the expected response hash and three selected monitors cast eligible Success votes. The contract can filter to `{S}`. But the consumer may still have received no correct result by its contractual deadline. Under a **consumer-delivery** service SLA the true history is F, making the 25 provider credit potentially excessive. The existing provider signature requirement prevents success votes without a signed expected response hash; it does not prove consumer delivery. Under a *provider-result-generation* SLA, the same trace may have different contractual truth, which illustrates why R1's service terms matter.

### Counterexample C4 — provider response accepted during monitoring grace

The contract requires a valid provider response transaction to be included by `monitoringClose` (115), **not** necessarily by `responseDeadline` (110). Its positive vote rule checks `responseAuthenticated`, without a separate test for an externally trusted response-event time. A provider can therefore submit a response signature at chain time 114, and three selected monitors can submit positive votes at 115; sealing at 116 yields Success, even if the *stipulated physical service result was only produced and received after the contractual deadline 110*. Under a contract whose fulfillment predicate includes consumer delivery by 110, the true physical world is F and the full 25 provider credit is excessive. **It is not sound to infer from inclusion time 114 alone that physical completion was late**; a timely response might have been included late due to chain latency. The problem is the **absence of independently established physical response time** while the policy treats the authenticated response/vote as conclusive. This is a distinct conditional counterexample, not an executed EVM exploit.

### No false opposite quorums with four one-vote monitors

Three success votes and three failure votes cannot simultaneously be collected when only four distinct selected monitors each cast at most one vote. The `if ... else if` priority therefore does not create two simultaneous opposite quorums in the assumed four-person design. This **does not** solve quorum-to-truth soundness.

## 3. On-chain versus physical time and clock uncertainty

There are at least four distinct times:

- **Physical service event time**: when a request actually reaches a process or correct output reaches the consumer.
- **Monitor local time**: what a host clock displays when its agent observes a timeout or response.
- **Transaction inclusion time**: the `block.timestamp` used to decide whether signed evidence may enter the contract.
- **Contractual SLA deadline**: the service property defined by the lease, which may not be the same as transaction admission window.

WP-05 `BoundedClockReading(reported_at=t, max_error=ε)` models the external *conditional assumption* that actual event time lies in `[t-ε, t+ε]`. For deadline D:

- `t+ε <= D` is **certainly timely**;
- `t-ε > D` is **certainly late**;
- otherwise **unknown**.

Example: signed monitor timestamp 110, assumed maximum error 2, SLA deadline 110 => physical time could be 108 through 112; neither success-before-deadline nor failure-after-deadline is established. The model does **not** verify that a remote clock's claimed error bound is truthful. NTP jitter/dispersion are performance estimates, not automatically Byzantine-safe proof. Note also that chain inclusion after the deadline does not imply the off-chain event was late, and an included vote after a deadline does not prove its corresponding probe observed a post-deadline failure.

## 4. Research comparison and what should be adapted

- **Dwork, Lynch and Stockmeyer (JACM 1988), _Consensus in the Presence of Partial Synchrony_.** Network delay assumptions and stabilization matter. Adopt **explicit asynchronous/partial-synchrony fault scenarios**, but do **not** claim SSE is solving the consensus problem or inherit consensus guarantees for cloud SLA truth. Source: https://research.ibm.com/publications/consensus-in-the-presence-of-partial-synchrony
- **Chandra and Toueg (JACM 1996), _Unreliable Failure Detectors for Reliable Distributed Systems_.** Failure detectors can make mistakes; accuracy and completeness are distinct. Adapt **suspicion versus conclusive contractual failure** terminology. Source: https://research.ibm.com/publications/unreliable-failure-detectors-for-reliable-distributed-systems
- **RFC 5905, NTPv4.** Explicit offset, delay, jitter and dispersion estimates support *measuring* clock uncertainty. Do not treat server-reported time bounds as cryptographically certified physical times. Source: https://www.rfc-editor.org/rfc/rfc5905
- **EIP-712 typed structured data.** Provides authenticated message hashing/signing and domain separation, not proof of external service delivery or event time. Source: https://eips.ethereum.org/EIPS/eip-712
- **SSE actual source.** The named transition gates in `contracts/SSESettlement.sol` are the relevant implementation evidence; this independent reference is only a source-traced *shadow*, not an execution of the contract bytecode.

## 5. Implementation decisions

### Implement now, in R1/R4 research SDK (without monetary policy activation)

1. Canonical, versioned **event-type and service-SLA claims**, with caller/role identity and raw evidence hash; keep observation and assertion different types.
2. Publish explicit **clock-domain and uncertainty metadata**, including which clock produced a timestamp. Treat time as unknown if a trusted bound is unavailable.
3. Track **on-chain inclusion timestamps separately** from physical service timestamps and captured monitor-local times.
4. Store monitor outcomes as **positive observation, negative observation, or inconclusive**, not as authoritative N/F/S physical classifications.
5. Record and expose **policy assumptions** in the committed SLA, with a versioned rule table of which physical worlds may be excluded and why.
6. Add true on-chain **Foundry differential tests** in WP-06 for all relevant vote, ACK, response and timestamp branches, plus randomized event orderings. The present WP-05 source guards are insufficient.

### Defer/conditional

- Signed consumer receipt: useful when combined with explicit honest-receiver assumption, result integrity verification, and trustworthy deadline semantics. Refusal to sign must remain possible without automatically proving failure.
- Trusted external time evidence: requires authenticated clocks/oracle and error-bound or trust assumption; increased engineering and trust model.
- Stronger proof of execution/storage: service-specific, cost-heavy and still not proof of external delivery or physical resource leasing.
- Timeout-based final risk assignment: possible only as an **explicit contractual choice** or independently funded arbitration/insurance, not as an unconditional deduction of truth.

### Do not implement or claim

- Transforming 3/4 valid monitor timeout signatures into infallible physical-failure certificates.
- Assuming `block.timestamp` is the real time at which a consumer received bytes.
- Assuming a positive EIP-712 provider response means consumer delivery, correct compute capacity, or storage durability.
- Claiming 45 Python model tests or 120 combined model tests are equivalently strong as an EVM differential security test or a proof over all possible network executions.

## 6. Validation and next gates

- **WP-05 shadow-only tests:** 45 / 45 passed locally on Python 3.13. Includes 2 source-literal guards using a copy of unchanged `SSESettlement.sol`; those guards are not Solidity execution.
- **All research modules WP-02 through WP-05:** 120 / 120 passed in a combined standalone model environment. Existing 106 project Python tests and 35 Foundry tests **not rerun** in this authoring environment.
- Five demonstration results archived in `docs/research/validation/wp05_demo_2026-11-09.jsonl`.
- Model source has NOT been committed or hosted-CI verified yet. Do not connect it to payout authorization.

**Follow-up phase R1 WP-06**: exact Foundry EVM transition tests, real signature fixtures and differential comparison; then adversarial schedule enumeration to contrast conservative world-sound interpreters with current policy, under pre-declared service and adversary assumptions. **P0/P2**: write a formal lemma that authenticated yet observationally indistinguishable executions imply a bound on unconditional safe payouts; verify novelty against fair-exchange and information-theoretic monitoring prior work.
