# R56 — stage the REAL chain31340 native IPv6 EL/CL peer (G3) after R55 success

**Date:** 2026-11-21. **Status:** GITHUB DOCUMENTED OPERATOR PLAN ONLY, **NOT EXECUTED** on either VM. Actual R55 WSL ↔ VM4707 IPv6 TCP/UDP payloads both succeeded with measured TCP RTT 1251.14 ms and UDP RTT 110.61 ms; see experiment Entry 085. No second Besu execution peer or Lighthouse consensus peer has been deployed or synchronized. No change to VM4706's original signing chain, genesis, Engine JWT, original execution DB, beacon DB or slashing protection is authorized.

## Architectural decision maintained

Keep the SAME genuinely running original **chain31340**, using the exact owner-verified original EL genesis and Beacon genesis.ssz, with an independent **NON-SIGNING** Besu + Lighthouse EL/CL observer first on VM4707. Do not create/derive/copy BLS validators, copy signer secrets, regenerate genesis, or start an EL+CL with a fresh incompatible chain. The owner VM4706 is the ONLY known live signer; VM4707 may join as an observer with no test ETH. No fixed participant count is imposed.

**Transport validated, consensus still pending:** actual public controllerless ZeroTier network `ff2328775f000000` (IPv6 6plane, no node approvals) carried BOTH actual TCP/UDP payloads from WSL Linux `fca0:2328:775d:17e8:a394::1` to VM4707 `fca0:2328:77b8:6578:a55::1`. It does not establish an Ethereum P2P handshake, direct rather than relay data path, Byzantine security, latency SLA, or decentralized root infrastructure. Root/relay availability is still an infrastructure dependence; final public claims must distinguish overlay admission from native plain-Internet admission.

Existing R48 observer source assumes its own Docker bridge and externally supplied two boot ENRs but publishes NO IPv6 P2P ingress; existing R49 seed source **requires a global IPv4** and publishes IPv4 port mappings. **DO NOT run existing R48/R49 `--apply` unchanged in the new ZeroTier IPv6 topology.** Existing original VM4706 G2 execution client was configured P2P disabled on an internal Docker network. Changing owner networking must be a **separate reviewed operator maintenance step**, not part of preparation on VM4707. Never pretend the second observer will synchronize until the original chain has a real native reachable peer/seed or another actually synced host.

## Gate A — copy ONLY original public verified genesis archive (VM4706)

**Prerequisite:** original VM4706 `~/sse-research` checkout at R55 SHA `708629c026cb7d57a27b49f5fd9ef232fff224ee`, the original public-only R47 archive already built at its fixed owner-local output. An earlier actual Step54 reported this archive with SHA-256 `1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7`. Do not rebuild if it exists; do not tar up the original G2 private runtime directory.

Run **only on VM4706**; a subshell refuses safely without terminating the operator's interactive shell:

```bash
(
  set -e
  cd "$HOME/sse-research"
  SOURCE_SHA="708629c026cb7d57a27b49f5fd9ef232fff224ee"
  test "$(git rev-parse HEAD)" = "$SOURCE_SHA"
  ARCHIVE="$HOME/.local/share/sse-r47-chain31340-public-artifacts/chain31340-public-native-observer-v1.tar.gz"
  EXPECTED="1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7"
  test -f "$ARCHIVE" && test ! -L "$ARCHIVE"
  test "$(sha256sum "$ARCHIVE" | awk '{print $1}')" = "$EXPECTED"
  python3 -B tools/sse_pos_r47_public_observer_bundle.py --verify "$ARCHIVE" --expected-commit "$SOURCE_SHA"
  echo "R56_ORIGINAL_PUBLIC_BUNDLE_VERIFIED=true"
  scp -o StrictHostKeyChecking=yes "$ARCHIVE" \
    ayoubakrvm4707@10.50.56.8:/home/ayoubakrvm4707/chain31340-public-native-observer-v1.tar.gz
  echo "R56_PUBLIC_ONLY_ARCHIVE_SCP_COMPLETED=true"
)
```

The source parser R47 verifies exact 4 public inputs/manifest: original `genesis.json` SHA-256 `22eb6c58288113b9c3671970967151012665137b345237b5c24060dc988b1ee8`, `config.yaml` SHA-256 `3e750d7d02e3ed83747f95cc09ff3299185f56f1777dfeb1f126b17881297b6e`, `genesis.ssz` SHA-256 `8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82`, `deposit_contract_block.txt` SHA-256 `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`; and no signing keys/JWT/mnemonics are included. The particular tarball hash is the actual owner-created archive hash, distinct from its file-members' hashes. SSH host key `SHA256:zO1v+7aN5N4mOid9NNwsZLhO65297wGWjrOM/E9oY8s` was independently verified from VM4707's console during R55. `scp` still requires operator SSH access. Do not overwrite any pre-existing differently hashed target without review.

## Gate B — verify received public archive and node host prerequisites (VM4707)

