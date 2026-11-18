# SSE GitHub-first execution and evidence policy (operator directive)

**Effective:** 2026-11-18. **Scope:** `AkrAyoub/sse-research`, branch `research/r7-vm-role-operator-no-ci`.

**User direction:** All development, versioned scripts, tests, scientific plans, artifacts and authoritative checkpoint updates must be performed in and delivered through the **private GitHub repository** by the connected GitHub app. Do not use ChatGPT terminal code pastes as an ad-hoc VM deployment mechanism. Do not assume GitHub has reachability to private Ubuntu VM addresses or shell capabilities it has not been granted.

## Current chain facts — do not extrapolate

- Original dev Anvil `31337` on VM4695 now `10.50.56.14`; VM4693 SSH tunnel manually restored using portal-verified original Anvil host key. Last **proven** chain block `26`.
- Consumer lease funding `0x013c7a1717e08473aa0c20f18cc83d26a2050aeea3da9a953b5e942c6ff39aa1` at block25. Provider acceptance `0x15f0331a3a9ebeb22df7450452e6756b45dd08ac27955d64902fb19e2486f648` at block26, receipt success.
- Assignment `1` last observed status `1 AwaitingRandomness`, snapshotSize `5`, requestedAt `1794946523`, randomnessTimeout `3600`, latest block timestamp `1794946789`, host time Nov18 08:48 UTC. Assignment contains permanently lost Monitor VM4699.
- **Operator explicitly confirms none of proposed expiry/lease-close commands were run.** No `evm_mine`, `expire(1)`, `closeLease(1)`, `withdraw` was sent based on those suggestions. Therefore no expired/refunded/closed status can be claimed.
- Other four Monitor host identities 4700–4703 independently verified on their VMs, but their chain RPC tunnels have not been reverified since Anvil IP reassignment. Provider current IP unverified after restart.
- New Besu QBFT chain `31338` is **repository design/config generator only**; no Besu runtime, consensus validators, rewards, contract redeployment or benchmark observations exist yet.
- Controller's prior private GitHub SSH fetch failed `Permission denied (publickey)`; GitHub connector writes are functional, but a VM checkout/fetch is **not** an established deployment channel.

## Github-native workflows

1. `.github/workflows/sse-qbft-offline.yml`: manually dispatched, GitHub-hosted, **no private network**, no participant keys, no transactions. Tests QBFT config and SSH discovery and produces a **non-deployable** synthetic four-address sample genesis as a GitHub Actions artifact. On a non-default branch, GitHub may require workflow registration/merge to default before UI dispatch is available. Existence of workflow file **does not imply a run**.
2. `.github/workflows/sse-lab-readonly-check.yml`: `workflow_dispatch` only; requires a previously reviewed and installed **self-hosted** runner with label `sse-lab-readonly` and GitHub environment `sse-lab-readonly` configured with appropriate human approval. Performs only read-only Foundry `cast` calls against Controller-local RPC `127.0.0.1:8545`; checks chain 31337, code, receipts, assignment metadata. It deliberately contains no `cast send`, `evm_mine`, SSH key management, Python wallet decrypt, or Docker changes. **No matching runner/environment is verified to exist, and this workflow cannot yet inspect live VMs.** It must not be run on a general privileged runner or unreviewed PR code.
3. Existing repo `.github/workflows/ci.yml` runs broad test suites on push/PR; maintain source review and controls. This project branch may use `[skip ci]` deliberately; do not claim CI passed unless an actual GitHub job run and result are observed.

## Execution trust boundary and minimal operator integration

Private VMs use `10.50.56.0/24` and are not public GitHub-hosted runner targets. To move from committed code to **actual VM operations**, the user or infrastructure admin must first explicitly approve provisioning a dedicated GitHub Actions self-hosted runner (or a narrowly scoped authenticated outbound deployment agent). The runner should be isolated from Ethereum wallet private keys and contract-signing capabilities, restricted to read-only chain diagnostics initially, run as a low-privilege non-root principal, constrain network egress, and never execute jobs from untrusted pull requests. Use GitHub environment protection, reviewed pinned-commit release artifacts, code reviews, bounded authorization and audit logs. Do not put tokens, encrypted keystore passphrases, Ethereum private keys, node private keys, or plaintext signers in repository, GitHub Actions secrets/environment, logs or artifacts. Any later state-changing action needs separate human approval, role-owner wallet signing and chain-state idempotency gates; cannot assume Github's API directly signs.

## Safety and truth criteria

- **Development committed** ≠ **tests executed** ≠ **GitHub workflow passed** ≠ **VM deployed** ≠ **on-chain transaction mined** ≠ **service evidence qualified**. Record each separately.
- No hand-wavy conversion from single-Anvil Dev chain to multi-validator consensus. The Besu four-validator chain must start from a **separate genesis**, separate P2P identities, and chain ID 31338; current Ethereum contract addresses and lease1 history do not automatically exist on it.
- Do not use stale external VM IPs as identities: see `ADR-004_STABLE_NODE_IDENTITY_IP_FAILOVER.md`. A permanent Monitor key loss cannot be replaced by impersonation. The initial committee is 4-of-4 confirmations; the epoch outcome quorum is 3-of-4 votes.
- Do not force old timestamps to fulfill overdue randomness. Before refunding old lease1, observe actual new block time, validate assignment status, and use existing contract-defined expiry and Consumer-owned settlement-close/withdraw flows only after approvals. Separately investigate whether lost Monitor4699's pending snapshot lock is released; do not lose the existing escrow or erase old receipts.
- In Github issue tracking, link per-phase work to implementation commit/PR, test run ID, VM deployment evidence, chain receipt and scientific acceptance before marking it complete.

**Current immediate next executable action:** complete GitHub-side offline validation via a genuinely executed Actions run and provision an approved read-only self-hosted runner if live diagnostics must be GitHub-controlled. No blockchain write is authorized by this policy.
