# SSE integrated execution board — R0–R11 + P0–P6 (manual-only)

Source branch baseline: `research/r7-vm-role-operator-no-ci` (238 commits ahead of main and includes merged WP09Q Solidity by direct branch history) + `research/wp09m-q-local-recovery` (2 user-supplied source/evidence commits). THIS IS NOT A PRODUCTION RELEASE.

> Status codes: SOURCE, COMPILED, TESTED-OFFLINE, LIVE-TESTED, DEPLOYED, MEASURED, ACCEPTED, BLOCKED. **Source existence != test success**. Any claim without exact commit/host/receipts is provisional. No GitHub Actions.

## Critical-path work packages

| ID | R/P tracks | Priority | Current state | Deliverable and hard exit evidence |
|---|---|---|---|---|
| M0-W1 | R0/R3 | P0 | **ACCEPTED: Windows local gate for 5475bc7**; Ubuntu remains pending | 842 Python tests, 20 Windows skips, 144/144 Foundry, 10/10 WP09Q; R9_ACCEPTANCE_NEXT_STEPS_2026-11-18.md records results and EIP170 measurements |
| M0-W2 | R2/R3 | P0 | SOURCE | Payment/VRF fees, refunds, selected bonds, timeout and adversarial replay invariants on real EVM |
| M0-W3 | R2/R9 | P0 | LIVE Anvil receipt checked | Original chain 31337 block26 conserved; inspect lease1 status, escrow, bonds, deadlines/expiry before transaction; no reset |
| M0-W4 | R0/R5/R6 | P0 | SOURCE | Repository PRs #8–#17 audited, old source research preserved, no GitHub Actions, safe reviewed baseline |
| M1-W1 | R1/P1/P2/P3 | P0 | RESEARCH SOURCE | Formal success/failure/nonresponse/inconclusive evidence semantics and independent negative tests |
| M1-W2 | R2/R3/P2 | P0 | SOURCE | True VRF coordinator or explicitly permissioned alternative with economic limits; Sybil, randomness withholding, churn, fee and liveness analysis |
| M2-W1 | R6/R9/P4 | P0 | **SOURCE PREPARED / NO LIVE VALIDATORS** | Per-VM local secp256k1 key ceremony, public 4-record assembly, chain31338 genesis SHA gate, compose canary and 4-way RPC measurements; verify on distinct Ubuntu hosts |
| M2-W2 | R6/R9 | P0 | SOURCE | HTTPS broker + one-use token + approved Tailscale, external WAN host, signed peer catalog & readdress acceptance |
| M2-W3 | R9/R10 | P0 | NOT TESTED LIVE | 1/2 validator failure, full restart, heads/rewards/times and no hidden single-host dependency |
| M3-W1 | R4/R5/R7 | P0 | SOURCE | Provider/consumer/monitor each own key/VM and complete signed remote compute/HTTP lease |
| M3-W2 | R6/R8 | P1 | SOURCE | External host joins, role identity and funded monitoring registration, read-only explorer; no central signing |
| M3-W3 | R7/R1 | P1 | SOURCE | Storage/OCI/API/HTTP/compute probes and digest-bound evidence, differentiated timeouts |
| M4-W1 | R9/R10/P4 | P0 | PLANNED | Pre-registered 5/12s, 15/30/60M, loads, churn, 0/1/2 validator outages; raw data/seed/repetitions |
| M4-W2 | R9/R10/P4 | P1 | PLANNED | Ethereum PoS comparator with actual rewards and attestations where resource budget permits |
| M4-W3 | R10/P0/P2/P4 | P1 | PLANNED | statistical baseline comparison, p50/p95/p99, confidence intervals and measured rather than theoretical TPS |
| M5-W1 | R10/P0–P5 | P0 | PLANNED | Literature, threat model, theorem limitations, formal protocol, scientific manuscript |
| M5-W2 | R11/P6 | P0 | PLANNED | Approved version, public signed artifacts, reproduction script and independent outside-host validation |

## Known regressions that the next SHA must avoid

