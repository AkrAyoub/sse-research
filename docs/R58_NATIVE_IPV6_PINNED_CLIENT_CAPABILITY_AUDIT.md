# R58 — audit the ACTUAL pinned client IPv6 flags on VM4707, no chain start

**Observed 2026-11-21:** R55 laptop WSL ↔ VM4707 real controllerless ZeroTier IPv6 TCP+UDP payloads BOTH succeeded (client TCP 1251.14ms, UDP 110.61ms). R56 VM4707 received original verified public-only chain31340 genesis archive SHA256 `1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7`. R57 immutable Besu26.11.1 image `sha256:4fd2ba40f0d65917bcb3abd9af60673946f66dee2ecb1b87f7cdfa6a30fe458d` and Lighthouse8.3.3 image `sha256:53f9063d98c3d3a2d290207873f019ea2298cfc02f8cd58d87c33b04aab856d1` were ACTUALLY pulled, ID/platform verified, and real --version output observed from offline Docker. The original signer VM4706 is unchanged. **R58 itself is currently GitHub SOURCE ONLY, not yet run on VM4707.**

## Actual 2026-11-21 R58 observations and false-negative correction

**OBSERVED:** VM4706 executed R58's original 12/12 regression tests and independently verified the exact SSH-copied Python SHA256 `09b423d55545285f3c12890f4fc2254e7edf1cfefbadcd7b93dfb01a1dad4339`. VM4707 actually executed `--audit` successfully (`R58_VM4707_AUDIT_EXIT=0`), verifying original PUBLIC genesis, exact client image IDs, public controllerless ZeroTier address and real offline Besu/Lighthouse CLI help. Besu real help exposed its dedicated IPv6 P2P host/interface/port/outbound flags; Lighthouse real help exposed IPv6 ports, private discovery, ENR and weak-subjectivity research flag. Original owner VM4706 EL/BN/VC Docker containers all reported `running`, but no current block/finality measurement was taken.

**R58 source audit predicate bug, fixed in GitHub SOURCE ONLY after observation:** the original audit falsely returned `requiredBesuIpv6OptionsPresent=false` because it required `--engine-rpc-host`, a flag not present in pinned Besu 26.11.1 and not part of the actual IPv6 P2P requirement. `--engine-rpc-port` and `--engine-host-allowlist` are documented Engine API options, but the latter is **an HTTP host-header allowlist, NOT an IP bind/access firewall**. Corrected source separates true IPv6 P2P options from Engine JWT/port/header controls, reports absence of explicit Engine bind-host setting separately, and always reports `engineApiIPv6HostNetworkIsolationVerified=false`. The corrected regression suite defines 14 focused methods. **These new tests/the corrected R58 auditor have NOT been rerun on either VM**, so do not replace earlier real output with expected values. R59 follows an isolated Docker IPv6 bridge with ONLY P2P host port mappings, rather than unsafe Engine exposure in Docker host network.

Next actual acceptance is still native Besu devp2p AND Lighthouse libp2p discovery/peer sync from separate hosts, correct original chain31340 genesis and matching canonical finalized checkpoints; none was established by R58.

## Why this actual-image help audit matters

Upstream Besu documents `--p2p-interface-ipv6`, `--p2p-host-ipv6`, `--p2p-port-ipv6`, IPv6 preference and discovery v5, but exact installed binary support must be confirmed before the R59 launcher chooses flags. Upstream Lighthouse documents IPv6 `--listen-address`, `--port6`, `--enr-tcp6-port`, `--enr-udp6-port`, `--enr-quic6-port`, `--enable-private-discovery` for non-public or private address discovery. Controllerless ZeroTier `fca0::/16` is NOT globally public IPv6; use appropriate local discovery setting if actual installed client exposes it. Docker ordinary IPv4 bridge networking is not necessarily capable of host ZeroTier IPv6 P2P and must not be called connected. No blanket host-networking launch until the Engine/JWT and RPC API binding boundaries are proved fail-closed by actual flags.

