# R175 — bypass actual blocked ZeroTier bootstrap-script endpoint with verified native Ubuntu 24.04 APT repo

## Actual VM4709 failure and provenance

- Actual new host Ubuntu 24.04 VM4709 first completed the private
  root-owned observer source stage under exact original R170 SHA.
- Actual targeted R173 tests + root read-only recovery gate passed,
  original archived genesis SHA256 matched and no SSE containers existed.
- R151 actual runtime could not download official vendor artifact;
  R174 read-only probes verified:
  `SIGNING_KEY: DOWNLOAD_OK bytes=3175`,
  `SIGNED_INSTALLER: R152_ZEROTIER_SIGNED_INSTALLER_DOWNLOAD_HTTP_403`.
  R174 scoped unit suite `Ran 14 tests ... OK`.
- We must not infer ZeroTier service or native EL/CL running from a
  successful original archive install; previous evidence shows
  ZeroTier absent, Docker active, no SSE nodes.

## Reviewed upstream alternative

ZeroTier publishes its installer SOURCE at:
`https://github.com/zerotier/install.zerotier.com/blob/main/install.sh.in`.
It configures the ZeroTier upstream APT repository and installs the
package. The upstream source explicitly lists Ubuntu 24.04 as
`noble`, URL base `download.zerotier.com/debian/noble`
and uses signed-by a local keyring for Ubuntu 22.04+.
Original first-party installation notes:
`https://github.com/zerotier/install.zerotier.com`.

R175 directly implements the same signed APT **package** path.
It never fetches nor executes the blocked install.zerotier.com
script, never curls unsigned root bash, never disables APT GPG
verification, never adds an APT trusted=yes repository or a global
trust key. It uses official HTTPS repository:
`https://download.zerotier.com/debian/noble`
and scoped APT source:
`deb [arch=amd64 signed-by=/usr/share/keyrings/sse-zerotier.gpg] https://download.zerotier.com/debian/noble noble main`.

Guards:
1. Root privileges and only fresh-node dependency installation; no
   old VM owner/validator data touched.
2. BEFORE APT config mutation, read-only HTTPS GET of
   `https://download.zerotier.com/debian/noble/dists/noble/InRelease`
   must return plausible PGP clearsigned metadata. Failure is
   labeled with fixed safe `R175_ZEROTIER_APT_METADATA_...` code;
   no bypass.
3. Download only exact already-observed working official GPG public
   key URL. Import to private throwaway GPG home, verify the **pinned
   full primary fingerprint**
   `74A5E9C458E1A431F1DA57A71657198823E52A61`
   and reject extra primary certificates.
4. Convert verified public key into a scoped 0644 APT keyring and
   create exact public sources file with O_CREAT|O_EXCL and O_NOFOLLOW;
   any preexisting unexpected/symlinked file aborts, never overwrite.
5. `apt-get update` performs actual repository Release signature
   checking using signed-by, then `apt-get install zerotier-one`
   verifies package hashes and installs real binary. Bounded
   sanitized APT stage identifiers only.
6. Proceed with actual ZeroTier service/join, immutable digest
   Docker image pulls, and native Besu+Lighthouse R137 runtime
   only on exact existing observer-selection protected host.

## Actual next gate

Run R175 source unit tests on actual VM4709 using public anonymous
GitHub checkout at full exact SHA, then read-only metadata preflight
via `verify_vendor_repo_metadata`. If either fails, no mutation.
Run R173 root-only read-only private selection + original archive
recovery gate. Then genuine R151 `--execute` **once**, using new
source without resetting existing pinned R170 original source.
Record any exact R175 metadata, GPG or APT failure and DO NOT
retry blindly or delete Docker/selected role state.

This replacement has not yet been executed on actual VM4709.
No native EL/CL handshakes/finality proven. The ten-minute
VM4707 public ENR record must be actively refreshed before a
new actual join. GitHub is still provisional centralized discovery,
not final infrastructure independent permissionless discovery.
