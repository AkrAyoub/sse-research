# R5/R8 — Real Anvil signed marketplace, monitor failure, and settlement observatory

**Status:** implementation committed, tests authored, **NOT YET VERIFIED ON OPERATOR MACHINE**. The R5/R8 source is a research lab slice, not a complete independent-cloud deployment. Parent baseline `db0e390` passed 550/550 Python tests (three skipped) on the operator's Windows development terminal.

## What this branch adds

### R5: one node-owned action surface, extending real transactions

`tools/sse_node_marketplace.py` now supports these **exact SSE contract entry points** in addition to the previously verified marketplace actions:

| Role | CLI action | Solidity function |
| --- | --- | --- |
| monitor | `monitor-vote` | `submitMonitorVoteDirect(uint256,uint256,uint8,bytes32)` |
| participant* | `seal-epoch` | `sealMonitoring(uint256,uint256)` |
| participant* | `settle-epoch` | `settleEpoch(uint256,uint256)` |
| participant* | `close-evidence` | `closeEpochEvidence(uint256,uint256)` |
| consumer | `close-lease` | `closeLease(uint256)` |
| participant* | `release-committee` | `releaseCommitteeAfterEvidence(uint256)` |
| participant* | `withdraw` | `withdraw()` |

*The Solidity functions themselves are permissionless except `closeLease` and `withdraw` (withdrawals always pay the caller's own balance). The app deliberately makes them available only on node-owned consumer/provider/monitor interfaces, not the global dashboard.

The default mode remains a **transaction preview**, not a broadcast. An explicit `--execute` command on the owning VM still requires an owner-controlled signer file and max total spend. The node-local web interface has preview controls for these added operations, but it does not itself submit money-moving transactions. All new transactions require actual deployed contracts and a working RPC.

**Evidence caveat:** `monitor-vote` commits a supplied nonzero evidence hash. A hash and a monitor signature are NOT a physically qualified SLA report by themselves. Binding to independently archived, validated R4 probe data remains a separate requirement.

### R5: opt-in genuine local EVM experiment

`tests/test_sse_node_marketplace_anvil.py` starts an ephemeral loopback Anvil, deploys the real Foundry artifacts, and uses real **signed raw transactions** from multiple role-specific accounts. The test is intentionally not run by default; it is meant to validate integration before remote VM deployment.

It attempts:

1. Contract deployment and reciprocal binding using explicitly public development accounts
2. Five bonded monitor wallet registrations
3. Consumer request, provider bid, bid selection **with actual 25 wei escrow**, provider acceptance
4. Legacy **lab-only source-controlled entropy** and a four-monitor assignment/confirmation
5. Consumer epoch admission
6. Three separately signed monitor `Failure` votes **after the response deadline**
7. Monitoring seal and `settleEpoch`: for a **no-acknowledgment** failure, history set N/F gives provider lower 0, upper 5, consumer refund lower 20, unresolved exposure 5
8. Evidence closure, lease closure, committee release and consumer withdrawal

The test uses the famous Anvil public test mnemonic for localhost only. **Never** provision that mnemonic to an Ubuntu VM, Sepolia, or a real-value chain. Its three mock evidence hashes are NOT evidence that real provider workloads failed; this is a protocol/economic transaction test. No unbiased VRF is claimed.

### R8: independent chain inspection and conditional financial reasoning

`tools/sse_event_decoder.py` recognizes specific Solidity event signatures from the actual contracts: requests, bids, funded selections, committee assignments, monitoring votes, epoch outcomes, settlement changes, evidence closure and withdrawals. It retains raw event metadata for verification and marks unrecognized topics as raw/unknown. Decoding is not proof of finality or physical truth.

The global dashboard now supports:

- Recent block and tx receipt inspection
- SSE contract event names, parameters and transaction hashes
- `GET /v1/chain/leases/{lease_id}/epochs/{epoch_id}`: pinned block-hash state using the existing `sse_chain_read.inspect_chain` verifier
- A **read-only N/F/S explanatory view**: permissible histories, provider lower/upper, consumer refund lower, unresolved exposure and comparison with current credited on-chain balances

The lease view requires an explicit configured and allowlisted `SSE_OBSERVER_SETTLEMENT_ADDRESS`. On the independently hosted dashboard, configure `SSE_OBSERVER_RPC_URL`, `SSE_OBSERVER_CHAIN_ID`, `SSE_OBSERVER_CONTRACTS`, `SSE_OBSERVER_SETTLEMENT_ADDRESS`, plus owner/read-only API tokens. The dashboard never sends a role transaction or runs a fault command.

It reports source-dependent, prefinality blockchain observations, not a physical-quality certificate. An unresolved history set may remain despite a voted failure.

### R6 runtime dependency adjustment

The first-boot Ubuntu virtual environment installs `pycryptodome==3.23.0` and `eth-account==0.14.0` so it can run the marketplace CLI under its pinned Python runtime. The bootstrap still does not silently update an existing installation, deploy signing keys, run Tailscale installation, or join a VM automatically.

## Test sequence before any VM

Use the newest branch from `research/r5-real-anvil-wallet-flow-no-ci`.

```bash
python -m unittest discover -s tests -p 'test_sse_node_marketplace.py' -v
python -m unittest discover -s tests -p 'test_sse_event_decoder.py' -v
python -m unittest discover -s tests -p 'test_sse_settlement_explain.py' -v
python -m unittest discover -s tests -p 'test_sse_dashboard_settlement_routes.py' -v
python -m unittest discover -s tests -q
forge build
SSE_RUN_ANVIL_INTEGRATION=1 python -m unittest discover -s tests -p 'test_sse_node_marketplace_anvil.py' -v
```

The last command **starts a temporary loopback-only Anvil** and sends **real signed local test transactions**. Run it only after reviewing the lab source and ensuring the selected Python virtual environment has the pinned `eth-account` and Foundry tools. No test status is claimed for this branch until the operator sends actual results.

## Scope that remains

- Real provider workload control and signed EIP-712 ACK/response
- R4 independently captured and qualified raw monitor evidence, not synthetic test hashes
- Autonomous node agents and the node-local **execute** approval path (as opposed to read-only previews)
- Secure automatic Tailscale package installation, enrollment broker deployment and dynamic discovery
- Immutable signed-update activation with safe rollback, including quorum-sensitive rolling restarts
- Independent Ubuntu multi-VM environment, operator separation and network fault injection
- Real dashboard archive/probe streams, complete historical indexer, reorg/finality policy, publication-grade experiments
- Review source/repo history/secrets before making private GitHub source public
