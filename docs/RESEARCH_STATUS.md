# R251 — Real chain31340 read-only preflight PASSED; next application wallet/deployment gate

Actual VM4707 RPC read-only R201 output on 2026-11-24:
**chain ID 31340 and original execution genesis verified**;
latest execution block **24840**, finalized execution block
**24692** (hash
`0xd00e0982d035f2c64fa7edcc7a01cfb4e9abf8ec1dce0c8b7667a16a4ccd0b44`),
block gas limit **30,000,000**, latest basefee **7 wei/gas**,
and original public Genesis funded EOA balance at finalized
**1,000,007.92902409 TEST ETH** (nonce **0**).
**No private key custody** or app keystore verified.

Full V2 source ABI/Foundry regressions are already green at
the immutable tested `6930c069b4e9738e63e2ce9d53b10d126053335e`.
No further test loops warranted without source change.
Next: explicit authorization to create owner-only encrypted
separate app deployer EOA (not Genesis), prove a legitimate
test ETH funding signer and bounded deployment budget, then
owner-authorized actual deployment with R206 finalized manifest.
The literal `marketV2Deployed:false` R201 field is NOT an
independent on-chain deployment scan. The full live network
resource SLA and independent Internet/validator experiments
remain outstanding.

Complete evidence/steps:
`docs/R251_ACTUAL_CHAIN31340_READ_ONLY_PREFLIGHT_AND_DEPLOYMENT_HANDOFF.md`.

---

# R250 — R249 real VM4707 full V2 source+compiled-ABI regression PASS

**Newest verified owner VM4707 source SHA**
`6930c069b4e9738e63e2ce9d53b10d126053335e`:
R249 and R235 full source gate success markers, 1,278
Python tests (1,275 PASS, 3 SKIP), R247 policy suite
10/10 PASS, real Solc ABI parity 21 actions/28 protocol
events + public getter structs PASS, adaptive V2 EVM
Foundry suite 21/21 PASS and whole `forge test -q`
exit 0. Marketplace runtime 19,263B; ledger 10,668B.

**R250 next step is NO MORE full-source retesting on the
same source SHA**: collect live chain31340 **read-only R201**
status from VM4707 and then, only on explicit owner approval,
prepare separate app wallet/funding and one deployment
transaction. This is not yet an actual live marketplace,
physical SLA, native public-Internet permissionless admission
or independent BLS-validator proof. Full evidence/plan in
`docs/R250_R249_ACTUAL_FULL_VM4707_SOURCE_GATE_GREEN_AND_LIVE_CHAIN_NEXT.md`.

---

# R249 — Compiler ABI parity: inherited EIP712 event repaired, RETEST REQUIRED

Actual VM4707 at SHA `c611ed1ff64059c642e30f0fc96f66d09feb057e`
executed **9/9 passing R248 R247 checker unit tests** and
successfully executed `forge build -q`.
Against the **actual Solc-built market artifact**, the first
R247 compiled event comparison stopped at the additional
**`EIP712DomainChanged()`**, inherited from OpenZeppelin
`EIP712`. This was not an SSE application event decoder mismatch
or native chain failure. Checks of ledger and compiled output
tuples were not reached.

R249 GitHub source now accepts ONLY the exact standard
inherited zero-field non-anonymous event; retains strict
event coverage for all SSE market/ledger application events
and rejects any other unexpected, malformed or duplicate event.
New regression covers both V2 contract roles and adversarial
schemas. **R249 revised code is committed but not yet
tested against actual compiler artifacts.**

Evidence: `docs/R249_VM4707_COMPILED_EIP712_ABI_EVENT_EXCEPTION.md`.
Prior R246 complete V2 source-only regression PASS at exact
SHA `6a25aa4aa86295cdac5d86596e95e18393e08b8f`
is unchanged; source test PASS is not live deployment or
independent physical SLA proof.

---

# R248 — R247 compiler-parity checker scalar/array return fix (NOT YET RETESTED)

Actual VM4707 at exact source `6e50557d30b9d7c6835b8a5927c5a90ec18f1bd6`:
38/38 R226–R229, 43/43 R231–R239, 6/6 R242,
5/5 R201 and 6/6 R206 all PASS. Full Python
1,275 run, **1 ERROR and 3 skipped**: a newly written
R247 ABI checker wrongly classified single `address[]`
return as nested Solidity struct, raising a tuple-unpack exception.
The fail-fast gate did NOT reach compiled-ABI checking or Forge.

