# R170 — R169 true API stale comment failure and direct live join integration

## Actual observed VM4707 regression

R169 git SHA `76b59ce5788673e5ca3897c5d2acd7c5de29c2a2`:
`Ran 1127 tests in 17.563s; OK (skipped=3)`.

VM4707 successfully refreshed its **real** public R156 EL/CL native
record in GitHub Issue #42 comment **7097016936**, same comment (no
duplicate), to expiresAt `1795429403`. Yet the immediately following
anonymous read reported one marked native comment but **zero valid
fresh** records, then `--discover` refused. This is **not** a
successful external peer join.

Inspection of the **actual** GitHub REST API later showed the SAME
comment id and actual updated-at timestamp `2026-11-23T10:13:24Z`,
the freshly updated `expiresAt=1795429403`, correct EL and Beacon
genesis identifiers, and valid public native enode/ENR fields. This
makes a stale response from the issue-comments LIST endpoint after
PATCH a concrete possibility. The initial VM validation failure
must not be conflated with an invalid original genesis.

## R170 correction: resolve current comment by ID

`tools/sse_pos_r168_github_rendezvous.py` now fetches the anonymous
public issue comments list with a cache-busting query parameter;
for every marked native R156 comment (up to eight to avoid N+1
resource abuse), it reads the corresponding **individual comment**
via a second uncached anonymous GET to the public REST API.

The numeric comment ID is returned dynamically by the list.
There is no pinned node address, enode or operator membership
whitelist in source code. Strict HTTPS, path, response-size, no
redirect and original genesis verification are retained.
The new unit regression reproduces **stale collection body +
fresh individual comment body** and checks that R168 discovery
uses the fresh body rather than the expired one. The diagnostic
read path uses the same fresh comment fetch.

GitHub is still one centralized availability provider and a
temporary experimental rendezvous; this does NOT prove independent
native P2P, finality or physical resources.

## R170 provisional third-node runtime integration

Previously R151 on a fresh VM without published independent R142
directories returned a zero-peer mode and could start a genuinely
isolated nonsigning EL/CL node. This is not a valid third-node
onboarding result.

R151's **actual execute path** now fetches the current R168 public
issue peer identities BEFORE any package, Docker or archive-state
changes. It supplies the actual dynamic EL enode and Beacon ENR
to R137's real native Besu/Lighthouse client launch. Failure
to obtain actual fresh peer hints raises
`PUBLIC_PROVISIONAL_PEER_DISCOVERY_UNAVAILABLE`, with no isolated
success claim and no hidden fallback to a static VM address.

The resulting mode
`EXPERIMENTAL_SINGLE_GITHUB_PUBLIC_RENDEZVOUS`
is explicit: it is not independently operated infrastructure and
has no identity/role admission authority. Real native EL and CL
handshake, exact public original genesis, Beacon checkpoint and
finality agreement must still be checked separately.

The root installer still requires an Ubuntu 24.04 fresh host, one
role selection, and a pinned public source commit. The initial
supported runtime roles are nonsigning observer/full_node ONLY;
validator and marketplace roles refuse rather than pretending
to activate. This temporary discovery source is used only in
the actual R151 runtime; its plan and older no-public-directory
unit tests remain nonmutating.

## Next operator checks

1. R170 exact SHA full regression on VM4707.
2. Real `--publish-live` refresh of comment #7097016936.
3. Anonymous `--diagnose-public` shows
   `freshValidNativeComments>=1`, then `--discover` succeeds.
4. VM4709 performs **read-only anonymous discovery** first, using
   GitHub public source; there is no need for a GitHub account,
   copied signer, SSH deploy key or manual peer IP.
5. Only after step 4, run the pinned one-command role installer
   on VM4709. Verify genuine Besu/Lighthouse native peer counts
   and the canonical finalized root. A Docker process alone is
   never synchronization evidence.

The peer advert TTL remains 600 seconds; a self-refreshing
publisher timer is STILL needed before any unattended multi-VM
join can be called persistent. The GitHub dependency will require
replacement by independent native/HTTPS rendezvous before the
project's strict final permissionless architecture is achieved.

Last verified VM green: R169 1127 tests (3 skipped). R170 has
NOT yet been run on VM4707.
