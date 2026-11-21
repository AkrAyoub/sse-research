# SSE — permissionless Ethereum PoS resource marketplace

SSE is a research implementation for leasing **actual HTTP and Docker-backed
compute resources** with signed observations, monitor bonding, and on-chain
escrow settlement on an **independently operated Ethereum Proof-of-Stake
network using valueless TEST ETH**.

> **Implementation status (2026-11-19):** This repository is transitioning
> from a successful but **single-VM, non-public** research network to the
> public permissionless network described in
> [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
> The public network, remote validator staking/activation, Internet-wide
> peer discovery and real cross-host SLA lifecycle **are NOT deployed or
> verified yet**. Do not advertise them as working. The existing
> chain31339 on VM4705 has known exposed genesis validator keys and is
> **not safe to expose publicly**.

## Unified fresh-node onboarding and role selection (R144)

**ONE repository and entry point:** after obtaining this verified source
on a NEW Ubuntu host, run
`python3 -B tools/sse_join.py --node-id <local-unique-id> --plan`
for an interactive role selection menu, or add
`--roles full_node,monitor` (for example).
A participant may combine full node, observer, validator, provider,
consumer and monitor subject to protocol-specific funding,
eligibility and conflicts of interest. User selection is a
**configuration preference**, not consensus membership, active
validator status or on-chain role authority.

The current unified command does *read-only planning*, and can
delegate to the guarded R137 nonsigning full-node **plan** after
the original verified chain31340 archive, image pins and real public
peer directories are available. It does NOT yet perform zero-touch
first-boot packages, new validator BLS staking deposits, public mirror
publication, marketplace smart contract deployments or real on-chain
role activation. Source distribution from this PRIVATE repository
requires development-only read access until public authenticated
release mirrors exist; do not confuse that with a permissionless
network join.

Detailed role/scale reference:
[complete architecture and all roles](docs/SSE_COMPLETE_ROLES_PERMISSIONLESS_SCALING_AND_VM_EXPERIMENTS.md).
[Unified installer specification and honest gates](docs/R144_UNIFIED_ROLE_SELECTING_INSTALLER.md).
For a **completely fresh Ubuntu VM**, see [R145 fresh-source bootstrap](docs/R145_FRESH_VM_SOURCE_BOOTSTRAP.md). It provides a guarded source-only create-once procedure using an independently configured read-only deploy key, followed by the same unified role-selection plan. **The repository is currently private; this is not yet publicly distributable permissionless zero-touch onboarding.**

[Fresh-VM sizing](docs/R143_NEW_VM_INVENTORY_AND_FIRST_BOOT_GATE.md).

## Canonical architecture

One open Ethereum-compatible PoS chain, with **separate** execution
(Besu), consensus (Lighthouse) and optional validator-client software
on independently operated machines. Peers discover one another using
native Ethereum P2P/discv5 and resilient, dynamically updated public
bootstrap records; IP addresses may change. No SSE operator approval,
Tailscale membership, fixed/static IP, predefined four-validator
roster, or shared infrastructure account is required to join the
P2P network. **Some reachable public bootstrap nodes are still
necessary**; NAT/CGNAT operators require suitable forwarding,
NAT traversal or peer relays.

Any participant may run zero or more roles under its own keys:
**full node, validator, consumer, provider, monitor, observer**.
Actual role authority comes from network/client protocol rules,
SSE contracts, funded escrows and observed evidence—not a YAML role
label, GitHub access, or administrator-issued invitation.

- **Validator:** participant generates BLS keys locally, runs EL+CL+VC,
  deposits the protocol-required *test* ETH into the network deposit
  contract, waits for activation, and earns/loses PoS rewards/penalties
  under Ethereum consensus. No fake miner competition.
- **Provider:** advertises an actual measurable resource, bids, runs
  a real pinned worker/HTTP service and signs completed work.
- **Consumer:** pays actual on-chain test-ETH escrow, issues signed
  lease-bound workload requests and verifies returned results.
- **Monitor:** independently registers an on-chain bond, checks actual
  service responses, retains signed raw evidence and participates only
  when legitimately selected. Collusion and Sybil risks remain
  experimental limitations.
- **Observer/full node:** peers and verifies the chain without
  needing SSE admin or PoS signing keys.

## Current code

| Area | Source | What it proves / does not prove |
|---|---|---|
| Ethereum PoS integration | `tools/sse_pos_*.py`, `scripts/sse_pos_launch.sh` | Private chain31339 smoke only; its genesis MUST NOT become public |
| SSE smart contracts | `contracts/`, `script/DeploySSEPos.s.sol` | Real deployed EVM contracts on **isolated** chain31339 |
| Ethereum contract tests | `foundry/test/` | Repeatable EVM unit tests, not remote network evidence |
| Real compute and SLA transport | `Dockerfile.sse-compute`, `services/provider-agent/`, `services/consumer-agent/`, `services/monitor-agent/` | Executable work/evidence code; no full independent cross-host live acceptance yet |
| Marketplace and service policy | `tools/sse_node_marketplace.py`, `tools/sse_sla_*.py` | Node-owned signing, on-chain operations and conservative observation logic |
| Public readiness gate | `tools/sse_public_network_preflight.py` | Checks a fresh release manifest; **never** asserts Internet reachability from metadata alone |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for consensus, native
networking, dynamic IPs, permissionless deposits, role conditions,
real-service trust boundaries and nonnegotiable acceptance tests.
See [docs/RESEARCH_STATUS.md](docs/RESEARCH_STATUS.md) for precisely
what has been observed rather than assumed.

## Development/testing, not deployment

Ethereum dependencies are tracked as pinned Git submodules:

```bash
git submodule update --init --recursive
python -m pip install -r requirements.txt
forge build --sizes
forge test
python -m unittest discover -s tests -p 'test_sse_pos_*.py' -v
```

These commands **never turn local mocks into evidence of a public
network**. A real public release requires independently held new
bootstrap keys, independently reachable P2P nodes, publicly retrievable
genesis/consensus configs, live open validator deposits/activation,
real provider workload execution and remote monitor receipts.

### Safety and provenance

No mainnet currency, no public private keys, no hard-coded wallet
secrets, and no GitHub Actions that control personal infrastructure.
The historical Anvil/QBFT/Tailscale lab branches and proofs are retained
in Git history and the explicitly named archive branch, not treated
as production deployment or admission authority. Public RPC/validator
key APIs must never be exposed without reviewed security controls.
