# R291 — STOP private 10.50.56.x / SSH dependency: rejoin SAME open chain31340 ZeroTier IPv6 overlay as VM4706/4707/4709

## Binding architecture restored — 2026-11-24

The owner objected (correctly) that R286–R290's
hardcoded private provider `10.50.56.22`, manually
authorized SSH identities and private LAN path
are **not** the permissionless network implemented
and observed on the older native chain31340 VMs.

Previously binding source:
- `docs/ARCHITECTURE.md` says private provider
  10.50.56.0/24 **FORBIDDEN** for native
  execution/consensus P2P bootstrap, advertised
  EL/CL records or fallback. **All native full
  nodes use the same open-join network mechanism
  as arbitrary Internet participants.**
- `docs/R61_COMMON_PERMISSIONLESS_P2P_BOOTSTRAP.md`
  establishes controllerless public ZeroTier
  ad-hoc network `ff2328775f000000`,
  assigned 6plane `fca0::/16`, Besu
  IPv6 devp2p/discovery and Lighthouse
  discv5/libp2p/QUIC. No project owner
  network membership invitation/whitelist.
- `docs/R55_ZEROTIER_CROSS_HOST_IPV6_TRANSPORT.md`
  records ACTUAL laptop WSL ↔ VM4707
  IPv6 TCP and UDP payload roundtrips across
  the open overlay (TCP 1251.14ms, UDP 110.61ms
  in that one actual test). Overlay itself
  depends on ZeroTier planetary roots/relays.
- `docs/R225_VM4707_VM4709_FINALIZED_EPOCH602_MATCH_SKEW_RESTRICTION.md`
  records REAL two separately operating EL+CL
  full-node observations: chain31340, two
  native execution peers and two Beacon peers
  on each VM, both reporting finalized
  epoch602 **exact same root**. Their capture
  skew exceeded that specific 180s comparison
  threshold by ~1.22s; R192 epoch571 comparison
  passed. Both peers belong to the ORIGINAL
  canonical chain, no new genesis.
- `docs/R171_VM4709_REAL_CROSS_VM_DISCOVERY_VERIFIED.md`
  records a publicly anonymous GitHub
  native EL/CL enode/ENR discovery check.
  Public source and dynamic identity hint
  are NOT a permanent central admission
  provider or proof of independent ISP
  native EL/CL sync.

The three monitor machines VM4711/12/13
actually passed the 21/21 R290 corrected
R288 SSH tests and created one separate
dedicated SSH ED25519 research identity
each, owner-TTY approved:
- VM4711 PUBLIC key fingerprint
  `SHA256:LeIVtAanRyTurwoNeaoVT3jBiPMI3fdjIfwiRdxhgWU`
- VM4712 PUBLIC key fingerprint
  `SHA256:aB50B+cp/X13fHPtvGH7L0ELYjxl7tPmye+itJET0uA`
- VM4713 PUBLIC key fingerprint
  `SHA256:HY3616d2+iJ3vw5+BtBhehqA1CAD57KNa/C1/c4Irn8`.

VM4714 R290 21/21 tests passed,
read-only `authorized_keys` metadata
reported **file exists, bytes0**, unchanged.
Thus no NEW SSH authorized keys were
installed for any of the three monitoring
hosts and no R287 authenticated private
SSH tunnel succeeded. The new SSH
identity files remain on their respective
owners and should not be copied or
reused as project-level SSE network admission.
Do not destroy/modify them without a
separately reviewed local owner action.
R286/R287/R288 continue as historical
*private-infrastructure diagnostics only*,
**NOT the SSE networking architecture
or mandatory provider/monitor onboarding.**

## New GitHub R291 — common open overlay for ANY participant

New `tools/sse_pos_r291_common_public_overlay_onboarding.py`
has exactly two guarded modes:

