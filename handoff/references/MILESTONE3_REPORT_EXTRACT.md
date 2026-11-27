# Extracted reference text — Report.pdf

Preserved from the supplied academic PDF. Text extraction only; figures, layout and math may be imperfect. Original PDF remains authoritative. Do not interpret historical prototype claims as current runtime status.

<PARSED TEXT FOR PAGE: 1 / 6>

  Settlement-Sufficient Evidence for Trustless Inter-
              Cloud SLA Enforcement
         Ayoub Akarkouz
Blockchain Application Development
     Al Akhawayn University
          Ifrane, Morocco


    Abstract—Blockchain-based cloud marketplaces enable              independently establish whether an external service was
resource exchange among mutually distrustful participants, but       correctly delivered. Contracts therefore depend on evidence
smart contracts cannot directly verify the fulfillment of external   produced by service participants, independent monitors, or
Service Level Agreements (SLAs). Authenticated service               external oracles [8], [9]. Although digital signatures
observations may remain consistent with several contractual          authenticate the origin and integrity of statements, they do not
histories, potentially requiring different payments. We              necessarily prove that the stated events occurred or that all
investigate Settlement-Sufficient Evidence (SSE), a settlement       relevant events were observed. Consequently, a record
model that derives guaranteed financial entitlements across all
                                                                     containing only authenticated information may still be
histories consistent with the accepted evidence. Rather than
                                                                     insufficient to establish a unique contractual outcome.
selecting an unsupported binary outcome, SSE releases only
financially justified amounts and retains unresolved escrow. An          Consider an SLA requiring a provider to respond to a
exposure-aware admission rule further restricts new service          consumer request within a specified period, with the
obligations according to their maximum additional monetary           provider's obligation conditioned on having received that
uncertainty. We specify an Ethereum-based architecture               request. Suppose the consumer possesses a signed request but
integrating independent monitoring, authenticated evidence,          no authenticated delivery receipt or provider response. Two
and deterministic contractual enforcement. A restricted Solidity     contractual histories remain possible: the request was never
implementation realizes three-history settlement and
                                                                     delivered, or the provider received it but did not fulfill the
conservative epoch admission. The extended architecture
                                                                     obligation. These histories may imply different contractual
specifies scalable monitoring, separately funded protocol
incentives, bilateral residual resolution, and distributed cloud     payments while remaining indistinguishable from the
participation; these extensions are distinguished from the           evidence available to the settlement mechanism. Selecting
experimentally exercised baseline.                                   either as a definitive outcome would require assumptions not
                                                                     established by that evidence.
     Keywords—Blockchain, cloud federation, Service Level
Agreements, smart contracts, incomplete evidence, financial
settlement.

                      I. INTRODUCTION
    Cloud federation enables independently administered
providers to exchange computing and storage resources
according to changing workload demands. A provider
experiencing temporary resource shortages may lease capacity
from another administrative domain rather than maintaining           Fig. 1: Indistinguishable request-delivery histories: an undelivered request
sufficient infrastructure for every demand peak. Decentralized             and an unfulfilled received request may yield the same available
resource markets have been investigated as mechanisms for                   authenticated evidence but different contractual entitlements.
coordinating such exchanges without relying exclusively on
dominant marketplace operators [2]-[4]. However, because                 We investigate Settlement-Sufficient Evidence (SSE) to
participants may have competing economic interests, the              address the financial consequences of this ambiguity. Instead
resulting service agreements require enforceable guarantees          of requiring every contractual event to be conclusively
for both consumers and providers.                                    determined, SSE considers the histories consistent with
                                                                     authenticated observations and identifies the financial
    Service Level Agreements (SLAs) specify measurable               entitlements guaranteed across them. The contract can release
service conditions, such as availability, response time, and         those guaranteed amounts while retaining only the portion
correct execution, together with the financial consequences of       whose allocation depends on unresolved evidence. Thus,
fulfillment or violation. In a conventional marketplace, a           uncertainty about the actual service outcome does not
trusted intermediary may record contractual obligations,             necessarily prevent financial finality for every part of the
collect service measurements, determine whether violations           agreement.
occurred, and authorize payments. Such arrangements
simplify enforcement but concentrate authority over records              Unresolved evidence also influences subsequent service
and financial decisions. Blockchain-based smart contracts            execution. Suspending every disputed lease can interrupt
provide an alternative for maintaining shared contractual state      useful inter-cloud cooperation, whereas continuing without
and enforcing predetermined payments through escrow [1],             regard to outstanding uncertainty may accumulate excessive
[5], [7]. Nevertheless, application execution and service            financial liability. SSE therefore introduces an exposure-
measurements remain outside the blockchain.                          aware admission criterion that accounts for the worst-case
                                                                     additional uncertainty created by future obligations.
    This distinction introduces an important limitation.
