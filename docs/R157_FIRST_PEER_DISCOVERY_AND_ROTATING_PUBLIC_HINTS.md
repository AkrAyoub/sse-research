# R157 — First-to-second-node fix, ephemeral peer registry and independent unicast rendezvous

**As of 2026-11-21:** source implementation and regression tests in
GitHub. No new independent VM has been proven to sync, and no
independently hosted public peer mirrors have yet been deployed.
Last operator-verified full Python suite remains R153:
**1,047 tests OK (3 skipped)** at SHA
`e10f23e842b1b0011a30212110dbb37a3088c11c`.

## Correctness bug fixed: first peer → second peer deadlock

R142 originally required **two distinct peer identities** AND two
distinct public source URLs. This is impossible for the SECOND node
to satisfy when the only active network peer is the FIRST peer,
even if that first peer is genuinely healthy, discoverable and
published by two independent mirror operators.

This was a hidden contradiction of the project's rule that
permissionless joining works with arbitrary current network size.

- R142 `discover()` now requires at least TWO *source feeds* but
  permits ONE independently identified matching reachable native
  bootstrap **peer hint**. A directory is not admission authority.
- R151 `peer_hints()` similarly accepts ONE Besu enode and ONE
  corresponding Beacon ENR (instead of requiring two pairs), and
  continues to reject an empty or mismatched result when external
  publication sources have been configured.
- R137 already accepts 1–64 matched EL/CL hints. This is per-
  invocation parser capacity, not a network membership limit.
- First-online peer may start with zero remote peers and no fabricated
  finality. One published peer can bootstrap the second; more discovered
  peers can subsequently improve resilience and routing.

A human-selected set of 6 VMs is an experiment population, NOT
the protocol's permitted membership.

## Real local identity source (R156) → mirrored feed (R157)

Each full node's R156 real local API capture contains:

- exact original chain31340 EL and Beacon genesis identity;
- Besu's native public enode node ID, derived from actual
  `net_enode`, not a hardcoded wallet or copied private key;
- Lighthouse's actual signed ENR from
  `/eth/v1/node/identity`;
- current ZeroTier 6plane IPv6, verified against actual host
  assignment and the ENR's RLP-encoded IPv6/ports;
- UTC capture time, short-lived `expiresAt` (600 seconds);
- explicit proof limits: no independent operator signature, no
  actual remote handshake or directory publication yet.

`tools/sse_pos_r157_public_peer_directory.py` consumes 1–64
bounded R156 source records and emits **exactly the R142
`SSE_R142_CHAIN31340_PUBLIC_PEER_HINTS_V1` format**. It enforces
original chain roots/ID, strict key allowlists, freshness and
expiry, no duplicate/equivocal identities and no copied secrets.
It always expires no later than the earliest supplied underlying
record. The output is a public untrusted *discovery hint*, not a
PoS voting certificate or trusted service-execution receipt.

The R157 writer is an **atomic rotating file**; a permanent HTTPS
`/peers.json` URL can change its contents as nodes readdress or
records expire without becoming a hardcoded node. It refuses a
symlink/irregular target and installs a complete bounded response
atomically, never a partially written JSON file.

**Important limits:** The local native ENR is produced by the
Lighthouse client, but R156's simple RLP parser does not independently
verify its secp256k1 signature. Remote untrusted directory entries
are not proof of signed publisher identity, alive peers, independent
operators or native handshakes. The actual Besu/Lighthouse protocols,
original genesis and finalized checkpoints remain independent checks.
Public directory operators could serve Sybil/eclipsing junk; clients
must prefer multiple independently operated mirrors and should
not treat directory content as a membership whitelist. Full security
against eclipse, rate abuse and source unavailability is unproven.

## Why not use ZeroTier multicast to discover everyone?

The working original public overlay is a ZeroTier controllerless
**ad-hoc** network. ZeroTier's official protocol documentation states
ad-hoc mode allows **IPv6 TCP/UDP UNICAST ONLY; no multicast or
broadcast**. A UDP multicast peer-announcement "solution" would
misleadingly appear locally sound yet fail on the actual existing
VM4706/VM4707 network.

See https://docs.zerotier.com/protocol/ .
Therefore, R157 builds unicast native peer hints for
**replaceable independent public HTTPS/DNS publishers**, with
actual remote reachability still to be verified. The immutable
ad-hoc transport network ID is not a fixed seed IP or an admission
list; ZeroTier public root/relay infrastructure is still a known
third-party dependency, not independent native public Internet P2P.

## Deployment/release state — no fake public URLs

`release/chain31340-public-release.json` still contains
`originalGenesisArchiveSources: []` and
`replaceablePeerDirectorySources: []`.
These must be populated ONLY after verified:
1. Original exact R59 public-only genesis archive is exported from
   an operator host and published as real bytes from a repeatable
   authenticated public source, with actual SHA256 confirmation.
2. At least two independently accessible public directory sources
   are deployed with periodically updated R157 JSON and genuine
   host-generated R156 native records.
3. A new unrelated VM from an independent Internet network joins
   using the source release and obtains genuine EL and CL peer
   connections and the same finalized Beacon checkpoint.

There is no automatic public HTTPS host, infrastructure credentials
or original binary archive available to the GitHub source connector
by itself. Committing a fabricated URL, a placeholder peer or a
pretend transaction is prohibited.

## Validation

```bash
.venv-tests/bin/python -B -m unittest discover -s tests \
  -p 'test_sse_pos_r142_public_peer_discovery.py' -v
.venv-tests/bin/python -B -m unittest discover -s tests \
  -p 'test_sse_pos_r151_unattended_full_node.py' -v
.venv-tests/bin/python -B -m unittest discover -s tests \
  -p 'test_sse_pos_r156_local_native_peer_identity.py' -v
.venv-tests/bin/python -B -m unittest discover -s tests \
  -p 'test_sse_pos_r157_public_peer_directory.py' -v
.venv-tests/bin/python -B -m unittest discover -s tests
```

Do not count a successful test as real peer publication, a
second-node sync event or finality proven from an external ISP.
