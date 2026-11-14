# WP-08F — Beacon REST reported-finality and execution ancestry cross-check

**Status:** 2026-11-14; stacked draft PR #21 based on draft WP-08E PR #20. **NOT cryptographically proven finality.** Do not merge before review, and do not use any new output for escrow settlement, a monitor vote, or physical SLA qualification.

## Security motivation

WP-08E provides separately signed witnesses of the same RPC-observed block plus portable evidence replicas. A local Ethereum execution RPC can fabricate or misreport its own fork, and two signers may share the same dishonest RPC. We therefore add an **independent data-source interface** to the consensus layer: an explicit, pinned genesis root plus a beacon node's reported finalized execution payload. Checking a second client's view and hash ancestry helps detect inconsistencies, but the Beacon API itself remains a trusted assertion rather than a verified Ethereum consensus proof.

## Code delivered

- `tools/sse_wp08f_beacon_finality.py`: `LoopbackBeaconREST` accepts only numeric `http://127.0.0.1:PORT` (no DNS, proxies, redirects, HTTP credentials or remote connections), enforces bounded response/timeouts, and checks `GET /eth/v1/beacon/genesis` against a *configuration-pinned* nonzero `genesis_validators_root`. This pinning is an explicit trust assumption; it does not authenticate the remote REST server by itself.
- The client calls `GET /eth/v2/beacon/blocks/finalized`, requiring `finalized == true`, `execution_optimistic == false`, and a supported response layout with `data.message.body.execution_payload.block_hash`, `block_number`, and `timestamp`. Unsupported forks (including any layout without a payload field) **fail closed**; support may need updating as consensus APIs evolve. Numbers must be canonical decimal strings and the block hash must be nonzero lowercase bytes32.
- `cross_check_reported_finality` starts from the *Beacon API reported* execution block, verifies its height, hash and timestamp against execution RPC block-by-hash **and** block-by-number, walks each `parentHash` back to the monitor-signed block anchor, and checks the original block hash/number/time. Maximum 128 execution-block ancestry steps prevents unbounded RPC traversal. A second execution RPC (different endpoint) may be required and is compared independently. Wrong chain ID, stale block, divergent header, missing ancestor, untrusted/corrupt Beacon response or height beyond the safety window aborts.
- `EvidenceArchive.load_beacon_reported` composes the existing *raw/provider signature + monitor EIP-712 + signed block anchor + two external witnesses + current RPC block* verification with this new strict consensus-API report cross-check. The result explicitly sets `pos_finality_proven = false` and `physical_service_verified = false`. No financial or Solidity code is modified.
- `tests/test_sse_wp08f_beacon_finality.py` exercises a real loopback HTTP fixture with positive and negative responses, root mismatches, fake "finalized" flags, optimistic execution, unsupported fork, redirects, duplicate JSON keys, malformed payload, forged ancestry, second-RPC disagreement, stale/orphaned blocks, chain-ID mismatch and same-endpoint caveats.
- The existing fresh marketplace-funded Anvil integration now mines one additional block, compares the archived hash to an explicitly **simulated** beacon-reported execution block, injects a fake dissenting RPC and rejects it, then rewinds the Anvil chain and rejects the stale report. **Anvil has no consensus-layer finalization:** this is a real execution-EVM ancestry test, *not* an Ethereum PoS finality experiment.

## Reproduce

With the exact project dependencies and Foundry/Anvil available:

```bash
python -m unittest discover -s tests -p 'test_sse_wp08f_beacon_finality.py' -v
python -m unittest discover -s tests -v
forge build
forge test -vv
python tools/sse_wp08c_live_marketplace.py
```

The Anvil runner uses disposable published lab keys and writes evidence to `.local/wp08c-live/`, refusing to overwrite a nonempty existing folder. GitHub Actions runs Ubuntu/Windows Python and Foundry and an independent fresh Anvil job. CI counts are recorded in the tracker after **all four** jobs pass on the final branch head.

## Explicit trust and protocol boundaries

1. **NO verifiable consensus finality.** Neither a Boolean `finalized` from a Beacon REST endpoint nor agreement between two RPC servers is a cryptographic proof of Ethereum PoS finality. A malicious Beacon server could fabricate the execution checkpoint, and a malicious execution RPC could fake its header chain. Validating BLS sync committee signatures, fork-specific SSZ Merkle proofs, trusted weak-subjectivity checkpoints, and consensus transitions remains future work.
2. **NO authenticated remote transport.** The built-in REST client is localhost-only. A local reverse proxy or malicious operator can misreport the node. HTTPS peer identity, pinning, remote independently controlled beacon/execution clients and network tests are not implemented.
3. **NO long history proof.** The fixed depth limit means old observations more than 128 blocks behind a trusted finalized report fail. A reviewed proof-of-ancestry/history format is needed for archival verification.
4. **NO service correctness or payment.** Even a mathematically valid finalized chain would prove chain inclusion, not timely physical consumer delivery or honest cloud CPU/storage performance. This feature supplies no `QualifiedFact`, on-chain vote, settlement authorization or escrow payout.
5. **NO live CL+EL deployment test.** The positive Beacon API HTTP fixture is synthetic; the live Anvil test's "beacon finality" claim is explicitly simulated and never counts as PoS consensus evidence.

## Next gate

WP-08G should design/integrate a **real, independently verified Ethereum consensus light client** or explicitly trusted finality infrastructure, with defensible weak-subjectivity and client-version handling. Also test genuinely distinct machines, remote authenticated transport, peer unavailability, byzantine RPCs, durable evidence retrieval and monitor independence. Physical-world evidence eligibility remains blocked by R1/P1.