Blockchain consensus can establish agreement on the                     This work investigates two complementary mechanisms:
transactions submitted to the network, but it does not               conservative settlement of financial entitlements common to

<PARSED TEXT FOR PAGE: 2 / 6>

all admissible contractual histories, and exposure-aware                        Castillo et al. [14] investigate trusted service monitoring
admission of further obligations. An Ethereum-based                         and verifiable SLA claims using trusted execution and zero-
architecture connects these mechanisms to authenticated                     knowledge techniques. When a sound proof establishes a
monitoring and enforceable escrow accounting. The cloud                     particular contractual predicate, that predicate need not remain
marketplace and deployment infrastructure support the                       uncertain. Such mechanisms complement SSE by reducing,
investigation but do not constitute the proposed scientific                 and in some cases eliminating, the uncertainty over the
contribution.                                                               contractual histories relevant to settlement.
                   II. LITERATURE REVIEW                                        Basin et al. [17] study compliance monitoring over
                                                                            incomplete and disagreeing logs, demonstrating the
A. Decentralized Cloud Markets and SLA Enforcement                          importance of distinguishing an unobserved event from an
    Blockchain-supported cloud marketplaces provide                         event known not to have occurred. Faisal et al. [12] employ
mechanisms for coordinating resource exchange among                         cryptographic summaries and state channels for agreed
independent providers. Nardini et al. [2] investigated                      quality-of-service    accounting,     while      fair-exchange
decentralized trading of computing resources, while                         mechanisms [16], [18] investigate complementary aspects of
CloudAgora [3] examined blockchain-based resource                           contractual accountability. These works motivate explicit
exchange as an alternative to centralized cloud-marketplace                 treatment of the remaining uncertainty rather than interpreting
coordination. Taghavi et al. [4], Uriarte et al. [5], and Khan et           missing evidence as an automatic violation.
al. [6] subsequently investigated service-quality monitoring,
                                                                            C. Synthesis and Research Gap
distributed SLA management, and real-time monitoring of
cloud-hosted services.                                                          Prior work establishes methods for decentralized resource
                                                                            trading, witness-assisted service enforcement, authenticated
    AWESOME [7] is a particularly relevant predecessor                      measurements, and dispute handling. In the reviewed
because it combines resource auctions, witness management,                  mechanisms, the financial consequences of observations are
SLA enforcement, witness compensation, and contractual                      generally associated with reported outcomes, agreed
payment allocation. Its enforcement mechanism uses witness-                 measurements, or dispute procedures. The specific problem
confirmed service assessments to determine whether                          investigated here is to derive payment guarantees across
contractual fees or refunds are due. SSE instead addresses the              multiple still-admissible contractual histories and use the
case in which accepted evidence does not justify a unique                   resulting monetary uncertainty to govern the admission of
payment-relevant history, deriving only the monetary                        further obligations.
entitlements common to every remaining history.
Accordingly, resource trading, witness participation, and                      SSE separates evidence sufficient to identify an outcome
monitoring incentives are not claimed as independent                        from evidence sufficient to authorize a payment. Its
contributions of SSE.                                                       contribution is therefore independent of the resource-
                                                                            marketplace mechanism and can be combined with different
B. Reliability and Interpretation of External Evidence                      monitoring protocols, provided their evidence interpretation is
    Oracle mechanisms introduce trust assumptions at the                    sound.
