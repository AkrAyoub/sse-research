# R289 — R288 SSH PUBLIC key trailing newline test failure corrected (source only)

## Actual owner's four R288 test outputs

VM4711, VM4712, VM4713 and VM4714 EACH ran the R288
18-test focused suite at Git SHA
`df7d96f6d3126ce25b4c212914cd5ce93cfac475`.
All four reported **17 tests passing, 1 test error**,
the identical `test_owner_client_public_only_reads_public_file`
error:

```
Refused: public SSH ED25519 key must be one bounded line
```

Root cause is that R288 `client_public()` directly
passed the entire contents of a normal SSH `.pub`
file (one newline at EOF) to `_valid_public_key()`,
which correctly forbids any newline in CLI-supplied
one-line public keys. The fixture contained that
normal single terminal LF, so it failed.

All owner commands ran with `set -euo pipefail`
and stopped on test failure; thus none reached
the `--client-preview`, `--client-create` or
`--provider-preview` sections. **No new SSH
private/public keys were created by these owner
runs, no existing authorized_keys were modified,
no existing Docker containers changed, no Ethereum
transaction signed or submitted.**

## GitHub R289 fix

Only `client_public()` removes **at most one terminal
LF** from the owner-controlled local SSH `.pub` file,
then passes it to the existing strict
`_valid_public_key()` unchanged. A second terminal
LF, an embedded second SSH public key, CRLF
in a context not explicitly allowed, non-ED25519
key, invalid blob, symlinked owner path, incorrect
owner file permissions or multiline public key
supplied via `--public-key` continue to REFUSE.

Two new focused regression tests were authored:
- Normal `ssh-keygen` single LF and a no-LF
  fixture both produce the same public ED25519 key;
  owner-private fake SSH file bytes remain unchanged.
- Double LF, embedded second public key and CRLF
  continue to be refused; no private SSH file read.

New total **20 authored R288 focused tests**,
but these have **NOT YET been executed on owner VMs**.
A local clone-based test execution attempt did not
run due lack of GitHub DNS from assistant's
isolated container; no passing tests were claimed
from that attempt. The existing 17 previously
passing tests were executed on four actual VMs
before this correction.

## New operator steps, only from pinned reviewed SHA

On each VM4711, VM4712, VM4713:
1. Fetch and checkout exact new R289 full SHA
   provided in chat into the existing
   `$HOME/sse-v2-standby-source` directory.
2. Run all 20 R288 focused tests; stop on any failure.
3. Run `--client-preview` (no effects).
4. Only when tests and preview pass and the VM owner
   chooses to do so, run interactive `--client-create`
   to generate one unique local owner-private
   dedicated SSH keypair. Do NOT paste any
   private key, EOA keystore, password or signing key.
   The public `ssh-ed25519 ...` key and SHA256
   fingerprint printed on success may be shared.

On VM4714, run the 20 tests at the SAME new
SHA and `--provider-preview` only.
No server key authorization occurs until
the three real public monitor SSH keys
are known and individually reviewed with
a separate owner-TTY authorization per key.

After real VM4714 restricted public-key
authorization, re-run existing R287 host-key
pinned SSH `--preflight` using independently
verified VM4714 host fingerprint
`SHA256:jWl81QyIY7+m7Y51lzA2g0wM6F0lIuvdE3bv2SeAFoY`
and explicit local owner-private
`--identity-file`. Only if preflight
succeeds may R287 temporarily SSH-tunnel
the real local Docker CPU worker and measure
a new OS-random 8192-round cross-VM computation.
Neither R288 nor R289 changes the original
native PoS chain31340 contracts/keys,
Docker worker or broadcast ports.

All three originally authorized native TEST
ETH role grants have been independently
finalized. New four standby VM application
wallets remain unfunded; separate onchain
funding/bonding authorization has not yet
been supplied.
