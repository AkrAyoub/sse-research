# WP-09L: fee-backed, quota-limited VRF request integration (OFFLINE)

**No GitHub Actions, GitHub writes, external RPCs, package installs, or paid services.**

The package extends the prior WP09K research VRF adapter with:

1. `configureVrfFeePolicy(uint256 feeWei, uint256 maxLifetimeRequests)`: bootstrapper locks fee and lifetime quota before binding adapter or creating leases.
2. `fundVrfRequestFee(leaseId)` (payable, exact fee): lease consumer escrows the VRF-request service fee after provider acceptance.
3. `requestLeaseRandomness(leaseId)` (permissionless): only a previously funded lease can spend one coordinator purchase, with a per-assignment no-repeat guard, a per-settlement reentrancy guard, and an immutable lifetime request-count cap. Fee is sponsor-earned on successful request transaction, not dependent on callback delivery.
4. `closeLease`: returns a fee if unspent; *does not* refund a fee if the coordinator order succeeded, even after VRF withholding or timeout. The WP09K pool cancellation protection remains.

**Important**: flat native-ETH fee is not the actual LINK/native cost of the VRF subscription. It reimburses a sponsor but does not guarantee sponsor solvency. The only strictly guaranteed cap is the **number of VRF purchases**, not their financial cost. Mock coordinator proves no cryptographic VRF, and all Solidity code remains **uncompiled/unaudited**.

## Verified local checks

```bash
python -m unittest discover -s WP09L_offline/tests -v
python -m unittest discover -s WP09L_offline/policy_reference/tests -v
(cd WP09L_offline/policy_reference/WP09I_offline && python -m unittest -v test_wp09i.py)
```

**68/68 Python tests passed**: 24 WP09L, 19 WP09K, 25 WP09I; 36,000 deterministic model actions in the WP09L suite. Test logs are included under `logs/`.

## Generate patch from your LOCAL WP09E checkout (no network)

```bash
python WP09L_offline/apply_wp09l.py \
  --repo /absolute/path/to/sse-research-WP09E \
  --out /absolute/path/to/new-empty-patch-output
```

The generator uses the WP09K exact anchors, patches only **in a separate output directory**, and refuses an unknown version, pre-existing VRF files, a nonempty output, or source-relative output paths. Review the generated `WP09L.patch` and output contracts.

## EVM validation later, only on your PC with EXISTING Foundry dependencies

```bash
bash WP09L_offline/verify_wp09l_locally.sh /absolute/path/to/sse-research-WP09E
```

This runner checks `forge` is already available, copies `contracts/`, `foundry/`, `foundry.toml` and `lib/` to a disposable `/tmp` workspace, generates the patch there, and uses `forge build --offline`, `forge test --offline` and a local gas report. **It installs/downloads nothing**, never accesses GitHub, and leaves the checkout unchanged.

## Files

- `wp09l_source.py`, `apply_wp09l.py`: WP09K→WP09L settlement fee transform and reproducible isolated patch generator.
- `wp09l_fee_model.py`: conservative ETH fee/credit/refund/quota state-machine model.
- `tests/test_wp09l.py`: 24 actual Python tests including 36k adversarial model steps.
- `foundry_test/VRFFeePolicy.t.sol`: 14 authored Foundry scenarios, not yet run (no solc/forge here).
- `policy_reference/`: the original WP09K transformer/adapter/mock and old independent policy test references needed to reproduce the combined patch. These are included so a second chat does not need previously uploaded ZIPs.
- `verify_wp09l_locally.sh`: safe local-only runner, which fails closed without `forge` and preinstalled library dependencies.
- `WP09L_FINDINGS.md`: protocol accounting, security assumptions, remaining research and project tracking.

**Project percentages unchanged**: R3 38%, engineering 26%, research 26%, overall 26%. The Solidity patch is research only until local EVM tests pass. Do not deploy with the mock coordinator or claim secure Chainlink VRF from the mock.