boundary between blockchain state and external observations                     SSE therefore complements monitoring and cryptographic
[8]. Distributed witnesses [9], accountable cloud mechanisms                verification rather than replacing them: stronger evidence
[10], proof-of-monitoring techniques [11], and independent                  narrows the admissible histories, while the settlement model
SLA monitoring [19] seek to strengthen the credibility or                   determines which payments remain justified under the
accountability of service assessments. Cryptographically                    uncertainty that persists
attributable interactions [15] and verifiable network-
performance measurements [13] provide additional methods
for establishing externally observed predicates.

                                   Table I: Comparison of Related Work by Evidence and Settlement Characteristics

                                                                          Incomplete history        Guaranteed partial        Exposure based
    Work             Principal Focus           Evidence Mechanism
                                                                              treatment                settlement               admission
 Nardini et al.   Cloud-resource trading      Blockchain coordination      Not primary focus         Not established          Not established
      [2]
 CloudAgora        Resource marketplace         Resource-trading           Not primary focus          Not established          Not established
      [3]                                          mechanisms
 Uriarte et al.      Distributed SLA           Monitoring and smart           Monitoring-             Not established          Not established
      [5]              management                    contracts                 dependent
  Zhou et al.          SLA witness             Distributed witnesses         Witness-based            Not established          Not established
      [9]               enforcement                                           assessment
 AWESOME          Auction, SLA, witnesses       Incentivized witness         Witness-based          Not established in its     Not established
      [7]              and payments                  committee                  verdicts          reviewed settlement rule
 Faisal et al.       QoS accounting           Cryptographic summaries           Agreed                 Not established         Not established
     [12]                                        and state channels          measurements
  Basin et al.    Compliance monitoring      Incomplete and conflicting        Explicitly        Not a financial-settlement    Not applicable
     [17]                                               logs                  represented                  system
     SSE            Financial settlement       Admissible contractual          Explicitly        Lower/upper entitlement      Bounded monetary
  (proposed)      under uncertain evidence            histories               represented                 bounds                  exposure

<PARSED TEXT FOR PAGE: 3 / 6>

                    III. SYSTEM DESIGN                             the provider's entitlement 𝐹(𝐻) for each history 𝐻 , with
                                                                   0 ≤ 𝐹(𝐻) ≤ 𝑉
A. System Model and Design Objectives
                                                                       The minimum and maximum possible provider payments
    The system consists of consumers, providers, monitoring        are:
candidates, selected monitors, settlement executors, and the
underlying Ethereum network. A consumer publishes                       𝐿(𝐸) = min 𝐹(𝐻) ,         𝑈(𝐸) = max 𝐹(𝐻)            (1)
                                                                                   ∈ℋ( )                    ∈ℋ( )
resource requirements and funds an escrow-backed lease. A
provider accepts the agreement and supplies the contracted             The guaranteed provider payment 𝑃, guaranteed consumer
off-chain service. Monitoring candidates register by posting       refund 𝐶, and unresolved exposure 𝑋 are
the required bond. For each lease, a committee is selected
                                                                        𝑃 = 𝐿(𝐸),     𝐶 = 𝑉 − 𝑈(𝐸),      𝑋 = 𝑈(𝐸) − 𝐿(𝐸) (2)
from eligible candidates, excluding the consumer and
provider. Selected monitors independently observe the service      Consequently,             𝑃+𝐶+𝑋 =𝑉                        (3)
and submit attributable reports and evidence commitments.
Permissionless executors advance deterministic contractual             Let 𝐻* detonate the actual contrusctual history. Under
transitions without authority to alter payment beneficiaries or    world soundness, to 𝐻∗ ∈ ℋ(𝐸) , and therefore
settlement rules. Roles are contextual: the same account may       𝐿(𝐸) ≤ 𝐹(𝐻* ) ≤ 𝑈(𝐸). It follows that the guaranteed
provide resources under one lease and consume them under           provider credit cannot exceed the provider's entitlement under
another, but cannot represent both counterparties of the same      the actual history, while the guaranteed consumer refund
lease.                                                             cannot exceed the corresponding contractual refund. Equation
                                                                   (3) further establishes conservation of the funded service
     The design requires: (i) financial allocations justified by   value. These guarantees depend on sound evidence
every admissible contractual history; (ii) preservation of         interpretation and correct computation of the entitlement
previously finalized entitlements as evidence accumulates;         bounds.
(iii) explicit treatment of inconclusive observations; (iv)
bounded additional monetary exposure; and (v) open                     The restricted model uses three histories: 𝑁, where the
participation without a privileged marketplace operator            request was not received, 𝐹, where it was received but service
controlling settlement.                                            failed, and 𝑆 where service succeeded. The SLA assigns
B. Threat Model and Security Assumptions                                𝐹(𝑁) = 𝑟,          𝐹(𝐹) = 0,     𝐹(𝑆) = 𝑓            (4)

    Consumers and providers may misreport service behavior,            where 𝑟 is the reservation entitlement and 𝑓 is the epoch
