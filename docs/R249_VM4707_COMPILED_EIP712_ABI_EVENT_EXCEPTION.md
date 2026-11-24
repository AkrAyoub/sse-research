# R249 — VM4707 actual compiled Solidity ABI parity: inherited EIP-712 event

## Actual owner VM4707 source-only result — 2026-11-24

Immutable tested SHA: `c611ed1ff64059c642e30f0fc96f66d09feb057e`.

- R248 R247 ABI-checker source unit tests: **9/9 PASS**.
- `forge build -q` returned success on the observer VM.
- Next source-only command, `python3 -B tools/sse_pos_r247_v2_compiled_abi_parity.py`,
  **correctly failed closed**, reporting:
  `market compiled events no longer match every Python decoder; missing=['EIP712DomainChanged()']; unexpected=[]`.
- This is a third-party inherited
  `EIP712DomainChanged()` event (IERC5267/OpenZeppelin
  `EIP712`) exposed in the compiler-generated ABI because
  `SSEAdaptiveMarketV2` extends OpenZeppelin `EIP712`.
  The SSE R227 event decoder intentionally describes SSE protocol
  events and not an un-emitted EIP-712 domain notification.
- This failure **does not show a contract or live chain failure**,
  but also does not establish R247 ABI parity PASS. The *ledger*
  compiled event parity check and struct-return checks were not yet
  reached because the script stopped at the market event.

## GitHub-only corrective implementation

- R247 checker now permits ONLY the exact inherited
  `EIP712DomainChanged()` event, if present on either V2 contract;
  validates `anonymous: false` and **zero inputs**.
- The code continues to require ALL application events from
  `MARKET_EVENTS` / `LEDGER_EVENTS` and checks exact signature,
  indexed parameter flags and data types.
- Missing SSE events, unknown new events, malformed anonymous
  domain events, altered parameter signatures or duplicate
  signatures still fail closed. Error text distinguishes
  `missingApplicationEvents` from `unrecognizedCompiledEvents`.
- Added R249 explicit tests for both contract roles, optional
  inherited domain event, missing application event, unknown event,
  malformed/anonymous domain event and duplicate.
- **R249 code has not yet been run on VM4707.** Do not assert
  that compiled market and ledger ABI schemas match until that
  owner-run output includes the generated full audit.

## Previous green baseline and incomplete real-network work

At immutable `6a25aa4aa86295cdac5d86596e95e18393e08b8f`,
R235 VM4707 complete regression passed: Python 1,268 OK
(3 skipped), adaptive Solidity 21/21, whole forge test exit0,
compiled market runtime 19,263B under EIP170. That is a
**source-only baseline**, not a V2 live deployment or
real provider SLA validation.

No source-only test broadcasts transactions; neither R248 nor R249
changed the original chain31340, VM4706 validator, test ETH,
Docker services, BLS keys or app wallets. PR #43 stays draft.
