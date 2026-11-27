# Extracted reference text — Report.pdf

Preserved from the supplied academic PDF. Text extraction only; figures, layout and math may be imperfect. Original PDF remains authoritative. Do not interpret historical prototype claims as current runtime status.

<PARSED TEXT FOR PAGE: 1 / 4>

Settlement-Sufficient Evidence for Trustless Inter-Cloud
                   SLA Enforcement
          Ayoub Akarkouz
 Blockchain Application Development
      Al Akhawayn University
           Ifrane, Morocco

                                                                      and protects the integrity of the signed message. It does not, by
                       I. INTRODUCTION                                itself, establish the truth of claims about external events or prove
    Cloud federation enables independently administered cloud         that the message was delivered to its intended recipient.
providers to share computing resources in response to fluctuating     Similarly, an authenticated append-only log can make
demand. A provider facing a temporary capacity shortage can           modifications to recorded events detectable without establishing
obtain resources from another provider rather than maintaining        that every relevant event was recorded.
sufficient infrastructure for every demand peak. However,                 Consider an SLA requiring a cloud provider to respond to a
because participating providers may have different owners and         consumer request within a specified deadline, with provider
economic interests, inter-cloud cooperation requires                  responsibility conditioned on receiving the request. Suppose the
mechanisms for enforcing contractual obligations without              settlement mechanism receives a consumer-signed request but
relying on mutual trust.                                              no authenticated provider response or delivery receipt. Two
    These obligations are typically expressed through Service         executions remain possible: (i) the consumer created the request
Level Agreements (SLAs), which define measurable service              but did not deliver it to the provider, or (ii) the provider received
objectives, such as availability and response time, and specify       the request but failed to respond. Although these executions may
the financial consequences of violations. Consider a provider         imply different contractual consequences, they are
leasing computing capacity from another cloud under an SLA            indistinguishable from the specified evidence alone, as
backed by a $100 payment escrow. Although the parties can             illustrated in Fig. 1.
agree on the contractual terms before provisioning, determining           The ambiguity arises because a signature proves that a
the final payment requires evidence of whether the promised           request was signed, not that it reached its intended recipient.
service was delivered.                                                Certified delivery, non-repudiable service interactions [16], and
    Traditional cloud marketplaces can rely on a central              fair-exchange-based SLA mechanisms [17] can provide stronger
intermediary to maintain contractual records, evaluate service        evidence under appropriate protocol assumptions. SSE does not
measurements, and authorize payments. In a federation of              replace these mechanisms; it addresses the settlement problem
mutually distrustful providers, however, this introduces an           when the evidence available under a chosen protocol still admits
additional trusted party. Blockchain-based smart contracts offer      more than one contractual history.
an alternative for maintaining shared contractual state, holding
funds in escrow, and enforcing predefined settlement rules
without delegating these functions to a single marketplace
operator. Decentralized cloud-marketplace research [2] and
blockchain-supported SLA management [5] illustrate how these
mechanisms can be applied to resource exchange and contractual
coordination. Such use is consistent with the blockchain decision
criteria discussed by Wüst and Gervais [1]. Resource
provisioning, application execution, and performance
monitoring nevertheless remain off-chain.
                                                                        Fig. 1. Indistinguishable request-delivery histories under limited
     This separation introduces a fundamental limitation:               authenticated evidence. Without a verifiable delivery receipt or
blockchain consensus establishes agreement on recorded                  provider response, a signed request is consistent with both non-
transactions, not on the correctness or completeness of                                delivery and provider non-response.
information describing external service execution. For example,
a smart contract cannot directly determine whether a cloud                The relevant question is therefore not only whether evidence
provider responded to a request within the deadline specified by      can be authenticated, but whether it is sufficient to determine the
an SLA. Such information must be supplied through external            financial consequences of an SLA. In particular, different service
evidence or an oracle, introducing an additional trust boundary       histories may remain possible while implying identical or
[8].                                                                  partially overlapping payment obligations.
    Existing approaches strengthen this boundary through                 This motivates the following research question:
