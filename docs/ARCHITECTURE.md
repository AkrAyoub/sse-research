# Architecture decision — one public, permissionless SSE PoS network

**Date:** 2026-11-19
**Status:** TARGET, NOT A DEPLOYMENT CLAIM.
**Predecessor (retained only for reproduction):** private PoS chain31339 on
VM4705, single host, exposed bootstrap mnemonic; Anvil31337, permissioned
QBFT31338 and Tailscale invite-gated networks are NOT this architecture.

## Zero centralized authorization or control — architectural veto

**There is no SSE authority that signs up, approves, permits, updates, controls, funds, or manages every participant.** Network membership depends only on independently verifiable genesis, compatible clients and native P2P; economic roles depend only on the relevant *on-chain/protocol rules*, not the original experiment operator, an admin's wallet, a central registry, privileged invitation, API account, hosted dashboard or Tailscale coordinator. A full node must be able to join after the original deployer, all original bootstrap peers, a single faucet, and a single HTTP/HTTPS mirror are offline, provided other peers and required publicly obtainable test funds remain.

Initial genesis publication and optional signed release snapshots are reproducible **information distribution**, never ongoing approval or unilateral upgrade power. Any user may cache/redistribute genesis and run their own compatible client; release artifacts should have multiple independent mirrors, transparently verifiable code and optional nonexclusive signatures. No mandatory central RPC, seed, VRF/faucet/operator, block explorer, UI relay or global node management service may control consensus or joining.

**Current contracts do not yet satisfy a proven no-central-dependency audit:** pre-binding `bootstrapper` configuration, VRF fee recipient/lifetime cap, a pinned randomness source/coordinator and potentially biasable sortition require real semantic review and engineering. They are **BLOCKERS**, not approval that the project is currently fully decentralized. Exact source findings, no-administrator threat model and independent host acceptance live in [DECENTRALIZATION_INVARIANTS.md](DECENTRALIZATION_INVARIANTS.md). Fresh host provenance, every command, every future fix and remaining automation gaps belong in [the VM4706 experiment journal](experiments/VM4706_2026-11-19.md).

## Nonnegotiable properties

1. **Our own Ethereum-compatible Proof-of-Stake chain, valueless TEST ETH.**
   Real Besu EL and Lighthouse CL/VC clients (or peer-compatible
   alternatives); real signed and gossiped blocks, attestation, fork
   choice, finality, proposer/attester rewards and slashing or penalties
   as implemented by the Ethereum consensus protocol. No invented
   PoW-miner competition or 'reward' counters in SSE application code.
   Prefer consensus-spec 12-second slots, 32 slots/epoch unless a
   documented benchmark necessitates deviation. EVM block capacity
   is predominantly a **gas limit**, not a fixed chosen byte size.
   Record actual network clock and gas utilization, not selected
   numbers that merely make plots look smooth.

2. **Permissionless external P2P join.** Anyone with compatible software
   and publicly available *exact genesis and consensus config* can
   run a full node, verify blocks and learn peers, without an SSE
   invitation, VPN membership, whitelisted address, four fixed
   validators or preapproved machine. Native execution devp2p/discv4-v5
   and consensus discv5/gossip form TWO genuine P2P layers.
   A signed bootstrap list is a discovery hint, NOT an admission list.
   Peers and full nodes can join even without test ETH.

3. **No fixed/static IP requirement; but real reachability is required.**
   Initial public bootstrap seeds MUST use stable dynamic-DNS names
   (free hosted dynamic DNS is acceptable) or independently published
   and frequently refreshed signed discovery records. Execution
   clients may resolve DNS in enodes; CL ENRs contain actual
   IP/port data and MUST update/re-advertise after external IP changes.
   Discovery needs reachable TCP+UDP paths and working NAT mapping,
   inbound forwarding, or real P2P relays where appropriate.
   Machines behind CGNAT may connect outbound and sync but cannot
   automatically act as inbound-reachable bootstrap nodes.
   **Dynamic DNS alone is not a CGNAT relay**. Peer admission is
   consensus/genesis validation, never the DNS publisher's permission.
   At least two independent, externally reachable bootstrap peers
   are required for resilience; use four independently operated PoS
   validator operators in the first measured public trial, not a
   permanent validator cap.

4. **No permissioned staking gate.** Each potential validator owns
   its own BLS signing key. A standard Ethereum deposit contract
   accepts the protocol-required deposit in worthless TEST ETH;
   Beacon watches deposits and handles activation queue, churn,
   proposer selection, attestations, rewards, penalties and exits
   according to its protocol. No SSE administrator signs a validator
   whitelist. Test ETH needs a publicly accessible and transparent
   distribution mechanism: its *issuance policy* is an explicit
   Sybil and availability assumption, not a role approval.
   Because it has no economic value, do not claim Ethereum-mainnet
   economic Sybil resistance. A prospective validator may need
   outbound P2P and valid funds, but not a public IPv4 at every node.