R248 now distinguishes flat single/multiple scalar/array outputs
from nested Solidity struct returns, with two new regression
tests. **The new fix is committed but has not yet been
executed on VM4707 or tested against actual compiled Foundry
artifacts.** See
`docs/R248_VM4707_COMPILED_ABI_SINGLE_OUTPUT_REPAIR.md`.

Prior exact `6a25aa4aa86295cdac5d86596e95e18393e08b8f`
R246 full PASS remains valid (1,268 Python OK/3 skip,
21/21 adaptive Foundry, full Forge exit0 and market 19,263B).
No V2 deployment, real application TEST ETH transfer,
validator change or independent physical SLA yet.

---

# R246/R247 — New full VM4707 source PASS; compiled ABI parity gate not yet verified

**Actual owner VM4707 result on exact immutable source
`6a25aa4aa86295cdac5d86596e95e18393e08b8f`:**
38/38 R226–R229 Python PASS, 43/43 R231–R239 Python PASS,
6/6 R242 sender-policy PASS, R201 5/5, R206 6/6,
full Python **1,268 OK (3 skipped)**, Solidity **68 files
compiled** by Solc 0.8.24, adaptive V2 **21/21 Foundry PASS**,
complete `forge test -q` returned 0, and the genuine success
marker `R235_SOURCE_ONLY_GATES_COMPLETED=true` was emitted.
New market runtime **19,263B** (5,313B EIP-170 headroom),
vote ledger **10,668B** (13,908B headroom).
The updated R236 post-accept idle/bond-release adversarial cases
are included in the 21/21 passing tests.
See `docs/R246_VM4707_COMPLETE_R235_PYTHON_SOLIDITY_REGRESSION_PASS.md`.

**New further R247 compiled-ABI gate committed AFTER that verified
SHA, not yet executed on VM4707:** `tools/sse_pos_r247_v2_compiled_abi_parity.py`
checks Solidity compiler-emitted function signatures, every
on-chain event/indexed field, and public state tuple return types
against exact R226/R227/R229 Python readers. Added to
`scripts/r235_vm4707_v2_source_only_gate.sh` and source CI;
it is NOT yet a passing result. Exact new SHA must be pinned and
tested before live V2 use.

All new tool and contract source remains a draft, unmerged and
**not deployed to native chain31340**; no app wallet,
TEST-ETH funding, live lease transactions, independent physical
SLA, external-native peer admission or second independent
BLS validator is proven by the R235 source-only tests.

---

# R245 — Latest actual VM4707 integration evidence (2026-11-24)

On real VM4707, Python 3.12 isolated venv and source
`1c75859ae777d4b39a14071b37c4fb0b0c8a3af3`:

- **R226–R229: 38/38 PASS** (new adaptive V2 market/ledger ABI,
  public EIP-712 signature tests and read-only finalized mock policies).
- **R231–R239: 42/43 PASS**, 1 real-source ERROR: strict
  `type(path) is not Path` in R237 rejected the ordinary Linux
  `PosixPath` keystore returned by `Path(...)`.
- **R245 source correction committed**: use
  `not isinstance(path, Path)` while retaining encrypted
  keystore owner/permission/symlink restrictions, regression added.
  **R245 fix has not yet been retested on VM4707.**
- **No full Python source suite, R242 sender tests, new R236 contract
  compile/Foundry tests, or EIP170 deployed runtime-size acceptance
  yet**, due to fail-fast source gate. No live V2 deployed, signed
  or funded; no physical remote SLA proven.

This paragraph supersedes the historical R243 statement below that
none of the new Python source had been tested, as those tests have
since genuinely run on the actual VM. See
`docs/R244_VM4707_R235_FIRST_REAL_REGRESSION_SELECTOR_TEST_REPAIR.md`
and
`docs/R245_VM4707_R235_SECOND_PYTHON_GATE_KEYSTORE_PATH_TYPE.md`.

---

# R243 — Active draft R226–R242 real-role integration, SOURCE-ONLY (unverified)

As of 2026-11-23, new research integration work is on
`feature/r226-adaptive-v2-operator-runtime` draft PR #43,
**stacked on** `feature/r136-independent-observer-preflight`
draft PR #41; original `main`, VM4706 signing validator,
running VM4707/VM4709 observers, chain31340 genesis and wallets
have NOT been touched.

