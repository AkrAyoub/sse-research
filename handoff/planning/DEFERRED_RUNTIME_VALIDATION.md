# Deferred runtime validation — OWNER-RUN ONLY

Nothing below was executed by the coding agent. Commands are **newly authored, awaiting validation** unless marked
"historically verified". Run on a disposable/isolated host first (e.g. the R427 test worktree pattern on VM4707:
`~/sse-r427-validation`), never against live chain state, wallets or signers unless a stage says so and the owner approves.
On any failure: stop, record exact command + full output in handoff/logs/BUGS_AND_FIXES_LOG.md, do not retry state-changing
steps blindly, hand back to a source session.

## Stage 0 — Source integrity (read-only)
DRV-00 `git -C <checkout> log --oneline -8` → expect top commits of this handback (see HAND_BACK.md); `git status` clean.
`git submodule status` → record lib/forge-std and lib/openzeppelin-contracts SHAs; compare with the R429 run (historically
verified toolchain: Forge 1.9.0, Solc 0.8.24 at `~/.local/share/sse-r19-toolchains/foundry-v1.9.0/forge`).
Acceptance: no unexpected modified files; submodule SHAs unchanged since R429.

## Stage 1 — Baseline (historically verified command shape)
DRV-01 `forge --version`; `forge build --sizes 2>&1 | tee build-sizes.txt`; `forge test -vvv 2>&1 | tee forge-all.txt`;
`python3 -m unittest discover -s tests -p 'test_*.py' 2>&1 | tee py-all.txt`.
Expected: legacy suites as before (R342e V3 36 tests, R429 10 tests pass). New V4 files may fail to compile — record exactly.
Acceptance: each failure attributed (legacy vs new); V3 results unchanged.

## Stage 2 — V4 contracts (new, awaiting validation)
DRV-V4-01 `forge test --match-contract 'SSEAdaptiveMarketV4Test|SSEMonitorRegistryV4Test|SSEStandbyCommitteeTest|SSEOrderedCommitteeSampleTest' -vvv --fuzz-runs 1024`
Expected: all pass. Fixture-sensitivity note: a few registry tests draw k of exactly k eligible entries with ≤8k attempts;
the chance a fixed seed misses is <1% per test — if such a test fails with `ok == false`, change the fixture seed and record it
(not a contract bug unless reproducible across seeds).
DRV-V4-SIZE `forge test --match-test testBytecodeSizeLimits -vvv`; `forge build --sizes | grep -E 'SSEAdaptiveMarketV4|SSEServiceBoardV4|SSEMonitorRegistryV4|SSEStandbyCommittee|SSEAdaptiveVoteLedgerV4Candidate'`
Acceptance: runtime ≤ 24576 B, initcode ≤ 49152 B, with the default profile (no `via_ir`). If "stack too deep" occurs,
record the function; do NOT enable via_ir silently — hand back.
DRV-V4-GAS `forge test --match-contract SSEAdaptiveMarketV4Test --gas-report` → record drawCommittee/activateCommittee/
startEpoch/finalizeEpoch gas for n=4,s=2; then parametrize n∈{7,10}, s∈{2,4} (add tests in next source session).
DRV-V4-PARITY Add (next session) a forge test that logs termsHash/digests for the fixture in tests/test_sse_v4_terms.py and
compare with `python3 -c` output of tools/sse_v4_terms.py. Acceptance: byte-identical.

## Stage 3 — Python (new)
DRV-PY-01 `python3 -m unittest tests.test_sse_v4_committee_planner tests.test_sse_v4_terms -v` (inside the pinned venv
`~/.venvs/sse-validator/bin/python` historically used). Acceptance: all pass.

## Stage 4 — Isolated chain rehearsal (new; disposable keys only)
DRV-V4-04 Start an isolated local node (`anvil --chain-id 31340 --block-time 2`) **on an isolated host, never pointing at the live
network**; deploy with `SSE_V4_DEPLOYER=<anvil test address> SSE_V4_PER_SEAT_BOND_WEI=1000000000000000 forge script
script/DeploySSEV4Candidate31340.s.sol --rpc-url http://127.0.0.1:8545 --broadcast --private-key <anvil test key>`.
Run the full lifecycle manually with `cast send` (request → bid → awardAndFund → wait 3 blocks → drawCommittee → 6 monitors
confirm/advance → activateCommittee → acceptLease → startEpoch …). Acceptance: events in expected order; escrowAccounting covered.
Safety: anvil chain-id 31340 collides with the real network ID — never expose its RPC, never reuse keys, wipe after.

## Stage 5 — Live chain31340 deployment (owner decision, later)
DRV-V4-05 Only after Stages 0–4 pass and owner approves the migration plan (V3 stays; V4 is a new version at new addresses):
read-only preflight of deployer balance/nonce; single run of the deploy script with a dedicated TEST-ONLY EOA; verify codehash
vs compiled artifact; publish addresses in a NEW manifest section. Never re-broadcast on uncertainty; reconcile receipts first.

## Stage 6 — Agents, UI, installer, experiments
Not yet implemented for V4 (see MASTER_TASK_CHECKLIST). When implemented, validation follows ROADMAP_AND_ACCEPTANCE B/C/D/E/F:
end-to-end lease with real compute worker, concurrent leases, restart/reorg recovery, reboot/logout persistence, fresh host
install, E7/E9/E10.

## Security
DRV-SEC-01 Secret scan of tree and history with an owner-approved scanner (e.g. `gitleaks detect --source . --log-opts=--all`).
If anything is found: do not print it; rotate; do not rewrite history unilaterally.
