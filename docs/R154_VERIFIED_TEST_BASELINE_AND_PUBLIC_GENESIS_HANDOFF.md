# R154 — Confirmed 1,047-test baseline and original public genesis handoff

**Date:** 2026-11-21. **Operator-observed VM4707 test record:**

- Pinned R153 Git SHA: `e10f23e842b1b0011a30212110dbb37a3088c11c`.
- `python3 -B -m unittest discover -s tests`: **Ran 1047 tests in 17.028s; OK (skipped=3)**.
- This proves a source-level suite pass on a host already running
  the genuine nonsigning chain31340 Besu/Lighthouse stack.
  It does not prove newly created VM4709 is installed, public native
  peer discovery, external operators or market roles are active.

## Immediate original chain artifact publication blocker

The original **PUBLIC-only** `chain31340-public-native-observer-v1.tar.gz`
is already present on an existing operator machine. Its pinned SHA256
is `1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7`.
R150 verifies that exact archive, four member hashes, file allowlist,
real Beacon state bytes and public manifest without reading BLS/EIP-2335
validator keys or copying any original signing wallet.

Because only the existing owner/observer VM holds the real bytes and
the GitHub source connector cannot copy a VM-local binary or upload a
release asset, a commit to GitHub alone **cannot honestly publish that
archive**. Do not fabricate genesis, derive it from chain ID or generate
another Beacon genesis for VM4709.

The one-time **maintainer** release preparation command on an already
trusted machine containing the original archive is:

```bash
cd "$HOME/sse-research"
python3 -B tools/sse_pos_r150_verified_genesis_release.py \
  --archive "$HOME/chain31340-public-native-observer-v1.tar.gz" \
  --out "$HOME/sse-chain31340-public-release-candidate"
```

It writes a public-only, separate verified output and does not change
the running blockchain, containers or signer. The next action is to
publish that public tarball through an authenticated, reviewed GitHub
Release upload or another independently retrievable public mirror,
then replace `originalGenesisArchiveSources` in
`release/chain31340-public-release.json` with actual verified HTTPS
download addresses and re-check SHA256 using R149. It is a **one-time
network release maintainer operation**, NOT a step demanded of each
joining VM. An automated release publication job must get the exact
verified binary from an authorized source, not a private signer directory.

## Upstream installer finding

R152's initial ZeroTier GPG key download erroneously used
`ZeroTierOne/main/doc/contact%40zerotier.com.gpg`, while the
published upstream signed-install workflow and actual reachable
key source use
`ZeroTierOne/master/doc/contact%40zerotier.com.gpg`.
Corrected the URL and regression-pinned the official release
fingerprint
`74A5E9C458E1A431F1DA57A71657198823E52A61`.
This adjustment has **not yet been real-VM verified**.

## Discovery still needs live evidence

An existing first-online node may run without remote enodes/ENRs, but
subsequent peer synchronization needs some real peer discovery path.
R142 currently consumes 2+ distinct published HTTPS mirrors with
actual native EL enodes and Lighthouse ENRs, not one permanent VM IP.
There are still no live verified publisher endpoints in the release
descriptor. A new node cannot infer external native peer locations from
an immutable genesis file; a decentralized rendezvous scheme must
still have an actual reachable discovery substrate.

The R154 acceptance goal is **publish actual original genesis once**,
prove two or more interchangeably hosted real peer records,
then use VM4709 as the first new full-node installation. Do not enroll
a new BLS signing validator before real independent Beacon deposit and
activation; do not claim operator independence when the VMs share
infrastructure.

## Deferred deep refactor

The operator directed an exhaustive codebase audit/cleanup and a
single paper-ready distribution **after** end-to-end native P2P,
validator, resource leasing, monitor and escrow experiments are
complete. Preserve working source and research history now; cleanup
and branch consolidation are a later separate gate.
