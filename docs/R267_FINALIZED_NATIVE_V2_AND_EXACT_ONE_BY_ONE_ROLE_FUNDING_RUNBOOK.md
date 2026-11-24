# R267 — Native chain31340 V2 DEPLOYMENT FINALIZED, exact one-by-one app wallet TEST ETH funding STAGED

## Real owner VM4707 finality + actual code verification completed (2026-11-24)

At exact owner-executed checkout `72265cc545ca6cfc68ec91bbe60968ce2b4e465e`,
owner logs show **8/8** new R265 funding-quote policy tests
PASS; actual original chain31340 read-only funding quote
PASS; **R260 actual first V2 deployment fully finalized audit**
PASS and **separate R206 actual original native runtime finalized
audit** PASS. Actual owner stdout:

- `R265_REAL_VM4707_THREE_ROLE_FUNDING_QUOTE_ONLY_NO_SEND=true`
- `R260_REAL_NATIVE_V2_MARKET_AND_LEDGER_FINALIZED_AND_R206_VERIFIED=true`
- `V2_DEPLOYMENT_FULLY_VERIFIED=true`
- Finalized execution block **25364** hash
  `0x6a55a553c18ce93a8eb433d79763c13b2a11e3061cf65838783070e111e6303a`,
  fully covering successful market CREATE block **25339**.
- Actual sole owner-authorized creation transaction
  `0xe9187bd24d72d2dec11fc6a2758802ddf6fa46a2941edd306329173fe132d6b6`.
  Actual RLP tx nonce0, contract CREATE value0,
  gasUsed **6,616,403**, gasPrice **1000 wei**,
  actual gas fee **6,616,403,000 wei**,
  less than authorized cap **8,342,601,000 wei**.
- Actual Market `0x6C01dBd7aA336a96d8Ab09Ea631E209612224080`,
  runtime SHA256
  `aed48968f9b5ef4e8f238efaed8c539af5c8799de181f290b38a21803386c261`.
- Actual internally created VoteLedger
  `0x6635849b77f037fab611736612d7d3493dc650ff`,
  runtime SHA256
  `3a14ac0cd120271c50ac31661b6080546477aa8218e9944e51dd89998b78622d`.
- Compiler exact Solc runtime bytes outside immutable slots
  100% match actual deployed bytes. Market has
  **27 Solc immutable slots**, ledger **12**. Their
  known immutable values bind votes(), settlement(),
  and minimumBond() **1000000000000000 wei**.
- Original exact one-time native genesis→app funding
  was separately proven canonical+finalized at its
  historical block; no erroneous assumption that
  app balance stayed 1 ETH after deployment gas.
- The *native V2 contract deployment milestone is
  COMPLETE*. Never rerun R257 --send, rerun the
  original Genesis R254 transfer, create a second
  market or alter validator/chain genesis.

## Real actual app-EOA funding quote also passed

Actual chain31340 R265 observed deployer app-only EOA
`0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0`
at pending nonce **1**, balance
**999,999,993,383,597,000 wei** (the original 1 TEST ETH
minus its real 6,616,403,000 wei CREATE gas).
The three newly owner-created VM4707 cryptographically
distinct encrypted app-only role EOAs remain real
ONCHAIN zero-balance, nonce0, no code:

| Actual role | Actual public address | Exact PROPOSED funding |
| --- | --- | ---: |
| Consumer | `0xD74A2aBC5a906BaFe39471CEe222c48BDD62DE3f` | 0.010 TEST ETH, 10000000000000000 wei |
| Monitor1 | `0xd63b2Ba14E8aD16Cf5f494259dAE05AD59fE0147` | 0.005 TEST ETH, 5000000000000000 wei |
| Monitor2 | `0xf8D4c882A7439507e2fc237DCBDf4A1c228F0FF8` | 0.005 TEST ETH, 5000000000000000 wei |

Actual native Besu estimated **21,000 gas** for EACH
recipient, price <=1000 wei/gas. Total *proposed*
role transfer value **20,000,000,000,000,000 wei**,
maximum cumulative transfer gas **63,000,000 wei**,
maximum proposed combined debit
**20,000,000,063,000,000 wei**.
None of these role TEST ETH transfers is yet authorized
by user or signed/broadcast. The wallet keystores are
private owner-local, never GitHub. All are the SAME
VM4707 fault domain, so not independent physical monitors.

