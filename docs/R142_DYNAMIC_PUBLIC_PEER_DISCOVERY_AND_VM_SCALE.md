# R142 — Replaceable multi-source discovery for joining original chain31340

**Committed source and mock-unit tests; NOT live externally verified.**
New nodes need **zero manually pasted enode/ENR values** if there are
at least two usable public HTTPS hint feeds. This is one component
of onboarding automation, **NOT yet zero-touch installation**.

## Confirmed original chain identity (VM4707 real R141 observation)

- Chain ID: `31340`
- EL genesis block hash:
  `0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf`
- Beacon genesis validators root:
  `0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd`
- Controllerless transport network: `ff2328775f000000`
- Last observed VM4707: Beacon head slot 6682, finalized epoch 204,
  EL peers 1, CL peers 1, not syncing/optimistic/EL offline.
  This is not proof of outside-ISP or multi-validator joining.

## What code does

`tools/sse_pos_r142_public_peer_discovery.py` accepts operator-provided
**public HTTPS directory URLs** (not a fixed peer address). It checks
that each bounded fresh JSON document identifies the original
execution/Beacon genesis, chain ID and overlay network, enforces
future-but-bounded expiry, rejects duplicate keys and malformed native
EL IPv6 enodes or CL ENR hints, ignores failed mirrors, and requires
two distinct functioning sources and two nonconflicting candidate
node records. There is no one special genesis peer. The result contains
a list of EL bootstrap enodes and CL boot ENRs.

R137 `sse_pos_r137_independent_observer_create_once.py` now accepts
repeatable `--discovery-source` in place of manually pasted
`--execution-seed-enode-v6` and `--beacon-seed-enr`.
The R137 create-once guard, pinned images, private Engine JWT,
non-signing behavior and local interactive authorization are retained.

**A directory is an untrusted discovery hint.** The current feeds
are neither publisher-signed nor on-chain authenticated, and an HTTPS
server/domain is not an SSE governance authority. Validating
syntactic enodes and ENRs DOES NOT validate ENR signatures, genuine
operator ownership, availability or native peer identity. The native
Besu/Lighthouse handshakes and chain/genesis/finality checks
are essential; use multiple independently operated publishers and
inspect Eclipse/Sybil poisoning risks. Release provenance,
cryptographically authenticated dynamic operator records and
self-publication are subsequent improvements.

## Example source document format

A publicly reachable mirror should serve ordinary JSON with the
following schema. This snippet contains **PLACEHOLDERS**, not actual
bootnodes or an existing published mirror:

```json
{
  "schema": "SSE_R142_CHAIN31340_PUBLIC_PEER_HINTS_V1",
  "chainId": 31340,
  "executionGenesisHash": "0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf",
  "beaconGenesisValidatorsRoot": "0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd",
  "networkId": "ff2328775f000000",
  "expiresAt": 1800001200,
  "peers": [
    {
      "nodeId": "actual-independent-peer-1",
      "executionEnode": "enode://ACTUAL_PUBLIC_EL_KEY@[ACTUAL_6PLANE_IPV6]:30404",
      "beaconEnr": "enr:ACTUAL_SIGNED_NATIVE_CONSENSUS_RECORD"
    },
    {
      "nodeId": "actual-independent-peer-2",
      "executionEnode": "enode://ACTUAL_SECOND_PUBLIC_EL_KEY@[ACTUAL_6PLANE_IPV6]:30404",
      "beaconEnr": "enr:ACTUAL_SECOND_NATIVE_CONSENSUS_RECORD"
    }
  ]
}
```

`expiresAt` must be a fresh Unix UTC timestamp within 24 hours of
a consumer's check. Do NOT copy the illustrative old timestamp.
Both mirrors may publish an overlapping directory; no mirror is
entitled to approve/exclude arbitrary peers. The current schema
is only an input to optional peer discovery, never an allowlist.

## New operator read-only plan

After a fresh independently operated Linux host already has the
reviewed source tree, exact public chain31340 archive, pinned official
Besu/Lighthouse images, Docker, working PUBLIC ZeroTier overlay,
and operator manifest from R136:

```bash
python3 -B tools/sse_pos_r137_independent_observer_create_once.py \
  --plan --manifest observer.json \
  --archive "$HOME/chain31340-public-native-observer-v1.tar.gz" \
  --discovery-source 'https://ACTUAL-FIRST-PUBLIC-MIRROR/peers.json' \
  --discovery-source 'https://ACTUAL-SECOND-PUBLIC-MIRROR/peers.json'
```

The URL placeholders are **not currently deployed** by this PR.
No username/password, network admission invitation, fixed VM IP or
manually pasted peer records are needed *after* public mirrors exist.
On an independently owned host, R137 `--apply` still requires
**one-time interactive local approval**. Do not run it on VM4706 or
VM4707, which already have active nodes.

## What's still required for genuine zero-touch onboarding

1. Publish the original verified genesis archive, exact client images,
   this code/release and at least two refreshing peer directories
   on real public independently maintained HTTPS mirrors.
   **A private GitHub repository does not meet this requirement.**
2. Build a reproducible one-command/cloud-init first-boot installer
   for new hosts: OS package provenance, guarded daemon installation,
   controllerless ZeroTier join, archive/client download+digest
   verification, local identity generation, reviewed OS permissions,
   isolated EL+CL installation, safe dynamic address handling and
   native peer/finality recovery. Existing R137 is NOT this installer.
3. Operators choose local validator/provider/consumer/monitor roles and
   locally authorize role-specific on-chain transactions. Validator
   creation requires fresh local BLS custody, real 32-test-ETH deposit,
   Beacon activation and slashing protection; monitor requires EOA
   bond and selection, etc. No central role approver.
4. Update/republish actual ENR/enode when the overlay IPv6 changes
   and verify fresh nodes can still bootstrap. R137 currently uses
   `--disable-enr-auto-update`, which can become stale without a
   reviewed reconciler. Original nodes also need compatibility tests
   with newly discovered nodes.
5. Demonstrate public-directory availability, outside-provider ISP
   joining, real native EL+CL peer counts, matching growing finalized
   checkpoints, permissionless validator deposits and real SSE
   provider/consumer/monitor workload lifecycle. Merely having a
   parsable discovery JSON does not pass any of these gates.

## Initial VM experiment (NOT a fixed network or role limit)

Six additional machines beyond VM4706/VM4707:
- VM A–B: nonsigning EL+CL first, then each independent BLS validator
  and a bonded monitor (only after actual activation/funding).
- VM C–D: EL+CL plus independent bonded monitor.
- VM E: EL+CL and real resource provider with independent host metering.
- VM F: EL+CL and consumer/workload client.

These roles can be combined differently and each can be scaled.
All VMs in one cloud tenancy remain one shared infrastructure
fault domain; use outside-ISP/operator nodes for independence claims.
A network with `k=4` existing fixed seats is **not** an adaptive
committee merely because four monitors run. Adaptive contract
migration remains a separate blocking deliverable.

## Regression

```bash
.venv-tests/bin/python -B -m unittest discover -s tests \
  -p 'test_sse_pos_r142_public_peer_discovery.py' -v
.venv-tests/bin/python -B -m unittest discover -s tests
```

These do not create VMs, install system packages, publish real mirrors
or authorize any signing/funding operation.
