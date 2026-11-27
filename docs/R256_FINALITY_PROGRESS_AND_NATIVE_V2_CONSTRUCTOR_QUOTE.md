# R256 — Genuine VM4707 healthy Beacon and canonical R254 funding awaiting finality; actual native deployment gas quote next

## Owner evidence 2026-11-24 UTC

R141 actual VM4707 original chain31340 native EL+CL health:

- 16:42:08.661933Z: Beacon head slot **26609**, execution block
  **24997**, finalized Beacon epoch **827**, finalized root
  `0xaf3a0dc5cc13527ea117952dc86bccc1467284a9f3c9318b18709827646a8861`.
- 16:42:32.379058Z: Beacon head slot **26611**, execution block
  **24999**, same finalized Beacon epoch **827** and same root.
- Both captures: original execution genesis, original Beacon
  genesis root, **2** native EL peers and **2** native CL peers,
  no EL sync, no CL sync, no optimistic head, no CL EL-offline.
- Head epoch `26611//32 = 831` and finalized epoch 827,
  a **four-epoch** gap. Two slots of identical checkpoint
  do not demonstrate finality stall, but 4 epochs behind head
  merits follow-up if it persists. The earlier R255 EL snapshot
  had finalized execution block 24852 and included funding
  tx block 24966; finalization has not reached that transaction.
- R255 reports from BOTH VM4706 and VM4707:
  `CANONICAL_RECEIPT_PRESENT_BUT_NOT_YET_FINALIZED_DO_NOT_RESEND`.
  No repeated signed sender/nonce0 transaction is allowed.
- R255 owner VM4706 targeted regression tests **8/8 PASS**.

## R256 substantive source implementation

`tools/sse_pos_r256_v2_readonly_native_deployment_quote.py`
performs an **actual call to the original VM4707 Besu
`eth_estimateGas`** using the fully compiled Foundry
`SSEAdaptiveMarketV2` constructor initcode AND exactly
one ABI-encoded `uint256 minimumBondWei` argument.
The market constructor itself creates the linked immutable
`SSEAdaptiveVoteLedger`, so this estimates their single
real contract-creation transaction, not a simple transfer.

It checks:
- exact R249 audited actual compiler ABI hashes for BOTH
  market and ledger, R247 action/event/return schema parity,
  exact known contract runtime bytes and market initcode bytes;
- approved original chain31340 ID and exact EL genesis;
- block gas limit, actual latest/finalized height, real app
  deployer latest and finalized balances, sender no code;
- actual `eth_gasPrice`, `eth_estimateGas` on constructed
  nonpayable create transaction with from the exact new app
  EOA `0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0`;
- illustrative 25% + 5,000 gas allowance and scenario upper
  fee at current reported gas price, against real block limit
  and balances. This is **not** an authorization for that
  gas cap or immutable policy value.

The code never asks for a password, imports a private key,
sends a raw transaction, writes a wallet, touches Docker or
unlocks a validator. Existing R249 green source verification
is not invalidated by this new tool addition.

Six new *mock-only* policy regressions exist in
`tests/test_sse_pos_r256_v2_readonly_native_deployment_quote.py`.
**This new code and the actual Besu quote have not yet been run
on VM4707**; return exact terminal output, don't claim PASS.

### R256 read-only owner command on VM4707

From the correct fetched immutable new SHA (provided separately),
with the existing user-owned pinned toolchain and pinned compiled
artefacts under `out/`:

```bash
cd /tmp/tmp.Ridv9nIavf/repo
export PATH="/tmp/tmp.Ridv9nIavf/testvenv/bin:$HOME/.local/share/sse-r19-toolchains/foundry-v1.9.0:$PATH"
python3 -B -m unittest discover -s tests -p 'test_sse_pos_r256_v2_readonly_native_deployment_quote.py' -q
forge build -q
python3 -B tools/sse_pos_r256_v2_readonly_native_deployment_quote.py \
  --rpc http://127.0.0.1:28545 \
  --minimum-bond-wei 1000000000000000
```

**The above 0.001 TEST ETH example is ONLY an estimate scenario**,
reused from the Foundry test fixture to exercise the constructor.
It is NOT research-backed resistance to Sybil attacks, a
final immutable bond policy, a transaction approval, or
permission to broadcast. TEST ETH is worthless; a
deposit denominated solely in freely obtainable TEST ETH
does NOT prove economic resistance or independent identity.

## Actual acceptance gates still open

- R255 funding transaction receipt must achieve original execution
  finality. Current receipt success and canonical inclusion are
  observed on two real nodes; **finality not yet proven**.
- Owner must approve an actual immutable minimum monitor bond and
  explicit bounded deployment gas/value fee before signing or
  broadcasting any V2 creation from VM4707 app EOA.
- Real V2 deployment and R206 finalized runtime/receipt/wiring,
  bonded monitor registration, paid real resource lease with
  independent monitor SLA, unbiased committee selection, and
  permissionless Internet/node/validator independence are still
  NOT verified.
