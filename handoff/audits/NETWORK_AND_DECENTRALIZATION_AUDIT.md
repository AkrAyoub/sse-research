# Network and decentralization audit — 2026-11-27 (documentation review only)

Source of truth: STATE_AND_EVIDENCE.md (historical observations). Nothing was run or contacted.
- Three active validators, all operated by the owner on owner VMs: no independent-operator claim possible; target ≥7 equally
  weighted independent operators (E10, Not executed).
- Native peer transport via controllerless ZeroTier network: depends on vendor roots/relays; `replaceablePeerDirectorySources`
  empty in release manifest → fresh independent join is not yet possible without owner-provided hints. **Blocked** on owner
  infrastructure decisions (BLOCKERS B-04).
- Public dashboard via rotating third-party quick tunnel: availability depends on a third party; read-only.
- Weak subjectivity: checkpoint-sync from owner-published SSZ (R186/R187) — trust assumption must be disclosed to joiners.
- TEST ETH is valueless: bonds and stakes give no economic security; Sybil resistance of monitors/validators is not established.
- V4 contracts introduce no central membership: anyone may register as monitor, request, bid.
