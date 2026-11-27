# Final static audit — session S1 (2026-11-27), refreshed after pass 3

Nothing in this session was compiled or executed. Current state: handoff/HAND_BACK.md.

Blocking before any V4 deployment: SC-13 size, SC-14 stack depth (awaiting compilation); DRV-V4-01 Foundry tests;
DRV-V4-PARITY encoder parity; DRV-V4-ABI hand-written ABI vs compiled ABI; DRV-PY-02 Python tests; Stage 4 isolated-chain
rehearsal (DRV-AGENT-V4, DRV-AGENT-V4-TERMS, DRV-OUTPUTS-V4, DRV-OUTPUTS-UI, DRV-UI-V4, DRV-NODE-V4, DRV-REWARDS-V4,
DRV-INST-V4); owner review of D-01…D-11 and decisions P-1…P-3; migration plan approval.

Pass-3 static review notes:
- Terms decoding (D-10) cannot weaken acceptance: decoded Terms are used only to recompute termsHash, and acceptance still
  requires the offer to be in the owner's approvedOfferHashes and the hash to equal the finalized on-chain value.
- Output fetch (D-11) is bound to the bid's endpointHash, so the local console cannot be steered to arbitrary URLs; public
  mode performs no outbound fetch. Output bodies are bounded (4 MiB).
- Self-keeping (D-09) is zero-value, owner-gated (`selfKeep` must be exactly true) and limited to the wallet's own leases.
- Console POSTs now require same-origin application/json and, in local mode, a loopback Host header.
