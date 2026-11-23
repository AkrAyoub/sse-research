# R140 — Genuine chain31340 SSE application deployment acceptance

**Source status:** read-only deployment verifier with pure mocked unit tests.
**Live status:** no SSE application deployment on the existing chain31340
is asserted. No EOA, signer, validator, or Docker state is changed.

## Why this gate exists

The earlier `script/DeploySSEPos.s.sol` requires **chain31339** and has
proven execution only on that separate historical ledger. Never change
its chain constant merely to redeploy legacy fixed 4/3 contracts and call
that the finished SSE design. The current `OpenMonitorCommittee` /
`SSESettlement` contain fixed four seats and quorum three. The
experimental variable-seat `SSEAdaptiveVoteLedger` is **not yet wired**
to the finalized marketplace. Delayed-block entropy is proposer-biasable;
a mocked VRF does not count as permissionless randomness.

## Deployment acceptance for the target application

1. Settle one reviewed **versioned** contract architecture with dynamic
   per-lease `k` and precommitted `q`, transparent objective eligibility,
   actual pre-funded monitor reward obligations and conservative
   inconclusive/dispute handling. Never claim bonded addresses imply
   physically independent operators.
2. Check and publish the EXACT chain31340 EL genesis block hash
   (`eth_getBlockByNumber("0x0",false)`), Beacon genesis root and full
   fork configuration. Do not accept the chain ID alone.
3. Compile pinned Solidity source/toolchain; compare independently
   exported `deployedBytecode.object` for **each** accepted contract
   against its real runtime after deployment, taking constructor
   immutable/library-link differences into account. Record canonical
   SHA256 of final actual deployed runtime bytes, not guessed artifacts.
4. Submit actual signed native-TEST-ETH transactions from an approved
   operator-controlled keystore, never a copied test mnemonic. Save
   transaction hashes, gas, block hashes and verified chain receipts.
   Track actual Beacon finalized execution state, not merely 1 block.
5. Verify mutual contract bindings, registration/funding/lease flows,
   monitor independence assumptions and real remote delivery evidence
   before settlement. Fail closed on unclear proof.
6. Demonstrate independent provider, consumer and monitors on different
   hosts with real resource accounting and independently archived
   evidence. Never translate raw monitor agreement into physical truth.

## Read-only postdeployment verifier

`tools/sse_pos_r140_marketplace_deployment_audit.py` accepts an
operator-generated **public** manifest containing the exact chain31340
genesis block hash, three accepted deployed contract addresses and
independently pinned `sha256(runtime_bytecode)` for each. No example
addresses are substituted for real deployments.

The manifest must be complete:

```json
{
  "schema": "SSE_R140_CHAIN31340_DEPLOYMENT_V1",
  "chainId": 31340,
  "executionGenesisHash": "0x<ACTUAL_64_HEX_GENESIS_BLOCK_HASH>",
  "contracts": {
    "committee": {"address": "0x<ACTUAL_40_HEX_ADDRESS>", "runtimeSha256": "<ACTUAL_64_HEX_SHA256>"},
    "settlement": {"address": "0x<ACTUAL_40_HEX_ADDRESS>", "runtimeSha256": "<ACTUAL_64_HEX_SHA256>"},
    "board": {"address": "0x<ACTUAL_40_HEX_ADDRESS>", "runtimeSha256": "<ACTUAL_64_HEX_SHA256>"}
  }
}
```

The placeholders are intentionally NOT valid input. Do not fill them from
the legacy chain31339 deployment or fake fixtures.

On VM4706 (owner) or VM4707 (observer), after a real deployment:

```bash
.venv-tests/bin/python -B tools/sse_pos_r140_marketplace_deployment_audit.py \
  --manifest /absolute/path/to/reviewed-public-deployment.json \
  --rpc http://127.0.0.1:18545
```

Use `http://127.0.0.1:28545` instead when running on VM4707.
The verifier reads at an actually finalized EL block and requires
matching genesis, SHA256 runtime bytes, committee→settlement,
settlement→board and board→settlement ABI bindings.
It never sends transactions, claims real SLA success, verifies economic
quorum soundness or substitutes for deployment receipt provenance.
Its report is **necessary but not sufficient** for a real complete
marketplace acceptance.

Run test suite:

```bash
.venv-tests/bin/python -B -m unittest discover -s tests \
  -p 'test_sse_pos_r140_marketplace_deployment_audit.py' -v
```

**Remaining code blocker:** dynamic committee and conservative
settlement contract migration. Do not deploy legacy fixed-quorum
contracts simply to obtain a green readiness report.
