# Dashboard and UI audit — 2026-11-27 (inventory level)

- Existing: V3 read-only console (R384–R394), unsigned intent forms (R388/R389), local approval browser (R392, not fully live
  tested), public tunnel (R398). Abandoned login (R399–R407) still in tree except R400 local pause; removal pending owner review.
- Missing for owner requirements: V4 service catalogue/request builder with artifact commitment, committee planner view
  (n/b/s/q, eligibility, exact cost, risk), bid comparison and award, provider marketplace filters, monitor assignment/standby
  deadlines, validator/full-node pages, explorer eth_getProof verification. **Not implemented** this session; the planner and
  encoders provide the backend computations such a UI needs.
