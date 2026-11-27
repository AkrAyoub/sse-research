# Dependency and compatibility audit — 2026-11-27

- foundry.toml: solc 0.8.24, optimizer 200 runs, src=contracts, test=foundry/test. Toolchain historically Forge 1.9.0 (R19).
- Submodules lib/forge-std and lib/openzeppelin-contracts: commit pins must be verified by owner (`git submodule status`);
  not fetched or updated in this session. V4 test uses `vm.setBlockhash` and `vm.computeCreateAddress` — confirm present
  in the pinned forge-std (Vm.sol lines ~2667 / ~2243 in the checked-out tree: present).
- Python: requirements.txt pins eth-account 0.14.0, pycryptodome 3.23.0, eth-abi 5.2.0; V4 tools use only eth_abi and the
  repo's keccak helper (tools/sse_challenge.py) — no new dependency.
- Working tree is CRLF on Windows; .gitattributes forces LF for .sol/.py/.sh. Linux git must use core.autocrlf=true.
