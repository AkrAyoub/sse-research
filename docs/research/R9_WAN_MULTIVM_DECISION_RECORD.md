# ADR-005 — R9 full blockchain versus same-host simulation: decision and acceptance

Date: 2026-11-18. **Status: architecture approved for implementation, source partially implemented, runtime network unverified.**

## Requirements recovered from previous project development

1. Use **multiple independent blockchain operators** to produce/validate blocks, with scientific block period/gas capacity and measurable incentives. Never equate SLA monitor votes (three of four) with chain consensus (three of four QBFT validators under the usual one-fault threshold).
2. Existing Anvil VM4695 chain 31337 was verified on November 18 at height26, block hash `0x84988bbfc7ec33dcb9b8b204894a2e14cec153f763523e9f0cc4f54694cccf78`; provider-acceptance receipt `0x15f0331a3a9ebeb22df7450452e6756b45dd08ac27955d64902fb19e2486f648` status1. Preserve its lease and bonded monitors. The old chain cannot be moved to chain31338 by merely copying contract addresses.
3. The old portal reused hostnames; VM4695 DHCP address changed; VM4699 was permanently lost; a tunnel depending on 10.50.56.20 repeatedly failed. Use stable cryptographic identities plus authenticated discovery/overlay, not hostname/IP or naive /24 scanning across the Internet.
4. Any authorized external machine should be able to obtain reviewed software and join as a participant **without belonging to the campus/private subnet** or receiving a shared GitHub personal token. Wallets and validator keys remain owned by the machines.
5. GitHub is the source of truth for code. Users and VMs fetch immutable reviewed commits/releases; never run Actions. No automatic server activation or wallet transactions without an operator gate.
6. R0–R11 engineering and P0–P6 research claims remain tied to tangible acceptance tests, manifests and observations. No simulated tests are relabeled as physical/cloud proof.

## Selected first-stage architecture

**Blockchain:** four dedicated independent Ubuntu Besu QBFT validator hosts, chain 31338, baseline 5s period/10s timeout/15M gas, optional fixed test-ETH proposer reward; non-validator P2P peers can join, but QBFT validator addition uses validator voting. Each host owns private node key, persistent blocks and local loopback RPC. Later compare to an actual independently hosted Ethereum PoS experiment and, only if required, a separately supported competitive PoW experiment. QBFT proposer rotation is not PoW mining and fixed QBFT rewards are not native PoS staking/slashing.

**Application network:** consumers, providers, monitors, observer/full nodes on independently operated machines. Initial WAN transport via outbound Tailscale, HTTPS token broker, role/tag ACL, signed peer catalogs. Off-chain role messages need signed identities and nonce/domain separation; overlay itself is not an SLA oracle. Distinct host ownership is documented with evidence rather than assumed from different IP addresses.

**Software delivery:** GitHub pinned SHA (reviewed source), signed/SHA256-verifiable public source archive for participants who cannot access private GitHub, cautious release/update gate. No GitHub Actions, no public Anvil RPC, no private key in GitHub.

**Discovery:** authenticated node key and signed peer catalog; magicDNS/FQDN/overlay IP are locator hints. Readdress/reboot/reconnect must be tested. For any untrusted external machine with no privileged mesh invite, the current design does not provide anonymous permissionless network access. The permissionless alternative (public discovery bootstrap, relay/hole punching, decentralized admission, anti-Sybil and validator governance) is a **separate open research gap**.

## Compared alternatives

| Requirement | Four Docker validators on one host | Four independent QBFT VMs with managed WAN mesh | Ethereum PoS comparator |
|---|---|---|---|
| Four validator identities | Yes | Yes | Yes |
| Distinct physical failure domains | No | Yes if separately hosted | Only when actually distributed |
| Independent administration | No | Potentially; prove operator separation | Potentially; prove operator separation |
| Genuine competitive PoW race | No | No | No; stochastic proposer selection |
| Native consensus issuance/penalties | No | Optional synthetic proposer reward, no PoS slashing | Native PoS duties/rewards/penalties |
| Across NAT / DHCP | One machine only | Tailscale, DNS and signed bootstrap; must test | Requires separate topology design |
| SSE Solidity compatibility | Yes in principle | Yes, after fresh deployments | Yes with compatible EVM execution client |
| Scientific throughput/failure evaluation | Poor physical baseline | Preferred first controlled baseline | More realistic comparator with greater complexity |

## Evidence gates

**Gate M0:** R7 WP09Q Solidity source and WP09M–Q measurements reconciled, no duplicate patch application, manual full Foundry/Python tests green on exact SHA, EIP170 size and gas reviewed; old Anvil escrow/recovery independently accounted for.

**Gate M1:** new validator-generated genesis identical on four machines; cryptographically independent P2P keys; signed catalog anchored to actual chain31338 block0; no private keys in repo.

**Gate M2:** all four live VMs produce/agree on blocks and validator sets, one vs two failures, recovery and IP readdressing measured; proposer reward balances checked.

**Gate M3:** actual application leases with independent consumer/provider/monitor signers, HTTP/container proof and economic settlement, read-only observatory and identity-separated UI.

**Gate M4:** preregistered 5/12 sec x 15/30/60M gas arms with same seeded workload; warmup and measurement windows disclosed, gasUsed/bytes/tx latency/tps/CPU/downtime/rewards and uncertainty recorded. Include a comparable PoS arm if resources allow.

**Gate M5:** documented threat model, limits, invariant tests, manuscript and replicable release.

No work here claims any of M1–M5 already passed. Phase completion estimates are unchanged until evidence on actual hosts is recorded.
