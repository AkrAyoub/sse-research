# R158–R159 — Open native peer hint directory and unattended self-announcement

**Research development source, not a deployed Internet directory.**
As of 2026-11-21 the existing original chain31340 has real Besu and
Lighthouse clients on VM4706/VM4707. The public repository contains
an *unpublished* original genesis binary release descriptor and
**no verified public directory endpoints**. Last actual VM4707 full
suite baseline: R153 1,047 tests OK, 3 skipped. R155–R159 source tests
have not yet been run on VM4707; no third-party ingress or cross-ISP
join is claimed.

## R158 — any operator may host a directory (no admission authority)

`tools/sse_pos_r158_open_directory_service.py` provides a simple
bounded experimental HTTP service whose ONLY operations are:

- `GET /peers.json` returns R142's bounded actual-chain-native
  public EL enode/Beacon ENR hint document, or HTTP 503 if no
  fresh public node records exist.
- `POST /peers.json` accepts a fresh R156 *public-only* real-node
  observation record, subject to strict schema and identical original
  chain31340 genesis, short TTL, duplicate checks, stable unexpired
  P2P enode identity and bounded memory. Returns HTTP 202
  `membershipOrRoleGranted=false`.
- Expired records disappear. An operator may reannounce the
  same native P2P public key with a changed dynamic IPv6.
- No staking address, admin registry, validator key, token, wallet,
  EVM transaction or application-role approval is read or required.

The experimental server **binds loopback 127.0.0.1 only**.
Independent operators must supply a genuine reviewed HTTPS
reverse proxy and domain before exposing it to outsiders.
It intentionally does NOT fake public Internet reachability.
Two or more distinct HTTPS directory mirror URLs may carry the
same ONE genuine first-online peer record, letting a second node
bootstrap without a permanent first-peer requirement. Directory
URL lists are replaceable PUBLIC release data, not baked-in VM
IPs/enodes/whitelists.

**Threats/open research:** The current stdlib service checks
input shape and timing but cannot prove ownership of P2P keys,
ENR signature validity or native peer reachability before accepting
a record. It is vulnerable to junk-registration/Sybil filling and
eclipse/denial-of-service. This implementation must **not** be
exposed to the public without additional signature/challenge,
per-source admission abuse controls, persistence/restart handling,
load limits and cross-operator testing. A public directory can
make discovery more available; it does NOT grant blockchain
membership or determine canonical state.

The 64 records per response are bounded HTTP message capacity,
**not a global number-of-nodes or validator cap**; other operators
may host more directories and more peers, and native Ethereum
protocols can discover additional peers.

## R159 — live node announces itself without manual peer input

`tools/sse_pos_r159_native_peer_announce.py` reads an actual
R156 record from a private local file; verifies its original
chain31340 identity and expiration; reads the exact pinned release
manifest's list of replaceable HTTPS directory sources; and
POSTs only the public metadata. It rejects HTTP redirects, local
IP literal sources, malformed acknowledgements, wrong genesis,
late or missing local records and unbounded body sizes. It never
sends a signer, P2P private key, validator key, wallet, mnemonic
or generic code execution request.

The R153 local evidence systemd timer now invokes:
1. actual R141 EL/CL finality check;
2. actual R156 read-only NET/Beacon local peer identity capture;
3. actual R159 public mirror POST for each **verified configured**
   source, if there is one.

All three are read-only with respect to the node's blockchain
state; the announcement is an outbound network POST only.
Systemd treats an unavailable public directory as best-effort
while the actual chain clients keep running; it does not claim
synchronized/finalized or external operator independence.
Two different URL acknowledgements are recorded as two *URLs*,
not proven independent operator ownership.

## Important actual transport caveat

The currently used ZeroTier controllerless PUBLIC ad-hoc network
allows IPv6 unicast only, **NOT multicast/broadcast** according
to https://docs.zerotier.com/protocol/ .
A multicast-only discovery implementation would fail the real
VM4706/VM4707 architecture. The 6plane network identity is
an immutable transport compatibility property, not a
hardcoded bootstrap IP or membership whitelist. Reliance on
ZeroTier public roots/relays remains an independent-infrastructure
research limitation.

## Missing deployment facts

1. Publish the EXACT existing genesis tarball (R150) through
   >=1 truly accessible immutable public artifact URL and
   verify SHA256 `1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7`.
2. Independently host >=2 real HTTPS directories or equivalent
   replaceable public rendezvous mechanisms; establish TLS,
   abuse resistance and uptime. Only then add ACTUAL
   proven sources to `release/chain31340-public-release.json`.
3. Publish genuine first-peer R156 identity and R157/R158 feed;
   permit **one real peer** as sufficient to join second node.
4. VM4709 runs one public installer/one role prompt;
   actual Besu+Lighthouse joins original genesis and
   observes same finalized checkpoint as VM4706/VM4707.
5. Repeat on unrelated ISP/cloud; vary nodes, validators
   (genuine 32-TEST-ETH deposits and activation), providers,
   consumers, monitors and real adaptive committee/security
   workloads. No synthetic service SLAs or mock confirmations.

**No mutable unknown GitHub branch, random VM IP, invented ENR,
fake public DNS URL or reinitialized genesis is an acceptable
workaround for these missing live facts.**

## R160 — unattended official package signature compatibility

Prior R152's GPG verification wrongly required precisely one
`fpr:` record from `gpg --with-colons --fingerprint`.
An authentic vendor public certificate can have its own signing/
encryption subkeys, each with a fingerprint. Rejecting a certificate
for containing these subkeys would break correct unattended
installation. R160 accepts exactly **one primary public certificate**
with the known ZeroTier release primary fingerprint
`74A5E9C458E1A431F1DA57A71657198823E52A61`
and allows its subordinate `sub:` fingerprints; it rejects
additional unrelated `pub:` certificates. The official signed
installer must still verify successfully with GPG before execution.
This does not bypass signature checks or trust arbitrary new keys.

The previous verified operator result (R153, 1,047 tests) predates
R160. Its new unit regression remains pending exact VM test.

## Testing

```bash
.venv-tests/bin/python -B -m unittest discover -s tests \
  -p 'test_sse_pos_r158_open_directory_service.py' -v
.venv-tests/bin/python -B -m unittest discover -s tests \
  -p 'test_sse_pos_r159_native_peer_announce.py' -v
.venv-tests/bin/python -B -m unittest discover -s tests
```

Full academic/refactor cleanup is intentionally deferred until
the real distributed measurements have finished; these sources
remain isolated research implementation increments for now.
