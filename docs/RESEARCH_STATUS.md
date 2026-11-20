# Verified state and gaps — 2026-11-19

## Current verified checkpoint — 2026-11-20 (after previous R19 results)

- **VM4706 is a development/test VM, NOT a launched chain31340 node.** Last observed R24 pinned Git SHA `298518e51eeaf59477a92450fbec48bb8980eccd`: **31/31** adaptive funded-monitor Solidity tests PASS, **196/196** full Forge Solidity tests PASS across 22 suites, `forge build --sizes` shows R24 V2 runtime **10,675 bytes**. These are local EVM fixtures with simulated balances, NOT native PoS deployment or independently measured service.
- **G0 COMPLETE: Step31 Python source tests** actually passed at immutable VM4706 source `f1ddae763735fe365e49e7286ae83e5fb689ed3a`: **13/13** genesis builder preflight, **9/9** owner-private EIP2335 public-only metadata exporter, and **16/16** genesis contribution checks; **38/38 PASS**, zero errors, final completion marker observed. Expected negative file overwrite and unconfigured-build refusals were successful checks. These are source/security tests with **synthetic fixture keys**, NOT creation of any live BLS validator/SSZ/chain31340. Previous Step30 12/13 incorrect-test-exception result is resolved by this G0 rerun.
- **G1 PARTIAL REAL KEY CUSTODY VERIFIED:** On VM4706 at detached `ce31a21a13f68190c1f9478d67446e856694a21c`, the existing Cast encrypted TEST-only owner EOA was **successfully unlocked through a hidden keystore-password prompt by checksum-pinned Cast**, and the derived PUBLIC address matched `0x13fb73aace8A11Be2899D047635A757a224Ce00B`. Owner-private encrypted key was preserved, no secret output. Actual JSON field-name probe confirmed expected `crypto,id,version` with no embedded address; original R20 false rejection now understood/resolved. **DO NOT recreate wallet**; offline backup still the owner's responsibility. Updated Lighthouse v8.3.3 `--wallets-dir` offline CLI check **PASSED on VM** (`R27_PINNED_LIGHTHOUSE_OFFLINE_HD_WALLET_CLI_VERIFIED=true`). At separate HD-wallet creation prompt the owner entered an unrelated string rather than `CREATE-BLS-HD-WALLET`; script correctly **REFUSED without creating mnemonic/HD wallet/BLS signing validator**. Consent is absent, do not rerun automatically. Step33 wallet-report tests **10/10 PASS**, field-name probe tests **5/6 PASS, 1 incorrect test message expectation FAIL**; source-only assertion corrected R29, not yet VM-tested. Under set -e skipped recovery script 6-test and Lighthouse 8-test static suites. **No EL/CL chain31340 Genesis or SSZ, native TEST ETH/finality, P2P, VM↔laptop, or deployed roles exist.** Pinned Besu/Lighthouse/generator remain verified.
- **G1 source gate progress Step36 (ACTUALLY OBSERVED):** VM4706 at immutable SHA `47eeeb2785494b9ef56765c2884120f68e30cdd8` passed **6/6** safe encrypted Cast schema tests + **6/6** existing wallet recovery guards + **8/8** corrected Lighthouse wallet guards + **16/16** genesis builder safety checks = **36/36 Python tests** plus two `bash -n` checks; final Step36 marker observed. No new keys, wallets, chain or containers started. The owner-controlled BLS-wallet operation remains deliberately **REFUSED** at separate human confirmation. **R30 GitHub-only source AFTER Step36** adds explicit EL Shanghai/Cancun/Prague/Osaka ordering and CL Altair/Bellatrix/Capella/Deneb/Electra/Fulu fork epochs/version uniqueness, plus 3 NEW parser tests (builder suite now 19); **not yet VM tested**. These checks do NOT certify complete cross-layer fork parity or real deposit runtime.
- **G1 REAL owner-encrypted Lighthouse parent wallet now CREATED (new actual operator result):** At immutable SHA `891d49029968b4220d03974c5a5624027c8d023f`, VM4706 operator explicitly typed `CREATE-BLS-HD-WALLET` in private R27 script, which returned `R27_ENCRYPTED_HD_WALLET_CREATED_ON_OWNER_VM=true`, `R27_BIP39_MNEMONIC_WAS_NEVER_PRINTED=true`. Owner-local encrypted EIP-2386 HD wallet, 0600 random password file and 0600 recovery mnemonic file genuinely exist. No OFFLINE backup has been confirmed by the owner yet; user must back up before deriving staking keys. This newer SUCCESS supersedes older repeated refused attempts documented above; the old attempts remain historical facts. **No BLS validator voting keys are derived yet, no Genesis SSZ, Beacon duties or chain31340.** R32 GITHUB-ONLY script now allows creating actual owner-encrypted EIP-2335 voting keystores from that same parent wallet with separate `BACKUP-CONFIRMED` and `DERIVE-BLS-VALIDATORS` approvals; eight new static tests are source-only and NOT VM-tested. [R32 owner ceremony](R32_EXISTING_HD_VALIDATOR_DERIVATION.md), Journal Entries050–051.
- **R30 genesis fork tests ACTUALLY PASS (Step37):** VM4706 at detached `d3049cf1d1dd8178ea168d6e60f963bea2f1562a` executed `test_sse_pos_genesis_build.py` **19/19 PASS** and completion marker. This validates input schemas and ordering ONLY, not real/working deposit contract or EL/CL fork parity. Do not use the deliberate REVERT-stub test fixture as an authentic deposit runtime.
- **Role source, NOT live role deployments:** marketplace request/bid/fund/provider accept/monitor registration CLI and local provider/monitor agents exist as code; parts of legacy live-role scripts are **hardcoded for abandoned chain31339**. New `SSEAdaptiveVoteLedger` has 31 passing EVM tests for per-lease variable k/q, signed votes and real-contract escrow accounting (EVM fixture balances), but **not integrated** with honest permissionless election or V2 SSE service settlement. V1 still hardcodes 4 seats/3 votes; world-soundness counterexamples CE01–CE04 remain open.
- **Next real multi-VM work starts after first honest chain31340 native blocks and finality on VM4706, NOT after all contract/dashboards are done.** Second available VM is an actual EL+CL peer first, no validator keys or funds required; user's sole external laptop joins as first non-VM peer after real reachable P2P proof. Do not fabricate independent operators and do not impose fixed counts for any role. Exact acceptance gates and optional machines: [R26 execution roadmap](R26_EXECUTION_ROADMAP_AND_HOST_ROLES.md).
- Historical VM4705 DID operate real (but compromised-for-public-use) chain31339 with signed blocks/finality and SSE deployed; it cannot be repurposed for 31340 without clean independent genesis and key custody. R26 preserves separate experimental results rather than conflating VMs.

