# Dashboard and UI audit — 2026-11-27 (inventory level)

- Existing: V3 read-only console (R384–R394), unsigned intent forms (R388/R389), local approval browser (R392, not fully live
  tested), public tunnel (R398). Abandoned login (R399–R407) still in tree except R400 local pause; removal pending owner review.
- Missing for owner requirements: V4 service catalogue/request builder with artifact commitment, committee planner view
  (n/b/s/q, eligibility, exact cost, risk), bid comparison and award, provider marketplace filters, monitor assignment/standby
  deadlines, validator/full-node pages, explorer eth_getProof verification. **Not implemented** this session; the planner and
  encoders provide the backend computations such a UI needs.

## Pass 2 update
tools/sse_v4_console.py (b70f8b3): marketplace list/filter/pagination, request detail with all bids (valid flag, exact funding),
request builder with live planner (quorum, eligibility, exact cost, draw probability, non-weakening alternatives), local
content-addressed upload → artifact commitment, lease page (phase help, SSE accounting, formation, frozen committee, epochs,
masks), provider bid form, monitor registration/exit, account credits, explorer (block, tx with decoded V4 events and priority
fee, eth_getProof verification with proof path). Security: loopback bind, CSP without inline script, no CORS, bounded bodies,
no RPC passthrough, no tracebacks. Not implemented: result download page for consumers (outputs are stored by the provider
agent under its state dir; serving them through the provider endpoint is NO), validator/full-node pages (peers, duties,
rewards) — the V3 console/R424 collector still provide these.
