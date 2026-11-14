# R3 WP-09D — Experimental canonical RSA-2048 proof-verified entropy

**Status:** 2026-11-14 · stacked **draft PR #25** on draft #24 → #18. Not merged, deployed, audited, or cryptographically standardized.

## Exact improvement and nonclaim

The previous V1 "legacy" randomness path let one authorized EOA submit an arbitrary seed. WP09C's alternative future-block hash does not require that source, but can still be influenced by block proposers and reorgs. WP09D adds a **third, one-way, mutually exclusive opt-in mode** that validates a deterministic RSA proof on-chain using the EVM's modular exponentiation precompile `0x05`. A caller cannot choose any integer seed or supply an alternate valid signature encoding for the same digest.

**This is NOT a proven VRF or full global fairness:** the key holder can compute an outcome in advance and selectively withhold its proof. The custom hash-to-integer representative has no standardized RSA-FDH security proof, the public modulus is accepted from bootstrapper setup (only its bit length and oddness are checked), and the candidate pool is still the **at most 64 participants in WP09B's predictable rolling window**, not a uniformly chosen subset of every active address.

## System and smart contracts

### RSA2048EntropyVerifier.sol

A pool-deployed verifier with public `modulus` and fixed public exponent `65537`. The pre-binding bootstrapper supplies exactly 256 bytes of an odd 2048-bit modulus. This **does not** independently verify that the modulus is the product of safely generated primes, or that a valid private exponent exists. Production key provenance, generation ceremonies and cryptanalysis remain prerequisites.

The verifier encodes a request `D` as eight `keccak256(abi.encode(REPRESENTATIVE_DOMAIN, D, i))` blocks for `i=0..7`, concatenated into 256 bytes. It clears the topmost bit to obtain a 2047-bit representative `M`, which is smaller than a valid full-width modulus. This **custom hash-to-representative encoding is not standardized RSA-FDH**.

For a submitted **exactly 256-byte** proof `S`, verification checks `0 <= S < modulus` in fixed-width big-endian form, then calls EVM `modexp(0x05)` to validate `S^65537 mod modulus == M`. The strict `S < modulus` condition prevents a signer/relayer from submitting the same mathematical root encoded as `S+modulus` to change the seed. Any malformed proof fails closed.

The on-chain verifier is deployed directly inside `OpenMonitorCommittee.enableRSAProofEntropy(modulus)`: users **cannot** register an arbitrary external contract whose `verify()` always returns true. However the bootstrapper remains responsible for ensuring a genuinely generated, trusted RSA key.

### OpenMonitorCommittee.sol

Before binding settlement, the bootstrapper chooses exactly one deployment mode:

- **Legacy:** no opt-in, existing authorized `fulfillRandomness(id, seed)` operates.
- **WP09C blockhash mode:** `enableDelayedBlockEntropy()`, any caller can fulfill after the target future block, and the arbitrary-seed callback is disabled.
- **WP09D RSA proof mode:** `enableRSAProofEntropy(bytes modulus)`, initializes the local verifier, and disables both the legacy seed callback and WP09C future-block fulfillment. No switching modes after pool binding.

The registration and per-lease request still use WP09B's bounded active roster. The assignment freezes its eligible snapshot under the existing `snapshotCommitment[id]` and request block. A signer receives the digest

```
D = keccak256(abi.encode(
    RSA_ENTROPY_DOMAIN, block.chainid, poolAddress, assignmentId,
    assignmentRequestedBlock[id], snapshotCommitment[id]
))
```

This binds a proof to a particular chain, pool, assignment, request block and candidate snapshot. An outside relayer submits `fulfillRSAProofEntropy(id, proof)`. After **actual proof verification**, the seed is

```
seed = uint256(keccak256(abi.encode(
    RSA_ENTROPY_DOMAIN, D, keccak256(canonicalProof)
)))
```

The unchanged bounded Fisher–Yates-style shuffle applies that seed to choose four committee members and ordered standbys. The existing four actual confirmations for activation, three monitor failure votes for monitoring quorum, WP09A no-show recovery, pending and assigned candidate bond locks, and all consumer/provider escrow and residual settlement logic remain unmodified.

### Failure and liveness boundaries