New source implements exact V2 unsigned ABI role actions, finalized
market+ledger event/runtime/lease audits, V2-specific EIP712
public signature tools and TTY consent-gated app-only signing,
V2 real HTTP Docker compute/provider/selected monitor evidence adapters,
public-DNS resource/SLA term commitments, per-node read-only status UI,
live-node actual gas/balance quoting, plus separately authorized
owner-local ONE-TX test ETH sender. R236 contract patch prevents
post-accept inactivity from indefinitely locking selected monitor
bonds; sealed no-quorum epoch fees remain escrowed for bilateral EIP712
resolution, and late consumer reactivation is rejected.

**CRITICAL:** NONE of R226–R242 sources, the amended R236 contract
or its added adversarial cases have yet been compiled/tested on
the user's VM. No source CI run reported PASS. The earlier R223
16/16 Foundry V2 success belongs ONLY to
`9a216518b3ea8c265f5186f6113987eb537d7949`, BEFORE
the new code. All new runtime/EIP170 sizes must be remeasured.
Explicit owner approval and a separate encrypted app wallet/funding
are required before any network transaction. No new native
testETH has been sent, no V2 market/ledger deployed, and no remote
physical independent SLA measured.

**Owner return:** see
`docs/R243_ADAPTIVE_V2_FULL_RUNTIME_INTEGRATION_AND_RETURN_GATES.md`
and `scripts/r235_vm4707_v2_source_only_gate.sh` at the exact
immutable branch commit provided in the return handoff.
If tests fail, correct through GitHub, not by patching a VM.

---

# R225 — New real two-node finalized checkpoint match, formal timing qualification

On 2026-11-23 the real VM4709 separately installed Besu+Lighthouse
observer reported the **same original chain31340 EL and CL genesis**
and **exact matching finalized Beacon epoch602/root**
`0x9d140067a9049103fc482221713f2f0c46cf7d0a89593bef4d6e19fb0dddecd7`
as VM4707. Both nodes independently reported 2 native EL peers and
2 native CL peers, no sync/optimism/offline flags; EL head17783 vs
17798, Beacon slot19394 vs19409. **Actual capture skew 181.223808s**
exceeded strict R141 180s compare requirement by 1.223808s. This is
**observed exact checkpoint agreement, NOT a formal same-window R141
`OBSERVED_CONSISTENT_CHECKPOINTS` result**. The earlier strict R192
epoch571 pair remains formally accepted. No live contracts, funding,
independent operators, external beyond-overlay P2P or physical SLA
were tested here. See
`docs/R225_VM4707_VM4709_FINALIZED_EPOCH602_MATCH_SKEW_RESTRICTION.md`.

---

# R224 newer actual network evidence — 2026-11-23 16:39:06 UTC

Original VM4707 **actual live two-layer R141 capture** (pinned source
`b02465bd6352bb87ae0f3109768a86aeed304141`): chain31340, correct
execution genesis **and Beacon validators genesis root**, EL head17783,
Beacon head slot19394, 2 native EL peers, 2 native CL peers, all
syncing/optimistic/offline flags false. **Finalized epoch602** with
root `0x9d140067a9049103fc482221713f2f0c46cf7d0a89593bef4d6e19fb0dddecd7`.
This is real live **VM4707-only** EL+CL health. VM4709 has NOT YET
been freshly checked at epoch602, and no contemporaneous two-host
finality match is claimed. Physical independent operators, global
Internet-native admission and V2 on-chain economics remain unverified.
Full observed report and restrictions:
`docs/R224_VM4707_LIVE_EL_CL_FINALITY_EPOCH602.md`.

---

# Current verified checkpoint — R223, 2026-11-23 (supersedes earlier 2026-11-21 source status)

On **real VM4707**, exact pinned source `9a216518b3ea8c265f5186f6113987eb537d7949`
was successfully compiled with Forge v1.9.0 / Solidity 0.8.24:
**68 Solidity sources; new adaptive V2 marketplace tests 16/16 PASS;**
full `forge test -q` returned exit 0 (full suite count not printed);
R201 mocked policy tests 5/5 PASS and R206 mocked audit policy tests
6/6 PASS. Observed operator gate ended with
`R222_SOURCE_AND_READONLY_GATES_COMPLETED=true`.
V2 runtime sizes: market 18,087 bytes; ledger 10,668 bytes.
Compiler/lint warnings remain and are **not** a security clearance.

