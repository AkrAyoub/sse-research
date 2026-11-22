# R163 — Publish exact original chain31340 genesis as ONE public immutable release

**Baseline owner VM4707:** pinned R161 commit
`1c5583968cdf5480382ca988d4a9501f55acee98`,
**1093 Python tests in 17.613s; OK (skipped=3)**.

**First-class real new evidence:**
VM4707 successfully completed R150 **one-time public-only original
genesis release staging**:

- Original file:
  `$HOME/chain31340-public-native-observer-v1.tar.gz`.
- Verified stage:
  `$HOME/sse-chain31340-public-release-candidate/chain31340-public-native-observer-v1.tar.gz`.
- R150 proof:
  `$HOME/sse-chain31340-public-release-candidate/verified-public-genesis.json`.
- Original AND staged SHA256:
  `1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7`.
- Actual four inner public genesis/config file hashes verified.
- Actual Beacon genesis.ssz byte count: `2737436`.
- `newGenesisGenerated=false`,
  `validatorSecretInspectedOrCopied=false`.

**No claim of PUBLIC publication yet:** VM4707's `$HOME` is not
a public artifact mirror and cannot be downloaded directly by
fresh external hosts. Merely committing text source cannot upload
the original binary file to GitHub.

## New R163 GitHub release maintainer publisher

`tools/sse_pos_r163_publish_verified_genesis.py` takes the existing
R150 **exact verified public-only archive** and one exact reviewed
Git source commit. It requires an already configured authorized
GitHub CLI `gh` account capable of releasing artifacts to the
public `AkrAyoub/sse-research` repository. It does not demand
authorization from future joining nodes.

The program validates original R150 archive and manifest, makes
NO changes in plan mode, checks authorization and existing
release state, and with `--publish` creates the single release
tag `chain31340-genesis-v1` pointing to reviewed source SHA,
attaches exact public archive bytes **without overwriting any
existing asset or tag**, and finally performs an **anonymous public
HTTPS download** and exact archive/member verification. An
already existing release, unavailable credentials, unverifiable
asset, wrong digest, or unexpected response is an explicit refusal.

There is NO use of GitHub credential strings, GitHub personal
access token in a shell argument, private cloud access keys or
Ethereum signer material. Do NOT paste any credentials or
private-wallet files into GitHub or this chat.

On the original maintainer VM4707, AFTER checking out a reviewed
pinned R163 Git commit and running its full regression suite:

```bash
# Read-only verification (does not require the gh CLI)
python3 -B tools/sse_pos_r163_publish_verified_genesis.py \
  --asset "$HOME/sse-chain31340-public-release-candidate/chain31340-public-native-observer-v1.tar.gz" \
  --commit "$REVIEWED_R163_COMMIT"

# One-time PUBLIC GitHub release; requires maintained gh authentication.
# This writes a public GitHub release binary but NO blockchain state.
python3 -B tools/sse_pos_r163_publish_verified_genesis.py \
  --asset "$HOME/sse-chain31340-public-release-candidate/chain31340-public-native-observer-v1.tar.gz" \
  --commit "$REVIEWED_R163_COMMIT" --publish
```

In public form the **proposed, NOT YET VERIFIED LIVE** canonical
asset download URL is:

`https://github.com/AkrAyoub/sse-research/releases/download/chain31340-genesis-v1/chain31340-public-native-observer-v1.tar.gz`

That URL is a distribution artifact identity, NOT a fixed
bootnode, VM IP, consensus member or app admission authority.
It will be added to the R149 repository release manifest **only
after public download and exact hash verification succeed**.
The installed R147 source SHA can then include that reviewed
manifest and obtain exact genesis automatically on every
new host.

**Important practical prerequisite:** VM4707 previously used
an SSH **read-only** deploy key to pull source; that key is
not and must not be escalated to write permission. The R163
`gh` publisher requires a separately authorized GitHub
maintainer session or other approved asset upload channel.
Our GitHub connector can edit UTF-8 source, but does not
provide a binary release-asset upload action and cannot read
VM4707's local original binary. A maintainer-only login,
if needed, is a one-time distribution operation, not a
fresh-VM installer step. Do not promise fully unattended
publication without such an approved channel.

## R163 GitHub release CDN redirect fix

Previous `tools/sse_public_genesis.py` refused ALL HTTPS redirects,
which would reject an authentic GitHub public release. GitHub
release downloads normally redirect to a short-lived HTTPS CDN
asset URL; R163 now permits at most three redirects **only
when the requested original URL is the exact, canonical
`chain31340-genesis-v1` public GitHub release asset**.
Only the known `github.com`,
`release-assets.githubusercontent.com`, and
`objects.githubusercontent.com` endpoints are accepted,
with HTTPS mandatory and no URL username/password or
nonstandard port. All other HTTPS mirrors remain no-redirect.
In all cases downloaded bytes are bounded and verified against
the exact original R59 SHA256 **and** individual public member
hashes, independent of TLS or mirror trust.

This is a supply-chain verification mechanism, not proof
that any unrelated host can reach native P2P participants.

## Remaining release milestones

1. One-time original archive public asset publication and
   independent HTTP content verification.
2. Update `release/chain31340-public-release.json` with
   the **real tested** archive download URL (not placeholders).
3. Independently host the **actual** R158 native discovery
   directories with HTTPS and abuse hardening; publish genuine
   R156 peer records. At least one honest peer and replaceable
   rendezvous paths are required to join a second node;
   avoid fixed VM IP/enode or SSE membership whitelists.
4. On the brand-new VM4709: one pinned source download,
   one role selection; real client setup, original archive,
   sync/finality and native peers. Do not claim success
   from source-only tests or Docker process startup.
5. Real independent validator deposits, monitor/provider/
   consumer services and experiments remain further work.

The operator requested comprehensive paper-ready cleanup
**after** the real network and marketplace experiments.
Preserve original VC, genesis, source history and scientific
evidence until then.