withhold requests or responses, or selectively disclose            fee.
evidence. Monitors may fail to report, collude, submit
contradictory observations, or register several addresses under        For 𝑓 = 25𝑤𝑒𝑖 and 𝑟 = 5𝑤𝑒𝑖 , accepted negative
common control. Relayers may reorder transactions or attempt       observations without sound proof of request receipt may leave
to replay authenticated messages. Network delay and message        ℋ(𝐸) = {𝑁, 𝐹}. The provider's guaranteed payment is zero,
loss can also make a functioning service appear unavailable.       the consumer receives 20𝑤𝑒𝑖, and 5𝑤𝑒𝑖 remains unresolved.
                                                                   If additional soundly establishes receipt, the admissible set
    The financial guarantees assume correct finalized              may reduce to 𝐹, allowing the retained amount to be credited
Ethereum execution, secure cryptographic authentication, and       to the consumer. Conversely, stronger evidence of successful
a sound interpretation of accepted evidence. In particular,        fulfillment may establish 𝑆.
world soundness requires that the actual contractual history
remain within the admissible-history set. This property is not         For a fixed obligation, if newly accepted evidence yields a
established merely by collecting signed observations or            sound refinement ℋ(𝐸 ) ⊆ ℋ(𝐸 ) , then 𝐿(𝐸 ) ≥ 𝐿(𝐸 )\
obtaining a monitoring quorum. If the evidence policy              and 𝑈(𝐸 ) ≤ 𝑈(𝐸 ) ). Consequently, the provider's and
incorrectly excludes the actual history, the resulting financial   consumer's guaranteed entitlements can only increase, while
bounds may authorize an unjustified transfer despite being         unresolved exposure can only decrease. The contract realizes
computed correctly.                                                this property through incremental credits and monotonicity
                                                                   checks, without reversing earlier payments.
   The approved committee policy assumes an upper bound
𝑏 on Byzantine selected identities. For 𝑛 monitors and a           D. Evidence Collection and Interpretation
matching-report threshold 𝑞 , honest intersection between              For each admitted epoch, selected monitors retrieve the
conflicting quorums requires 2𝑞 − 𝑛 > 𝑏, while availability        committed service descriptor and independently probe the
against 𝑏 unavailable or Byzantine monitors requires               provider. The agreed observation policy determines which
𝑞 ≤ 𝑛 − 𝑏 . The restricted implementation uses 𝑛 = 4 and           requests, responses, acknowledgments, and measurement
𝑞 = 3, corresponding to a one-Byzantine-identity example.          results establish contractual predicates. Service-specific
These conditions concern report consistency and potential          records are retained off-chain, while authenticated monitor
availability, not independent proof of physical service truth.     votes and cryptographic evidence commitments are submitted
Moreover, bonded addresses do not necessarily represent            on-chain.
independently administered operators.
                                                                       An authenticated monitor report establishes attribution,
C. Settlement-Sufficient Evidence                                  not the truth or completeness of the external observation.
    Let 𝐸 denote the accepted evidence for an escrow-backed        Under the specified evidence policy, sufficient success
obligation with contractual value 𝑉. The nonempty set ℋ(𝐸)         evidence may restrict the admissible histories to {𝑆}, whereas
contains every contractual history consistent with the accepted    accepted negative evidence without established receipt may
evidence and the stated fault assumptions. The SLA specifies       leave {𝑁, 𝐹}. A provider-signed acknowledgment binds the
                                                                   provider's key to the lease and request commitment but does
                                                                   not independently prove HTTP delivery or its timing.

<PARSED TEXT FOR PAGE: 4 / 6>

Excluding 𝑁 is therefore sound only when the contractual                    majority, and neither reward category consumes disputed
policy treats this acknowledgment as a binding admission of                 service escrow. Unresolved service funds remain retained
receipt, or when an additional sound receipt mechanism is                   after evidence closure unless both contractual parties
available. Conflicting or insufficient evidence must preserve               authorize an exact allocation through matching EIP-712
every history that cannot reliably be excluded..                            signatures. Such a transfer is a consent-based resolution rather
                                                                            than an entitlement established by SSE evidence. These
                                                                            economic extensions are present in the supplied source but
                                                                            have not been independently execution-validated in the
                                                                            reported prototype.
                                                                            F. Distributed Architecture
                                                                                The target architecture separates Ethereum contractual
                                                                            authority from independently deployed service agents. A new
                                                                            Ubuntu VM obtains a verified software release and
                                                                            authenticated network manifest containing the chain identity,
                                                                            deployed contract addresses, and protocol configuration. After
                                                                            role selection, the installer configures the participant agent,
                                                                            establishes outbound Ethereum connectivity, and initializes
                                                                            service discovery. Automatic overlay connectivity or a public
                                                                            gateway supports VMs without static public addresses. Role-
                                                                            specific registration, bond, funding, and service-reachability
                                                                            requirements are enforced separately from software
                                                                            installation.




    Fig. 2: Logical architecture of SSE, separating Ethereum-based
 contractual enforcement from off-chain resource execution, monitoring,
                         and evidence storage.

    The implementation distinguishes three data surfaces.
