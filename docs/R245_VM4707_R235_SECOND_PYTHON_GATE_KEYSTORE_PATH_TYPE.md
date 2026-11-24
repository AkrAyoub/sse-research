# R245 — Actual VM4707 R235 two-batch Python evidence and Linux keystore type correction

## Observed operator log, 2026-11-24

Exact pinned GitHub source:
`1c75859ae777d4b39a14071b37c4fb0b0c8a3af3`.
Original VM4707 user checkout:
`/tmp/tmp.Ridv9nIavf/repo` (isolated Python virtualenv:
`/tmp/tmp.Ridv9nIavf/testvenv`), real local Foundry v1.9.0.

- **R226–R229: 38/38 PASS**, including the corrected distinct
  market/ledger `withdraw()` four-byte selector assertion; V2 ABI
  payload, EIP-712 public signature tests, mocked finalized event
  decoding and mocked finalized lease state tests.
- **R231–R239: 42/43 PASS; 1 ERROR**, at
  `test_keystore_requires_nonroot_private_directory_and_encryption`.
  Actual exception: `Refused("encrypted app keystore must be absolute, owner-local and non-symlink")`
  from `safe_keystore(path)` for a normal locally created
  `Path(td)/"wallet.json"`.
- Python `Path(...)` on VM4707 Linux returns the concrete
  `PosixPath` subclass, so `type(path) is not Path` rejected
  legitimate input. **This was a production defect**, potentially
  rendering real app-wallet signing impossible, not a false
  test expectation.
- R245 source change:
  `type(path) is not Path` -> `not isinstance(path, Path)`.
  Keeps absolute path, no direct symlink, correct nonroot owner UID,
  owner-only 0700 directory/0600 file and bounded valid encrypted
  UTC-V3 input enforcement.
- R245 test now explicitly checks the real OS-specific
  subclass behavior. **New R245 source has not yet passed the VM test
  gate; do not claim it has.**
- R242 sender unit tests, whole Python regression, new R236
  Solidity contract build/Foundry tests and full Foundry regression
  were not reached in this user run, owing to the fail-fast gate.
  No new compiled runtime size proven.
- All executed tests are local/unit mock or local socket tests;
  no real provider CPU or remote independent SLA was observed.
- No wallet was opened, test-ETH transferred, live transaction sent,
  Docker container changed, validator touched or original genesis
  altered by these source tests.

## Next single VM4707 gate

Reuse same isolated checkout + isolated venv. Fetch
`feature/r226-adaptive-v2-operator-runtime`, detach at latest immutable
GitHub SHA printed to user and run
`bash scripts/r235_vm4707_v2_source_only_gate.sh "$SHA"`.
Stop/fix next real error via GitHub, do NOT patch VM source.
The distinct draft PR #43 stays unmerged.

## Original-chain/project completion status

The real original chain31340 with separately running
VM4706 signing-validator, VM4707 and VM4709 non-signing observers
has already demonstrated native PoS finality and matching finalized
epoch602/root observationally; two capture timestamps were 181.223808
seconds apart vs R141's strict 180s compare requirement, and
earlier epoch571 formally met the strict bound.

The V2 market/ledger source has local earlier Foundry evidence but is
NOT live deployed on chain31340. Real app-owned wallets, authorized
funding receipts, actual marketplace request/bid/escrow/vote/reward,
multi-host physical SLA, independent additional BLS validators and
public no-overlay peer onboarding remain unverified. New authored
provider/monitor/console tools do not by themselves complete these
actual-network requirements.