**Public network acceptance: NOT MET.**
The architectural target is defined in [ARCHITECTURE.md](ARCHITECTURE.md).
Do NOT confuse private single-host smoke data with a permissionless,
Internet-public deployment. Research claims require actual observations.

| Observation | Evidence and exact scope |
|---|---|
| Private PoS smoke VM | **Historical isolated chain31339** on VM4705, 4vCPU/11GiB, Besu EL+Lighthouse CL/VC, all operated on ONE host; **not public and not suitable for public reuse** |
| Consensus | Execution blocks increased to at least 1157; Beacon finalized checkpoint previously observed |
| Deployed source | SSE Solidity R16 commit `cd2fe67e3031d4f25c41bfc714c6539b7ca1ebef` |
| Committee | `0x9965bAC16C5Df538df0373a906e42eA0E0C327d9` |
| Settlement | `0x879878f7561F5a0a1f6dd22348FfdE81cD5fEe7F` |
| Board | `0xF1147CA8aC9e28F845529A6Ae5837873806C7788` |
| Deployment receipts | Seven canonical successful tx in blocks 953–959, 10,947,092 total gas; **finalized by execution block 1088**, verified by VM4705 R18 tool |
| Python tests | **51/51** targeted `test_sse_pos_*.py` passed at Git SHA `f846e770744fb18f3364801781d9075498eacc6b` |
| Foundry tests (historical) | **147/147** EVM Solidity tests passed at R16 on earlier historical source; superseded for current R19 validation by the separate VM4706 run below |
| Faucet | 1M genesis-allocated TEST ETH; no real ETH |
| User wallets | Faucet, consumer, provider and monitor01–05: eight encrypted local keystores on VM4705 |
| Local role funding | Attempt failed BEFORE broadcast in R18 due to EIP-55 checksum; R18b fix passed 51/51 Python tests, not yet retried live |
| Monitor bonds | **ZERO active registered candidates** in latest user-observed read-only plan |
| SSE real workload | **No real cross-host consumer/provider/monitor SLA execution witnessed** |
| Public PoS P2P | **No independent remote P2P peer or dynamically readdressing seed witnessed** |
| Public validator joining | **No new BLS deposit/activation from an independent host witnessed** |
| Genesis key security | First upstream PoS launch printed genesis consensus mnemonic and premine private keys. **Compromised for any Internet-public use.** |

**Chain identity and custody:** The preceding VM4705 chain was **31339** (historical, one-operator, leaked genesis mnemonic/private key material). It must never be published or repurposed as the independent public network. **31340** is a *proposed new chain ID*, not an already validated or deployed network; its genesis, independently generated validator identities, and Internet P2P remain outstanding. These chain IDs are not real Ethereum Mainnet and contain only worthless TEST ETH.

**Important distinction:** The successful ledger is genuine PoS and
the three SSE contracts genuinely exist there. But 32 genesis
validator BLS identities under one operator, and seven application
EOAs under one VM, do not represent independent operators. A quorum
of four SSE monitors on one VM is also not physical independence.

