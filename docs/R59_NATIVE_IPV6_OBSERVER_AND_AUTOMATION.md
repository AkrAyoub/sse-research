# R59 — ONE reviewed non-signing Ethereum EL+CL node installer, IPv6 P2P only

**2026-11-21 status: GitHub SOURCE ONLY, not VM-tested or deployed.** R58 actually observed both original client images' IPv6 P2P flags, while its previous `requiredBesuIpv6OptionsPresent=false` was caused solely by incorrectly requiring the nonexistent `--engine-rpc-host` in the IPv6 gate. That audit bug was corrected in subsequent GitHub code (not rerun on VM). Original VM4706 real Besu, Lighthouse BN and one Lighthouse VC all remain RUNNING on `sse31340-g2-internal`; no original P2P seed or second native peer observed.

**Design:** `tools/sse_pos_r59_native_ipv6_observer.py` is a SINGLE SELF-CONTAINED stdlib Python role installer. It does not need the developer Git repository to run on an external host. It consumes the exact original R47 public chain31340 archive and immutable R57 Besu/Lighthouse Docker images already present on VM4707. `--plan` is read-only; `--apply` is operator-consented and create-once, and starts an actual NON-SIGNING execution+consensus pair in a dedicated user-defined Docker `--ipv6` bridge. It NEVER creates a VC, validator key, new genesis, or wallet, and does not read/modify the owner signing machine.

## Native network/API separation

- Host ZeroTier `ff2328775f000000` overlay must be OK PUBLIC, with assigned host `fca0::/16` address actually attached to the interface. ZeroTier ad-hoc requires both directions of UDP packets to target ports 9000..30303. Docker port mapping may rewrite packet ports/addresses; **measure real external discv5/libp2p/QUIC and Besu devp2p**, do not infer success from R55 socket echo.
- **Docker P2P-only publication** to *the exact* local 6plane IPv6 (no host wildcard): Besu `[ZT_IPV6]:30303:30303/tcp` and `.../udp`; Lighthouse `[ZT_IPV6]:9000:9000/tcp`, `.../udp`, `[ZT_IPV6]:9001:9001/udp`. No exposed P2P on host public IPv4 or private eth0. Docker daemon's actual IPv6 bridge behavior may vary, and published host IPv6 must be validated from the external laptop.
- Developer loopback-only API exposure: execution JSON-RPC `127.0.0.1:28545:8545/tcp`; Lighthouse Beacon REST `127.0.0.1:25052:5052/tcp`. No host publication whatsoever for JWT-authenticated Engine API port 8551. EL and BN communicate inside a dedicated Docker bridge by the EL's Docker DNS name and a **new local 0600 Engine JWT**; it is NOT the original owner JWT. Docker bridge is *not* `--network host` and *not* `--internal` (genuine outbound P2P must work). Engine host-header allowlist is **not** a bind/firewall policy. Docker publication and bridge-level access control are the actual boundaries; check real external API inaccessibility before claiming safe public network.
- All Docker daemon privileges are exercised with scoped operator-authorized `sudo -n` **during the one-time installation**; containers are `--user <operator uid:gid>`, `--cap-drop ALL`, `--read-only`, `no-new-privileges`, with bounded RAM/CPU and 0700 fresh local data directories. No private GitHub key, old wallet, validator EIP2335, mnemonic or slashing database are copied.
- `--restart unless-stopped` means Docker normally starts already-created node containers on host/container-daemon restart without asking a password each time. **NOT YET IMPLEMENTED**: robust systemd ordering against ZeroTier network readiness, dynamic 6plane address rebind/restart after ZeroTier identity change, atomic updates/migration, crash-loop monitoring and state recovery. A reboot *before* the overlay address exists can prevent Docker from binding a fixed host IPv6; do not claim hands-free unattended restart accepted until an actual reboot/failure test passes. The finished role installer must solve these.
- Signed EL/CL bootstrap ENRs may be provided together as optional `--execution-seed-enr` and `--beacon-seed-enr` strings. Regex formatting is NOT crypto signature verification, public reachability, original chain validation or trustworthy distribution. Without real bootnodes, a created node is merely a live native observer **with no expected original head/finality synchronization**. Do not call it G3 or evidence of multi-node PoS finality until actual bidirectional native peer handshakes and original canonical finalized-root match.

