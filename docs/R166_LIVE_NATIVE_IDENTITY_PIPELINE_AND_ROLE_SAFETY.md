# R166 — Real R165 green, file-based native discovery repair and honest selected-role admission

**2026-11-23 actual VM4707 output (user-observed):**

- Exact R165 Git SHA `0a108e90ee316dcdd629dcb973de69e2597989ee`.
- **Ran 1108 tests in 17.544s; OK (skipped=3)**.
- **PUBLIC GENESIS VERIFIED** through anonymous real GitHub release
  download: SHA-256 `1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7`,
  4 original public members verified, no signer read or chain change.
- **ACTUAL NATIVE EL/CL IDENTITY CAPTURED** from VM4707 by R156:
  `node-vm4707-observer`, `expiresAt=1795425990`,
  `realPeerIdentityCaptured=true`,
  `publishedToAnyExternalDiscoveryService=false`.
  No actual enode or ENR bytes were displayed or assumed from this
  summary output. Captured metadata alone does **NOT** equal a public
  bootstrap directory, actual remote IP reachability or an additional
  synchronized peer.

## R166 development corrections

1. **R156 on-disk JSON defect:** the CLI with `--out` appended
   literal `\\n` characters after serialized JSON, causing an
   invalid document for R157 and R159. The previous live invocation
   did not use `--out`, so this bug escaped the source-level
   integration tests. R156 now appends a genuine newline. Tests cover
   saving and atomically rotating the private public-only record.
2. **R156 → R157 → R159 complete interface regression:** new in-process
   test performs the actual R156 local-client read-only capture logic
   using synthetic HTTP response *fixtures*, saves/loads a private
   file, builds an R142-compatible discovery directory, and attempts
   the R159 announcement with no configured endpoints, which must
   return `AWAITING_REAL_PUBLIC_DIRECTORY_SOURCES`. This is test
   evidence for the source pipeline, **not** simulated node admission
   or proof of real Internet peering.
3. **All chosen roles, not partial silent installs:** R147 previously
   allowed `full_node,provider`, `observer,monitor` and
   `validator`, started only nonsigning EL/CL, then could report
   successful installation. R166 rejects ANY role outside
   `full_node` and `observer` **before performing APT, Git or
   local state mutations**. It specifically refuses active validator
   claims: real independent 32 TEST ETH funding/deposit, signer key
   custody and Beacon activation remain incomplete. Tests cover
   mixed and market-only selections, no partial silent activation.
   The one-menu user requirement stays; the validator and marketplace
   roles must be implemented before those selections can activate.

## LIVE read-only original-VM local directory check (after R166 suite)

This runs on **VM4707 only**, with the exact pinned R166 Git revision.
It collects current REAL Besu and Lighthouse public peer identities
and builds a **private local candidate directory**. It does not
change Docker, clients, wallets or the original signer. It does
NOT host a public HTTPS directory, so it must not be advertised as
the real VM4709 bootstrap solution.

```bash
(
  set -e
  cd "$HOME/sse-research"
  umask 077
  D="$HOME/.local/state/sse-r166-discovery"
  mkdir -p "$D"
  chmod 700 "$D"
  python3 -B tools/sse_pos_r156_local_native_peer_identity.py \
    --node-id node-vm4707-observer --out "$D/real-local-peer.json"
  python3 -B tools/sse_pos_r157_public_peer_directory.py \
    --record "$D/real-local-peer.json" --out "$D/local-directory.json"
  python3 - "$D/local-directory.json" <<'PY'
import json,sys
from pathlib import Path
o=json.loads(Path(sys.argv[1]).read_text())
assert o["chainId"]==31340
assert len(o["peers"])==1
print("R166_LIVE_EL_CL_PUBLIC_IDENTITIES_TO_DIRECTORY_VALID=true")
print("R166_DIRECTORY_HOSTED_PUBLICLY=false")
print("R166_NATIVE_REMOTE_PEER_HANDSHAKE_VERIFIED=false")
PY
)
```

The output directory is private and contains only a PUBLIC native
enode/ENR record; there are no validator keys. Actual network
publisher identity and independent HTTPS availability remain unknown.

## Next operational blockers, not imaginary defaults

- R165 already solved original public genesis distribution. Never
  regenerate genesis or modify the original signing VM4706.
- R156/R157 can now generate *genuine* short-lived advertised P2P
  records from the running observer. To use them as independent
  discovery, one or more remote hosts must **actually** serve them
  from reachable HTTPS (or a replaceable native protocol rendezvous),
  rotating records before expiration and proving real peer
  handshakes. Two URLs pointing at one administrator do not by
  themselves prove infrastructure independence.
- ZeroTier controllerless ad-hoc supports IPv6 unicast, not multicast.
  The existing overlay transport is open membership, but is not
  proof of fully independent Internet P2P network infrastructure.
- Do not install and call VM4709 joined until original genesis,
  real EL/CL native peer counts, same finalized Beacon checkpoint
  and actual out-of-operator network discovery are verified.
- The already described deferred exhaustive paper-ready refactor
  starts after real multi-host node, independent validator,
  marketplace and monitoring experiments finish.

**Latest R166 tests have not been run on a VM yet.** The last green
remains the real R165 1108-test result.
