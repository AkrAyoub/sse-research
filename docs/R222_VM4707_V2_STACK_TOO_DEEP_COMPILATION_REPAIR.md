# R222 — VM4707 adaptive V2 Foundry stack-too-deep source repair (unverified)

## Actual operator-observed failure, 2026-11-23

VM4707 used exact immutable Git source `93ece499832bd2250069765e2deb2a5e42b6ea71`,
official Foundry v1.9.0, pinned submodules and Solidity 0.8.24.
`forge build --sizes` compiled the 68-file source set but returned nonzero
after dynamic test linking fallback to native linking, with:

```
Error: Compiler run failed:
Compiler error (/solidity/libsolidity/codegen/LValue.cpp:51):Stack too deep.
--> foundry/test/SSEAdaptiveMarketV2.t.sol:244:36
244 | market.resolveInconclusive(leaseId, 0, consumerShare, providerShare,
```

**This is observed failing V2 source verification, NOT a live-chain failure,
successful V2 compile or evidence of a live on-chain market.** No blockchain
transaction or wallet action resulted from the user's build.

## GitHub-only source remediation (R222)

Code commit: `41640102ca00edd21acf23cd7da361f82725d1f0`.

- Extract the independent consumer-signer funded lease setup into a small
  test helper, preserving all original real EVM test operations.
- Move the EIP-712 residual-claim signing into a helper with a typed
  `ResidualClaim` struct, reducing simultaneously live Solidity stack
  locals in the same adversarial test without deleting any assertions.
- Correct the late-provider regression test's accidentally double-escaped
  EIP-191 prefix to the genuine `\\x19\\x01` typed-data signing prefix.
  An invalid signature must not make a deadline test vacuously pass.
- Production V2 contracts, funds, native chain and Docker are untouched.

## Acceptance gate — STILL PENDING

On VM4707, fetch an exact immutable **new** branch head, retain
an isolated checkout, assert the full SHA and run:
`forge build --sizes`,
`forge test --match-contract SSEAdaptiveMarketV2Test -vv`,
`forge test -q`,
the R201 and R206 mocked read-only gate unit tests, and
R201 live read-only localhost-chain probe.

**Never claim PASS until the operator provides observed output.**
If compile errors persist, fix through GitHub and retest the new exact SHA.
Do not use `--broadcast`, `cast send`, or transfer signing keys.
Production chain31340 contract deployment and actual physical SSE SLA
remain unverified and require separate authorization.