5. **Any independent host may operate any combination of roles**:
   `observer`, `full_node`, `validator`, `consumer`,
   `provider`, `monitor`. Local preference/UI role tags
   are optional; they are not the authority.
   - Observer/full node: client sync and correct genesis/fork.
   - Validator: independent BLS, deposit, Beacon active status.
   - Consumer: its own EOA and gas/test-ETH escrow.
   - Provider: advertised actual capacity, correct resource profile,
     bid and funded lease, live service endpoint.
   - Monitor: independent EOA, on-chain minimum bond, eligibility,
     on-chain selection, correct signed observation.
   A participant may be consumer/provider/validator simultaneously,
   but **a provider or consumer must not attest its own lease as a
   committee monitor**. An EOA restriction is necessary but cannot
   cryptographically prove absence of common human ownership.

6. **Actual resources and SLA workflows, never a synthetic success
   presented as delivery.** Provider runs a real pinned container or
   HTTP service on *its own host*. Consumer transmits an actual
   signed lease-bound workload over publicly reachable authenticated
   HTTPS (hostnames can change IP). The provider measures and signs
   the actual response; different remote monitors probe the actual
   endpoint, record timestamped signed raw requests/responses and
   failures/timeouts. SLA thresholds are agreed by on-chain hashes
   and canonical policies. Timed-out or partitioned observations
   may be inconclusive and MUST NOT silently convert to failures.
   Monitor observations and EIP-712 votes lead to on-chain quorum,
   conservative bounded settlement, withdrawals and gas receipts.
   Test mock services, deterministic vectors and local Anvil are
   acceptable as **automated unit tests only**, never as the main
   experimental fulfillment or empirical evidence.

7. **No secrets or coordinator privileges at bootstrap.** The
   single-VM chain31339 is permanently INELIGIBLE for Internet
   release: its upstream first-launch log disclosed a shared
   genesis validator mnemonic/prefunded account private keys.
   A new chain/network ID and clean genesis ceremony MUST use
   independently generated keys with safe, reviewed launch
   logging. Never copy a shared BIP39 validator mnemonic across
   machines. Public artifacts may include genesis/CL config,
   trusted code tags, public ENRs, enodes and deposits, NEVER
   private keys or keystore passwords. Public RPC should be
   separately secured/rate-limited or remain local to each
   operator; Engine API, key-manager and signer ports NEVER
   publicly exposed.

## Canonical new network, not VM4705 promotion

**Provisional chain ID:** `31340` for the FIRST future
Internet-public SSE test-ETH PoS experiment. This ID is intentionally
different from private chain31339; do NOT start using it until the
new multi-operator genesis hashes, clients, bootnode reachability
and software versions are actually reviewed. Chain ID alone is NOT
globally unique and MUST be confirmed alongside the exact execution
genesis, Beacon validators root and fork config.

The protocol has **NO fixed number of nodes for ANY role**.
At genesis, the initiating independently owned validators form a finite
explicitly documented initial snapshot (not a future-validator cap).
After genesis, eligible outsiders join through standard Beacon deposits
and exit rules; users independently choose any combination of full-node,
validator, consumer, provider, and bonded monitor roles.
For experimental fault-domain arguments, four independent PoS owners
with 25% stake each is just ONE example: after one fails, the remaining
75% nominal stake exceeds the >2/3 finality threshold. It is NOT a
four-validator/owner admission requirement, persistent roster, proof
of physical independence or guarantee of liveness under partitions.
Public discovery uses multiple genuinely independent and replaceable
reachable seeds; source mirror counts do not constrain P2P membership.
Genesis count, measured resource sizes, gas utilization, security assumptions
and active stakes require real benchmarks. Explicit per-genesis acceptance
thresholds are config inputs, NOT code defaults or global membership caps.
See [R21 adaptive roles and quorum](R21_ADAPTIVE_ROLES_AND_QUORUM.md).

**Bootstrap/public source distribution:** This repository is PRIVATE.
The future network's public genesis, Beacon config, client versions,
public key fingerprints, ENR seeds and signed network release manifest
must be available on a genuinely public HTTPS/mirror endpoint without
a GitHub invitation. A public repository, release mirror or
HTTPS-hosted signed manifest works; a private repo URL does NOT.

## No-administrator test-ETH funding — mandatory for economic roles

Public full nodes and observers join and synchronize with **zero** test ETH. New external validators, monitors, consumers and providers generate independent local EOA wallets and (where selected) BLS keys; their role requirements are funded with **chain-native, worthless TEST ETH**, not real Ethereum Mainnet ETH or a central operator's private keys. A validator needs the protocol's 32-test-ETH deposit per validator plus measured gas; monitors need the actual on-chain `minimumBond()`; consumers need their actual lease escrow, incentive deposits and gas; providers need gas and any on-chain required collateral. Funds and role activation are NEVER inferred from UI tags.

