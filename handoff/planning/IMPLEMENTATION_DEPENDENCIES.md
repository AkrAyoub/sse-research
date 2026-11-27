# Implementation dependencies
- V4 agents (C-01) and UI (B-03/04) depend on the V4 ABI → must follow owner compile of A-01..A-05 (any ABI change after compile
  invalidates agent work).
- tools/sse_v4_terms.py depends on exact struct field order in SSEServiceBoardV4.Request/Bid and SSEAdaptiveMarketV4.Terms.
  Any reorder must update REQUEST_FIELDS/BID_FIELDS/TERMS_FIELDS and re-run DRV-V4-PARITY.
- Planner constants ATTEMPTS_PER_SEAT/MAX_ATTEMPTS mirror SSEMonitorRegistryV4.
- Deployment depends on: size gate, test pass, owner migration decision, funded disposable deployer EOA (owner).