independent monitoring, distributed witnesses, authenticated
interaction records, and cryptographically protected                      How can mutually distrustful cloud parties safely settle SLA
measurements. Nevertheless, authenticating an observation does        obligations when authenticated runtime evidence is insufficient
not necessarily establish that all relevant events were recorded or   to uniquely determine service fulfillment?
that the observation uniquely identifies the responsible party.       B. Proposed Direction: Settlement-Sufficient Evidence
Consequently, even cryptographically valid evidence may leave             We propose to investigate Settlement-Sufficient Evidence
multiple service histories consistent with the available              (SSE), a model for determining which SLA payments can be
information.                                                          safely finalized when authenticated evidence does not identify a
A. The limits of Athenticated Evidence                                unique service outcome. Rather than requiring all uncertainty to
   Under appropriate cryptographic and key-management                 be resolved before settlement, SSE evaluates the financial
assumptions, a valid digital signature authenticates the signer

<PARSED TEXT FOR PAGE: 2 / 4>

consequences of every contractual history that remains                     As shown in Fig. 2, SSE separates off-chain evidence
consistent with the available evidence.                                interpretation from on-chain escrow enforcement. The smart
    Let E denote the authenticated evidence collected for a fixed      contract must verify the resulting settlement bounds or a
set of SLA obligations, and let ℋ(𝐸) be the nonempty set of            suitable proof of their correctness before authorizing transfers.
admissible contractual histories consistent with the evidence and      C. Settlement-Aware Continuation
the assumed fault model. For each history 𝐻 ∈ ℋ(𝐸), the SLA
                                                                           Evidence ambiguity affects not only the final distribution of
settlement function 𝐹(𝐻) specifies the provider's entitlement
                                                                       escrowed funds but also whether service execution should
from a total escrow V, where 0 ≤ 𝐹(𝐻) ≤ 𝑉.                             continue while a disagreement remains unresolved. A
   The possible provider payments are therefore:                       conservative protocol may suspend accounting when the parties
                𝒮(𝐸) = {𝐹(𝐻) ∣ 𝐻 ∈ ℋ(𝐸)}                               disagree about an observation, protecting previously agreed
                                                                       obligations but potentially interrupting otherwise useful service.
   Assuming a nonempty finite set of admissible histories, the         For example, Faisal et al. [12] use cryptographic summaries and
lower and upper settlement bounds are defined as:                      state channels to establish agreed quality-of-service accounting
         𝐿(𝐸) = min 𝐹(𝐻) and 𝑈(𝐸) = max 𝐹(𝐻)                           information, illustrating the importance of agreement on off-
                  𝐻∈ℋ(𝐸)                        𝐻∈ℋ(𝐸)                 chain measurements.
    Here, 𝐿(𝐸) is the minimum provider entitlement across all             SSE motivates an alternative decision criterion based on
admissible histories, while 𝑈(𝐸) is the maximum. Their                 unresolved monetary exposure rather than the mere presence or
difference, 𝑋(𝐸) = 𝑈(𝐸) − 𝐿(𝐸) represents unresolved                   number of disputed observations. An ambiguous event need not
settlement exposure: the portion of the escrow whose allocation        prevent continuation if its possible financial consequences
depends on evidence that has not yet resolved the contractual          remain bounded. Conversely, a single disputed event may justify
ambiguity.                                                             suspension if it creates substantial uncertainty about payment.
    If the actual contractual history belongs to ℋ(𝐸), then its            Let 𝐵𝑀 denote a contractually specified monetary exposure