- `--status` read-only, any non-signing
  compatible machine can inspect whether
  its installed ZeroTier CLI/daemon can
  access the same actual original
  controllerless ID `ff2328775f000000`.
  It verifies `OK PUBLIC`, actual local
  assigned 6plane IPv6 `fca0::/16`,
  effective `zt...` network device and
  CLI daemon online. It does **not** treat
  another provider's `10.50.56.x` address
  as an application data-plane endpoint.
  It distinguishes installed, CLI access,
  joined and actually ready, and never
  invents a network success/EL peer/SLAs.
- `--join` is an explicitly independent
  local-OS-owner approved one-command
  `sudo -n zerotier-cli join
  ff2328775f000000` after preview.
  A network controller does not
  authorize/approve/enroll any SSH account
  or cloud VM IP. Local system owner
  permits the installation/join on
  their own device. Existing member
  whose ZeroTier is unhealthy is NEVER
  blindly rejoined. Original VM4706,
  VM4707, VM4709 owner usernames and
  existing original BLS custody paths
  are protected against accidental
  duplicate experimental join. This
  is a **source operation protection**,
  not a global join membership list;
  arbitrary other Linux operators may
  join the same public overlay independently
  without seeking the SSE owner's account.
  ZeroTier planet/relay vendor dependency
  remains a known independence blocker.

The network encodes inclusive destination
port range **9000..30559**. We verify
Besu P2P 30404, Beacon 9000/9001,
the existing R55 genuinely bound IPv6
TCP/UDP echo ports29000/29001 and
return UDP port29002, and a possible
future authenticated provider ingress
port29080 lie inside it. SSH22 and
Engine API8551 lie outside. Do not
bind unrestricted RPC, Docker socket,
raw unsigned worker HTTP8877 or
BLS validator APIs on the overlay.

New source-only R291 tests
`tests/test_sse_pos_r291_common_public_overlay_onboarding.py`
(18 mocked tests) verify network
identity/ports, membership, fca0
address, multiple failures, original
signer guards, exact owner consent,
join command-only and zero private-IP
admission policy. Tests not yet user-VM-run.

## Optional official signed-package installation on NEW app VMs only

Some VM4711–14 may have ZeroTier
ABSENT. The current logs contain
NO ZeroTier inventory for these VMs;
do not infer it is installed.

If absent, local operator can later
separately run:
`bash scripts/r291_vm4711_4714_signed_overlay_install.sh
<SAME_PINNED_SHA> --install`.

This is one **privileged OS operation**
with an exact per-host TTY owner approval.
It is restricted to those four dedicated
laboratory machines so original VM4706
signing state and existing VM4707/4709
native EL+CL aren't accidentally touched.
No central network admission:
this is ONLY a new lab VM signed
package installer guard.

It reuses VM4709-source-vetted R175/R177
`tools/sse_pos_r152_unattended_host_dependencies.py`
`install_verified_zerotier_apt()` ONLY
(not broader `setup()`, which also installs
Docker/EL/CL). Before modification:
exact clean pinned Git SHA, Ubuntu24.04
x86_64, preexisting owner noninteractive
sudo, absence of an installed ZeroTier
binary, required GPG/APT/systemd
commands, and original verified full
vendor GPG primary fingerprint
`74A5E9C458E1A431F1DA57A71657198823E52A61`.
Actual upstream scoped signed-by Ubuntu
Noble APT repo, HTTPS metadata preflight
and APT signature verification are
required; never curl|bash/skip signature.
The signed-package subprocess uses `NEEDRESTART_MODE=l` (list-only) and refuses any APT package other than `zerotier-one`, to avoid automatically restarting unrelated services such as the already running VM4714 Docker worker. Package installation can still change local OS/service state and is not a no-risk operation. The operation creates only reviewed
scoped apt keyring/source, installs
zerotier-one package and enables
its daemon. **It does not join any
network**, Docker install/start/stop,
native EL/CL/VC, original genesis, API,
Ethereum wallet, provider container,
SSH keys or native transactions.
OS package/service changes are real
and need local owner authorization.