1. User's `research/wp09m-q-local-recovery` has a WP09Q Foundry test but **not** the WP09Q `OpenMonitorCommittee` implementation. Main-based build fails at `enableGlobalBatchedRecovery()`. This integration branch intentionally retains R7's patched WP09Q source and test. No second `apply_wp09q.py`.
2. Previous R7 Ubuntu controller had wrong/missing checkout source and reported **0 tests run**. Always verify `git rev-parse HEAD`, actual checkout path, test discovery count and exact paths.
3. Foundry may be on Git Bash PATH but not PowerShell PATH on Windows; use whichever environment reports `forge --version`. Never infer that a command succeeding in one shell is available in the other.
4. Missing Foundry path on VM caused gas funding not to execute; ordinary Ubuntu participant agents should not require Foundry. Only chain operator/compiler nodes need it.
5. Old private-lab DHCP IP changed; a VM hostname was duplicated; the lost monitor key cannot be reconstructed; no trust-on-first-use SSH, no blind `known_hosts` deletion, no copied wallet keys.
6. A successful Tailscale overlay/role heartbeat is not an on-chain monitor registration, signed observation, authenticated service delivery or validator consensus proof.
7. WP09D research RSA test key is **public and insecure**, blockhash entropy can be biased, and mock Chainlink VRF v2.5 is not production randomness. Bound selection fairness claims to assumptions.
8. WP09Q forty-index recovery still has relayer withholding, churn and capped success probabilities; it can expire even if eligible monitors exist beyond the draw. Check proactive no-show replacement and bond unlock.
9. Full VM network must **not** use the four-container one-host R10 smoke configuration as its final topology; 4 independent validator hosts required for R9 fault experiments.
10. `research/r7-vm-role-operator-no-ci` contains old GitHub workflow files. This integration branch removes them **only from its own tree**; repository settings should independently disable Actions before any PR or merge.

## Current manual test plan (after checking out THIS commit)

```bash
python -m unittest discover -s tests -p 'test_sse_mesh_broker_http.py' -v
python -m unittest discover -s tests -p 'test_sse_network_peers.py' -v
python -m unittest discover -s tests -p 'test_sse_peer_refresh.py' -v
python -m unittest discover -s tests -p 'test_sse_qbft_readiness.py' -v
python -m unittest discover -s tests -p 'test_sse_signed_release_install.py' -v
python -m unittest discover -s tests -v
forge build
forge test --match-path 'foundry/test/WP09QBatchedGlobalRecovery.t.sol' -vv
forge test -vv
```

Attach logs with Git SHA/OS/Python/Forge/Solc versions and label real EVM execution separately from Python models. A failing test is a BLOCKED gate, not permission to deploy. The R0 historical acceptance remains valid for its original SHA, not automatically for an integrated branch.

## Do not deploy on the preserved Anvil

- VM4695 10.50.56.14 hosts chain31337 at block26; SSH ED25519 fingerprint originally pinned; successful Provider accept receipt and block0/26 must be retained.
- Pending lease1 economic obligations require a separate read-only state/receipt audit before any expiry, refund, replay or withdrawal.
- All *new* consensus keys/blocks use distinct chain31338 and new host data folders. No transaction is sent by new enrollment/readiness programs.

## Scientific boundaries

The phase percentages in `docs/research/PHASES_TRACKER.csv` are **historical planning estimates** and are not revised by source commits. Record measured outcomes and update only with actual, independently reviewable evidence. Build/crypto-soundness, independence, throughput, physical SLA truth, and third-party permissionless onboarding are different claims.

## 2026-11-18 — GitHub-to-new-VM repeatable release gate

VM4704 (new Ubuntu24.04.4, SSH-deploy-key checkout) passed **50/50**
Ubuntu-only security tests, no skips, at
`0f070f6f676336be3decc02a41dd2361cb81100e`.
The same SHA passed 856 Python tests (20 Windows skips) and 144 Foundry
tests locally. This is **not** a four-validator network or remote
participation acceptance. The host has Tailscale installed but
**NeedsLogin**, Docker daemon running but socket access restricted to sudo,
2 vCPU/3.8 GiB RAM, and a reused private-lab 10.50.56.20 IP.

The next GitHub source package adds repeatable first-host Ubuntu gates,
read-only doctor, explicit local Besu key creation after Tailscale
authorization, and an exact-SHA stopped-node source updater with test/rollback.
No deployment to VM4704 is assumed from committing code: host must
explicitly fetch the approved new SHA and rerun its tests. The source updater
is not a consensus rolling upgrade and is not permitted on the old Anvil
host. See `docs/research/R9_VM_SOURCE_ROLLOUT_AND_FIRSTHOST.md`.

## 2026-11-18 — headless validator admission implementation