## GitHub regression and stage gates — DO NOT APPLY UNTIL CODE REVIEW

The R59 source is `tools/sse_pos_r59_native_ipv6_observer.py`; focused security/behavior tests are `tests/test_sse_pos_r59_native_ipv6_observer.py` (16 methods). Both committed on existing feature branch, not merged to main. Tests are SOURCE ONLY, **NOT yet run** on VM. Only after an exact frozen commit source-test pass and SHA256-verified transfer from existing owner source checkout, run nonmutating `--plan` on non-signing VM4707.

Developer-stage commands on VM4706 (update the exact SHA to the newest immutable R59 commit from the operator's response, never a floating branch HEAD):

```bash
(
 set -e
 cd "$HOME/sse-research"
 export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/sse_vm4706_readonly -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o BatchMode=yes"
 git fetch --no-tags origin feature/r19-fresh-external-node-preflight
 SHA="4b88f459e14510e6fc117e0e1d4ec9e3427a94b3"
 git switch --detach "$SHA"
 test "$(git rev-parse HEAD)" = "$SHA"
 python3 -B -m unittest discover -s tests -p 'test_sse_pos_r59_native_ipv6_observer.py' -v
 echo "R59_SOURCE_TESTS_PASSED=true"
 sha256sum tools/sse_pos_r59_native_ipv6_observer.py
 scp -o StrictHostKeyChecking=yes tools/sse_pos_r59_native_ipv6_observer.py \
   ayoubakrvm4707@10.50.56.8:/home/ayoubakrvm4707/sse_pos_r59_native_ipv6_observer.py
)
```

Then on VM4707 only, comparing transfer SHA256 and refreshing privileged local timestamp if needed:

```bash
sha256sum "$HOME/sse_pos_r59_native_ipv6_observer.py"
sudo -v
python3 -B "$HOME/sse_pos_r59_native_ipv6_observer.py" --plan
```

**Do not execute `--apply` at this stage.** The full launcher source is a proposed implementation, not an approved deployment. Review real R59 plan and actual Docker bridge IPv6/firewall/port mapping before authorizing new P2P ports; inspect pinned Lighthouse/EL flag semantic compatibility and assign real canonical source ENRs. The original VM4706 has not yet enabled native EL P2P. Once an apply is actually authorized, manual on-host token `CREATE-REAL-R59-NONSIGNING-OBSERVER` is required exactly once. A partial apply is never automatically rerun or reset; preserve state for diagnosis, including the new local JWT/data and copied PUBLIC genesis.

## Finished production onboarding contract (still unfinished)

1. Operator obtains publicly downloadable *signed and hash-pinned* installer, original public genesis manifest and native clients from redundant neutral mirrors, **without** private GitHub access, SSH to an existing owner VM, static public IP, registration, invite, or admin approval by the SSE network. The current private developer repository/SSH copy is NOT that public release.
2. One local OS authorization step provisions the node's designated minimal service account/runtime and its chosen legitimate role(s); per-role identity is generated owner-locally, never distributed. A **non-signing full node needs no TEST ETH and no validator key**. A validator needs independently generated BLS keys and standard real on-chain 32-TEST-ETH deposit/activation; provider and monitor need the separate actual on-chain contract eligibility/bonds.
3. Daemon/manager supervises the participant's chosen services and maintains dynamic discovery and safe automatic reconnect after address change, reboot or process crash. Routine start/stop/restart/read-only health checks require no SSH password, GitHub authentication, local sudo password or enrollment approval. Operator retains authority for privileged upgrades, validator withdrawal/staking, and risk-sensitive security changes; no unattended recovery may duplicate a validator signer.
4. Public release must distinguish permissionless *application consensus/admission* from ZeroTier root/relay dependencies, untested third-party reliability, and host administrator permission. Fully trustless rootless networking and independent physical operator fault domains are NOT demonstrated by R55, R56, R57, R58 or R59 source.
