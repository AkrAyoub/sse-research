# R254 — Explicitly approved EXACT one native TEST ETH funding transaction

## Explicit owner authorization in this conversation

The owner explicitly approved **one** transaction on original
native PoS chain **31340**, and only this scope:

- VM4706 EXISTING encrypted owner TEST-only EOA source:
  `0x13fb73aace8A11Be2899D047635A757a224Ce00B`
- VM4707 separate new encrypted adaptive V2 deployer destination:
  `0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0`
- Exactly **1 native worthless TEST ETH** value,
  1,000,000,000,000,000,000 wei
- Maximum **21,000** gas; maximum **1,000 wei/gas**;
  maximum additional gas fee 21,000,000 wei and maximum
  total debit 1,000,000,000,021,000,000 wei
- Owner previously tested actual `cast estimate` **21,000**
  and `cast gas-price` **1,000 wei/gas** on VM4706;
  operator-on-demand script must freshly verify current bounds.
- The transaction is NOT broadcast by this GitHub commit,
  this document or any assistant API. It is owner-local and
  deliberately waits for an additional exact TTY approval
  and existing KEYS-only hidden password prompt.

## One-shot script

`scripts/r254_vm4706_authorized_one_time_v2_deployer_funding.sh`

Pre-authorization checks:
- require the exact branch Git commit SHA and a clean tracked checkout,
  VM4706 nonroot owner, real TTY and `--send-one`;
- check installed Cast SHA256 against pinned v1.9.0 binary and
  old encrypted owner keystore file and directory permissions;
- fixed localhost VM4706 RPC, check original chain ID **31340**,
  actual original genesis hash, live EOA/no-code, current
  destination zero balance, pending sender nonce **0**;
- check fresh available native TEST ETH, block gas limit,
  current basefee and suggested price <= 1,000 wei/gas,
  actual `eth_estimateGas` == 21,000;
- unlock owner keystore solely to derive **public** EOA address,
  compare against exact publicly funded source, then request
  literal `SEND-ONE-CHAIN31340-1-TEST-ETH` approval;
- once approved, create an owner-only create-once *attempt marker*
  under original private owner app directory BEFORE broadcast.
  This permanently disables casual reruns of the script even
  after a node/CLI error. If the send times out, **do not
  delete marker or rerun** without inspecting live chain status.

Exactly ONE signed Cast CLI submission invocation:
- fixed `--keystore` owner local encrypted original file;
  prompts hidden keystore password (NEVER on command line);
- fixed `--legacy --gas-limit 21000 --gas-price 1000` (bare numeric price in wei)
  to enforce maximum gas fee; `--nonce 0`, `--chain 31340`,
  `--from` exact source, `--rpc-url` fixed localhost;
- fixed `--value 1ether` destination, `--async` returns
  transaction hash without receipt wait; no built-in retry.
- credentials kept out of GitHub/chat; original encrypted
  keystore never moves to VM4707. No Lighthouse signing keys
  or Docker modifications.

**IMPORTANT:** R254 script is newly committed GitHub source;
NOT claimed executed or green on actual VM4706. Operator must
first run `bash -n` for shell syntax and the interactive
live preflight. If it refuses, return the SANITIZED refusal
marker; NEVER bypass checks or manually rerun Cast.

## After receiving public transaction hash

Do **only read-only verification**, first on VM4706, then
on independent observer VM4707. Ensure the final receipt has:
- successful status 1;
- exact sender/source and destination;
- 1 ether transaction value;
- gasUsed <=21,000, effectiveGasPrice <=1,000 wei/gas;
- canonical included block and consensus-finalized execution
  height >= transaction block;
- deployer balance actually increased by exactly 1 TEST ETH;
- source nonce advanced to 1.

A successful `--async` send only establishes RPC accepted a
submitted hash, not finality. Finalization must be independently
observed before V2 deployment; no re-submit.

## Proven prior context

- R249 source suite verified on VM4707 at SHA
  `6930c069b4e9738e63e2ce9d53b10d126053335e`:
  Python 1,275 PASS, 3 skipped, V2 Foundry 21/21 PASS,
  compiler ABI match 21 actions and 28 events.
- Actual VM4707 separate new V2 app EOA has zero native TEST ETH,
  encrypted keystore mode0600 and directory0700.
- Actual VM4706 source EOA balance
  **1,000,007.984391109 TEST ETH**, nonce **0**.
- Historical VM4706 R28 owner keystore unlock derived exact
  funded Genesis public address.

**A funding transfer alone is not deployment.** Subsequent
app-only deployer EOA signing from VM4707 requires a SEPARATE
explicit approval for ONE market+ledger deployment, safe
minimumBondWei and bounded deployment cost, then R206
finalized code/receipt verification.
