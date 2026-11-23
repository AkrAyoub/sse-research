# R167 — Correct actual VM4707 R166 two-test regression

## Evidence

The operator ran the real R166 source revision
`4b58ea5d9c9f11f74ac154cae4cedef3b38ddb33` on
VM4707 and reported:

```text
Ran 1108 tests in 16.993s
FAILED (failures=1, errors=1, skipped=3)
```

The 1108 total includes one test module that could not import.
This is **not a green run**. The previous pinned R165
revision `0a108e90ee316dcdd629dcb973de69e2597989ee`
remains the last observed green result:
`Ran 1108 tests in 17.544s; OK (skipped=3)`.

## Root causes and fixes

1. `tests/test_sse_pos_r164_no_source_only_pseudoinstall.py`
   newly added mixed-role test contained double backslashes for
   Python line continuation in a `with` statement; Python reported
   `SyntaxError: unexpected character after line continuation character`.
   R167 uses **parenthesized context managers**, supported in the
   actual Ubuntu 24.04 Python 3.12 VM, with no fragile trailing
   continuation characters. The test continues to verify mixed
   validator/marketplace roles are rejected **before package,
   filesystem, or signer mutations**.
2. `tests/test_sse_pos_r156_local_native_peer_identity.py`
   incorrectly asserted the saved identity file ends with literal
   two bytes `\\n`; the R166 implementation correctly writes
   a **single LF byte 0x0a**. R167 now checks `bytes([10])`
   explicitly. The JSON loader assertion already passed, proving
   the R166 file writer correction works.

R167 also adds a **repository-wide Python AST parse gate** for all
checked-in `tools/`, `scripts/`, and `tests/` Python source
files in `.github/workflows/r147-public-install-regressions.yml`.
This catches missing syntax on files that an ordinary focused
unittest discovery would not import.

No client processes, Docker containers, wallets, validator keys,
network configuration, or original chain31340 genesis were touched
by the GitHub-only repair.

## Next acceptance

The R167 branch must be checked out at one exact reviewed full Git
SHA and its full `unittest discover -s tests` suite rerun
on VM4707. Afterwards, the **actual** read-only
R156 `--out` → R157 local peer-directory JSON pipeline
can be executed using the R166 command and its private local
diagnostic directory. That local directory is not a public
Internet rendezvous and does not demonstrate third-host native
EL/CL peering or finality. Publishing independent, refreshing
native discovery remains the next network infrastructure gate.

No source-level or GitHub Actions result should be described as
passing before an actual tool result/VM log shows it.
