# SSE Intercloud

Smart contracts and services for cloud-resource leasing and evidence-based escrow settlement.

**Milestone III research-prototype alignment:** see [README-MILESTONE3.md](README-MILESTONE3.md) and [system design](docs/MILESTONE3_SYSTEM_DESIGN.md). This is an Anvil + local Docker experimental prototype, not a deployed permissioned-QBFT or independently operated cloud federation.

## Structure

- `contracts/` — lease settlement, monitor committee, bonded registration and resource bids.
- `foundry/test/` — Solidity tests.
- `apps/control-plane/` — local FastAPI backend and web dashboard.
- `services/` — monitoring, resource-profile and node-status agents.
- `infra/ansible/` — Ubuntu role-agent deployment.
- `tools/` — inventory handling, network diagnostics and settlement calculations.

## Development

Requires Python 3.12, Git and Foundry. On Windows, run from PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\test.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\dashboard.ps1
```

Open `http://127.0.0.1:8800` with the token printed by the dashboard command.

In Git Bash, after installing Foundry:

```bash
bash scripts/install-contract-deps.sh
forge build
forge test
```

The API manages local node records; it does not provision hosts. Ethereum node deployment and the monitor's signing/RPC dependencies are not yet integrated.

## Phase 4 Ethereum research extension

- [Ethereum implementation technical register](docs/PHASE4_ETHEREUM_IMPLEMENTATION.md)
- [Source-grounded Section IV manuscript draft](docs/SECTION_IV_ETHEREUM_DRAFT.md)
- New optional EIP-712 two-party residual resolution and separately funded fixed reward budgets are in `contracts/SSESettlement.sol`.
- New Foundry tests: `foundry/test/ProtocolEconomics.t.sol`; independent typed-message utility: `tools/sse_residual_typed_data.py`.
- **Validation status:** the new Solidity source requires `forge build` and `forge test -vv` on a machine with Foundry; it has not been independently compiled here. New deployments are required for any changed contract bytecode.

