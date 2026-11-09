# R0 Python dependency policy (WP-01)

- CI target: CPython **3.12** on Linux and Windows. Source syntax is also checked on Python 3.13 in the inspection runtime.
- `requirements.txt` pins direct Python dependencies, including `pycryptodome==3.23.0` (Ethereum Keccak) and new `eth-account==0.14.0` (EIP-712 signing/recovery). Never replace Ethereum Keccak with standardized SHA3-256.
- The exact direct-version pins are **not a transitive, hash-locked lockfile**. A fully frozen, hash-verified deployment lock must be generated and tested on the supported Python 3.12 platforms before claiming R0 complete. Do not treat an unrelated `pip freeze` as reproducible lock data.
- Fresh development setup: `python3.12 -m venv .venv`; activate; `python -m pip install -r requirements.txt`; `python -m pip check`; `python -m compileall -q apps services tools tests`; `python -m unittest discover -s tests -v`.
- Solidity: Foundry toolchain, Solidity 0.8.24, OpenZeppelin Contracts v5.0.2 and forge-std v1.9.5 as configured by existing scripts. Verify exact resolved dependency commits after installation, then `forge build && forge test -vv`.
- `tests/test_entrypoint_smoke.py` executes real `--help` subprocesses to catch missing runtime imports, without starting services.
- No package installation or contract compilation was possible in the 2026-11-09 isolated inspection environment (DNS unavailable; Foundry absent); see `R0_VALIDATION.md` for transcripts and limits.

The signed remote probe requires a **provider EIP-712 signature**. Both existing provider HTTP examples are unsigned and therefore deliberately return `INVALID`, not SUCCESS. Working signed provider-service integration, hardened remote RPC, on-chain vote submission, and independent VM deployment are future R4/R5/R6 work, not R0 accomplishments.