Blockchain transactions and events provide an auditable                         Fig. 3: Target distributed deployment architecture, showing node
history of submitted operations, while contract storage                       onboarding, role-specific cloud instances, service discovery, Ethereum
maintains enforceable lease terms, monitor assignments,                                      connetivity, and network observability.
verdict-related state, evidence digests, deadlines, credits, and
unresolved exposure. Complete SLA documents, workload                           The node console and network observatory provide
descriptors, HTTP requests and responses, and monitoring                    operational and audit interfaces, but their availability is not a
logs remain off-chain, with selected records bound to on-chain              prerequisite for contractual authority. Automatic enrollment
commitments. A matching evidence hash establishes record                    into a private connectivity overlay must also be distinguished
integrity but does not independently prove external truth,                  from open participation in the public Ethereum application.
timely delivery, or continued availability.                                 The distributed deployment is part of the complete
                                                                            architecture, not a demonstrated feature of the restricted local
E. Exposure-Aware Continuation and Financial Resolution                     prototype.
   Before admitting another epoch, the contract checks
whether outstanding financial uncertainty plus a conservative                    IV. ETHEREUM-BASED IMPLEMENTATION
bound on the new obligation remains within the lease's
                                                                            A. Network, Identity, and Registration
exposure budget:
                                                                                The intended public deployment inherits proof-of-stake
                     𝑋         + Δ𝑋        ≤𝐵                         (5)   consensus from Ethereum. Execution and consensus clients
    Here, 𝑋        is the lease's outstanding unresolved service            maintain and validate blockchain state, while optional
exposure, Δ𝑋         is the maximum additional exposure                     validator clients participate in block proposal and attestation.
associated with the proposed epoch, and 𝐵 is the lease-                     SSE consumers, providers, monitors, and executors need only
specific monetary exposure budget. The restricted                           signed Ethereum transactions and suitable RPC access; they
implementation conservatively takes Δ𝑋          = 𝑓, where 𝑓 is             are not required to operate validators.
the full next-epoch fee.                                                       The restricted implementation uses Anvil to execute
   Service escrow is accounted for separately from                          Ethereum-compatible transactions in a local development
monitoring and execution compensation. The extended                         environment. It therefore demonstrates EVM contractual
Solidity source defines a prefunded incentive budget, fixed                 behavior without establishing an independently operated
rewards for eligible monitoring reports, and one-time bounties              public-consensus network.
for successful settlement-related transitions. Monitor                         Participants are identified by Ethereum accounts. Provider
compensation does not depend on agreement with the                          acknowledgments and response commitments are

<PARSED TEXT FOR PAGE: 5 / 6>

authenticated through EIP-712 signatures, while monitoring          response deadline. These deadlines are enforced using
evidence may be submitted through signed, relayed reports or        Ethereum block time and do not independently prove when
direct transactions from selected monitoring accounts. These        HTTP messages were delivered.
Ethereum identities do not require a conventional certificate-
                                                                        After monitoring closes, any account may seal the
authority PKI. TLS may separately protect service endpoints.
The committee contract accepts bond-backed registrations and        monitoring result. At least three matching success reports
                                                                    classify the epoch as Success, while three matching failure
records lease-specific assignments. The restricted
implementation selects four monitors using a seed supplied by       reports classify it as Failure; otherwise, the classification
                                                                    remains None. SSESettlement combines the sealed
a configured randomness authority, from a candidate registry
limited to 32 lifetime identities. Verifiable randomness and        classification with the provider-acknowledgment state to
                                                                    restrict the admissible N/F/S histories. It then computes the
scalable membership are features of the approved extended
design, not implemented guarantees.                                 lower and upper provider entitlements on-chain, updates only
                                                                    the incremental guaranteed credits, and retains unresolved
