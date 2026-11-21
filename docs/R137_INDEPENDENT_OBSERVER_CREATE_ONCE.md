# R137 — Create-once independent non-signing chain31340 node

**Status: GitHub implementation, NOT yet acceptance-verified on a third physical/VM operator.**
Do not run these steps on VM4706, VM4707, or on any host containing
the original signer, its recovery data, or the R59 observer install.

## What is implemented

`tools/sse_pos_r137_independent_observer_create_once.py` reuses verified
R59 client image digests, existing original-chain public artifact checks and
host collision protections. Unlike R59 it derives new Docker resource names,
a separate private on-disk data root and an IPv6 address from the new host's
actual controllerless overlay membership. This deploys **only** Besu EL and
Lighthouse BN, no BLS keys, validator client, deposits or PoS signer.
EL Engine port 8551 and Lighthouse internal API are accessible on the
dedicated Docker network but **never published to the host**. Host REST/RPC
are loopback only; native EL/CL P2P binds to that host's assigned overlay IPv6.

The installer is **create-once, not an existing-node recovery tool**.
An existing directory, Docker network or named container causes refusal;
if the process partially fails, preserve and inspect everything rather
than deleting resources or rerunning `--apply`. A local interactive
phrase is required for mutation, separate from `--plan`.
It cannot prove protocol handshakes or chain finality just by starting
containers.

## Requirements on a genuinely separate, independently operated machine

- Linux x86_64, Docker, ZeroTier CLI, local Python 3 with same pinned source
  checkout, working passwordless `sudo -n docker` for the operator account.
- The **unchanged** original public chain archive installed under that
  operator's HOME at `~/chain31340-public-native-observer-v1.tar.gz`.
- Pinned Besu and Lighthouse OCI image IDs available locally; **not**
  unpinned Docker tags. No original-owner wallet, validator, or R59
  observer data.
- Native execution `enode://...` and consensus `enr:...` records
  obtained from actual existing chain31340 peers; published identifiers
  are not credentials. Syntax alone does not authenticate bootstrap.
- A controllerless public ZeroTier 6plane assignment on the new host.
  This is an incremental onboarding transport, **not proof of full
  Internet-open permissionlessness**, CGNAT traversal or unrestricted
  public reachability.

Use the R136 example manifest with **a new nodeId**, e.g.
`third-party-observer`. From the repository checkout on the **third**
machine, use the existing archive path and real bootnode records:

```bash
ARCHIVE="$HOME/chain31340-public-native-observer-v1.tar.gz"
python3 -B tools/sse_pos_r137_independent_observer_create_once.py \
  --plan --manifest observer.json --archive "$ARCHIVE" \
  --execution-seed-enode-v6 'enode://REAL_PUBLIC_ENODE' \
  --beacon-seed-enr 'enr:REAL_SIGNED_ENR'
```

The placeholders above **must** be replaced with genuine records and
an actual host with pre-existing prerequisites. The installer accepts
no made-up records. Only after reviewing a successful plan and
verifying that this is not an existing chain host, use `--apply`
instead of `--plan`; the script then requires a local interactive
authorization phrase. Do not run `--apply` through GitHub Actions
or on the two running VMs.

The R137 preflight uses the same original archive location as R59,
and will refuse alternate archive paths. Do not invoke it via
`sudo python3` unless HOME semantics are explicitly verified:
the caller's home directory is used to locate the original chain
artifact and choose the new state root.

## Mandatory on-node acceptance after an authorized install

1. Docker reports two new running containers only, non-signing, with
   correct image IDs, isolated data/JWT mounts, and exactly reviewed
   native P2P / loopback REST port publications. No host binding of 8551.
2. New EL local `eth_chainId` is `0x7a6c` (31340); new BN responds
   to its localhost `/eth/v1/node/syncing` endpoint with
   `is_syncing=false`, `el_offline=false`, `is_optimistic=false`.
3. Real `net_peerCount > 0` **and** Lighthouse peer count > 0;
   native protocol identity/dial and independent network provider
   visibility must be observed, not inferred from open sockets.
4. Canonical head advances; finalized root matches the running
   owner/observer at the **same checkpoint epoch**. A historical
   checkpoint match is insufficient: show new finality progression.
5. Test reboots and host underlay-IP changes on the third node
   without a second signer or chain reset. R137 does **not** install
   automatic recovery: that is an outstanding reliability gate.
6. Verify genuinely independent operator infrastructure and Internet
   accessibility separately from overlay membership.

## Unit tests

```bash
python3 -B -m unittest discover -s tests \
  -p 'test_sse_pos_r136_independent_observer_preflight.py' -v
python3 -B -m unittest discover -s tests \
  -p 'test_sse_pos_r137_independent_observer_create_once.py' -v
```

These tests are pure mocks and safety checks. They do not substitute
for live third-host deployment, native handshake, validator activation
or SSE real-resource SLA evidence.