The GitHub R58 Python is standard library only. It requires Linux x86_64, original public archive hash, exact `ff2328775f000000` membership `OK PUBLIC`, an assigned host-bound 6plane IPv6, non-owner signing-state, exact R57 image IDs and linux/amd64. Then it runs three ephemeral offline help commands (Besu `--help` and optional `--Xhelp`, Lighthouse `bn --help`) using only immutable refs, no ports/mounts, network=none, rootless container UID, no caps, read-only. Returns a JSON map of exact flags seen in the installed executables; does NOT start any EL, BN, VC, signer, chain, wallet, Docker network, privileged API or peering. A failed `--Xhelp` is separately reported as unavailable, not confused with native execution. It refuses an inaccessible Docker daemon or mismatched original archive.

## A — GitHub/source test gate on developer VM4706 (DO NOT RUN the audit here)

```bash
(
  set -e
  cd "$HOME/sse-research"
  export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/sse_vm4706_readonly -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o BatchMode=yes"
  git fetch --no-tags origin feature/r19-fresh-external-node-preflight
  SHA="79cf0837772845ec56573a5aa0863448acd03093"
  git switch --detach "$SHA"
  test "$(git rev-parse HEAD)" = "$SHA"
  python3 -B -m unittest discover -s tests -p 'test_sse_pos_r58_native_ipv6_cli_audit.py' -v
  echo "R58_SOURCE_TESTS_PASSED=true"
  sha256sum tools/sse_pos_r58_native_ipv6_cli_audit.py
  scp -o StrictHostKeyChecking=yes tools/sse_pos_r58_native_ipv6_cli_audit.py \
    ayoubakrvm4707@10.50.56.8:/home/ayoubakrvm4707/sse_pos_r58_native_ipv6_cli_audit.py
)
```

If the source tests fail, DO NOT transfer/run the script; fix in GitHub and issue a new immutable SHA.

## B — actual client capability audit ONLY on non-signing VM4707

```bash
FILE="$HOME/sse_pos_r58_native_ipv6_cli_audit.py"
sha256sum "$FILE"
sudo -v
python3 -B "$FILE" --audit
echo "R58_VM4707_AUDIT_EXIT=$?"
```

Compare the transferred source hash to the VM4706 source hash. The output reports `besuP2pCliFlagsPresent`, `lighthouseBeaconCliFlagsPresent`, `requiredBesuIpv6OptionsPresent` and `requiredLighthouseIpv6OptionsPresent`. The Boolean presence flags are *capability discovery*, NOT proof that these command combinations will actually bind, resolve the 6plane address, authenticate peers or synchronize.

## C — R59 acceptance definition; NOT yet performed

Once actual flag output is inspected, author a reviewed non-signing VM4707 EL+CL launcher on GitHub that consumes ONLY original R47 public genesis and uses fresh independent local JWT and databases, exact R57 images and native IPv6. Bind only native P2P ports to intended ZeroTier interface; prevent exposure of any EL Engine API, JSON-RPC, Beacon HTTP or validator signing endpoint beyond host loopback/strictly local network. The Docker security model and permissions need an explicit tradeoff review (host namespace, bind paths, no sudo group grants). Do not use R48/R49 --apply unchanged. There is currently **NO authentic VM4706 seed peer** because owner EL had P2P disabled on its internal Docker network. Before claiming G3, separately plan a safe owner maintenance path preserving original one validator, signer keys and slashing data, so an EL+CL pair on VM4707 can connect to at least one canonical original chain31340 peer. A listening node/ENR alone is NOT success. Observe actual devp2p EL and libp2p CL peer handshakes, independent head/finalized-root agreement, and reconnection.

Sources:
- Besu IPv6 flags: https://docs.besu-eth.org/public-networks/reference/options
- Lighthouse Beacon node CLI: https://lighthouse-book.sigmaprime.io/help_bn.html
- Docker host networking and public-port risk: https://docs.docker.com/engine/network/drivers/host/
- Original real evidence: `docs/experiments/VM4706_2026-11-19.md` Entry 085–088