## New R267 OWNER-ONLY single transfer implementation

`tools/sse_pos_r267_vm4707_one_by_one_role_funding.py`
only operates on the above EXACT three fixed recipient
addresses, values and order. **Default is READ-ONLY**:
`--role consumer` previews proposed ONE consumer transfer
after redoing real native R206 finalized receipt/runtime/wiring
audit. It checks actual source APP balance/latest+pending
nonce1, gas/base fee <=1000, actual 21000 gas estimate,
recipient zero balance/nonce/no code, capacity for all
remaining allocations.

Subsequent transfers use exact roles
`monitor-1` at source nonce **2** and
`monitor-2` at source nonce **3**. No stage
can run until all its preceding transfer attempt
markers exist, the actual signed transaction matches
fixed chain31340/from/to/value/nonce/gas, the receipt
status is successful, inclusion is canonical,
**inclusion is FINALIZED**, and recipient still holds
at least the original funded value. Each stage also
revalidates R206 actual finalized market state.

Only after explicit separate user authorization of
these transfers may owner use `--send`. This enforces:
- Only VM4707 nonroot `ayoubakrvm4707` owner, correct
  encrypted existing app-only deployment keystore in
  existing private 0700 directory / 0600 file;
  **original Genesis signer, BLS validators never used**;
- Exact pinned Git SHA, clean source and immutable
  original audited V2 Solidity code; no source
  or EVM code drift;
- Clearly printed exact public intent and per-role
  TTY approval phrase specifying role, value in
  wei and exact nonreusable nonce, private hidden
  keystore password;
- Fresh full native R206 and same-target no-double
  funding/nonce/gas preflight after approval;
- Locally sign exact legacy EIP-155 chain31340,
  verify recovered APP signer, then RLP-decode
  actual signed raw transaction and verify nonce,
  recipient, full wei value, 21000 gas, gas price
 1000, chain v, empty data;
- Atomically write an owner-only 0600 create-exclusive
  per-role funding-attempt marker holding ONLY public
  metadata and locally precomputed signed tx hash
  **BEFORE exactly one** `eth_sendRawTransaction` call.
  If RPC ambiguous/rejects, marker persists; do NOT
  rebroadcast, delete the marker or blindly replace nonce.
  Signed raw tx and secret never printed;
- No loops, auto retries, batch signing, unattended
  background broadcasts, or user-keystore copies.

New focused offline mocked and fake-ephemeral-signing
tests authored in
`tests/test_sse_pos_r267_vm4707_one_by_one_role_funding.py`.
**Source/testing stage: NOT yet executed on VM4707**.

## Next owner action: safe public-only one-stage check

After fetching exact latest R267 Git SHA communicated in
chat and verifying checkout, use actual existing testvenv:

```bash
PY=/tmp/tmp.Ridv9nIavf/testvenv/bin/python
"$PY" -B -m unittest discover -s tests \
  -p 'test_sse_pos_r267_vm4707_one_by_one_role_funding.py' -q
"$PY" -B tools/sse_pos_r267_vm4707_one_by_one_role_funding.py \
  --source-sha <exact-current-40-character-Git-SHA> \
  --role consumer --rpc http://127.0.0.1:28545
```

**DO NOT run `--send` without new explicit user approval**.
After user approves exact three funding transfers and caps,
send only consumer nonce1, obtain real canonical+finalized
receipt first; then monitor1 nonce2, finality; then
monitor2 nonce3, finality. Do not fabricate progress.

## Genuinely separate provider/other monitor operators still outstanding

After funds/registrations on chain, onboarding/real compute
requires distinct provider and two additional monitors,
actual operator-host wallets and network reachability,
real provider Docker worker and real external HTTP
monitor evidence. Four Ethereum EOA addresses in one
laboratory VM do NOT demonstrate physical fault domain
independence, economically meaningful Sybil resistance
or the user's public Internet permissionless onboarding
requirement. The 0.001 TEST ETH bond is an experimental
research minimum, not production economic security.
