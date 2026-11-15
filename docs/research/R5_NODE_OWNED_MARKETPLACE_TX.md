# R5 — Participant-owned marketplace transactions (research slice)

**Status (2026-11-15):** code and offline regression tests committed; NOT yet locally executed or accepted. No VM configured or Ethereum transaction sent by this branch.

## Trust boundary

The consumer, provider and monitor run the CLI **on their own Ubuntu machines**, with their own signer. The independent SSE dashboard cannot send requests, select bids, set prices or sign votes. A signed transaction is not proof that the underlying provider delivered an SLA-compliant service; monitor vote production remains a separate evidence-bound R4 task.

The default mode emits a **read-only JSON plan**, with canonical Solidity selectors and static ABI calldata. It neither contacts an RPC nor reads any key. Only `--execute` can read a local owner-only signing file and submit a transaction.

Supported actions:

| Owner role | Action | Actual contract entry point |
|---|---|---|
| consumer | `request` | `OpenResourceBoard.requestResource` |
| provider | `bid` | `OpenResourceBoard.placeBid` |
| consumer | `fund` | `OpenResourceBoard.chooseBidAndFundLease` |
| provider | `accept` | `SSESettlement.acceptLease` |
| monitor | `monitor-register` | `OpenMonitorCommittee.register` |
| monitor | `monitor-confirm` | `SSESettlement.confirmMonitorAssignment` |
| consumer | `admit-epoch` | `SSESettlement.admitEpoch` |

A funded bid selection uses the consumer's **exact** `selectedEpochFeeWei × maxEpochs` deposit, verifies the live winning bid's fee and contract reciprocal binding, and rejects changed fees before signing. Contracts enforce ownership and phase restrictions; RPC preflight estimates gas and checks the chain ID and deployed bytecode.

**Not yet implemented:** locally signed provider HTTP/ACK response wired to lease; R4 evidence collection and independently qualified signed monitor votes; committee randomness or eligibility activation; automatic autonomous transaction schedules; UI-triggered wallet approval and key custody; production-grade signer isolation; public hosting; deployable running code updates; finality proof. Provider/monitor UI currently stores draft preferences only.

## Offline demo plan

Use actual contract addresses from an existing deployment, not the placeholder addresses below for `--execute`.

```bash
python tools/sse_node_marketplace.py \
  --role consumer --action request \
  --params-json '{"profileHash":"0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","policyHash":"0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","maxEpochFeeWei":25,"biddingClose":1800000000}' \
  --chain-id 31337 \
  --board 0x1111111111111111111111111111111111111111 \
  --settlement 0x2222222222222222222222222222222222222222 \
  --pool 0x3333333333333333333333333333333333333333
```

This prints only the proposed transaction, including `ethereumTransactionsSent: false`. It is safe as an offline demonstration of encoding, not an SLA/chain validation.

### Explicit lab-only transaction mode

`--execute` additionally requires `--rpc-url`, `--signer-file` and `--max-total-wei`. The signing file must be owned by the executing Ubuntu account, mode `0600`, inside a non-world-writable root-owned/owner-owned `/run/sse/` directory and contain a 64-hex-character EOA secret. **This plaintext local key mechanism is a lab-only adapter**, not recommended production custody. Do not put wallet secrets into browser forms, GitHub, URL parameters, shell command arguments or centralized dashboard data. Provision owner-controlled one-off lab keys through secure VM facilities. Never use Anvil's public deterministic mnemonic on Sepolia or with real value.

The RPC must be HTTPS or loopback HTTP. A remote Anvil host must be made reachable with a properly authenticated private tunnel/HTTPS RPC proxy. Transactions use explicit fee/escrow caps, live gas estimation and returned receipt verification; receipt status `MINED_UNFINALIZED` is not proof of chain finality. Do not run `--execute` against an unspecified or placeholder deployment.

## Acceptance tests

```bash
python -m unittest discover -s tests -p 'test_sse_node_marketplace.py' -v
python -m unittest discover -s tests -q
```

Additional acceptance requires dedicated disposable Ubuntu Anvil testnet, independently controlled role signers, real resource board and settlement contracts, actual request/bid/winner/funding/acceptance flows, contract event indexing, and eventually node-local UI integration with separately authorized signer operations.

The `fund` action is not equivalent to `chooseBid` alone: **funding escrow is part of the contract method**. Monitor `register` is bond-backed, but initial committee participation still requires a properly selected/confirmed assignment and qualified evidence.
