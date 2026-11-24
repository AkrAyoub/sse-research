# R257 — ACTUAL original chain31340 finalized first TEST ETH funding; V2 create deployment now prepared BUT UNAUTHORIZED

## Owner VM4707 real R255 finality output (2026-11-24)

R255 (read-only, executed against actual original Besu localhost RPC
`http://127.0.0.1:28545`) returned unequivocal
`R255_REAL_NATIVE_V2_DEPLOYER_FUNDING_FINALIZED=true`
and the following verifiable facts:

- Original chainId **31340**, original execution genesis verified.
- Exact successful owner-authorized value transfer:
  `0x07e3ff069936936b3daf17efc5cb484c1712e93dc6bd6040c55a5fae1b8d2a90`
- Exact genesis-funded VM4706 sender:
  `0x13fb73aace8A11Be2899D047635A757a224Ce00B`
  with finalized sender nonce **1**.
- Exact separate application-only VM4707 deployer beneficiary:
  `0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0`
  now holding **1,000,000,000,000,000,000 wei = 1 TEST ETH**
  at the actual finalized execution state.
- Included successfully and canonically in block **24,966**;
  observed actual finalized execution block **25,076**
  (hash `0xe7c624b819d145adcf421f0cc8e1cd83cd564986250415f4a48309192395a73e`).
- The one real native transaction used **21,000 gas**,
  **1,000 wei/gas** effective, deducted **21,000,000 wei**
  network fee. Total sender debit **1,000,000,000,021,000,000 wei**.
- No V2 contracts were yet deployed or independently verified.
  NO further funding sender transaction is needed or allowed.
- Original VM4706 Genesis funded keystore and original signer
  stay on VM4706; no copying wallet or BLS validator material.

## Live VM4707 R256 native constructor fee evidence

At checked-out GitHub SHA
`b4018ce02d131e3f8a52935c2796248a4edab195`:

- **6/6** new R256 focused tests PASS on VM4707;
  actual `forge build -q` PASS;
- Compiled ABI SHA/source and constructor envelope matched the
  VM-green R249 source; the market constructor creates
  exactly one `SSEAdaptiveVoteLedger` internally;
- REAL `eth_estimateGas` from separate funded V2 deployer
  for `new SSEAdaptiveMarketV2(10**15)`
  was **6,670,081 gas**;
- Read-only padded ceiling proposal **8,342,601 gas**
  (25% + 5,000 allowance);
- Actual Besu suggested legacy gas price **1,000 wei/gas**,
  latest base fee **7 wei/gas**, block limit 30,000,000 gas;
- At 1,000 wei/gas, a padded execution cost cap would
  be **8,342,601,000 wei = 0.000000008342601 TEST ETH**,
  from the separate 1 TEST ETH deployer balance.
- The `10**15 wei = 0.001 TEST ETH` constructor monitor bond
  was used as an **illustrative R256 input**, not an
  economically meaningful Sybil deterrence assumption.
  TEST ETH has no real market value or independent identity.

## New substantial R257 application deployment operator code

`tools/sse_pos_r257_vm4707_one_time_v2_deployment.py`
is a new, not yet VM-tested one-shot native application deployment
sender. Its **default is strictly read-only preview**:

- Pins exact immutable feature branch Git HEAD and clean tracked
  source; rejects changes to V2 Solidity source, Foundry build
  profile and vendored libs relative to real R249 green SHA
  `6930c069b4e9738e63e2ce9d53b10d126053335e`.
- Calls R255 again; demands the exact real 1 TEST ETH funding
  tx is successful, canonical AND FINALIZED with 1 TEST ETH
  confirmed on VM4707 and source nonce1.
- Calls actual R256 native `eth_estimateGas` with the
  R249-pinned compiled V2 initcode, enforcing only the
  PROPOSED immutable `minimumBondWei=1000000000000000`,
  actual estimated/padded gas <=**8,342,601**, actual
  gas/base fees <=**1000 wei/gas**, app EOA finalized
  balance>=1 TEST ETH, EOA has no pending nonce/used nonce
  and the predicted CREATE address has no code.
- Prints a compact public authorization preview, initcode SHA256,
  predicted market CREATE address, immutable bond scenario,
  max gas/price/fee and no secrets or raw compiled bytes.
- NO wallet access, signing, creation or broadcast in preview mode.

A separate explicit `--send` mode is STAGED, NOT APPROVED
by the user merely from sharing finalized funding output.
It requires all guards above plus real owner VM4707 nonroot
interactive TTY, a fresh exact consent phrase
`DEPLOY-ONE-V2-CHAIN31340-BOND-0.001-TEST-ETH`,
local separately encrypted 0700/0600 application-only UTC-V3
keystore, hidden password prompt, decrypted PUBLIC signer
match, fresh native preflight after confirmation, signed
legacy contract CREATE tx with nonce0, value0, immutable
gasLimit8,342,601 gasPrice1000 wei and original chainId31340.

Before its ONLY `eth_sendRawTransaction` call it atomically
creates a private 0600 create-once attempt marker under the
app wallet directory. It prints the public precomputed txHash
before the RPC call; NEVER automatically resend if RPC fails,
times out or returns unknown status. The original funded
Genesis EOA is strictly NOT used as V2 deployment signer.
The script performs NO BLS, Docker or chain node changes.

### Next owner action: R257 only read-only preview

Fetch the exact GitHub SHA given in chat, pin checkout,
retain existing previously R249-successful compiled artifacts
(brief `forge build -q` only if absent), run the NEW
R257 focused policy tests and public-only default preview:

```bash
python3 -B -m unittest discover -s tests \
 -p 'test_sse_pos_r257_vm4707_one_time_v2_deployment.py' -q
python3 -B tools/sse_pos_r257_vm4707_one_time_v2_deployment.py \
 --source-sha <exact-current-SHA> --rpc http://127.0.0.1:28545
```

**No `--send`**, no password, no transaction, no keystore access
during this next task.

## Separate owner approval still required

The owner must explicitly approve the ONE actual deployment
from VM4707 app EOA with immutable
`minimumBondWei=1000000000000000`,
`gasLimit=8342601`, `gasPriceWei<=1000`,
`value=0`, and original chain31340. Even after approval,
actual native gas/preflight conditions may change; the sender
must fail closed rather than silently raise caps.

Actual deployment receipt and finalized on-chain Market+Ledger
runtime fingerprints/bindings must be independently verified
by R206 before any marketplace role transaction.
No live provider/monitor SLA, independent operator, Internet
permissionlessness or genuine unbiased VRF is claimed.
