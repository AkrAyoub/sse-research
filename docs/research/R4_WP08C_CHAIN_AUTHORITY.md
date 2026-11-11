# WP-08C — on-chain scope and monitor authority, without physical-truth claims

## What this increment adds

The WP-08B provider/monitor pipeline already produced valid EIP-712 signatures and stored the received HTTP payload. Until now, however, `VerificationContext` accepted a caller-supplied list of monitors and an expected provider address. A correctly signed message by a **non-selected** identity could be treated as authorized if the caller supplied a false context.

`tools/sse_chain_authority_v1.py` reconstructs expected provider and selected monitor addresses from the deployed **SSESettlement V1** and **OpenMonitorCommittee** state at the **same** EIP-1898 block-hash-pinned RPC reference. No V1 Solidity code or payout logic changes.

Validation steps:
1. An explicit `AuthoritySpec` pins expected chain ID, settlement and committee addresses, independently known Keccak runtime-code fingerprints, and evidence scope (lease/epoch/SLA/resource/request).
2. Query the chosen `finalized` block tag (or opt in explicitly to `safe`/`latest` for research) and retain its number/hash/timestamp.
3. Use `{blockHash,requireCanonical:true}` for **every** `eth_call` and `eth_getCode`. An RPC that does not support the EIP-1898 object must fail closed, never silently use `latest` or height-only state.
4. Require both contract bytecode digests to match the independently supplied fingerprints; check EIP-712 settlement domain; verify bidirectional settlement↔committee binding.
5. Read `nextLeaseId` and `getLease`: require real consumer/provider, `Ready` or `Active` lease, exactly four monitor confirmations, four distinct non-party monitor addresses, nonzero assignment, and exact SLA/resource scope.
6. Require `assignmentStatus=Assigned` and equality between `getCommittee(assignmentId)` and the lease's four selected monitors.
7. Read `getEpoch`: require actual admission, exact request hash, expected deterministic response commitment, ordered time windows and an unsealed/open monitoring window **in the selected block's chain timestamp**.
8. Fetch that block number again to detect a visible reorganization, construct a portable **chain-authority reference** with block hash, and derive the narrow `VerificationContext` and provider identity.
9. `verify_against_chain` authenticates an existing WP-08A RAW monitor observation; `capture_with_chain_authority` passes derived context into WP-08B capture. Neither produces a `QualifiedFact`.

`tools/sse_chain_authority_cli.py` offers a **read-only local Anvil** command that prints the RPC-reference JSON and a Keccak commitment. It never uses a funded private key, sends transactions or credits escrow.

## Assumptions and deliberate limits

- A full Ethereum header or Merkle/Verkle storage proof is **NOT** verified. A malicious or partitioned RPC can lie about the tagged block, bytecode and contract state; comparing values within the same RPC does not resolve that problem. A deployment fingerprint must be obtained independently, not `eth_getCode` from that same untrusted endpoint and then trusted by default.
- The `finalized` tag is the RPC's assertion. It is not an independent finality guarantee. `safe` and `latest` are opt-in and may reorganize.
- A monitor selected/confirmed at the referenced block is authorized to *make an observation*. A valid signature and monitor observation do **not** prove correct/timely consumer delivery or soundly exclude N/F/S histories.
- Only the existing V1 4-monitor model is supported. The scalable/open R3 pool, unbiased randomness and absent-monitor recovery are still unimplemented.
- For existing direct leases `slaPolicyHash=0`, WP-08A's nonzero-SLA scope cannot be constructed. The new adapter fails closed rather than pretending the lease has a signed SLA commitment.
- No authenticated external consensus, remote TLS, chain-source quorum, durable *atomic* archive of chain-reference+evidence, consumer receipt proof, universal settlement safety proof or new on-chain evidence policy.
- `ChainAuthoritySnapshot` is an ordinary constructible Python dataclass; it is not a cryptographic capability or security boundary. Call it only after `read_chain_authority` with a trusted client/configuration.

## Test strategy and acceptance

`tests/test_sse_chain_authority_v1.py` adds **31** new tests, primarily with an explicitly **synthetic mocked RPC**. They exercise exact ABI decoding, EIP-1898 request pinning, runtime bytecode fingerprints, chain and reverse contract binding, lifecycle and selected roster, epoch/request/SLA identity, timeout/seal failures, reorgs, missing EIP-1898 support, optional unfinalized tags, and EIP-712 signer authority. The mock proves *parsing/authorization algorithm behavior under stipulated RPC inputs*, not agreement with a live Ethereum chain.

Previous merged baseline: 337 Python named tests and 52 Foundry tests on Windows/Ubuntu CI. Expected combined branch outcome: **368 Python tests and 52 Foundry tests**, with no failures or skips, subject to actual execution.

The first independent on-chain integration test should deploy a real lease with four confirmed monitors and an admitted epoch on Anvil, record **independently checked** runtime code fingerprints, and run `sse_chain_authority_cli.py` against that process. Verify whether the local Anvil version supports EIP-1898 block-hash tags (especially for `eth_getCode`). No compatibility is assumed without that run.

## What's next

1. WP-08C host/CI integration and review; correct any ABI/RPC portability issue without relaxing the pinning or checks.
2. WP-08D: bind and archive the chain-reference with evidence **atomically**; add actual bytecode/committee reconciliation against the authenticated chain source; consider independent RPC/verified Ethereum storage proofs for publication claims.
3. R3: scalable registration/selection, configurable committee and Sybil fault assumptions, no-show reassignment, absent-consumer bond release.
4. P1/P2/R2: sound qualified physical receipt and delivery certificates, full conditional proofs and versioned payout integration.
5. R9/R10: distinct independent hosts, network partitions, clock uncertainty, baseline comparisons and evidence availability experiments.