The same VM4707 command independently queried the *original*
chain ID 31340 execution genesis and finalized EL block via localhost
JSON-RPC: EL latest **17751**, finalized **17621**, original genesis
`0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf`.
Original EOA `0x13fb73aace8A11Be2899D047635A757a224Ce00B`
at finalized state: **1,000,005.544827172 native TEST ETH, nonce 0**.
R201 did **not** read live Beacon root/peers and did **not** inspect V2
deployment addresses/code; do not construe its hardcoded
`marketV2Deployed:false` status as a chain-wide contract absence scan.

Historical real **VM4707+VM4709** cross-host EL/CL finality match
epoch571/root `0x48c1976b872c24b9fc00d8b7fd3c08e1b82a44534e3eb4034292c2621e25db63`
remains separately documented by R192. The later R223 EL-only probe
does not by itself refresh that cross-host proof.

**NOT YET VERIFIED:** current cross-VM CL finalized agreement after the
R223 time point; a new private application-only deployer EOA; funding
transactions; V2 market+ledger deployment receipts/runtime; live
provider/consumer/monitor SLA and payments; multiple independent
validator operators; outside-overlay globally permissionless admission.
No new genesis/validator, wallet import, broadcast or Docker changes
were performed by the R223 tests. Read
`docs/R223_VM4707_V2_SOURCE_GREEN_AND_LIVE_CHAIN_READONLY.md`.

---

# Verified state and gaps — updated 2026-11-21

## CURRENT chain31340 live evidence — supersedes older dated status entries below

**Live operator observations, 2026-11-21:** VM4706 runs original
Besu execution + Lighthouse Beacon and ONE original signing validator.
VM4707 runs separate real nonsigning Besu+Lighthouse peers.
On owner head slot 6549 (epoch 204) and observer head slot 6550
(epoch 204), both independently reported **previous justified epoch 201**,
**current justified epoch 202**, **finalized epoch 200**, identical
finalized root
`0x0e870e8687dd93737daf777c0a9c690a9ddc73bca03ac6b62fa44b3579a0a467`.
VM4707 Beacon `/eth/v1/node/syncing`: `is_syncing=false`,
`is_optimistic=false`, `el_offline=false`, sync distance 0.
Owner Beacon logs reported one native consensus peer, verified execution
payload hashes and advancing blocks. This is **REAL PoS FINALITY**;
historical entries stating that chain31340 has not launched are now stale.

**Limits of this milestone:** one BLS signing key/operator and two
same-cloud VMs, not multiple independent validator owners.
Dynamic Internet-wide P2P onboarding, outside-provider independent
connectivity, real third-party validator deposit/activation, authenticated
real cross-host resource leasing, monitor quorum and conservative SLA
settlement remain **NOT VERIFIED**. ZeroTier ad-hoc IPv6 is a public
controllerless overlay but still depends on ZeroTier underlay/root/relay
services; a VM overlay IP is not proof of ISP or physical independence.

**GitHub verification, 2026-11-21:** VM4707 tested R136/R137
targeted suites (6+7), corrected R54/R69 suites (11+6).
At integration revision `bb7d3db455231771a2b4eb5390aa185b77656070`
using isolated `.venv-tests`, full Python discovery ran
**920 tests, 1 failure, 0 errors, 3 skipped**. The sole failure was a
source-tree integrity conflict: obsolete `services/role-agent` existed
from a prior research restoration. New GitHub-only remediation moves
the legitimate non-signing monitor snapshot console to
`services/node-console`, updates its behavioral test and deletes
the obsolete `services/role-agent` path. **That remediation has not
yet been VM retested.**

**R140 current source-only:** finalized-chain31340 read-only marketplace
runtime/contract-binding audit tool and tests. No actual chain31340
marketplace contracts, bonds, leases or withdrawals are claimed.
The old `script/DeploySSEPos.s.sol` is explicitly chain31339;
`OpenMonitorCommittee` and `SSESettlement` still have fixed 4/3
committees. Adaptive and evidence-sound contract migration is a blocker
before the research-marketplace deployment.

Older entries below are retained as historical evidence of earlier stages
and MUST NOT be interpreted as current deployment status.

---


## Latest ACTUAL VM4706 checkpoint — 2026-11-20 Step40

