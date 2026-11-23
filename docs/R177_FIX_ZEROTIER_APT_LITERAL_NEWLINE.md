# R177 — VM4709 APT source malformed literal backslash-n: exact root cause and narrow repair

## Actual first-run evidence

VM4709 has already completed a REAL R147 source stage and preserved
a root-only 0600 `/var/lib/sse/selection.json` with role observer and
original pinned R170 release. The original genesis SHA256 and archive
were independently checked by R173. No SSE Besu/Lighthouse Docker
containers were present.

The revised R175 ZeroTier package path on VM4709 previously passed
54 targeted tests and official HTTPS InRelease transport preflight,
but R151 subsequently returned
`R152_ZEROTIER_SIGNED_APT_INSTALL_EXIT_100`.

The owner's READ-ONLY package inspection showed:
- `dpkg-query zerotier-one`: package not installed.
- `apt-cache policy zerotier-one`: Unable to locate package.
- `/etc/apt/sources.list.d/sse-zerotier.list` actually contained a
  trailing literal **backslash followed by n**:
  `deb [arch=amd64 signed-by=/usr/share/keyrings/sse-zerotier.gpg] https://download.zerotier.com/debian/noble noble main\n`
  instead of a POSIX newline. The current source code was reviewed
  and **confirmed to produce this exact malformed line**.
- Vendor keyring's full pinned primary GPG fingerprint was correct:
  `74A5E9C458E1A431F1DA57A71657198823E52A61`.
  A separate signing subkey is expected and not suspicious.
- No SSE Docker containers created; Docker daemon remained running.

## Code correction

R177 fixes the code generator itself to emit an actual newline
at the end of the valid single-line scoped signed-by repository.

The R152 installer can now repair ONLY the precise already-observed
R175 malformed line, comparing exact bytes against a pinned legacy
constant before atomically replacing the one file. It refuses
symlinks, unexpected files or nonmatching content. The existing
fingerprint-verification process, scoped signing key, HTTPS Noble
repository and APT signature checks remain required. No
unsigned root shell-script execution or `trusted=yes` bypass.

Tests explicitly assert actual LF, legacy exact literal two-byte
backslash+n signature, safe repair, idempotence and arbitrary-file
conflict refusal. These are mocked tests; they do not claim a
successful live package install or native Besu/Lighthouse peering.

## Real next test

On VM4709 fetch an exact new R177 commit into an independent
public source checkout. Run R152, R173 and R151 narrow tests with
system Python (no unrelated marketplace dependencies).
Run a read-only R173 check before attempting R151 again.

Before R151, ensure VM4707 genuinely refreshed public ENR once.
When current public discovery succeeds, execute R151 once only.
If any install stage fails, inspect the preserved host state,
never repeat R147 or delete original genesis/selected role.
Record the actual package candidate, ZeroTier overlay and genuine
Besu/Lighthouse Docker peers/finality before claiming success.

This temporary GitHub discovery service is NOT the final
permissionless decentralized bootstrap architecture. Real
native P2P and independent multisource bootstrapping are
still pending and must be demonstrated separately.