After Windows **869/869 Python tests successful (20 skipped)** and **144/144
Foundry tests**, Ubuntu VM4704 passed **50/50 security checks** and
39 isolated QBFT Python checks, then manually authenticated Tailscale
as `sse-validator-1`, overlay `100.65.29.101`. The personal tailnet
still needs policy review; it is NOT accepted as isolated production.
No Besu validator key or genesis block was deployed by those steps.

The next source package adds distinct one-use validator invitation
SQLite/OAuth service, an HTTPS headless join client, a root-only
source-staged VM firstboot wrapper, a dedicated-tailnet least-privilege
policy example and offline security tests. It expressly rejects
re-authentication of VM4704, grants no QBFT vote, and does not
expose the Python pilot publicly. See
`docs/research/R9_AUTOMATED_MESH_ONBOARDING_V1.md` for outstanding
automatic *source publishing*, key-bound invitation, server hardening,
cloud-init secret delivery and live independent-host acceptance.

## ADR-007 — role admission and transport correction

On 2026-11-18 the operator identified a conceptual flaw: network join
was incorrectly coupled to Tailscale owner approval, and the fixed
`validator-1..4` bootstrap roles were presented as general permissionless
enrollment. **This must not be claimed as achieved in a QBFT lab.**
New read-only source now supports externally signed multi-role requests
including validator/full_node, independent transport choices (native P2P
or relay even with another Tailscale account active), current QBFT set
membership checks, and monitor bond checks without claiming lease votes.
The complete network remains NOT permissionless in its QBFT consensus
layer; a genuine PoS/PoW alternative requires separate protocol selection,
economics, testing and comparison. See ADR-007 and manual new SHA gate.

## 2026-11-18 — ADR-007 validation regression (operator logs)

VM4704 checked out exact `73d5817fb10d76a619f0a0b57bccbe6dbcb69d66`, and its
**50 Ubuntu security tests passed without any skips**. Tailscale stayed online,
device IP 100.65.29.101. Doctor correctly reported
`DOCKER_SOCKET_REQUIRES_REVIEWED_OPERATOR_ACCESS` and
`readyForContainerCanary=false`; nothing started on the chain.

The same ADR-007 commit was **NOT accepted on Windows**. Three new suites
passed, but the open-role test for an empty list failed because the test
fixture treated `[]` as a request for default roles; the QBFT authority
suite had four errors caused by an undefined `SECP256K1_P` modulus.
The manual gate halted at this failed Python test, BEFORE its Solidity stage.
A corrective GitHub commit adds the real secp256k1 field modulus and
explicit empty-role fixture semantics, plus a known elliptic-curve generator
regression. No code was pushed to a live VM. Re-run all new targeted suites
and the complete manual Windows gate before accepting the corrective SHA.

## 2026-11-18 — R10 scientific falsification and real Besu canary bundle

Operator-supplied logs at source SHA
`2bc993b2d05a08b831669a3b735a73a40959c78c`: **910 Python
tests on Windows (890 run, 20 platform-skipped), 144/144 Foundry,
50/50 Ubuntu security tests (no skips)**. Existing real Anvil 31337
and VM4704 Tailscale were not modified by the R10 source work.
No real Besu genesis/canary/consensus deployment has been observed yet.
The new R10 source package includes a reproducible, hash-indexed
synthetic observation-conditional settlement experiment, strict local
EVM/Ubuntu paper-evidence extraction, and an **explicitly apply-gated**
VM4704 disposable real Besu client canary; it checks P2P-disabled RPC
block0 and records a Docker registry digest before cleanup.

Besu security required >=26.11.1 for the *new* research release due
to upstream Shanghai/QBFT unauthorized withdrawals
GHSA-p4h2-gvh4-pv6j (26.8.1 fixed) and the later 26.11.1 JVM
CVE-2026-114938 mitigation. Neither patch is proof that the
experimental client has no other vulnerabilities.

**Status: SOURCE ONLY until Windows full gate on new SHA and VM4704
real Docker canary logs.** Full multi-VM SLA/permissionless admission
and a publication novelty claim remain separate, unverified gates.
See `docs/research/R10_PUBLICATION_CAMPAIGN_AND_LIVE_CANARY.md`.

## 2026-11-18 — VM4704 first real Besu canary failure (root cause)

