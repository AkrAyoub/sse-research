# WP-08C — Read-only chain-bound evidence-capture context

**Status (2026-11-13): implementation branch; CI and review pending.**
**Scope:** R4/R5 integration slice, no production contract, ABI, settlement, or reward changes.

## Goal

WP-08B accepted a caller-supplied `VerificationContext` holding a monitor
address. That was legitimate for the synthetic lab but insufficient for
authorization against an actual SSE lease. This increment adds the **optional**
`--rpc-url` path to `services/monitor-agent/evidence_capture.py`.

In chain-bound mode, `sse_wp08c_chain_binding.bind_capture_to_chain` invokes
the existing **read-only** `sse_chain_read.inspect_chain` and rejects capture
unless the existing SSE V1 contract reports all of the following:

1. Expected chain ID; settlement bytecode, EIP-712 domain, and lease ID at one
   numbered local block (provided by the existing inspector).
2. A real admitted epoch whose lease/epoch IDs, exact request hash, expected
   deterministic response hash, provider, SLA-policy hash and resource-profile
   hash match the user-supplied expected scope.
3. The exact localhost provider endpoint matches the on-chain endpoint
   commitment (checked by `inspect_chain`).
4. The lease is **Active**, evidence remains unsealed/open, and the sampled
   chain block timestamp has not exceeded `monitoringClose`.
5. All four selected committee addresses are valid, distinct from one
   another and from the consumer/provider, and all four have confirmed their
   assignments. Because SSE V1 only increments the confirmation counter once
   for each selected monitor, the recorded count 4 implies all four confirmed.
6. The requested provider matches the lease provider. The complete authorized
   monitor set is then derived from the on-chain selected addresses, **not**
   from the invoking monitor key.

The resulting `VerificationContext` is used by WP-08B when validating the
monitor key and when inserting the signed raw observation into SQLite. A
nonselected signer is refused.

### Running (local Anvil only)

Existing WP-08B synthetic capture remains unchanged if `--rpc-url` is omitted,
but is explicitly labeled operator-supplied. To enable a chain-bound run, use
the same arguments as `R4_WP08B_SIGNED_HTTP_ARCHIVE.md`, adding:

```bash
  --rpc-url http://127.0.0.1:8545
```

**Important:** The sample WP-08B lease/epoch/provider values are synthetic.
They will be rejected by this mode. Use a genuinely funded, active epoch with
matching on-chain commitments and a selected, confirmed monitor. The original
direct-lease demo does not set a nonzero SLA-policy hash; it cannot satisfy
the WP-08C `EvidenceScope` and is deliberately rejected. A marketplace-created
lease with a nonzero SLA-policy commitment is required under this version.

The RPC URL must pass the existing `LocalRPC` loopback restriction. An RPC
error, wrong chain, unadmitted epoch or mismatch aborts the command; it **never
falls back** to the synthetic context after `--rpc-url` is selected.

## Reproduction

```bash
python -m unittest discover -s tests -p 'test_sse_wp08c_chain_binding.py' -v
python -m unittest discover -s tests -v
forge build
forge test -vv
```

The WP-08C tests inject structured results from the existing chain inspector;
they exercise the authorization boundary and refusal matrix. The independent
existing `test_sse_chain_read.py` exercises the RPC/ABI inspector. **The new
tests are not a live end-to-end Anvil/HTTP integration test.**

## Explicit nonclaims and remaining work

- A locally configured RPC can lie or be compromised. Reading contract state
  from a single local RPC, even at a numbered block, is **not a proof of
  finalized canonical Ethereum state**. No independent header/finality
  validation, cross-client RPC quorum, or light-client proof is implemented.
- There is no protection here against a reorganization between state reading
  and the off-chain probe. This is a preflight authorization snapshot, not
  atomic execution with finality.
- The archived HTTP payload, provider signature and monitor signature do not
  prove consumer-side physical delivery, timing, service correctness or
  independence of monitor operators.
- No `QualifiedFact`, monitor `Success` vote, SLA payout, slash, or on-chain
  evidence assertion is authorized by this extension.
- Off-chain archive persistence is local SQLite; no external checkpoint or
  cross-host replication is implemented.
- The `monitorConfirmations == 4` requirement exposes SSE V1's no-show
  availability limitation; changing committee size/reassignment is **R3**.

**Next WP-08C/D gate:** bind to authenticated finalized chain state and its
header/hash provenance; persist block identity with records; add an actual
marketplace-funded Anvil + independently started monitor integration test; then
review any future physical-evidence qualification policy under R1/P1 before
allowing money-releasing behavior.
