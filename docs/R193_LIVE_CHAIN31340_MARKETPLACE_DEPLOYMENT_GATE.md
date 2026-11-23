# R193 — Genuine two-VM original chain31340 finality complete; marketplace deployment next

## Proven real network (R192)

Two read-only R141 live captures 5.828319 seconds apart on VM4707 and VM4709
agree on original chain31340, original execution genesis hash
`0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf`,
original Beacon validators genesis root
`0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd`,
finalized epoch571 root
`0x48c1976b872c24b9fc00d8b7fd3c08e1b82a44534e3eb4034292c2621e25db63`.
Each has two actual EL native peers and two CL peers, non-optimistic,
not syncing. This establishes empirically verified cross-host PoS
agreement, not a synthetic test.

## Existing marketplace implementation audit

The repository ALREADY has original real Solidity contracts:
`OpenMonitorCommittee`, `SSESettlement`, `OpenResourceBoard`
and their milestone Foundry tests, plus `OpenTestEthFaucet`,
VRF/election extensions and existing worker/monitor code.
Foundry `foundry/test/PoSDeploymentBootstrap.t.sol` tests real
deployment/wiring logic. `foundry/test/MarketplaceEscrow.t.sol`
exercises consumer requests, bids, escrow funding, monitor selection,
votes and settlement in isolated Foundry test context, **not** actual
chain31340 end-to-end services.

**Important discovered mismatch:** existing
`script/DeploySSEPos.s.sol` requires `OWN_SSE_POS_CHAIN=31339` and
would revert on real network chain31340. New
`script/DeploySSE31340.s.sol` copies exactly the original
committee/settlement/board construction and safe order, but enforces
`block.chainid == 31340` (only original test-ETH research
network). Old 31339 deployment script is left unchanged, and no
existing on-chain state was modified by GitHub edit.

The new chain31340 script requires an explicitly funded, locally
authorized, test-only deployer EOA. It uses `vm.startBroadcast()`
and hence should NOT be invoked with broadcast before checking
local keystore availability, test ETH balance, chain identity and
Foundry tests. Never paste mnemonic/key or source it from signer
or Engine JWT directories. This script reuses only existing
contracts; it does not invent new economics or protocol choices.

### Next safe live VM4707 check

On the original VM4707 SSH shell, from a *pinned fresh GitHub
checkout that includes this feature commit*, run read-only:
`command -v forge`, `command -v cast`,
`forge --version`, `forge build`,
`forge test --match-contract PoSDeploymentBootstrapTest -vv`,
and use `cast chain-id --rpc-url http://127.0.0.1:28545`,
`cast block finalized --rpc-url ...`. Do not fund, sign or
broadcast yet. Existing signer private keys must not be used.

Before deploying new contracts, inspect actual `eth_getCode`
and any prior chain31340 deployment manifests for all three
contracts, to prevent redundant/bad deployment. R140 audit
verifies the three finalized on-chain runtime hashes and mutual
bindings if a trustworthy deployment manifest already exists;
it does not discover contracts or prove a deployment happened.
If no real chain31340 deployment exists, use an operator-owned
independent dev/test EOA with test-ETH and published receipts.

### Real-market acceptance gates

1. Real chain31340 test-ETH deployer balance, verified original
   genesis, finalized block and source-pinned contract build.
2. Commit real finalized contract creation/binding transaction
   receipts and runtime hashes+contract addresses; R140 audit
   succeeds from both VMs.
3. Register actual independent monitor test EOAs with staking
   bonds, provider advertisements, consumer requests, provider
   bids, test-ETH escrow; prove receipts/events.
4. Run actual SSE job/service with physical resource allocation,
   real monitors measuring success/failure and real SLAs;
   finalize outcome/dispute/withdrawal based on real chain data.
5. Complete independent external infrastructure, true native
   open admission outside the overlay, real PoS validator
   lifecycle/rewards and scientific measurements. Do not equate
   this networking acceptance with completed full project.
