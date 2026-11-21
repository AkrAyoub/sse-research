# R60 — original chain31340 P2P migration readiness (no restarts)

**Observed 2026-11-21:** VM4706 original Docker network is sse31340-g2-internal, internal=true, ipv6=false. Its original running Besu EL (sse31340-g2-el-r40) explicitly has --p2p-enabled=false. Existing Beacon BN printed no networking flags in the short user allowlist, which is NOT proof of its effective defaults. Original EL/BN/VC were all observed running on this isolated network. VM4707's R59 plan succeeded, but no real native EL/BN bootstrap ENRs or cross-machine Ethereum handshakes exist yet.

R60 is a self-contained **owner-only read-only** source audit, not a migration or network service. On VM4706, tools/sse_pos_r60_owner_native_p2p_readonly_audit.py checks actual owner G2 EL genesis+Beacon genesis hash and local JWT metadata (never reads JWT), inspects only allowlisted Docker native P2P flags/network/port publications, and reads local loopback EL JSON-RPC chainId/blockNumber/peerCount and Beacon genesis/head/finalized checkpoint. It prints only redacted/sanitized summary fields; no signer secrets, keystores, private JWT data, raw full Docker command arrays or shell variables are printed.

**Observed first source run:** 11 passed, 1 failed before the live audit: R60 `safe_flags` lacked the allowlisted `p2p-host` option, so the malformed flag negative test failed. New GitHub-only fix now includes `p2p-host` and an explicit positive/negative regression (13 total tests). The corrected tests and R60 live audit have NOT yet been executed. Do not claim measured health until rerun. Nothing is started, stopped, restarted, reconfigured, backed up or exported.

## VM4706-only operator source and audit gate

Run inside a subshell, so failure does not exit the operator's interactive shell. Source is fetched using the existing owner's read-only scoped deploy key; no transfer to VM4707 is needed.

~~~bash
(
  set -e
  cd "$HOME/sse-research"
  export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/sse_vm4706_readonly -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o BatchMode=yes"
  git fetch --no-tags origin feature/r19-fresh-external-node-preflight
  SHA="6b2a6e24322567114c383ed7a5056ed7749939e1"
  git switch --detach "$SHA"
  test "$(git rev-parse HEAD)" = "$SHA"
  python3 -B -m unittest discover -s tests -p 'test_sse_pos_r60_owner_native_p2p_readonly_audit.py' -v
  echo "R60_SOURCE_TESTS_PASSED=true"
  sudo -v
  python3 -B tools/sse_pos_r60_owner_native_p2p_readonly_audit.py --audit --expected-commit "$SHA"
)
~~~

Expected source tests: 12 methods. Whether they pass is not yet observed. The live audit output is a point-in-time observation; no current EL block height, Beacon head or finalized root should be presumed until the user executes it. Its report never establishes remote peer sync.

## State-preserving native P2P migration (separate reviewed stage, NOT applied)

- A live --p2p-enabled=false Besu cannot become a valid bootnode merely because Docker publishes a port. Original internal bridge cannot route to external/IPv6 peers. Docker cannot retroactively add --publish to existing containers; connecting a running container to a bridge without changing the EL startup flags also does not enable Besu P2P.
- Before modifying owner containers, establish current original head and finalized root, review exact existing EL/BN/VC mount points, determine host/overlay routes and recoverable consistent backups. Never copy BLS signing keys, JWT or slashing data to another host, generate a new genesis or run duplicate EL/VC against owner databases.
- Plan controlled migration of only the existing owner EL/BN runtime networking while retaining the original EL+Beacon+VC persistent state. A brief signing outage may require the owner's explicit maintenance approval, slashing safety and rollback. Engine API port 8551 must remain inaccessible from outside its local trusted Docker network.
- **WITHDRAWN: no VM4706↔VM4707 native blockchain bootstrap over the cloud provider's private 10.50.56.0/24 LAN.** Both full nodes (including the original signer) must support the SAME open-join Internet-accessible network mechanism available to external operators, initially the verified controllerless ZeroTier public ad-hoc IPv6 overlay `ff2328775f000000`. VM4706's current Docker internal-only network prevents native outbound P2P; bringing it onto the common overlay must use an explicitly reviewed owner-state-preserving installation and P2P migration. ZeroTier overlay addresses alone do not prove that the underlying path avoids the same-provider private LAN: observe actual paths and require at least one genuinely external laptop-native EL+CL peer before declaring public WAN acceptance. Require real authenticated EL+CL peer handshakes and matching original-chain finalized roots; no private-LAN peer counts for G3.
- Docker published P2P port and host address behavior must be actually checked after any run. Enabling Docker IPv6 or configuring host firewalls is a privileged maintenance change, not a harmless read-only probe.

## Public onboarding requirement

The present owner-only GitHub fetches, manual SHA-pinned SCP of source, and VM password prompts are development-lab debt. Final external participant onboarding must use an authenticated PUBLIC immutable release and original PUBLIC genesis from independent mirrors, no private GitHub credentials, owner VM SSH or per-host approval. One-time local OS privilege may be needed for installation; runtime services/reconnect must need no repeated passwords. This product requirement remains a separate open implementation gate, not a result of R60.

Refs: docs/ARCHITECTURE.md; docs/R59_NATIVE_IPV6_OBSERVER_AND_AUTOMATION.md; https://docs.docker.com/engine/network/drivers/bridge/; https://docs.besu-eth.org/public-networks/reference/options; https://lighthouse-book.sigmaprime.io/advanced_networking.html.
