# R261 — REAL VM4707 on-chain market & ledger bytecode+immutable bindings at LATEST; finality remains open

Owner VM4707 real loopback Besu read-only RPC result from
2026-11-24, existing real native original chain31340:

- Single successful actual owner-authorized V2 CREATE tx
  `0xe9187bd24d72d2dec11fc6a2758802ddf6fa46a2941edd306329173fe132d6b6`,
  included in canonical execution block **25339**,
  actual execution gas used **6,616,403** (from R260 successful receipt).
- Actual on-chain latest state execution block **25424**,
  finalized execution block **25268**. Finalized does NOT yet
  cover deployment: **71 blocks short**. Do NOT resend.
- `eth_getCode(market,latest)` nonzero: contract
  `SSEAdaptiveMarketV2` at
  **`0x6C01dBd7aA336a96d8Ab09Ea631E209612224080`**,
  **19,263** runtime bytes with actual runtime SHA256
  **`aed48968f9b5ef4e8f238efaed8c539af5c8799de181f290b38a21803386c261`**.
- `eth_call(market.votes(),latest)` returned distinct actual
  vote ledger **`0x6635849b77f037fab611736612d7d3493dc650ff`**.
- `eth_getCode(ledger,latest)` nonzero:
  **10,668** runtime bytes, actual SHA256
  **`3a14ac0cd120271c50ac31661b6080546477aa8218e9944e51dd89998b78622d`**.
- `eth_call(ledger.settlement(),latest)` returned exactly
  the deployed market; `market.minimumBond()` returned
  **1,000,000,000,000,000 wei** as owner authorized.
- Owner command asserted `MARKET_LEDGER_MUTUAL_LINK_VERIFIED=True`
  and `LATEST_STATE_LINKAGE_VERIFIED=true`.
- This is **REAL EVM code on the live canonical head**,
  NOT a simulation, but runtime fingerprints/immutables
  are only verified at latest head, NOT yet R260 byte-for-byte
  parity or R206 at finalized block.

## Useful concrete progress: public R206 manifest candidate created

Committed `evidence/r261_vm4707_latest_state_v2_deployment_candidate.json`
from the above actual VM4707 output. It contains only
PUBLIC market/ledger addresses, runtime SHA256s, deployed
tx hash, test-Eth bond and original chain genesis/deployer.
It is a **candidate**, NOT R206-verified yet. Do NOT rename
it into a verified attestation or merge it to main as proven.

As soon as execution finality covers block **25339**, the
existing source read-only `R206` can independently audit
the exact successful creation transaction, canonical/finalized
receipt, both actual runtime hashes, and immutable
market/votes/ledger/settlement/bond bindings, using this
candidate directly (without first writing a new manifest):

```bash
PY=/tmp/tmp.Ridv9nIavf/testvenv/bin/python
$PY -B tools/sse_pos_r206_adaptive_v2_deployment_audit.py \
  --manifest evidence/r261_vm4707_latest_state_v2_deployment_candidate.json \
  --rpc http://127.0.0.1:28545
```

The deeper R260 audit also checks real Solc compiled
bytecode outside immutable patch slots, exact authorized
constructor, original historical funding and fee cap:

```bash
$PY -B tools/sse_pos_r260_v2_readonly_finalized_deployment_audit.py \
  --rpc http://127.0.0.1:28545
```

R260 may return `R260_NOT_FINAL_YET_DO_NOT_RESEND` until
finality reaches 25339. Neither tool accesses wallets or
changes running chain/node/validator. If R260 encounters
a runtime parity mismatch, investigate actual data; NEVER
rerun R257 --send.

To cross-check after finalization, fetch same pinned public
manifest source on VM4706 and run existing R206 on
`http://127.0.0.1:18545` with VM4706's available Python
environment. A same-manifest PASS from two actual separately
running EL clients improves network consistency evidence.

## Next application deliverables (NOT yet live)

Genuine monitor, consumer and provider independently owned
application EOAs and native test-ETH balances, actual bond
registration, resource profile/physical provider Docker
workload, real independent monitor HTTP observations and SLA
votes, finalization/payout, actual WAN onboarding and
validator independence remain open. The existing
`R226/R239/R242` send plan requires **separate approval for
every wallet, funding and role transaction**, never reuses
R257's already consumed CREATE approval.

Although 0.001 TEST ETH is real on-chain contract escrow,
it has no meaningful external value and is not Sybil
resistance or proof of physically independent monitors.
