# R255 — Actual first original chain31340 native TEST ETH transfer submitted; finality NOT YET PROVEN

## Observed real VM4706 owner output, 2026-11-24

On VM4706 the owner fetched immutable R254 GitHub SHA
`c0e0d78f0be3f5816b146eb51cd07ee98c4d4c22`
by HTTPS, detached the exact SHA, and ran
`bash -n scripts/r254_vm4706_authorized_one_time_v2_deployer_funding.sh`
successfully.

The owner then executed the live R254 single-use script.
Actual log confirms:

- `R254_ORIGINAL_CHAIN_GENESIS_AND_FUNDED_NONCE_ZERO_VERIFIED=true`.
- `R254_NEW_V2_DEPLOYER_ZERO_BALANCE_AND_NO_CODE_VERIFIED=true`.
- The exact sender's existing encrypted private keystore was
  locally unlocked only to verify its corresponding **public
  address** matched original genesis-funded EOA.
- Operator typed the explicit TTY consent
  `SEND-ONE-CHAIN31340-1-TEST-ETH`.
- The one-time attempt marker was consumed BEFORE the Cast send:
  `R254_BROADCAST_ATTEMPT_CONSUMED=true`.
- A separate hidden local Cast password prompt allowed **one**
  legacy signed `cast send --async` invocation.
- Public submitted RPC-accepted transaction hash:

  `0x07e3ff069936936b3daf17efc5cb484c1712e93dc6bd6040c55a5fae1b8d2a90`

- `R254_SINGLE_CAST_SEND_RETURNED=true`.
- `R254_DO_NOT_RERUN_THIS_SCRIPT=true`.

The native authorization was ONLY one transfer of
**1 valueless TEST ETH** from
`0x13fb73aace8A11Be2899D047635A757a224Ce00B`
to new separate VM4707 adaptive-V2-deployer
`0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0`,
on original chain31340, source nonce0, legacy gas limit 21,000
and fixed gas price 1,000 wei/gas. Max deduction is
1,000,000,000,021,000,000 wei.

**A returned public hash from --async does NOT prove an actual
inclusion, successful receipt, finality, or recipient balance.**
None of those are verified yet. DO NOT send again even if the
receipt is temporarily unavailable. The consumed owner-private
attempt marker remains in place. The Genesis keystore and BLS
signing keys were not moved or uploaded.

## New R255 finalized receipt verifier

`tools/sse_pos_r255_v2_funding_finalized_audit.py`
is read-only. It verifies chain31340 + actual original genesis,
exact public transaction hash and owner-authorized
sender/recipient/amount/nonce/chain type/gas price/gas limit,
successful actual receipt and paid gas, canonical block hash,
finalized execution height, on-chain finalized destination
balance >= 1 TEST ETH and source nonce >= 1.

It can be run from either approved localhost node:
VM4706 `--rpc http://127.0.0.1:18545`
or VM4707 `--rpc http://127.0.0.1:28545`.
It never requests a password, touches wallets, sends
transactions, modifies Docker or operates Lighthouse.

The checker deliberately exits with:
- `0` + `R255_REAL_NATIVE_V2_DEPLOYER_FUNDING_FINALIZED=true`
  ONLY when complete proof succeeds;
- `3` + `R255_FUNDING_NOT_FINAL_YET` when transaction
  is unseen, receipt pending or canonical inclusion
  precedes current finalized height. **Never re-send**;
- `2` + `R255_FUNDING_AUDIT_REFUSED` for a mismatching
  chain, genesis, authorized payload, receipt, gas, canonical
  block hash or finalized account state.

Tests under `tests/test_sse_pos_r255_v2_funding_finalized_audit.py`
are synthetic RPC mocks ONLY; no live test success is claimed until
the owner provides real VM4706 + VM4707 R255 output.

## Remaining project milestones

The V2 source-only compiled ABI gate is already fully green
at `6930c069b4e9738e63e2ce9d53b10d126053335e`.
The single funding tx is a live chain milestone, but the
adaptive V2 market+vote ledger are NOT YET verified deployed.
After finality: obtain separate owner approval for one real
contract deployment from the **new, funded application-only
EOA on VM4707**, choose and justify minimum monitor
bond, verify gas and receipt, and run R206 postdeployment
audit. Actual cross-host independent provider/monitor
real SLA and permissionless public validator joins still remain.