associated payment lies between 𝐿(𝐸) and 𝑈(𝐸). For an initially        budget. A preliminary continuation condition requires the
unallocated escrow, the provider can receive the guaranteed            unresolved exposure to remain within this budget. However,
entitlement 𝐿(𝐸), the consumer can recover 𝑉 − 𝑈(𝐸), and the           current exposure alone is insufficient: admitting additional
contract can retain 𝑋(𝐸) without allocating disputed funds             service obligations may increase future exposure. A proposed
prematurely. A progressive settlement protocol must                    exposure-aware admission policy therefore accounts for a
additionally account for previously executed transfers to prevent      conservative bound on the additional unresolved exposure that
duplicate payments:                                                    could arise before the next enforceable checkpoint:
                𝐿(𝐸) + [𝑉 − 𝑈(𝐸)] + 𝑋(𝐸) = 𝑉
                                                                                            𝑋(𝐸) + Δ𝑋max ≤ 𝐵𝑀
     For example, suppose the escrow is $100 and the evidence
admits two histories yielding provider entitlements of $98 and             Here, Δ𝑋max is a conservative upper bound on any increase
$100. The lower and upper bounds are therefore $98 and $100,           in unresolved settlement exposure before the next enforceable
leaving $2 in unresolved settlement exposure. The provider can         checkpoint, considering the obligations admitted and the
receive $98 while the remaining $2 stays in escrow. Conversely,        possible evolution of evidence. This bound must account for the
if all admissible histories yield the same payment, the escrow can     combined SLA settlement function, possible future evidence,
be fully allocated even when the actual service history remains        and dependencies between obligations. Establishing a sound
uncertain. Thus, financial finality does not necessarily imply         computation of this bound is part of the proposed research.
outcome finality.                                                          Exposure-aware continuation also requires enforceable
    The safety of these transfers requires world soundness: the        checkpoints, dispute-age limits, restrictions on outstanding
actual contractual history must remain in the admissible set. It       obligations, and a contractual fallback for unresolved disputes.
also requires that the SLA payment function correctly represents       The proposed admission condition is a candidate design rule
the agreed contractual obligations and that the enforced               rather than a complete safety guarantee; its validity depends on
settlement bounds are computed or verified correctly. SSE              sound exposure bounds and the treatment of previously
therefore does not remove the off-chain trust problem                  committed obligations. The approach investigates whether
automatically. Its proposed trustless enforcement depends on           useful execution can continue under these constraints without
sound evidence interpretation, verifiable computation of               exceeding a predefined unresolved settlement exposure budget.
settlement bounds, and safeguards against strategic omission or
                                                                                        II. LITERATURE REVIEW
manipulation of evidence.
                                                                       A. Decentralized Cloud Markets and SLA Enforcement
                                                                           Blockchain-based cloud marketplaces have been
                                                                       investigated as alternatives to centralized resource coordination.
                                                                       Nardini et al. [2] developed a decentralized marketplace for
                                                                       computing resources, demonstrating the integration of
                                                                       blockchain transactions with outsourced computational
                                                                       execution. CloudAgora [3] similarly explored blockchain-
                                                                       supported resource trading to reduce dependence on dominant
                                                                       cloud-marketplace operators. These works establish important
                                                                       foundations for decentralized resource exchange, but the
                                                                       interpretation of incomplete SLA evidence is not their primary
                                                                       focus.
Fig. 2. Proposed SSE architecture. Authenticated observations define       Subsequent research addressed service quality and
    admissible histories whose possible SLA payments determine         contractual enforcement. Cloudchain-related work by Taghavi et
 guaranteed entitlements and unresolved settlement exposure. Safe      al. [4] investigated blockchain-based cloud federation with
 enforcement requires sound evidence interpretation and verifiable     oracle-supported quality verification for leased computing
                         settlement bounds.

<PARSED TEXT FOR PAGE: 3 / 4>

resources. Uriarte et al. [5] proposed distributed SLA                particularly relevant basis for investigating disagreement and
management using smart contracts and monitoring entities,             settlement. SSE examines the additional question of whether
while Khan et al. [6] examined blockchain-enabled real-time           financial obligations can be partially settled when the available
monitoring of cloud-hosted services. AWESOME [7] combined             evidence does not determine a unique service outcome. A
auctions, witnesses, SLA agreements, and financial settlement         detailed protocol-level comparison is required to establish which
within a decentralized cloud marketplace.                             continuation and settlement guarantees differ.
    Together, these contributions demonstrate that blockchain-            State-channel-based fair exchange mechanisms [21] provide