New R291 root helper
`tools/sse_pos_r291_verified_vendor_package_only.py`
and twelve mocked unit tests
`tests/test_sse_pos_r291_verified_vendor_package_only.py`
are source-authored, NOT yet user-VM-run.
Future anonymous participants do not
need the existing four lab usernames
to join the open overlay; they obtain
the signed vendor client on their
own OS and follow the same native
release/genesis/peer bootstrap.

## Correct real verification sequence on new VM4711–14

1. ALL FOUR host owners fetch the same new
   reviewed R291 SHA. Run 17+10 focused
   R291 tests and `python3 -B
   tools/sse_pos_r291_common_public_overlay_onboarding.py
   --status`; this is zero-effect.
   Record `zerotierClientInstalled`,
   `readOnlyZeroTierCliAccessible`,
   `daemonReportsOnline`,
   `actualOpenOverlayReadyForCrossHostTransport`.
2. On host where client ABSENT, after review
   (no older live PoS clients) and owner
   chooses it, run the exact separate
   signed-package-only script. If local
   sudo -n unavailable, preserve host
   and report; don't workaround with
   `curl|bash` or a Docker socket change.
3. Once ZeroTier installed and daemon
   online, owner independently chooses
   `--join` and types the exact
   `JOIN-EXISTING-OPEN-SSE31340-ZEROTIER`
   phrase. The command reports actual
   membership and distinct overlay IPv6.
   An asynchronous status may require
   new `--status`, not repeated `--join`.
4. After actual 6plane IPv6 is observed,
   verify REAL independent cross-VM
   IPv6 TCP+UDP with ALREADY-EXISTING
   R55 code: VM4714 `--server`
   binds a harmless ten-minute echo
   on its *own* overlay IPv6
   TCP29000/UDP29001; each independent
   monitor VM can `--check` its
   real refreshed provider-assigned
   overlay IPv6, client UDP source
   bound29002. NO private LAN, SSH
   tunnel or raw CPU worker exposed.
   This is transport proof ONLY,
   not signing, lease/sla or EL+CL
   peer/finality.
5. For actual signed resource service,
   use a separately authenticated
   provider gateway bound ONLY to its
   actual overlay IPv6 with TLS and
   signed EIP712 V2 response bound to a
   real finalized paid lease (existing
   R234/R232 policy), not just forward
   raw unsigned VM4714 local Docker HTTP.
   The real worker remains
   `127.0.0.1:8877`. A provider
   that has no funded V2 lease/valid
   signing response cannot be claimed
   publicly service-ready.
6. Any new full EL/CL observer from
   anywhere must install the exact
   original public chain31340 genesis
   and clients, obtain dynamic native
   ENR/enodes via replaceable public
   discovery hints and actually sync
   both Besu and Lighthouse P2P/finality,
   as earlier VM4707/4709 did.
   This is independent of whether
   an app-only provider/monitor
   runs its own full node.

## Honest limitations

- ZeroTier controllerless open-join
  is not equivalent to fully independent
  native direct Internet P2P. Vendor
  planetary root/relay reliance and
  public bootstrap feed independence
  remain to be addressed with alternate
  direct/redundant transports.
- VM4711–14 are still operated in
  the same underlying VM cloud. Even
  if their fca0 overlay addresses differ,
  underlay packets might use provider
  LAN; do not call cross-host overlay
  tests genuine independent-ISP
  or global decentralization proof.
  R55 external WSL TCP/UDP evidence
  was real, but laptop native Besu
  + Lighthouse sync has not yet been
  proven.
- Original VM4706/4707/4709 are
  running REAL native chain31340;
  preserve them unchanged. VM4714
  existing Docker CPU worker already
  ran genuine 8192-round SHA work
  under strict 0.5cpu/256MiB caps,
  but none of VM4711–13 has yet
  run a signed remotely observed SLA.
- All THREE original VM4707
  native role fundings finalized;
  four new VM4711–14 Ethereum
  application wallets still unfunded.
  Four new 0.005 TEST ETH grants
  with maximum combined
  0.020000000084 TEST ETH incl gas
  remain READONLY QUOTED and NOT
  separately owner authorized.
  R291 does not sign/send transactions
  or authorize additional spending.