This is genuine runtime evidence, not a simulated failure. The
VM4704 `sse-r9-canary-01/docker.log` reported
`java.lang.UnsatisfiedLinkError ... /tmp/jna*.tmp ... failed to map
segment from shared object`, preceded by Netty `/tmp/...so cannot be
executed; check noexec`. Besu initialized enough to read CLI and set
HTTP RPC127.0.0.1:18559, then died. `docker ps -a` confirmed the
canary was removed; no real block0 was observed and no validator was
deployed. New source sets **exec only on the ephemeral P2P-disabled
canary /tmp tmpfs** while retaining no-new-privileges, cap-drop and
read-only root; a real production validator needs a more restrictive
executable-library extraction strategy. The fix also corrects the
Wilson CI boundary and the 26.10.1 test expectation. New SHA full
gate + new run directory required. Preserve original failure logs.


## 2026-11-18 — R11: four is an EXPERIMENTAL QBFT number only

Operator confirmed Besu26.11.1 real synthetic canary on VM4704
with observed real RPC genesis hash (synthetic validator addresses)
and no remaining Docker container. Windows gate was green with
927 Python tests / 20 Windows platform skips and 144/144 Foundry
on caa88863901afc0a3f12871c4c8b666b1087dadb.
The CANARY HASH is not the final real-validator genesis hash.
R11 GitHub source patches actual lab Compose to accept signed enode
URLs rather than a filename and executable tmpfs for Besu native
libraries. Added four-PUBLIC-validator real-genesis canary and
signed-peer host environment generator. These tools never copy node
private keys or grant open validator consensus. The four genesis
validator QBFT network is permissioned; genuinely open validator
membership must run on a rule-based permissionless consensus engine,
for example a public Ethereum PoS research/testnet deployment.
New code has NOT passed its new full manual gate or run on VMs yet.
See docs/research/R11_OPEN_VALIDATOR_POLICY_AND_REAL_GENESIS.md.

## 2026-11-18 — R12 decisive architectural change: SSE OWNS a PoS blockchain (zero real ETH)

The operator REJECTED using public Ethereum testnets and REJECTED
permissioned QBFT validator admission. Chain31338 QBFT is now a
HISTORICAL CONTROL BASELINE, NOT the requested SSE launch.
An independently owned Ethereum PoS research devnet (chain31339) will
mint *test ETH* in its genesis, initialize an EL/CL/validator stack,
and admit later validators under the underlying Ethereum Beacon
deposit/activation protocol rather than administrator votes.
The genesis operator's 64 provisional validator keys are NOT evidence
of decentralized ownership; free testETH yields no real Sybil-resistant
economic security. External P2P, public non-discretionary faucet,
independent validator deposits and physical service experiments
must still be implemented and demonstrated before claiming open
operational participation.

New GitHub source: sse_pos_devnet_plan, sse_pos_test_wallet,
sse_pos_devnet_health, sse_pos_contract_attest,
scripts/sse_pos_launch.sh, script/DeploySSEPos.s.sol and
targeted tests. Upstream ethPandaOps ethereum-package source is
pinned to d3014d6d23d683362025b9e23a0d69de49e77cca. No code
was run on the user's VMs, no Ethereum mainnet ETH was spent and
no live chain31339 or contracts have been measured yet.
See docs/research/R12_OWN_ETHEREUM_POS_NO_REAL_ETH.md.

## 2026-11-19 — VM4705 fresh SSE-PoS R13 single-client bootstrap

VM4704 is DESTROYED by user decision; ALL prior faucet, genesis
validator mnemonic, validator key and Tailscale enrollment are abandoned,
with no recovery. VM4705 fresh Ubuntu24.04.4: four vCPU, 11GiB memory,
93GB free disk, Docker29.1.3 via sudo; not yet a GitHub checkout or
Kurtosis host. SSH host ED25519 fingerprint:

SHA256:kCbjaZ49EwtsyJ2QgYTt3XjuZqrkju/R+tHIyn0zz/4

Private repo requires a NEW read-only deploy key with GitHub settings
owner action. R13 GitHub source reduces initial bootstrap from two
EL/CL/VC stacks to one triple, with 32 provisional genesis BLS validator
keys, no Dora explorer and no public P2P. Underlying Ethereum-PoS
consensus remains dynamic and rules-driven, but the one-host initial
environment is NOT decentralized, not permissionless network-reachable
and not an economic Sybil resistance experiment. Reviewed upstream
package d3014d6d requires Fulu AND all five BPO forks be deferred
for this small smoke profile. New sse_pos_launch_preflight verifies
source Git SHA, private config SHA256, no default mnemonic, no public
exposure and correct BPO epochs; launcher refuses other configs.
No new chain launched and no new keys generated at GitHub commit.
See docs/research/R13_VM4705_SMALL_POS_BOOTSTRAP.md.
