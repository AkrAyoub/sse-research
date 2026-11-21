# R162 — Verified VM4707 R161 regression and original-genesis release gate

**Observed owner VM4707 source test:** exact R161 Git revision
`1c5583968cdf5480382ca988d4a9501f55acee98`,
`Ran 1093 tests in 17.613s`; `OK (skipped=3)`.
All five earlier R160 errors and assertion failures have disappeared.
This remains source-level evidence, not newly installed independent
EL/CL, live public discovery, active new validator, or funded SSE lease.

## Next real dependency: the original public genesis bytes

The original chain31340 public-only archive remains an actual
VM-local file. It is not present as a verified public release asset
or retrievable by GitHub source tools; GitHub visibility alone
cannot supply those bytes. R150 is already committed and audited
at source level; do not create another exporter or fake genesis.

A **one-time MAINTAINER operation** on existing VM4707
(not on a freshly joining VM) can stage a public-only release candidate
without restarting Besu/Lighthouse or reading signing keys:

```bash
(
  set -e
  cd "$HOME/sse-research"
  test "$(git rev-parse HEAD)" = "1c5583968cdf5480382ca988d4a9501f55acee98"
  ARCHIVE="$HOME/chain31340-public-native-observer-v1.tar.gz"
  test -f "$ARCHIVE" && test ! -L "$ARCHIVE"
  test "$(sha256sum "$ARCHIVE" | cut -d' ' -f1)" = \
    "1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7"
  python3 -B tools/sse_pos_r150_verified_genesis_release.py \
    --archive "$ARCHIVE" \
    --out "$HOME/sse-chain31340-public-release-candidate"
  sha256sum "$HOME/sse-chain31340-public-release-candidate/chain31340-public-native-observer-v1.tar.gz"
)
```

The operator must never upload any directory containing a validator
wallet, keystore, BLS mnemonic, Engine JWT, chain database or owner
secrets. The exact R150 output public genesis archive is the only
candidate for public GitHub Release/mirror publication. The R150
script intentionally fails if the output directory already exists
and does not change the original archive.

An authorized publication path must transfer those **exact bytes**
to a public immutable artifact endpoint. The current GitHub
connector exposes text source file edits but no binary GitHub
Release asset upload, and has no access to VM4707 filesystem.
No claim of actual publication until an independent HTTP download
has been verified byte-for-byte against the original archive hash.

## Network-first admission and peer directories

R142/R157 allow a second node to find the one real first-online peer
provided by two interchangeable public HTTPS sources; R156 captures
real native Besu/Lighthouse public identities without signer keys.
The open R158 relay is still a **loopback-only experimental
directory**: it lacks public TLS and anti-Sybil identity proof,
so exposing it externally is not justified. Two actual independently
reachable public endpoint URLs remain to be established and tested.
No hardcoded VM IP/ENR, copied genesis signer, member whitelist
or new genesis is permitted.

### Testing and paper preservation

Before accepting any additional infrastructure changes, preserve
the R161 green pinned SHA and full source test evidence.
The operator's requested exhaustive repository cleanup and paper
reproducibility packaging remain deferred until the external
multi-VM chain and genuine SSE role experiments are completed.