based resource exchange and SLA enforcement are established           an additional point of comparison because they investigate how
research areas. The proposed SSE model therefore does not seek        parties can complete economic exchanges under adversarial
to introduce another marketplace architecture. Instead, it            conditions. Unlike the proposed SSE formulation, which
investigates how contractual payments can be determined when          explicitly maps admissible service histories to payment bounds,
authenticated monitoring evidence remains insufficient to             their application concerns digital-goods exchange. The extent to
establish a unique service outcome.                                   which their settlement guarantees can be adapted to inter-cloud
                                                                      SLAs requires further examination.
B. Evidence Reliability and Dispute Handling
    The reliability of off-chain evidence remains a central               Earlier adaptive SLA monitoring also considered switching
challenge for blockchain-based service enforcement. Al-Breiki         between external monitoring and mutually committed
et al. [8] surveyed blockchain oracle mechanisms and their            observations according to perceived risk [23], illustrating that
associated trust assumptions. Witness-based verification [9],         monitoring strategies and trust assumptions can vary over the
accountable cloud-service mechanisms [10], and proof-of-              lifetime of an SLA.
monitoring approaches [11] investigate ways to strengthen the             Reasoning over incomplete and disagreeing logs [18]
reliability, provenance, or accountability of service observations.   provides another conceptual foundation. Such research
    Independent SLA monitoring services [22] address the              demonstrates that analysis can account for multiple executions
reliance on provider-reported performance information, while          consistent with incomplete observations. SSE proposes to extend
accountable logging protocols [20] strengthen the traceability of     this perspective to financial settlement by evaluating admissible
recorded interactions. Both are relevant to the evidence available    contractual histories under an SLA payment function.
for SLA enforcement, although reliable recording alone does not       C. Synthesis and Research Gap
determine the financial consequences of observations that
remain incomplete.                                                        Prior research addresses complementary aspects of
                                                                      decentralized SLA enforcement: blockchain marketplaces
    Non-repudiable service interactions [16], verifiable network-     coordinate resource exchange, monitoring and witness
performance measurements [14], and more recent verifiable             mechanisms strengthen evidence collection, and incomplete-log
SLA monitoring [15] strengthen evidence about external service        analysis provides ways to represent uncertainty. However, these
behavior through different protocol and cryptographic                 contributions do not, by themselves, establish a general rule for
assumptions. For example, Castillo et al. [15] investigate trusted    allocating escrow when multiple contractual histories remain
execution environments and zero-knowledge proofs for                  admissible. SSE investigates this intersection by deriving
verifiable SLA violation claims. Such approaches complement           guaranteed payments from the range of admissible settlement
SSE by improving the evidence supplied to settlement; they do         outcomes and by examining whether unresolved monetary
not remove the need to specify which contractual histories            exposure can govern service continuation. Its intended
remain admissible when observations are incomplete.                   contribution is a formally specified settlement model with
                                                                      verifiable enforcement; the novelty and effectiveness of this
    Faisal et al. [12] developed a distributed-ledger-supported       combination remain to be established through further