- G1 actual: real pinned upstream binary successfully created 2,737,436-byte Beacon genesis.ssz (SHA256 8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82) from the one EXISTING real owner-derived BLS public validator. EL genesis SHA256 22eb6c58288113b9c3671970967151012665137b345237b5c24060dc988b1ee8 and CL config SHA256 839072fe3d4b2092b4867010ad01254145872969d89f66ecc86610700f381b13. Source R34 9/9 PASS. Exact SHA f8f36b0a9c2b696cfdd217c30f13e022831a8d6a. One real owner/physical fault domain. No active chain31340, real finality or Internet P2P verified by this step.
- R35 GitHub source only: native client exact artifact preflight, one-host Docker Besu+Beacon+existing validator client isolated startup, local read-only real health probe, seven source tests. NOT YET RUN ON VM. Do not claim signing/finality until owner reports actual results. See Entry055.

### Historical checkpoint context retained below
## Current verified checkpoint — 2026-11-20 (after previous R19 results)\n\n- **G1 Step39 ACTUAL 2026-11-20 VM4706:** owner ran SHA `447fa98292ba82b2c5966968d53fb67205a77bfb`, R33 pinned standard deposit source tests **7/7 PASS** plus R25/R30 genesis regression tests **19/19 PASS** (total 26/26); real existing R32 public-only contribution collector succeeded with EXACTLY 1 declared operator, 1 public BLS voting key, balance 32,000,000,000 Gwei and SHA256 `efc4d4d51c3acff8e8fa7238fb12428c6866c2d3d3d770f50ba6a98177a19140`. Output explicitly `blsProofOfPossessionVerified=false`, `executionGenesisVerified=false`, `consensusGenesisSszBuilt=false`, `readyToLaunch=false`. Owner-observed `== STEP 39 SOURCE AND PUBLIC CONTRIBUTION CHECKS COMPLETED ==`. **R34 new GitHub source only, NOT run on VM:** public-native EL/CL genesis input generator for this actual contribution, chain31340 TEST EOA funding and real Beacon SSZ builder preparation. Do not claim any new Genesis SSZ or live finality yet.\n

- **R33 current G1 SOURCE change after Step38 — NOT VM-tested:** The real `--build-single-operator-lab` path now requires the **standard ungated** Ethereum deposit runtime **and 31 constructor-initialized zero-hash storage entries**, from pinned upstream source commit `0b518636eec53e41e6d261f46ae07147d546a456`. Nonfunctional REVERT test fixture and arbitrary code do NOT pass the real-build preflight. Seven new tests in `tests/test_sse_pos_deposit_predeploy.py` and unchanged 19 genesis parser regression methods require **actual owner VM execution**; no passing result yet. No EL/CL artifacts built or tested by clients, and cross-layer forks / live deposit activation remain unverified. See `docs/R33_G1_REAL_DEPOSIT_PREDEPLOY.md`, Journal Entry053.
- **LATEST ACTUAL CHECKPOINT — VM4706 Step38 R32 REAL voting key derived, 2026-11-20:** At detached immutable `cc393edf498a7d552b7c9559c790e3dca0b55ee4`, source-only R32 derivation guards **8/8 PASS** plus shell syntax check. After independently entering `BACKUP-CONFIRMED` and `DERIVE-BLS-VALIDATORS`, the owner actually invoked the pinned offline Lighthouse v8.3.3 CLI against the **existing** EIP-2386 encrypted wallet to derive **one genuine EIP-2335 encrypted BLS validator voting keystore**. Real script reported `R32_REAL_OWNER_BLS_VOTING_KEYSTORES_CREATED=true`, `R32_BLS_VOTING_KEY_COUNT=1`, `R32_PRIVATE_SLASHING_PROTECTION_RETAINED=true`, `R32_PUBLIC_GENESIS_CONTRIBUTION_CREATED=true` and `R32_RECOVERY_BACKUP_ATTESTED_BY_OWNER=true`. Separate existing TEST-only withdrawal EOA is `0x13fb73aace8A11Be2899D047635A757a224Ce00B`. Backup is **human-attested**, not checked by source; exactly **ONE real operator fault domain**, not multioperator participation. **NEVER rerun R20/R27/R32 creators**. This actual event supersedes historical paragraphs below stating BLS keys absent/R32 unexecuted; retain those as historical snapshots only. **Still false/unverified:** BLS public subgroup/PoP, EL/CL chain31340 genesis and SSZ, actual PoS blocks/finality, native Internet P2P, independent peers, economic roles and real SLA/payout. The current genesis builder only checks EL deposit predeploy code **shape**, not functional contract bytecode or constructor-initialized deposit Merkle storage; generator/client interoperability and fork parity require real proof before launch. See journal Entry052.
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
