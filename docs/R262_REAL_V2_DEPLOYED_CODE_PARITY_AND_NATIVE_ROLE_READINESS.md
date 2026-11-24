# R262 — REAL deployed Solidity runtime parity PASS; native role readiness one-shot audit

## Owner-reported real live execution evidence (VM4707)

Original chain31340 Besu localhost endpoint `http://127.0.0.1:28545`:
- Successful exactly one actual on-chain market CREATE receipt
  `0xe9187bd24d72d2dec11fc6a2758802ddf6fa46a2941edd306329173fe132d6b6`;
  included at block **25339**, gas used **6616403**.
- Actual **LATEST** market address
  `0x6C01dBd7aA336a96d8Ab09Ea631E209612224080`
  bytecode **19263B**, SHA256
  `aed48968f9b5ef4e8f238efaed8c539af5c8799de181f290b38a21803386c261`.
- Actual **LATEST** linked vote ledger
  `0x6635849b77f037fab611736612d7d3493dc650ff`
  bytecode **10668B**, SHA256
  `3a14ac0cd120271c50ac31661b6080546477aa8218e9944e51dd89998b78622d`.
- Actual VM4707 owner command imported R260
  `verify_compiler_runtime` on both **REAL live** deployed
  `eth_getCode` blobs and the pinned Foundry compilation.
  **`LATEST_SOLC_BYTECODE_PARITY_VERIFIED=true`**.
- It proved **ALL nonimmutable bytes match** actual compiler runtime.
  Solc-reported immutable patch slots: **27 market, 12 ledger**.
  The three known actual constructor-assigned immutable
  values proved via both getters and actual Solc patch slots:
  market.votes points to ledger, market.minimumBond==1e15
  wei and ledger.settlement points to market.
- **`TRANSACTIONS_SENT=false`** from this read-only parity check.
- Previous owner R141 captured Beacon head slot27061
  (epoch845), finalized Beacon epoch841, 2+2 native peers,
  EL head25449/finalized25300; latest formal observation
  still **39 execution blocks SHORT** of deployment finality.
  No claim of finality after this until a newer on-chain read.
- R260/R206 finalized contract audit still NOT observed PASS.
  This is NOT physical operator, real SLA, external physical
  compute or unbiased VRF evidence.

## New useful code to advance *actual* marketplace operations

`tools/sse_pos_r262_native_v2_live_market_readiness.py`
is a NEW, deliberately single-shot (no polling) and completely
READ-ONLY RPC market-state observer. It requires exactly
chain31340+original genesis, actual owner-approved successful
canonical market CREATE receipt, both latest on-chain bytecodes
with **exact R261 recorded SHA256 hashes**, actual immutable
getters market↔ledger+minimumBond, byte-for-byte Solc compiled
nonimmutable parity, the three actual known Solc immutable values,
then reads public getters:

- `market.activeMonitorCount()`: **how many real bonded
  monitor EOAs have actually registered**, not planned counts;
- `market.nextRequestId()`, `market.nextLeaseId()`:
  actual consumer resource request/escrow lease counters;
- `totalServiceEscrow()`, `totalPendingMonitorFunding()`,
  `totalMonitorBonds()`, `totalWithdrawable()`;
- `ledger.totalUnspentReserves()` and
  `ledger.totalWithdrawableCredits()`;
- actual MARKET + LEDGER native latest contract balances and
  invariant each exceeds/equals its reported outstanding
  escrow/bond/withdrawal liabilities;
- actual latest versus finalized execution heights and
  precise remaining deployment-finality blocks.

The observer does **not** send any transactions or touch
wallets, Docker or Beacon. It does **not** treat a finalized
height covering the inclusion block as R206/R260 audited
code/finality; it separately prints `formalR260R206FinalizedAuditRunByThisTool:false`.
New 5 unit mock tests are included, but **not yet VM-tested**;
source authorship is not live test evidence.

### Immediate VM4707 command

Use the exact immutable R262 source SHA from chat, the
existing `/tmp/tmp.Ridv9nIavf/repo` checkout, and existing
`/tmp/tmp.Ridv9nIavf/testvenv/bin/python`:

```bash
PY=/tmp/tmp.Ridv9nIavf/testvenv/bin/python
"$PY" -B -m unittest discover -s tests \
 -p test_sse_pos_r262_native_v2_live_market_readiness.py -q
"$PY" -B tools/sse_pos_r262_native_v2_live_market_readiness.py \
 --rpc http://127.0.0.1:28545
```

As soon as `finalizedExecutionBlock>=25339`, run R260
then R206 on `evidence/r261_vm4707_latest_state_v2_deployment_candidate.json`.
Do NOT rerun R257 `--send`.

**The next genuine state-changing application milestone** requires
actual separately controlled funded monitor EOAs (>=4 eligible
for one Byzantine-fault-tolerant committee with f=1),
consumer and provider EOAs, and real service hardware/endpoint.
`tools/sse_pos_test_wallet.py` already creates owner-only
encrypted research EOAs on their actual host with hidden
password confirmation; this does NOT fund them or prove
independent physical operators. Role transaction sender
R242 remains **separately consent-gated**. Do not imply
permission to transfer more TEST ETH based on prior
one-time deployment consent.
