# R155–R156 — Native join evidence and actual dynamic peer identity publication input

**Original chain:** 31340 (no new genesis). **Status:** GitHub source only,
pending pinned full VM4707 test and genuine installation on VM4709.
**Last operator-observed suite:** R153, 1,047 Python tests, OK (3 skipped).

## R155 — prevent false acceptance of another chain

The original R141 node observation validator checked valid schema and
chain ID 31340 but did not, by itself, compare both observed genesis
roots with *our exact running original chain*. R153 had accepted any
well-formed 31340 report as `ACTUAL_LOCAL_CHAIN_FINALITY_VERIFIED`.
This was incorrect: two independent networks can share the same
numeric chain ID.

R153 now requires BOTH:
- actual Besu execution block-zero hash exactly
  `0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf`;
- actual Lighthouse Beacon genesis validators root exactly
  `0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd`;
- nonzero actual EL and CL connected-native peer counts;
- all previous R141 finalized epoch, sync, optimistic, EL-offline and
  timestamp checks.

Otherwise local evidence stays `WAITING_FOR_ACTUAL_EL_CL_FINALITY`.
This does not prove independent public ISP ingress or service delivery.
Unit tests now verify rejection of an unrelated chain and zero peers.
One R151 test was also fixed to use an isolated temporary archive
target and never inspect/modify VM4707's actual original archive.

## R156 — P2P public identities from LOCAL real client APIs

A new node needs to publish its current identity to help later nodes
find it, but the publisher must not read or upload its P2P private key.
`tools/sse_pos_r156_local_native_peer_identity.py` uses:

1. Local Besu `net_enode` (read-only **NET** JSON-RPC namespace, not
   dangerous `ADMIN`) for the actual public secp256k1 P2P node ID.
2. Local `eth_chainId` and `eth_getBlockByNumber("0x0", false)`
   to require the real chain31340 execution genesis.
3. Lighthouse `GET /eth/v1/node/identity` for the real
   Lighthouse-generated signed ENR and
   `GET /eth/v1/beacon/genesis` to verify the correct Beacon root.
4. Current `zerotier-cli -j listnetworks` and the actual host IPv6
   interface through our previously proven R59 overlay inspector.
   **No VM IP or manual enode/ENR is hardcoded.**
5. Strict, bounded ENR base64/RLP decoding to require advertised
   `ip6` to match the *currently assigned* 6plane address and
   `tcp6/udp6` to match actual configured P2P ports.
6. Combine the real Besu public node ID with **the observed**
   dynamic overlay IPv6 and configured 30404 native EL port;
   the beacon ENR is preserved unchanged from Lighthouse.
7. Emit an atomically replaced, root-private, nonsecret peer record
   with a **600-second expiration**. It does not sign a separate
   publication with a validator key, read any private signer, or
   declare a remote native handshake.
8. The existing R153 systemd evidence timer now tries to refresh
   this ephemeral peer record alongside EL/CL finality observations.
   A stale or inconsistent native address is refused rather than
   silently published.

**Security boundaries:** The strict RLP decoder does not independently
verify EIP-778 ENR signatures; the live native Ethereum networking
handshake is needed to validate peers. This file is a **publisher-ready
local source**, not itself an independent public directory mirror.
The value of a source requires honest HTTPS publication and a
replaceable rendezvous graph. A single owner-maintained mirror would
remain a discovery availability/censorship dependency. A node may
publish its own public identity without receiving consensus or market
membership privileges.

Relevant upstream supported APIs:
- Besu NET `net_enode` documented under node keys:
  https://docs.besu-eth.org/public-networks/concepts/node-keys
- Lighthouse Beacon `/eth/v1/node/identity` documented under
  https://lighthouse-book.sigmaprime.io/api_bn.html

## Remaining dynamic address work

R137 currently binds Docker ports to the host's 6plane IPv6 and
starts Lighthouse with `--disable-enr-auto-update`. Therefore a
true assigned address change **cannot be solved by updating a JSON
file alone**. Rebinding Docker ports and updating the advertised ENR
requires a safe, exclusive, interruption-aware restart/recreate
procedure that **preserves EL/CL chain state and signer separation**.
R156 detects stale advertisement and its TTL prevents indefinite
reuse, but does not claim automatic rebind yet.

## Permissionless network discovery versus genesis

The first online node needs no remote bootnode but must load exactly
the original public chain31340 genesis. It can generate a public
P2P node identity and broadcast/publish its own reachable identity.
Other nodes may discover it through replaceable mirrored ENR/enode
directories, native Ethereum discovery and independent transports.
No fixed owner VM, fixed IP, permanently privileged bootstrap
participant, hardcoded total validator/node count or private GitHub
access is acceptable.

Public original genesis remains unavailable as verified downloadable
bytes, and R142's source lists are currently empty. Until they are
actually published and joined from an unrelated VM, an installer
cannot truthfully report globally permissionless network access.

## Tests

```bash
.venv-tests/bin/python -B -m unittest discover -s tests \
  -p 'test_sse_pos_r153_local_node_evidence.py' -v
.venv-tests/bin/python -B -m unittest discover -s tests \
  -p 'test_sse_pos_r156_local_native_peer_identity.py' -v
.venv-tests/bin/python -B -m unittest discover -s tests
```

These tests are executable source regression evidence, not yet
recorded as a passing VM4707 run at this new Git SHA.