quality-of-service monitoring approach using cryptographic            comparison and evaluation.
summaries and state channels to establish agreed accounting
information across monitoring epochs. This provides a
                 Table I. Comparison of related work by evidence mechanism, ambiguity handling, and settlement approach.

 Work                Application          Evidence mechanism                Treatment of incomplete             Settlement focus
                                                                            evidence
 Nardini [2]         Cloud market         Blockchain coordination           Not primary focus                   Resource exchange
 CloudAgora          Cloud market         Verifiable computation            Not primary focus                   Resource trading
 [3]
 Cloudchain [4]      Cloud federation     Oracle verification               Oracle-based verificiation          SLA quality enforcement
 Uriarte [5]         SLA                  Monitoring entities               Monitoring-based assessment         Contract enforcement
                     management
 Zhou [9]            Cloud SLA            Distributed witnesses             Witness based assessment            SLA enforcement
 AWESOME             Cloud market         Witnesses                         Witness supported assessment        SLA settlement
 [7]
 Faisal [12]         QoS monitoring       Cryptographic summaries,          Agreed QoS accounting               QoS accounting
                                          state channels
 Basin [18]          Compliance           Incomplete logs                   Explicit incomplete-log             Not financial
                                                                            semantics
 SSE                 Inter-cloud SLA      Admissible histories              Admissible-history uncertainty      Bounded partial
 (proposed)                                                                                                     settlement

                                                                      [1]    K. Wüst and A. Gervais, “Do you Need a Blockchain?,” Proc. Crypto
                          REFERENCES                                         Valley Conf. Blockchain Technology, 2018, pp. 45–54, doi:
                                                                             10.1109/CVCBT.2018.00011.

<PARSED TEXT FOR PAGE: 4 / 4>

[2]  M. Nardini, S. Helmer, N. El Ioini, and C. Pahl, “A Blockchain-based       [13] I. Avramopoulos and J. Rexford, “Stealth Probing: Efficient Data-Plane
     Decentralized Electronic Marketplace for Computing Resources,” SN               Security for IP Routing,” Proc. USENIX Annual Technical Conference,
     Computer Science, vol. 1, Art. 251, 2020, doi: 10.1007/s42979-020-              2006, pp. 267–272.
     00243-7.                                                                   [14] K. Argyraki, P. Maniatis, and A. Singla, “Verifiable Network-
[3] T. Bakogiannis, I. Mytilinis, K. Doka, and G. Goumas, “Leveraging                Performance Measurements,” Proc. ACM CoNEXT, 2010.
     Blockchain Technology to Break the Cloud Computing Market                  [15] F. Castillo, E. Brito, S. Werner, P. Pullonen-Raudvere, and J. Heiss,
     Monopoly,” Computers, vol. 9, no. 1, Art. 9, 2020, doi:                         “Towards Trusted Service Monitoring: Verifiable Service Level
     10.3390/computers9010009.                                                       Agreements,” Proc. ICSOC 2025, LNCS 16321, Springer, 2026, pp. 159–
[4] M. Taghavi, J. Bentahar, H. Otrok, and K. Bakhtiyari, “A Blockchain-             174.
     Based Model for Cloud Service Quality Monitoring,” IEEE Transactions       [16] N. Cook, P. Robinson, and S. Shrivastava, “Component Middleware to
     on Services Computing, vol. 13, no. 2, pp. 276–288, 2020, doi:                  Support Non-repudiable Service Interactions,” Proc. International
     10.1109/TSC.2019.2948010.                                                       Conference on Dependable Systems and Networks, 2004, doi:
[5] R. B. Uriarte, H. Zhou, K. Kritikos, Z. Shi, Z. Zhao, and R. De Nicola,          10.1109/DSN.2004.1311931.
     “Distributed Service-Level Agreement Management with Smart Contracts       [17] F. Qazi, A. Jhumka, and P. D. Ezhilchelvan, “Towards Automated
     and Blockchain,” Concurrency and Computation: Practice and                      Enforcement of Cloud SLA,” Companion Proc. 10th International
     Experience, vol. 33, e5800, 2021, doi: 10.1002/cpe.5800.                        Conference on Utility and Cloud Computing, 2017, pp. 151–156, doi:
[6] K. M. Khan, J. Arshad, W. Iqbal, S. Abdullah, and H. Zaib, “Blockchain-          10.1145/3147234.3149186.
     enabled Real-time SLA Monitoring for Cloud-hosted Services,” Cluster       [18] D. Basin, F. Klaedtke, S. Marinovic, and E. Zălinescu, “Monitoring
     Computing, vol. 25, pp. 537–559, 2022, doi: 10.1007/s10586-021-03416-           Compliance Policies over Incomplete and Disagreeing Logs,” Runtime
     y.                                                                              Verification, LNCS 7687, Springer, 2013, pp. 151–167, doi: 10.1007/978-
