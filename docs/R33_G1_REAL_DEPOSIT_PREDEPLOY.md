# R33 — Non-secret, standard Beacon deposit predeploy integrity gate

**2026-11-20. SOURCE-ONLY after VM4706's real Step38 one-validator derivation. NOT YET VM-tested or live.** This is a narrowly scoped safety fix on existing G1→G2 path, not a change of network architecture or an additional wallet ceremony.

## Actual defect and scope

Previous `tools/sse_pos_genesis_build.py` only checked the presence of *some* EL genesis `alloc` bytecode at `config.depositContractAddress`. Its honest unit fixture uses **`0x60006000fd`** (a REVERT stub); such bytes cannot accept future permissionless validator deposits. Further, the genuine Ethereum Beacon `DepositContract` constructor initializes a zero-hash tree in EVM storage. A genesis code predeploy **does not run the constructor**, so runtime code without the 31 required preinitialized storage values silently produces an incorrect deposit tree/root.

The PUBLIC reference in `reference/standard_deposit_predeploy_r33.json` contains the **standard UNGATED** upstream ethpandaops Ethereum Genesis Generator `apps/el-gen/system-contracts.yaml` `deposit` entry pinned to commit `0b518636eec53e41e6d261f46ae07147d546a456`: actual runtime code, zero initial balance and zero_hashes[1..31] at storage slots 34..64. The separate upstream `gated-deposit-contract.yaml` is NOT allowed.

`tools/sse_pos_deposit_predeploy.py` checks the EL public JSON's single normalized deposit account, exact byte-for-byte reference runtime, exact 31 canonical constructor storage words computed from SHA256, zero balance, no duplicate JSON properties/links. This local pin is a **source integrity condition**, NOT a deployment audit. `tools/sse_pos_genesis_build.py` now invokes it ONLY in `--build-single-operator-lab` BEFORE the real SSZ generator or output directory. `--inspect` remains an intentionally **shape-only** public parser (its unit REVERT fixture is never accepted into a build). No own EOA/BLS keystores or passwords are read. Seven new negative/source tests in `tests/test_sse_pos_deposit_predeploy.py` require VM verification.

## Still mandatory before any actual chain31340 launch

Authentic runtime reference matching **does not** prove native EVM execution, correct deposit events, EL/CL current-fork system contracts or Genesis SSZ semantics, BLS subgroup/PoP, native 0x01 withdrawal binding, live deposit/activation, signing attestations, PoS finality, public P2P or independently operated nodes. Proper EL+CL fork parity, timestamp/pinned-client compatibility and accurate upstream genesis generation remain G1 blockers. Never present a one-operator lab as public decentralized acceptance. Do NOT rerun owner R20/R27/R32 creator scripts.

## Safe source gate on VM4706

After checkout to the exact NEW GitHub SHA given in chat:

```bash
python3 -B -m unittest discover -s tests -p 'test_sse_pos_deposit_predeploy.py' -v
python3 -B -m unittest discover -s tests -p 'test_sse_pos_genesis_build.py' -v
```

These are SOURCE/unit tests, not a Genesis creation or client run. Reference material: official `ethereum/solidity-deposit-contract/deposit_contract.sol`; pinned `ethpandaops/ethereum-genesis-generator` file at commit `0b518636eec53e41e6d261f46ae07147d546a456`. For full observed VM evidence, see `docs/experiments/VM4706_2026-11-19.md` Entry052.

Immediately after actual G2 native finality on VM4706, G3 joins the next available VM as a real keyless EL+CL peer and G4 joins the one true external laptop. No protocol role count cap, Tailscale admission, fake keys, or central admin.