B. Smart-Contract Components                                        service exposure. Beneficiaries subsequently withdraw their
    Three cooperating contracts form the active application.        credits through a separate pull-payment operation.
OpenResourceBoard records resource requests and bids and
atomically funds a selected lease through SSESettlement.
OpenMonitorCommittee maintains bonded candidates, lease-
specific eligibility snapshots, committee assignments, and
locked bonds. SSESettlement enforces participant
permissions, epoch deadlines, evidence acceptance, N/F/S
financial bounds, exposure accounting, and pull-based
withdrawals. SSEBoundsPure provides an independent pure
implementation of the restricted entitlement calculation for
comparison and testing.
   The consumer selects a provider bid and funds the lease's
maximum configured service liability through the resource
board. Lease creation also requests a monitoring assignment,
excluding the contractual counterparties. After provider
acceptance and committee selection, the assigned monitors             Fig. 5: Sequence diagram of service monitoring, authenticated
                                                                         evidence submission, admissible-history refinement, and
confirm their participation; all four confirmations are required
                                                                                      conservative SSE settlement.
before the lease becomes ready. The consumer may then admit
an epoch if its request commitment is unique, sufficient                The consumer may close the lease to additional epochs and
uncommitted escrow remains, and the worst-case additional           recover uncommitted service escrow. Monitoring bonds may
exposure fits within the lease budget.                              be released after lease closure and closure of every admitted
                                                                    epoch's evidence window. Any unresolved service amount
                                                                    remains distinct from guaranteed credits and is not
                                                                    automatically refunded at timeout. The extended settlement
                                                                    source additionally defines separately funded monitor and
                                                                    executor rewards and bilateral EIP-712 residual allocation.
                                                                    These functions are source-level additions whose execution
                                                                    behavior requires validation independently of the restricted
                                                                    prototype's previously exercised settlement path.
                                                                    D. Crucial Smart-Contract Logic and Prototype Scope




Fig. 4: Sequence diagram of resource discovery, provider bidding,
escrow-funded lease creation, monitoring committee selection, and
                        epoch admission.

C. Evidence and Settlement Workflow
    Each admitted epoch establishes three on-chain deadlines:
the response deadline, monitoring closure, and evidence
closure. The consumer commits a unique request hash, while
the provider may submit authenticated acknowledgment and
response commitments. Selected monitors evaluate the
external service and submit evidence digests through
authorized direct or EIP-712-signed transactions. The contract
accepts success votes only after a provider response
commitment is authenticated, and failure votes only after the

<PARSED TEXT FOR PAGE: 6 / 6>

    Algorithm 1 admits an obligation only if the complete           was initially drafted manually, and completed by Codex.
additional epoch fee fits within the remaining exposure             Figures 1, 2 and 3 were manually created, while the diagrams
budget. This conservative reserve may be larger than the            in figures 4 and 5 were generated by draw.io provided with
exposure that later becomes unresolved, but prevents                written svg code. The two algorithms were drafted manually,
admission based on an underestimated payment interval. The          and their figures generated by ChatGPT for better
reserved amount is subsequently reduced as authenticated            visualization.
evidence establishes guaranteed entitlements.
                                                                                                 REFERENCES
                                                                    [1]   K. Wüst and A. Gervais, “Do You Need a Blockchain?,” CVCBT,
                                                                         2018, doi:10.1109/CVCBT.2018.00011.
                                                                    [2] M. Nardini et al., “A Blockchain-based Decentralized Electronic
                                                                         Marketplace for Computing Resources,” SN Computer Science, vol. 1,
                                                                         art. 251, 2020, doi: 10.1007/s42979-020-00243-7.
                                                                    [3] T. Bakogiannis et al., “Leveraging Blockchain Technology to Break
                                                                         the Cloud Computing Market Monopoly,” Computers, 2020,
                                                                         doi:10.3390/computers9010009.
                                                                    [4] M. Taghavi et al., “A Blockchain-Based Model for Cloud Service
                                                                         Quality           Monitoring,”        IEEE         TSC,         2020,
                                                                         doi:10.1109/TSC.2019.2948010.
                                                                    [5] R. B. Uriarte et al., “Distributed Service-Level Agreement
                                                                         Management with Smart Contracts and Blockchain,” CCPE, 2021,
                                                                         doi:10.1002/cpe.5800.
                                                                    [6] K. M. Khan et al., “Blockchain-enabled Real-time SLA Monitoring for
                                                                         Cloud-hosted Services,” Cluster Comput., 2022, doi:10.1007/s10586-
                                                                         021-03416-y.
                                                                    [7] Z. Shi et al., “AWESOME: An Auction and Witness Enhanced SLA
                                                                         Model for Decentralized Cloud Marketplaces,” Journal of Cloud
                                                                         Computing, vol. 11, art. 27, 2022, doi: 10.1186/s13677-022-00292-8.
                                                                    [8] H. Al-Breiki et al., “Trustworthy Blockchain Oracles: Review,
                                                                         Comparison, and Open Research Challenges,” IEEE Access, 2020,
                                                                         doi:10.1109/ACCESS.2020.2992698.
                                                                    [9] H. Zhou et al., “A Blockchain Based Witness Model for Trustworthy
                                                                         Cloud      SLA       Enforcement,”     IEEE     INFOCOM,        2019,
                                                                         doi:10.1109/INFOCOM.2019.8737580.
    Algorithm 2 derives the payment interval from the               [10] M. Zichichi et al., “Accountable Clouds Through Blockchain,” IEEE
