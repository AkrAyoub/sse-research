# R164 — Verified R163 suite; publication blocked by missing GitHub CLI authorization

**Actual operator output from VM4707 (2026-11-23):**

- R163 pinned commit `ca3a9e1ef747f56f99220f5b1bafa7f0a06e9969`.
- `Ran 1103 tests in 17.231s; OK (skipped=3)`.
- R150 public-only original genesis was independently staged with immutable SHA256:
  `1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7`.
- R163 `--plan` reported `authOrNetworkMutated=false`,
  `originalGenesisRecreated=false`,
  `publishingRequested=false`.
- Real attempt to check publication prerequisites reported:
  `R163_PUBLIC_RELEASE_BLOCKED=GITHUB_CLI_AUTH_UNAVAILABLE`.
- **No GitHub binary release asset was published** and no original
  validator/chain client was modified by this action.

## Two R164 fixes after reviewing the actual outcome

1. **Avoid a permanent pseudo-install on new host:** R147 previously
   completed basic source installation with an empty public genesis
   source list, wrote `/var/lib/sse/selection.json`, then refused
   any retry because the host now appeared already installed.
   R164 stops before persisting source/role state when the immutable
   original genesis URL is still absent. A source-only clone cannot
   masquerade as completed EL/CL installation, and no new genesis
   is synthesized. Unsupported marketplace-only roles also refuse
   **before any package installation or filesystem mutation**, until
   genuine agents and on-chain role activation are integrated.
2. **Independent anonymous public readback:** R163 now supports
   `--verify-public` to verify a public uploaded release using
   HTTPS and exact original file/member SHA256, **without** any
   `gh` CLI, account login, BLS signer, or write operation. This
   is valuable after an interrupted or partially completed
   one-time maintainer upload because `--publish` deliberately
   refuses overwriting an existing immutable tag.

## One-time publishing authority is a REAL dependency

Only the original owner VM possesses the staged binary asset.
The GitHub plugin has authorized repository text writes but does
not expose binary GitHub Release asset upload and has no path to
VM4707's local `$HOME`. Consequently the assistant cannot
truthfully upload these bytes merely by writing another GitHub
commit, running an unauthenticated source clone, or fabricating
a release URL. The R163 `gh` publisher requires a one-time
**maintainer-authorized GitHub CLI session** on a machine holding
that exact verified public archive.

This **one-time genesis release** is distinct from the user
experience of **every permissionless joining VM**, which must
continue to require only one installer command and local role
selection—never GitHub login, manual archive download, fixed
bootnodes or a private repository deploy key.

Once the one-time binary upload actually succeeds:

```bash
python3 -B tools/sse_pos_r163_publish_verified_genesis.py --verify-public
```

Only after the anonymous readback verifies should the manifest's
`originalGenesisArchiveSources` be updated to the real
`https://github.com/AkrAyoub/sse-research/releases/download/chain31340-genesis-v1/chain31340-public-native-observer-v1.tar.gz`
URL. **The current source list stays empty before publication**.
Then test a new pinned installer from an independent Ubuntu host,
with actual Besu/Lighthouse synchronization and finality.

The independent peer directory sources and signed native P2P
advertisements remain a separate infrastructure gate. Source
tests, GitHub URL existence and controllerless ZeroTier membership
are not evidence of independent Internet native EL/CL peering.

Full paper-ready refactoring is deferred until the real
multi-VM blockchain and economic role experiments are completed.
