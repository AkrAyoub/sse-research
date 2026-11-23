# R165 — Original chain31340 genesis is NOW publicly published

## Actual evidence, not a simulated asset

Owner VM4707 ran the reviewed original-genesis release command and
reported on-chain-safe status:

- Previous pinned R163 suite at
  `ca3a9e1ef747f56f99220f5b1bafa7f0a06e9969`:
  **1103 tests in 17.231 s, OK (skipped=3)**.
- R150 source and release-candidate exact public archive SHA-256
  `1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7`.
- R163's output:
  `SSE_R163_ORIGINAL_PUBLIC_GENESIS_PUBLISHED_V1`,
  `publishedPublicBytesIndependentlyVerified=true`,
  `publicArchiveMembersVerified=4`,
  `newChainGenesisGenerated=false`,
  `validatorSecretsUploaded=false`,
  `onChainServicesOrValidatorsChanged=false`.
- GitHub's public release API has independently been inspected:
  the `chain31340-genesis-v1` release is **published, not a draft**;
  the asset is uploaded and its API digest is the exact original
  SHA-256 above. GitHub API also reports its original source tag
  target `ca3a9e1ef747f56f99220f5b1bafa7f0a06e9969`.

Immutable-in-content canonical download (public, no authentication):

```text
https://github.com/AkrAyoub/sse-research/releases/download/chain31340-genesis-v1/chain31340-public-native-observer-v1.tar.gz
```

GitHub release tags/assets are mutable by repository maintainers:
the installer **never trusts the URL alone**, and still verifies
the exact baked-in archive SHA256 and member hashes.

## R165 source integration

`release/chain31340-public-release.json` now contains the
verified canonical HTTPS URL under
`originalGenesisArchiveSources` and changes
`currentPublicReleaseStatus` from blocked to
`PUBLIC_GENESIS_MIRRORED_NATIVE_DISCOVERY_PENDING`.
The previously checked strict URL + controlled GitHub release
HTTPS CDN redirect downloader R149/R163 makes the immutable
source archive available to any future joining Ubuntu node.

The previously blocked source-only installer now has a real
artifact source. It still must NOT be advertised as fully
functional or safe for unrestricted external installation until
the real dynamic native EL+CL peer discovery and full startup
observations have been verified on genuinely fresh new hosts.
`replaceablePeerDirectorySources` remains an **empty list**;
no directory or native peer address has been invented.

Updated unit tests assert the published release URL,
the exact original SHA256, and the still-missing dynamic
native peer discovery sources. This R165 Git SHA's regression
tests are not yet owner-VM tested; last confirmed source
green is R163 1103/3.

## Next measured protocol steps

1. Capture *actual* original VM4707 Besu `net_enode` and
   Lighthouse `/eth/v1/node/identity`, plus exact original
   genesis and dynamically observed overlay IPv6 using the
   previously committed R156 read-only collector.
2. Check advertised enode/ENR and live transport against actual
   EL/CL peers. Do not infer public Internet direct reachability
   from ZeroTier 6plane addressing.
3. Establish replaceable independent, public, anti-abuse
   native rendezvous sources; then populate genuine verified
   URLs and test first-to-second-node joining.
4. Install the selected observer/full-node role on genuinely
   fresh VM4709 with NO copied signer. Verify same chain and
   finalized checkpoint using objective R141/R153 evidence.
5. Add real application agents, genuine independent validator
   BLS/deposit custody, TEST ETH funding and proof of actual
   lease/monitor/settlement; do not mark chosen roles active
   before their network/economic prerequisites.
6. Defer exhaustive paper-ready refactoring until all live
   multi-operator experiments have completed.

### Security note

The maintainer authenticated GitHub CLI on VM4707 and its
login output reported credentials stored in plain text.
A GitHub CLI auth token on a running P2P VM is a privileged
repository-write credential, not a native blockchain
requirement. Treat it as a one-time maintainer capability:
inspect local file permissions, remove/revoke that session
after release maintenance, and never distribute it to
joining VMs. Do not paste tokens into chat. Read-only
existing GitHub SSH key must remain separate.