[7] Z. Shi, V. Ivankovic, S. Farshidi, J. Surbiryala, H. Zhou, and Z. Zhao,          3-642-35632-2_17.
     “AWESOME: An Auction and Witness Enhanced SLA Model for                    [19] A. Deshpande, L. Hellerstein, and D. Kletenik, “Approximation
     Decentralized Cloud Marketplaces,” Journal of Cloud Computing, vol. 11,         Algorithms for Stochastic Boolean Function Evaluation and Stochastic
     Art. 27, 2022, doi: 10.1186/s13677-022-00292-8.                                 Submodular Set Cover,” 2013.
[8] H. Al-Breiki, M. H. U. Rehman, K. Salah, and D. Svetinovic,                 [20] M.-K. Yoon and Z. Shao, “ADLP: Accountable Data Logging Protocol for
     “Trustworthy Blockchain Oracles: Review, Comparison, and Open                   Publish-Subscribe Communication Systems,” Proc. IEEE ICDCS, 2019,
     Research Challenges,” IEEE Access, vol. 8, pp. 85675–85685, 2020, doi:          pp. 1149–1160, doi: 10.1109/ICDCS.2019.00117.
     10.1109/ACCESS.2020.2992698.
                                                                                [21] S. Peldszus, M. Lohr, J. Jürjens, and S. Staab, “Fast, Favorable, and Fair
[9] H. Zhou, X. Ouyang, Z. Ren, J. Su, C. de Laat, and Z. Zhao, “A Blockchain        Blockchain-based Exchange of Digital Goods using State Channels,”
     Based Witness Model for Trustworthy Cloud Service Level Agreement               Proc.       IEEE       ICBC,       2024,      pp.       279–287,      doi:
     Enforcement,” Proc. IEEE INFOCOM, 2019, pp. 1567–1575, doi:                     10.1109/ICBC59979.2024.10634451.
     10.1109/INFOCOM.2019.8737580.
                                                                                [22] A. Badshah, A. Jalal, U. Farooq, G.-U. Rehman, S. S. Band, and C. Iwendi,
[10] M. Zichichi, G. D'Angelo, S. Ferretti, and M. Marzolla, “Accountable            “Service Level Agreement Monitoring as a Service: An Independent
     Clouds Through Blockchain,” IEEE Access, vol. 11, pp. 48358–48374,              Monitoring Service for Service Level Agreements in Clouds,” Big Data,
     2023, doi: 10.1109/ACCESS.2023.3276240.                                         vol. 11, no. 5, pp. 339–354, 2023, doi: 10.1089/big.2021.0274.
[11] N. Weerasinghe, R. Mishra, P. Porambage, M. Liyanage, and M.               [23] K. P. Clark, M. Warnier, and F. M. T. Brazier, “Self-adaptive Service
     Ylianttila, “Proof-of-Monitoring (PoM): A Novel Consensus Mechanism             Level Agreement Monitoring in Cloud Environments,” vol. 9, no. 2, pp.
     for Blockchain-Based Secure Service Level Agreement Management,”                135–155, 2013, doi: 10.3233/MGS-130203.
     IEEE Transactions on Network and Service Management, vol. 20, no. 3,
     pp. 2783–2803, 2023, doi: 10.1109/TNSM.2023.3234862.                       [24] A. Alzubaidi, K. Mitra, and E. Solaiman, “A Blockchain-based SLA
                                                                                     Monitoring and Compliance Assessment for IoT Ecosystems,” Journal of
[12] T. Faisal, D. Di Francesco Maesa, N. Sastry, and S. Mangiante,                  Cloud Computing, vol. 12, Art. 50, 2023, doi: 10.1186/s13677-023-
     “Automated Quality of Service Monitoring for 5G and Beyond Using                00409-7.
     Distributed Ledgers,” Proc. IEEE/ACM IWQoS, 2021, pp. 1–6, doi:
     10.1109/IWQOS52092.2021.9521260.