- Only a signer with the RSA private exponent can produce a valid root for a new digest **assuming a correctly generated modulus and computational RSA-root hardness**. The proof can be *checked* by anybody after submission; this does not make its production independently decentralized.
- The signer can compute the full elected committee before publishing and selectively **withhold** if unfavorable; even if each request has one canonical proof, **released results need not be an unbiased sample of all requests**.
- A caller may strategically time/cancel requests. A coalition can register many bonded EOAs (Sybil) or manipulate the predictable membership window via churn. Distinct addresses do not prove distinct physical operators.
- Failure to submit a valid proof before the existing randomness timeout causes a **fail-closed assignment**, with `expire()` releasing pending candidate locks and the consumer's pre-epoch `closeLease()` refunding uncommitted service escrow. No automatic fallback to the EOA-seed or blockhash modes is permitted.
- Proof validity does not prove Ethereum PoS finality, independent witness consensus, truthful service response, physical SLA completion, `QualifiedFact`, or entitlement to escrow.
- This changes Solidity bytecode and mode wiring: **new deployments required**, not a proxy or upgrade of existing contract addresses.

## Integration and testing evidence

- **Foundry `foundry/test/RSA2048EntropyProof.t.sol`:** real RSA verification against an offline-generated static known-good signature and representative; wrong digest/proof length/corrupted proof; canonical `S+N` rejection even though modular exponent is mathematically identical; malformed key length/format, unauthorized or conflicting deployment mode, legacy/future-block disabling, request-scoped digest and replay/timeout/bond/refund invariant tests. One dynamic pool state-machine test **mocks the verifier output explicitly**; it is not presented as evidence of real RSA correctness.
- **Python `tools/sse_wp09d_rsa_entropy.py` and `tests/test_sse_wp09d_rsa_entropy.py`:** independent ABI/domain, canonical proof, fixed representative and math reference, wrong-pool/chain/request/snapshot digest and seed replay tests.
- **Real fresh Anvil marketplace E2E `tools/sse_wp08c_live_marketplace.py`:** pool enables the RSA option before binding settlement; five monitors register; consumer creates actual funded marketplace request; eligible roster is frozen; the lab-only RSA signer computes a lease-specific proof; the on-chain verifier `eth_call` checks it via real EVM `0x05`; an unprivileged outsider submits the **real proof**, and the contract chooses the committee. The previously established 3/4 pre-epoch no-show recovery then selects a standby, followed by authenticated provider/monitor HTTP evidence capture, signed witness/replica and negative ancestry/reorg experiments. No paid monitor SLA claims or service payouts occur.
- **Lab-only public key:** `tests/fixtures/wp09d_public_lab_rsa2048.json` includes the private exponent by design. It must **NEVER** be copied into production keys/config or used for real assets. A valid local test key has no unpredictability or confidentiality.

Validated [4/4 CI source run](https://github.com/AkrAyoub/sse-research/actions/runs/43546849192): **81/81 Foundry**, **393/393 Python Ubuntu**, **393/393 Python Windows**, and **fresh local Anvil EVM proof verification + signed evidence pipeline**. A test-only Solidity 8-bit addition overflow was corrected before this successful run; it was not a change to verifier logic.

Run in a disposable checkout:

```bash
forge build
forge test -vv
python -m unittest discover -s tests -v
python tools/sse_wp08c_live_marketplace.py
```

A 2048-bit RSA public-key signature verification using EVM modexp is tested, but execution gas is **not benchmarked for production cost**, and cryptographic security, formal uniqueness under malicious key setup, multi-operator availability and global fairness have **not** been validated.

## Remaining R3 / WP09E research targets

1. Use a reviewed **standard** VRF coordinator/proof implementation and explicit authenticated randomness-provider/key-setup policy; test adaptive last-revealer and withholding/selective-abort attacks under the exact network model.
2. Eliminate predictable 64-member window bias with a gas-bounded but globally snapshot-consistent eligibility commitment (e.g. authenticated indexed Merkle structure), with proofs of chosen membership and valid exclusion of consumer/provider.
3. Quantify time-to-assignment, candidate concentration, acceptance/abort selection bias, entropy withholding probability, bond opportunity cost, on-chain gas and reaction under concurrent requests/roster churn.
4. Model independent operator identities and Byzantine majority assumptions; then evaluate dynamic `k`, `q` and anti-Sybil policies without conflating reporting majority with physical service truth.

**Research checkpoint estimate:** R3 29% → **33% (+4 percentage points)**; research phase percentages unchanged. This is a planning estimate, not an assurance score.