admissible-history mask and releases only the increase in                Access, 2023, doi:10.1109/ACCESS.2023.3276240.
guaranteed entitlements. Monotonicity checks prohibit               [11] N. Weerasinghe et al., “Proof-of-Monitoring (PoM): A Novel
reversals of previously credited amounts, while the unresolved           Consensus Mechanism for Blockchain-Based Secure SLA
difference remains in escrow.                                            Management,”                IEEE             TNSM,              2023,
                                                                         doi:10.1109/TNSM.2023.3234862.
    The restricted prototype implements three-history SSE           [12] T. Faisal et al., “Automated Quality of Service Monitoring for 5G and
settlement,     exposure-aware      admission,       EIP-712             Beyond Using Distributed Ledgers,” IEEE/ACM IWQoS, 2021,
authentication, and escrow accounting using a local                      doi:10.1109/IWQOS52092.2021.9521260.
compute/HTTP workload. Its fixed committee, trusted                 [13] K. J. Argyraki, P. Maniatis, and A. Singla, “Verifiable Network-
                                                                         Performance Measurements,” in Proceedings of ACM CoNEXT, 2010,
randomness source, unsigned HTTP responses, and locally                  doi: 10.1145/1921168.1921170.
coordinated execution do not establish independently                [14] F. Castillo et al., “Towards Trusted Service Monitoring: Verifiable
administered monitoring or verifiable external delivery time.            Service Level Agreements,” in Service-Oriented Computing, Lecture
Scalable committee selection, stronger receipt evidence, and             Notes in Computer Science, vol. 16321, Springer, 2026, pp. 159–174,
automatic distributed node deployment remain separate                    doi: 10.1007/978-981-95-5015-9_12.
extensions requiring implementation and validation.                 [15] N. Cook et al., “Component Middleware to Support Non-repudiable
                                                                         Service Interactions,” DSN, 2004, doi:10.1109/DSN.2004.1311931.
                                                                    [16] F. Qazi et al., “Towards Automated Enforcement of Cloud SLA,” UCC
                                                                         Companion, 2017, doi:10.1145/3147234.3149186.
                    AI USAGE DISCLAIMER                             [17] D. Basin et al., “Monitoring Compliance Policies over Incomplete and
   AI-assisted tools contributed to research brainstorming,              Disagreeing Logs,” Runtime Verification, 2013, doi:10.1007/978-3-
manuscript organization, language drafting and revision, code            642-35632-2_17.
development assistance, and the preparation of technical            [18] S. Peldszus et al., “Fast, Favorable, and Fair Blockchain-based
                                                                         Exchange of Digital Goods using State Channels,” IEEE ICBC, 2024,
diagrams and pseudocode.                                                 doi:10.1109/ICBC59979.2024.10634451.
    The submitted report is a 5th iteration of the draft, and the   [19] A. Badshah et al., “Service Level Agreement Monitoring as a Service:
final version was proof-read and edited by ChatGPT for                   An Independent Monitoring Service for Service Level Agreements in
                                                                         Clouds,” Big Data, vol. 11, no. 5, pp. 339–354, 2023, doi:
grammar and vocabulary enhancements. The submitted code                  10.1089/big.2021.0274