Run on **VM4707 only**, non-signing host. These diagnostics do **not** change Docker, package or network settings; they report local facts, not live native Ethereum peer proof.

```bash
(
  set -e
  ARCHIVE="$HOME/chain31340-public-native-observer-v1.tar.gz"
  EXPECTED="1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7"
  test -f "$ARCHIVE" && test ! -L "$ARCHIVE"
  test "$(sha256sum "$ARCHIVE" | awk '{print $1}')" = "$EXPECTED"
  echo "R56_VM4707_GENESIS_ARCHIVE_HASH_VERIFIED=true"
  printf '== public archive member names (not extracted) ==\n'
  tar -tzf "$ARCHIVE"
  printf '== real ZeroTier IPv6 interface ==\n'
  ip -6 addr show dev ztrb6cq527
  printf '== route to laptop ZeroTier IPv6 ==\n'
  ip -6 route get fca0:2328:775d:17e8:a394::1
)
```

Then separately check native image readiness without downloading/starting anything:

```bash
sudo -v
echo "== Docker daemon version =="
sudo -n docker info --format 'server={{.ServerVersion}} cgroup={{.CgroupVersion}}'
echo "== Besu image (may not yet exist) =="
sudo -n docker image inspect --format '{{.Id}} {{.Os}}/{{.Architecture}}' \
  hyperledger/besu:26.11.1
echo "== Lighthouse image (may not yet exist) =="
sudo -n docker image inspect --format '{{.Id}} {{.Os}}/{{.Architecture}}' \
  sigp/lighthouse:v8.3.3
```

Expected ORIGINAL image IDs if installed: Besu `sha256:4fd2ba40f0d65917bcb3abd9af60673946f66dee2ecb1b87f7cdfa6a30fe458d`; Lighthouse `sha256:53f9063d98c3d3a2d290207873f019ea2298cfc02f8cd58d87c33b04aab856d1`; BOTH must be linux/amd64. Missing images is not a blockchain consensus failure; the separate reviewed image pull/install stage follows. Never use mutable/latest images or accept only matching tag names while image IDs differ. Also distinguish original owner `sudo` permission and VM4707 local authorization.

## Gate C — source implementation review required BEFORE native P2P exposure

The prior R48/R49 launchers are NOT overlay IPv6 launchers. Build a separate new owner-free, non-signing IPv6 implementation AFTER observing Gate B and actual pinned CLI help. Research verified that modern Besu has distinct IPv6 P2P interface/advertisement options (`--p2p-interface-ipv6`, `--p2p-host-ipv6`) and that Lighthouse supports IPv6 `--listen-address`, ENR advertisement and optional `--enable-private-discovery`. **Exact flag compatibility with pinned 26.11.1/8.3.3 must be proven on actual immutable image-ID CLI `--help` before an apply command is authored or trusted.** Merely placing both clients on an IPv4 Docker bridge will not expose host-assigned ZeroTier IPv6: choose an explicitly reviewed IPv6-capable bridge forward or Linux host-network model; host networking shares host namespace and requires careful binding of ALL non-P2P local endpoints to loopback and strong least privilege. For host network, ensure Engine API/JWT, public JSON-RPC and Lighthouse HTTP REST are NOT accessible on ZeroTier.

Native peer acceptance MUST include real signed Besu devp2p peers, both directions' execution discovery, Lighthouse discv5 & authenticated libp2p peers, correct original genesis/fork, independent head/finalized checkpoint matching owner canonical data, actual sustained observable traffic, and fault/disconnect/restart test. Do not infer peer existence from Docker RUNNING status or an arbitrary ENR string. Besu's IPv6 node-key/ENR and Lighthouse gossip are distinct networking layers; require both. Bootstrap records must be redistributable/redundant and adapt changing addresses, never a single operator's permanent approval endpoint.

**Operator pause:** do NOT start a new native EL/BN on VM4707 from R48/R49, do NOT change VM4706 EL/BN/VC, do NOT create validators, and do NOT modify overlay config until these verified prerequisites and exact pinned-client networking CLI evidence are reviewed. Gate A/B are safe, concrete, necessary steps toward native multi-host Ethereum PoS, not a new detour into synthetic network probes.

## External docs / provenance

- Docker host networking: https://docs.docker.com/engine/network/drivers/host/
- Besu CLI options / IPv6: https://docs.besu-eth.org/public-networks/reference/options
- Besu TCP/UDP ports: https://docs.besu-eth.org/public-networks/how-to/connect/configure-ports
- Lighthouse IPv6 networking: https://lighthouse-book.sigmaprime.io/advanced_networking.html
- Original project R47 archive verification: `tools/sse_pos_r47_public_observer_bundle.py`, original R48/R49 launchers, `config/pos_client_image_pins.json`
- Actual user evidence and source/proposed distinctions: `docs/experiments/VM4706_2026-11-19.md`, Entry 085
