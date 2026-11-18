# Validation acceptance — Windows integration baseline, 2026-11-18

## User-observed manual evidence

Checked out from GitHub `integration/r7-wp09q-wan-multivm-no-actions`
at **`65875660849865082e9d5eba0bcf2bddffc13b2f`**, on
Windows Git Bash, Python 3.12.10, Forge 1.9.0, Solidity 0.8.24.

The operator executed `bash scripts/manual_integrated_gate.sh`; the transcript
ended with `SSE_LOCAL_GATE_COMPLETED on 6587566...`.

- 825 Python tests reported `OK (skipped=18)` in 86.966 seconds;
  **807 passed**, **0 failures**. POSIX-only key permissions, service-account
  checks, symlink cases and machine identity require independent Ubuntu tests.
- Foundry: **144 of 144 tests passed**, 0 failed, 0 skipped.
- WP09Q batched-global recovery: **10/10 EVM tests passed**. Five batches of
  eight proofs used reported gas `680497, 613317, 612008, 613768, 638445`
  for their individual batch calls in one test run. These are **Foundry call
  measurements**, not live multi-host Ethereum transaction latency or TPS.
- Actual runtime code length reported:
  `OpenMonitorCommittee` = **22,670 bytes**; EIP170 headroom = 1,906 bytes.
  `SSESettlement` = **22,533 bytes**; EIP170 headroom = 2,043 bytes.
- Adversarial evidence, escrow conservation, EIP712 signatures, VRF adapters,
  fees, global Merkle proofs, no-show recovery, bytecode checks and gas
  benchmark suites passed in the reported local Foundry environment.

### What this did NOT prove

- Real four-node QBFT consensus, independent VM failure domains, proposing
  rewards, changed-IP discovery, Tailscale admission or external network joins.
- Actual Chainlink VRF v2.5 coordinator/funding; mock adapter test != live VRF.
- Any new contracts deployed on VM4695; original Anvil chain31337 remains
  at height26 and retains historically funded lease obligations.
- Ubuntu POSIX permissions, wallet isolation or SSH identity security.
- Economic soundness of every nonresponse ambiguity; observational limits and
  conditional guarantees remain formal research work.

**Approval limited to that exact Git SHA.** Later integration/R9 commits
require their own targeted tests and then repeat the full suite manually.
No GitHub Actions used and no production-readiness claim is made.

Evidence source: uploaded operator terminal transcript (not stored in GitHub
because local logs may contain machine details); local source logs are under
`.local/manual-gate`. Preserve sanitized checksums and selected results using
the `sse_experiment_evidence.py` tool before cleaning the local workspace.
