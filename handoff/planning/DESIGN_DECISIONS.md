# Design decisions (append-only)
- D-01 (2026-11-27) Split V4 into Board/Registry/Standby/Ledger/Market modules wired by precomputed CREATE addresses, no admin.
  Why: EIP-170 headroom (V3 runtime 23753 B) and separation of funds. Alt: single market (rejected: size), factory (more initcode).
- D-02 Sample at draw time from an append-only roster with population cut frozen at award; reserve only n+s seats.
  Why: avoids R411 lock-all griefing, gives global sampling. Alt: Merkle snapshot of eligible set (needs off-chain builder, more
  trust); rotating window (not global).
- D-03 Bounded attempts (8/seat, ≤512) with fail-closed full refund. Why: bounded gas; never weakens n/b.
- D-04 Consumer fixes n, s, b in the request; quorum q = n − ⌊(n−1)/3⌋ (n ≥ 3b+1 ⇒ 2q−n > b, q ≤ n−b).
- D-05 Unpromoted standbys unpaid for now (owner economics decision pending); listed as A-10.
- D-06 `responseAdmitsReceipt` is an explicit bilateral term, default false (V3 semantics) — no retroactive change.
- D-07 Qualified negative evidence: keep conditional quorum; proposed future format = provider-signed response whose output
  digest differs from a deterministic reference recomputation committed in the policy (only for deterministic workloads).
- D-08 Cancel before provider acceptance: consumer any time, anyone after acceptDeadline; no penalty either side (no work done).
