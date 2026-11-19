# Architecture decision — one public, permissionless SSE PoS network

**Date:** 2026-11-19
**Status:** TARGET, NOT A DEPLOYMENT CLAIM.
**Predecessor (retained only for reproduction):** private PoS chain31339 on
VM4705, single host, exposed bootstrap mnemonic; Anvil31337, permissioned
QBFT31338 and Tailscale invite-gated networks are NOT this architecture.

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

A recommended first physical experiment has **four independently
controlled PoS operators** (each can run EL+CL and optional VC),
two or more separate Internet-reachable bootnodes, one real provider,
one real consumer, and four or more independently controlled
bonded monitors, with a spare. Initial validator stake fractions
should avoid one host holding >=1/3 active stake; for example,
four equal operators with 25% each leaves 75% attesting if one host
fails, nominally above the >2/3 finalization requirement.
This is a fault-domain/consensus argument, NOT a guarantee of
liveness under correlated partitions or a permanent four-node
protocol roster. New validators can deposit and activate later.
Genesis validator-key count, resource size and block occupancy
must be measured against protocol requirements and host capacity;
do not present arbitrary count as research optimization.

**Bootstrap/public source distribution:** This repository is PRIVATE.
The future network's public genesis, Beacon config, client versions,
public key fingerprints, ENR seeds and signed network release manifest
must be available on a genuinely public HTTPS/mirror endpoint without
a GitHub invitation. A public repository, release mirror or
HTTPS-hosted signed manifest works; a private repo URL does NOT.

## Source and boundary map

`contracts/OpenMonitorCommittee.sol`,
`contracts/SSESettlement.sol`, and
`contracts/OpenResourceBoard.sol` already implement actual
bonded registration, global or bounded monitor election, funded
resource bidding, 3-of-4 threshold reporting and escrow accounting.
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
- [ ] At least four monitors on independent hosts bond/test real
      service behavior and commit signed raw evidence tied to the
      correct canonical lease; 3/4 agree OR an inconclusive window
      is handled conservatively on-chain.
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
