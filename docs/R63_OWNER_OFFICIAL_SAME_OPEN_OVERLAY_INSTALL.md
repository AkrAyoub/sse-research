# R63 — original validator host joins the SAME open-join transport as every full node

**Date:** 2026-11-21. **GitHub SOURCE ONLY, not yet run on VM4706.** Original R62 OBSERVED: exact single-owner chain31340 Besu EL chainId 31340, execution block 3029; Lighthouse Beacon head slot 3247, finalized epoch97 and root `0x3874c8cc77e52b4986b84b94bcc5977a98be3377f524e00a1d00046c478de928`, genesis time `1795219212` confirmed by actual HTTP200 inside original Docker network namespaces; original single VC container running. Host API published ports null because isolated internal bridge, but internal services respond. Native Ethereum peers=0; no remote syncing yet.

Original VM4706 does **not** currently have ZeroTier. This is a **one-time OS networking installation**, separate from Ethereum P2P; it must never recreate original genesis, new validators, change existing Docker networks, restart Besu/Lighthouse or transfer signing secrets. User insists NO provider-private LAN as blockchain peer/bootstrapping; this transport must match VM4707 and independent laptop open-join network. The existing measured external WSL laptop↔VM4707 ZeroTier IPv6 payload transport is a prerequisite but not real native EL/CL proof. A ZeroTier virtual 6plane address by itself does not prove packets avoid provider-private underlay; future acceptance must include outside-provider native peer and real underlay inspection.

## R63 implementation (not executed yet)

`tools/sse_pos_r63_owner_open_overlay_install.py` is a single standard-library script that imports the existing reviewed R60 owner audit guard. Two modes:

- `--plan --expected-commit SHA`: read-only. Requires exact Git checkout, original actual VM4706 chain/genesis and local JWT metadata (never content), all three EL/BN/VC still running on unchanged internal Docker network, Ubuntu 24.04 noble Linux amd64, existing IPv4 default management route. It identifies whether the official ZeroTier CLI exists, exact 1.16.2 version and only our public controllerless ad-hoc `ff2328775f000000` IPv6 6plane membership. It does NOT install the network or alter routes.
- `--install-and-join --expected-commit SHA`: **changes the host OS**, requires explicit interactive user approval `INSTALL-OWNER-OPEN-P2P-TRANSPORT` after the same read-only preflight; this is **NOT** a blockchain-native peer creation. It downloads the public publisher GPG key from ZeroTier's official GitHub; verifies the expected primary fingerprint **`74A5E9C458E1A431F1DA57A71657198823E52A61`**; configures `signed-by=` apt trust only for ZeroTier's official HTTPS Noble repo `https://download.zerotier.com/debian/noble noble main`, then `apt-get update` and installs **exact `zerotier-one=1.16.2`** via APT-signed repository metadata. No `curl|bash` or unsigned .deb. It rejects any existing apt repo/key file or broken symlink rather than overwriting. Then joins only `ff2328775f000000`, sets `allowDefault=0`, `allowDNS=0`, `allowGlobal=0`, verifies host IPv4 default route did not change, and rechecks original three native containers/owner genesis/metadata still intact. It reports real `OK PUBLIC` and assigned 6plane IPv6 only when actually observed; initial `REQUESTING_CONFIGURATION` is explicitly marked pending, not a success.
- IMPORTANT privilege: package install creates the system ZeroTier service and persistent host-local ZeroTier identity. This is a new network interface/service; the public ad-hoc network is globally open-join to anybody, so do NOT expose privileged Ethereum Engine8551, raw RPC/5052 or signer/admin APIs. Existing original Docker network remains internal-only with no new P2P ports. APT installation and overlay operations must not be done without owner operator approval. After a partial failure, inspect and reconcile; do NOT blindly rerun installer.
- In normal operation, ZeroTier's service persists and requires no repeated developer SSH/SCP or local sudo password each time it runs. Future external onboarding still needs public independently verifiable genesis+release distribution and stable discovery/relay substitution; present private GitHub source checkout is developer-only. No owner VM↔VM4707 private-LAN native Ethereum bootstrap permitted.
- Real cryptographic Ethereum P2P remains disabled on original EL until a **separately reviewed state-preserving Besu and Lighthouse networking migration** (R64); do NOT claim native sync or independent validator participation from R63 ZeroTier alone.

## Operator gate — VM4706 ONLY (after exact commit SHA is given)

Use owner-local GitHub read-only fetch, pinned detached checkout, run **14 R63 regression methods** (SOURCE mocks only), and run `--plan`. If any preflight result fails, stop and do not run `--install-and-join`. The owner must explicitly agree before real host networking is modified.

```bash
(
  set -e
  cd "$HOME/sse-research"
  export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/sse_vm4706_readonly -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o BatchMode=yes"
  git fetch --no-tags origin feature/r19-fresh-external-node-preflight
  SHA="bfd604f6f379d18980de4154cea4bf5f0e38fd57"
  git switch --detach "$SHA"
  test "$(git rev-parse HEAD)" = "$SHA"
  python3 -B -m unittest discover -s tests -p 'test_sse_pos_r63_owner_open_overlay_install.py' -v
  echo "R63_SOURCE_TESTS_PASSED=true"
  sudo -v
  python3 -B tools/sse_pos_r63_owner_open_overlay_install.py --plan --expected-commit "$SHA"
)
```

**Only after reviewing the real owner plan and validating service security/OS prerequisites**:

```bash
cd "$HOME/sse-research"
sudo -v
python3 -B tools/sse_pos_r63_owner_open_overlay_install.py --install-and-join --expected-commit "$(git rev-parse HEAD)"
```

This command requires a separate exact terminal confirmation. It may install a package, create a ZeroTier identity/service, alter host network interface/overlay route and add apt repository/key; it NEVER restarts original Docker clients/VC, exposes Engine API, or joins native EL/CL P2P.

Official sources: https://www.zerotier.com/download/ ; https://docs.zerotier.com/protocol/ ; https://docs.zerotier.com/config/ ; https://download.zerotier.com/debian/noble/ ; https://github.com/zerotier/ZeroTierOne/blob/master/doc/contact%40zerotier.com.gpg . Original evidence and distinctions: `docs/experiments/VM4706_2026-11-19.md`, Entries 094–096; common P2P architecture `docs/ARCHITECTURE.md` and `docs/R61_COMMON_PERMISSIONLESS_P2P_BOOTSTRAP.md`.