A public ownerless claim contract with independent gas sponsors and transparent finite reserves is a candidate route, not a deployed system or promise of infinite test ETH. Sponsor nodes are replaceable participants, not an SSE authorization authority; public donation/claim accounting is verifiable on-chain. Anyone can run a sponsor and transfer their own test ETH. Publicly funded claims do not establish human uniqueness; unlimited Sybil addresses can deplete finite free reserves despite per-address/per-block rate limits. No one wallet, website, faucet key or registry may decide who can join the P2P network or whitelist validators. On depletion, joining and full-node sync remain available, while economic role activation truthfully remains pending.

Candidate `contracts/OpenTestEthFaucet.sol`, adversarial Foundry tests and design/remaining integration gates: [PUBLIC_TEST_ETH_FUNDING.md](PUBLIC_TEST_ETH_FUNDING.md); tracked in #37. **No faucet or independent auto-funding has yet been observed live on chain31340.**

## Source and boundary map

`contracts/OpenMonitorCommittee.sol`,
`contracts/SSESettlement.sol`, and
`contracts/OpenResourceBoard.sol` already implement actual
bonded registration, global or bounded monitor election, funded
resource bidding, **legacy fixed 3-of-4** threshold reporting and escrow accounting. This fixed committee is NOT the required adaptive production behavior; the R21 dynamic migration is an explicit public-release blocker (#38).
The current delayed-block entropy is **proposer-biasable**, not a
strong unbiased VRF. Benchmark/selection/security work remains.

`services/provider-agent/` includes real HTTP/Docker compute
adapters; `services/consumer-agent/` includes signed live
request transport; `services/monitor-agent/` includes probe,
signed evidence and archive. Some are still local-only or
Tailscale-specific at the network edge; their **public HTTPS
transport, real deployment and remote evidence workflow remain
unimplemented/unverified**. Do not equate code presence with a
deployed resource marketplace.

`tools/sse_pos_*` includes 31339 smoke and deposit verification.
It is a **historical smoke pipeline**, not the new public network
launcher. Current `sse_pos_live_roles.py` hardcodes the exact
31339 genesis, addresses and faucet; it cannot be used to onboard
arbitrary external public participants. It must be generalized for
31340 through public trust-minimized release manifests and each
participant's own encrypted wallet, not an owner-maintained
seven-wallet directory.

Older `infra/qbft-multivm`, owner-issued overlay enrollment and
fixed VM operator scripts are archived, not public runtime
dependencies.

## Public acceptance (must be OBSERVED, not inferred from local tests)

- [ ] Four independently keyed, distinct host/owner EL/CL stacks start
      same fresh chain31340 and their block/attestation traffic peers
      via public TCP/UDP WITHOUT Tailscale or shared VM private IP.
- [ ] A fifth arbitrary new external node finds seeds from a public
      signed manifest/DNS, downloads authenticated genesis, syncs
      through native P2P and maintains head/finality after seed loss.
- [ ] Change at least one bootstrap's real public IP, update DNS/ENR,
      verify fresh peers can discover it and existing peers recover
      automatically; test restrictive NAT/relay case separately.
- [ ] A new participant with its own fresh BLS keys deposits 32
      worthless test ETH, appears pending then ACTIVE in Beacon
      registry and performs a valid attestation/proposal WITHOUT any
      SSE administrator action.
- [ ] A consumer and provider on separate hosts exchange signed
      live work against an actually allocated pinned worker/container;
      record actual CPU/memory/network metering and request/result.
- [ ] Vary the REAL population of independently owned bonded monitors,
      then elect and snapshot a gas/budget/risk-affordable committee of
      size k for each lease. Freeze a justified threshold q BEFORE votes,
      verify correct evidence and signed outcomes at q unique seats,
      and handle all undecided windows as inconclusive on-chain.
      Neither total monitor membership nor q is fixed to 4/3.
- [ ] Provider/consumer withdrawals and monitor compensation are
      real successful/finalized transactions with gas and timing
      measurements, signed evidence hash chain and crash recovery.
- [ ] VM/network faults, validator proposer liveness, partitions,
      reorgs, dishonest providers, sybil-like identities and
      censorship tested against documented baselines with observed
      failures distinguished from simulation/unit tests.

## Sources

- Ethereum PoS roles: https://ethereum.org/developers/docs/consensus-mechanisms/pos/
- EL/CL node architecture: https://ethereum.org/developers/docs/nodes-and-clients/node-architecture/
- Ethereum node discovery: https://ethereum.org/developers/docs/networking-layer/network-addresses/
- Lighthouse public reachability and dynamic ENR:
  https://lighthouse-book.sigmaprime.io/advanced_networking.html
- Besu public node identities/hostnames:
  https://docs.besu-eth.org/public-networks/concepts/node-keys
- EIP-1459 signed DNS discovery (optional):
  https://eips.ethereum.org/EIPS/eip-1459
- Ethereum standard validator deposit and activation:
  https://ethereum.github.io/consensus-specs/specs/phase0/deposit-contract/

This document is the sole CURRENT architectural source of truth.
Historical architecture designs remain in Git history for audit and
must not be reintroduced as competing production targets.
