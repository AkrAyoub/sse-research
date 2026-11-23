# R174 — Real VM4709 ZeroTier vendor fetch failure isolated, do not reset

## Actual VM4709 evidence

The pinned R173 source checkout and existing R170 originally selected
observer state were **read-only verified**:

- 3 R173 recovery tests OK, 13 R152 host-dependency tests OK,
  15 R151 runtime tests OK and 18 R168 public discovery tests OK
  on the actual fresh Ubuntu VM4709, using system Python without
  unrelated marketplace-only Python packages.
- Exact original public chain31340 genesis archive SHA256 verified.
- No SSE containers existed, Docker daemon active, ZeroTier CLI
  absent and ZeroTier systemd service inactive.
- Anonymous GitHub R168 public peer record check: one current record.
- Actual R151 --execute then returned
  `R151_UNATTENDED_NODE_REFUSED: official signed vendor artifact unavailable`.
  This message originates from the R152 urllib fetch handler for either
  the pinned ZeroTier public signing key OR the official signed
  bootstrap installer. **We do not yet know which fetch failed**.
  It does not demonstrate a GPG signature failure, and no reason to
  bypass any verification follows from this evidence.

## Read-only next gate

Using a separate immutable GitHub checkout of R174 source,
call `sse_pos_r152_unattended_host_dependencies.fetch_https`
once for each of its exact two public allowlisted URLs, without
installing any dependency. Print only SUCCESS and byte size, or the
bounded R152 stage error. Never print downloaded signed scripts or
public key content, machine credentials, proxy URLs, or signer files.

R174 now distinguishes:

- `R152_ZEROTIER_SIGNING_KEY_DOWNLOAD_HTTP_N` or `...TRANSPORT_UNAVAILABLE`
- `R152_ZEROTIER_SIGNED_INSTALLER_DOWNLOAD_HTTP_N` or `...TRANSPORT_UNAVAILABLE`

This is safe to run on an already partly-installed VM because it
does not call apt, gpg, shell installers, ZeroTier join, Docker,
or write to the original /opt/sse checkout. The official ZeroTier
download instructions document a signed installer verification
using GPG; bypassing signature verification or curling an unsigned
shell script into root's bash is **not** an acceptable recovery.

After proving the actual fetch failure and preserving selection,
make a targeted correction with a pinned vendor mirror or
verifiable alternative; then rerun the guarded recovery and actual
R151 runtime ONCE only after inspecting the current state. Do
not rerun first-time R147, delete existing source, clone signer keys,
generate genesis, or claim a native peer or finalized root.

## Current proven status

Original chain31340 public genesis published and verified;
VM4707 genuine dynamic native identity published; independent VM4709
anonymous discovery verified. Actual VM4709 EL/CL containers,
handshakes and finality remain unproven. GitHub issue #42 remains
temporary centralized rendezvous with 600-second record expiry.
