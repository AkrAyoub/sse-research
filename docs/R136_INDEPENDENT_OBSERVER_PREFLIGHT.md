# R136 — Independent operator observer preflight (chain31340)

**Status: implemented and unit-tested locally; NOT yet deployed on a third host.**
The original owner VM4706 and non-signing observer VM4707 have independently
reported finalized epoch **200**, root
`0x0e870e8687dd93737daf777c0a9c690a9ddc73bca03ac6b62fa44b3579a0a467`,
with current justified epoch 202 and head epoch 204 (2026-11-21).
This verifies live PoS finality and cross-node checkpoint agreement. It does
**not** show a third-party operator can join from the public Internet.

## Narrow scope of this first independent-onboarding change

`tools/sse_pos_r136_independent_observer_preflight.py` does not name either
existing VM, its IP, its filesystem layout, or its Docker containers. It
accepts a small declarative manifest and verifies:

1. Chain **31340**, non-signing observer-only intent and exact known public
   original-chain archive checksum; no replacement genesis.
2. A live **PUBLIC** ZeroTier membership in the existing controllerless network
   `ff2328775f000000`. The interface and IPv6 are taken from the local node,
   verified against the actual local interface, **not copied from VM4706/4707**.
3. No operator-supplied wallet, signing key, image command, fixed host IP, or
   other unreviewed manifest field.
4. A machine-readable `PREFLIGHT_ONLY_NOT_DEPLOYED` report that never claims
   successful EL/CL peering, public reachability, validator activation, sync,
   or marketplace execution.

This tool is read-only and does not create containers, join ZeroTier, load
wallets, publish endpoints, start validators or register roles. ZeroTier is a
transport choice for this existing chain; membership alone does **not** prove
Internet-wide native peer accessibility or independent infrastructure.

## Example manifest (PUBLIC metadata only)

```json
{
  "schema": "SSE_R136_INDEPENDENT_OBSERVER_V1",
  "chainId": 31340,
  "nodeId": "third-party-observer",
  "role": "observer",
  "networkId": "ff2328775f000000",
  "archiveSha256": "1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7"
}
```

A genuinely separate candidate host must already have the *unmodified*
public original-chain archive and functioning ZeroTier membership. Save the
manifest as `observer.json`. Run **on that separate host**, without uploading
private credentials or keys:

```bash
sudo python3 -B tools/sse_pos_r136_independent_observer_preflight.py \
  --manifest observer.json \
  --archive "$HOME/chain31340-public-native-observer-v1.tar.gz"
```

Use an absolute archive path when invoking sudo if sudo changes HOME.
The tool reports the host's *actual* overlay IPv6 rather than requiring a
static host-IP input. Run the pure tests on the checked-out GitHub branch:

```bash
python3 -B -m unittest discover -s tests \
  -p 'test_sse_pos_r136_independent_observer_preflight.py' -v
```

## Remaining implementation/acceptance gates

- Replace the two-VM-specific R59 **deployment** guard with a generalized,
  create-once, container-name/data-dir-isolated and separately reviewed
  installation flow; never run the R59 apply path on either existing VM.
- Native Besu EL and Lighthouse CL peer discovery from an independently
  administered third-party host, actual blocks/head sync, same finalized
  checkpoint, and reboot recovery **on that third host**.
- A correct validator onboarding lifecycle: independent BLS key generation,
  original chain deposit contract and test-ETH deposit, activation, and
  slashing-safe VC only after the operator explicitly authorizes signing.
- Live resource-provider, consumer, monitor, escrow and actual SLA service
  lifecycle on the verified chain, with independent measurements.
- Replace infrastructure-specific overlay dependence for genuinely open
  Internet access where required; dynamic overlay IPv6 alone is not a
  sufficient guarantee of unrestricted global access.

No current-owner/observer container, genesis or signer should be modified to
pass this gate.
