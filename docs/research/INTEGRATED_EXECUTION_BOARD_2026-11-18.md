# SSE integrated execution board — R0–R11 + P0–P6 (manual-only)

Source branch baseline: `research/r7-vm-role-operator-no-ci` (238 commits ahead of main and includes merged WP09Q Solidity by direct branch history) + `research/wp09m-q-local-recovery` (2 user-supplied source/evidence commits). THIS IS NOT A PRODUCTION RELEASE.

> Status codes: SOURCE, COMPILED, TESTED-OFFLINE, LIVE-TESTED, DEPLOYED, MEASURED, ACCEPTED, BLOCKED. **Source existence != test success**. Any claim without exact commit/host/receipts is provisional. No GitHub Actions.

## Critical-path work packages

| ID | R/P tracks | Priority | Current state | Deliverable and hard exit evidence |
|---|---|---|---|---|
| M0-W1 | R0/R3 | P0 | **ACCEPTED: Windows local gate for 6587566 only**; Ubuntu remains pending | 825 Python tests, 18 Windows skips, 144/144 Foundry, 10/10 WP09Q; report and EIP170 measurements in VALIDATION_WINDOWS_GREEN_2026-11-18.md |
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