**New public system:** None of the entries above establishes the
fresh multi-operator public chain31340, public reachable P2P, or
permissionless external validator entry. It has to be launched with
independently created **non-exposed** genesis keys. No legacy
QBFT/Tailscale gate is acceptable as a substitute.

## R19 fresh-host source validation on VM4706 (latest observed)

**Verified from the operator's actual terminal outputs on 2026-11-19; NOT a deployed Internet-public network:**

| Check | Observed result and immutable revision |
|---|---|
| Fresh-host/architecture/public-manifest Python suites | **31/31 PASS** at `5fa84572f83bb58c0cddf97d59a5e381df8bc414`; exact checks 13 + 5 + 13 |
| Foundry v1.9.0 provenance | Official Linux amd64 release SHA-256 `8d17599b42e3139f1a9c171be3798c4ed8e743ae17b84cc3435e57bf2a51ae99` verified and installed on VM4706 |
| Solidity compile | **60 files compiled using solc 0.8.24** at Git SHA `c4acd52379710bec399e5af90ace3c9c31aa4a8c`; significant static warnings remain to audit |
| Faucet source EVM tests | **12/12 PASS**, included inside full EVM suite; test-only transfers, NOT live test-ETH distribution |
| Full EVM Solidity suite | **20 suites, 155/155 PASS, 0 failed/skipped** at `c4acd52379710bec399e5af90ace3c9c31aa4a8c` |
| Docker daemon and native client executable checks | Docker server 29.1.3 with cgroup v2; Besu **26.11.1** by digest `4fd2ba40f0d65917bcb3abd9af60673946f66dee2ecb1b87f7cdfa6a30fe458d` and Lighthouse **v8.3.3** by digest `53f9063d98c3d3a2d290207873f019ea2298cfc02f8cd58d87c33b04aab856d1`; version-only isolated runs at `2908450be6e3360d58ea35d64f7a72bcfa4f5f43`; **no native P2P** |
| Client diagnostics | Previously nonfatal Besu Log4j `UnknownHostException` **resolved by actual VM4706 offline by-digest retest** at `ef495d358462437a155e7689d7ea96f678303d77`; 7/7 image pin tests PASS |

**Critical blockers:** proposed new chain31340 execution/Beacon genesis is not built; independent owner-generated BLS/EOA keys and 32 worthless-test-ETH deposits are not activated; no unrelated remote EL/CL P2P clients joined; no production faucet, consumer escrow, bonded independent monitors, verified resource delivery or per-node public HTTPS UI; no final no-central-authority and entropy-security audit. Historical chain31339 remains unsuitable for public use. Repository is still private and the developer deploy key must never become public-network admission.

**More recent VM4706 milestones:** official Beacon genesis generator v0.0.8 installed with verified archive SHA-256 and actual binary SHA-256; **14/14** genesis contribution tests passed and checksum-verified existing tool reuse succeeded at `2eec47e0619c8b2fd0a28991fe33ac218f5ab2b0`. The later owner-wallet source suite at `a7955a2afbf7eb57f67d142bdb6069a88271dae1` ran **6 tests: 5 PASS, 1 FAIL**, caused by a false-positive test assertion matching the harmless `"privateKeyPrinted": false` status; source-only test corrected, **not yet VM rerun**. Because `set -e` stopped the command, **NO new operator wallet was generated**.

**Critical adaptive-role blocker (user reaffirmed 2026-11-19):** public network may not impose a fixed number of nodes in **ANY role**. Current `OpenMonitorCommittee.sol` and `SSESettlement.sol` still hardcode four monitors and 3/4 quorum, including selection/confirmation/escrow ABI. They are **NOT production-adaptive**. The new `AdaptiveMonitorQuorum.sol` and ten Foundry test methods are **source-only mathematical preparation** not yet integrated or VM-tested; actual variable committee/threshold contract migration, independent SLA samples and fault-domain checks are required (#38). Per-genesis security minimums are now explicit configurable inputs, not permanent network role-count defaults. See [R21 adaptive requirements](R21_ADAPTIVE_ROLES_AND_QUORUM.md).

**Testing accounting:** 31 Python and 155 Solidity tests passed in **separate runs on separate immutable Git source revisions**; do not claim a single complete 186-test run at one SHA or conflate Foundry test doubles with a public blockchain.

The full exact command/commit/failure ledger is [VM4706 experiment journal](experiments/VM4706_2026-11-19.md).

## Repository hygiene

The former `main` at `7e86edb9aff6a2e45eac940cf7ced3b2c88f2bea`
was 264 commits behind the R18b working integration branch and
incorrectly presented Anvil as the current runtime. The cleanup
work is reviewed on `refactor/permissionless-public-pos-mainline`
with a PR to `main`. Before merge, run Python/Foundry tests on a
clean checkout and review retained executable dependencies.
The snapshot branch
`archive/legacy-pre-public-pos-2026-11-19`
preserves the full previous integration tree for historic grading,
research reproducibility and potential migration.

CI/test status and current architecture MUST be refreshed from the
exact new GitHub commit: no static audit document or passing mock
unit test can prove live public Internet behavior.
