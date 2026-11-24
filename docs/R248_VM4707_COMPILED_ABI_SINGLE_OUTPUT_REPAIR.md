# R248 — VM4707 R247 compiled ABI test: fix single array/scalar vs struct ambiguity

## Observed VM4707 source-only test result

Date 2026-11-24. Immutable source
`6e50557d30b9d7c6835b8a5927c5a90ec18f1bd6`
on observer VM4707, existing isolated Python 3.12 venv and
Foundry 1.9.0:

- Targeted R226–R229 **38/38 PASS**.
- Targeted R231–R239 **43/43 PASS**.
- R242 one-transaction consent policy **6/6 PASS**.
- R201 read-only original-chain mock policy **5/5 PASS**.
- R206 finalized runtime mock policy **6/6 PASS**.
- Full Python **1,275 run, 1 ERROR, 3 skipped**;
  therefore 1,271 passing and no reported assertion failures.
- Exact failure:
  `test_sse_pos_r247_v2_compiled_abi_parity.TestR247CompiledV2ABIParity.test_check_dynamic_selected_addresses_and_escrow_abi`.
  The checker `check_function` assumed any single tuple in
  `outputs` was a nested Solidity struct:
  `if len(outputs)==1 and type(outputs[0]) is tuple`.
  But `[("monitors","address[]")]` is a normal single
  dynamic array getter, so iterating strings as field pairs raised
  `ValueError: too many values to unpack (expected 2)`.
- This is a **new R247 ABI checker defect**, not a chain31340 failure,
  and was caught before it attempted actual compiled Solidity ABI parity.
  The full R235 script is fail-fast; this VM run did **NOT**
  reach new Solidity compilation, real artifact ABI inspection,
  21-test Foundry suite or full Foundry suite.
- The prior full R235 source PASS at
  `6a25aa4aa86295cdac5d86596e95e18393e08b8f`
  remains valid: Python 1,268 OK (3 skipped), 21/21 adaptive V2
  Foundry PASS, full Forge exit0 and market runtime 19,263 bytes.
  Do not misattribute those to this new R247 revision.

## GitHub-only correction

- Distinguish a **nested struct schema**
  `[((fieldName,fieldType),...)]` from normal
  **flat scalar/array returns** `[(fieldName,fieldType)]`,
  `[(fieldName,fieldType),...]`.
- R247 now fails closed for invalid field-schema shapes with
  `Refused`, rather than leaking a Python unpack exception.
- Two added regression tests cover single `address[]`, single
  `bool`, multi-scalar escrow, nested Lease struct and
  misdeclared ABI return types.
- The original R247 test **remains in place**. No ABI compatibility
  PASS is asserted until actual Foundry artifacts pass the new gate.
- Only Python source/tests and research documentation changed;
  original VM4706 signing validator, chain31340, existing
  VM4707/VM4709 Docker, encrypted owner wallets and live
  TEST ETH balances were not altered by this GitHub patch.

## Next owner VM4707 gate

Use exact new SHA from GitHub handoff in original isolated checkout:
run **targeted R247 Python unit tests**, a quiet local Foundry
build, and `python3 -B tools/sse_pos_r247_v2_compiled_abi_parity.py`
against actual compiled market and ledger artifacts. If all pass,
continue source-only R235 full gate; do not deploy, sign or
transfer any TEST ETH.
