# WP-01 — Reproducible source baseline and signed monitor import repair

Date: 2026-11-09. Input: SHA256 `d921cb6ca4ba80cad300bc25f00c15e73562ae7c0d05e74cf6de010661da438d` (`repo_original_2026-11-08.zip`). Audited code and archive-extracted tree agree byte-for-byte before editing.

## Scientific and technical scope

This is **R0 source repair**, not proof of world soundness, external receipt, monitor independence, correct timeout attribution, or contractual financial safety. It preserves all Solidity code and current N/F/S money semantics.

Changes:

1. `services/monitor-agent/monitor_agent.py`: replace four missing internal modules with existing `sse_challenge`, `sse_chain_read`, `resource_profile` and two new narrow adapters; check consistent on-chain state, selected monitor identity, resource profile and chain/domain before signing; reject late observations and refuse overwriting evidence.
2. `services/monitor-agent/typed_evidence.py`: Solidity v1-compatible EIP-712 ProviderResponse and MonitorVote schemas with domain separation, signature recovery, canonical evidence commitment and local signing via `eth-account`. Typed signatures authenticate a statement, not its physical truth.
3. `services/monitor-agent/signed_probe.py`: explicit HTTPS for remote roots, size-bounded challenge response and **mandatory provider signature**; unsigned/invalid responses never count as SUCCESS. Legacy unsigned HTTP examples are retained for local regression (not silently upgraded).
4. `requirements.txt`: pin `eth-account==0.14.0` for signing; existing `pycryptodome==3.23.0` remains required for Keccak-256.
5. `services/role-agent/agent.py`: expose an argparse `--help` smoke path without starting its read-only heartbeat server.
6. `tests/test_monitor_signed_adapter.py`: synthetic EIP-712 provider response/vote and malformed-response tests; `tests/test_entrypoint_smoke.py`: real CLI `--help` process probes.
7. `.github/workflows/ci.yml`: syntax compilation, `pip check`, existing Python suite including new smoke gate, original Foundry job unchanged.
8. `docs/research/*`: reproducibility, scientific next steps, validation and project progress.

## Contracts, ABI, security, compatibility

- **Zero Solidity/ABI/storage-layout changes.** No contract migration or funding.
- The signed monitor's CLI now supports `--expected-chain-id` defaulting to Anvil `31337`, while the local RPC restriction from existing read-only tooling remains. Remote HTTPS endpoints must match the lease's immutable endpoint profile.
- `monitor_agent.py` is an experimental *offline evidence producer*: it does not submit votes or prove delivery/timing, and cannot obtain positive signatures from the current unsigned provider service. Its negative classifications mean 'not observed by this monitor' only.
- Existing local demos and tests are deliberately preserved. New signers are not auto-installed onto public VMs, no live private keys are embedded in source, and no financial transitions are triggered.
- This is an interim module location; R4 must consolidate the message encoding into the versioned shared SDK, with independent cross-language Solidity tests.

## Audit traceability

A02: missing imports replaced in source; **runtime verification blocked by unavailable dependencies**. A32: CI smoke gate added; **CI not run here**. A41: legacy unsigned and signed paths clearly distinguished, but **not yet consolidated**. A01/A14/A38: still open; external receipt and world-soundness policies remain unresolved.

Next: run WP-01 on a connected Python 3.12 + Foundry host, generate a real transitive lock, compile and execute tests, fix any findings, then mark the R0 exit gate only if demonstrated.
