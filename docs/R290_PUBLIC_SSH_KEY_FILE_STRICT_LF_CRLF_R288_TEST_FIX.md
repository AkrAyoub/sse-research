# R290 — Repair R289's double-escaped SSH public-key regression fixtures; read actual key file bytes so CRLF remains rejectable

## Actual observed owner results, 24 Nov 2026

Each of the four actual owner VM terminals — VM4711, VM4712,
VM4713 and VM4714 — checked out Git SHA
`51b85653d9ea5a348c556a9d4b1bd52e2924b089`
and ran the R288 focused suite (20 tests). Each
reported **three subtest failures in one new test**:
`test_client_public_rejects_double_lf_or_embedded_keys`.
The test constructed strings using double-escaped
`\\n` / `\\r` literals, producing actual
backslash-letter bytes in the dummy `.pub` file
instead of real LF/CRLF. Consequently:

- Double *literal slash-n* suffix is not a real
  double newline, so the production parser
  correctly did not reject it.
- The embedded literal slash-n altered the number
  of public-key text fields, causing rejection
  with a different message than the test expected.
- The literal slash-r slash-n is not CRLF, so it
  also did not trigger the intended newline gate.

There is an ADDITIONAL real parser strictness
problem: Python `Path.read_text()` normally
performs universal-newline conversion, so a
CRLF public-key file may be transparently
normalized to LF before validation. A parser
claimed to reject CRLF must examine exact
bytes rather than normalized text.

Each owner invocation used `set -euo pipefail`
and stopped on the focused unit-test failures
**before** `--client-preview`/
`--client-create` on the monitors or
`--provider-preview` on VM4714.
Therefore NO new SSH identity was generated
in these owner runs, NO server authorized_keys
file was modified and NO Docker/PoS/native
transactions or key imports occurred.

## Exact GitHub R290 source changes

- `tools/sse_pos_r288_monitor_to_vm4714_ssh_publickey_bootstrap.py`:
  the local owner-public `.pub` reader now uses
  `public.read_bytes().decode("ascii")`
  to preserve actual line endings; it removes
  *at most one ordinary terminal LF* before
  calling the **unchanged strict** one-line
  `_valid_public_key` function. A normal
  ssh-keygen public file ending with LF is
  accepted, but CRLF retains its preceding CR,
  and second or embedded LF remains rejectable.
  The corresponding SSH **private key bytes
  are not opened/read/printed**.
- `tests/test_sse_pos_r288_monitor_to_vm4714_ssh_publickey_bootstrap.py`:
  the three malformed test cases now create
  genuine LF / LF-LF / CRLF ASCII file bytes,
  not double-escaped text. A new fourth case
  separately checks a real multiline file
  containing two ED25519 public-key records.
  Test expectations assert strict refusal
  without depending on incidental error wording.

**Authored R288 focused test count is now 21.**
The user has **NOT YET run the 21-test suite on
actual VMs**. A self-contained isolated
behavioral parser reproducer was run locally
and reported **PASS** for:
single LF, no LF (accepted);
double LF, embedded second key, CRLF,
multiline public record (rejected).
This local reproducer is **not** the full
R288 test suite and must not be reported as
owner VM tests passing.

## Next owner action

On each of VM4711, VM4712, VM4713 and VM4714,
fetch the next exact reviewed Git SHA and
rerun the 21 R288 focused tests. Stop
if any fail; do not bypass tests by
creating SSH keys manually.

Only on success:

- Monitor VMs 4711–13: run `--client-preview`,
  then optionally the existing separately
  TTY-owner-approved `--client-create` once
  per host. These create distinct SSH
  ED25519 research keys in private host
  directories, never reuse an EVM validator
  or payment wallet key. Public `ssh-ed25519`
  lines only can be shared.
- Provider VM4714: run `--provider-preview`
  only, read-only. Do not run
  `--provider-authorize` before the three
  distinct actual PUBLIC monitor key lines
  are known/reviewed, each owner-confirmed
  append is a distinct deliberate SSH
  authorization event.
- Once provider restrictions exist, use
  separately host-key-pinned R287 SSH
  `--preflight` and then temporary CPU
  `--probe` only on SSH login success.
  Raw unsigned worker port 8877 stays
  loopback-only, original Docker containers
  and chain31340 consensus clients untouched.

Original three native role grants previously
finalized. The new four VM4711–14
application EOAs remain unfunded; R282
four grant quote is still NOT an
additional spending authorization.
