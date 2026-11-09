# SSE — Fast end-to-end local integration (Sprint Patch)

**What this adds:** `tools/sse_e2e_local.py` plus offline regression tests. It needs the existing Checkpoint B1 `tools/sse_chain_read.py`, your existing `tools/sse_challenge.py`, existing `services/monitor-agent/http_probe.py`, and current deployed `SSESettlement`. It changes no Solidity source, deployment, provider service, or existing test.

## 1. Install

Extract the ZIP into your SSE project root; merge new files, do not delete others.

Make sure Anvil at `http://127.0.0.1:8545` is still running with the known contract and unlocked dev accounts. Your `.venv` should already have `requirements.txt` installed. The full Python suite is expected to reach **63 tests** (48 existing + 15 new); Solidity remains at 17.

In **terminal A** (leave it running):

```bash
python services/provider-agent/http_service.py --port 8877
```

In **terminal B** (existing venv):

```bash
export RPC_URL="http://127.0.0.1:8545"
export NEW_SSE="0x0DCd1Bf9A1b36cE34237eEaFef220932846BCD82"
python -m unittest discover -s tests -v
forge test -vv
python tools/sse_e2e_local.py --rpc-url "$RPC_URL" --settlement "$NEW_SSE"
```

The last command is **preflight only**: it checks the original lease, Anvil unlocked identities, committee pool and local HTTP service and changes nothing.

When it reports `PREFLIGHT_OK`:

```bash
python tools/sse_e2e_local.py --rpc-url "$RPC_URL" --settlement "$NEW_SSE" --execute --fast-forward
```

**Expected final printed status:** `SUCCESS_COMPLETE`, `quorumReached: true`, `finalEpoch.outcomeName: Success`, `providerCredited: 25`, `consumerCredited: 0`, `unresolvedExposure: 0` (wei). A brand-new lease will be created; old lease 1 remains untouched.

Artifacts: `.local/sse-e2e-runs/lease-<id>/run.json`, `provider_http_observation.json`, and `monitor_1..3_evidence.json`. Evidence commitments are shown per monitor in `run.json`; each hash is Keccak-256 of the compact JSON serialization with `sort_keys=True` and separators `(',', ':')`. These hashes are committed on-chain. **Do not delete the evidence artifacts** until you have completed your research demonstration. Keep this directory out of version control.

## What really happens

1. Verify the old on-chain lease 1 is completed and this is the known Anvil settlement and 31337 chain.
2. Create a new local *direct* lease (this demo does **not** submit a marketplace request/bid), fund 25 wei escrow, let provider accept.
3. Request committee randomness from the previously configured local randomness account, assign 4 monitors and confirm all four.
4. Consumer admits epoch 0 using a fresh challenge; inspect the real on-chain deadline and ensure localhost endpoint hash matches committed URL.
5. Probe provider HTTP service. Use Anvil's `eth_signTypedData_v4` for provider account, relay it to `submitProviderResponse`, verify on-chain authentication.
6. Three committee members each run their own HTTP probes from the **same localhost machine**, produce individual evidence files and Keccak commitments, sign EIP-712 `MonitorVote` with Anvil, and relay three success votes. The contract authenticates signers and quorum.
7. `--fast-forward` *simulates chain time advancement* using Anvil (`evm_increaseTime` and `evm_mine`). Seal monitoring, settle epoch, close evidence, close lease, release committee bonds, and verify final on-chain accounting.

## Important limitations

- Development-only: uses unlocked RPC accounts and time-control methods; **never point it at a public/forked production RPC**. It refuses non-loopback RPC, wrong chain ID, wrong settlement, and unknown baseline identities.
- Provider HTTP service remains **unsigned at the HTTP layer**; provider's EIP-712 response is authenticated separately on-chain. This demo does not prove that the HTTP server itself possesses the provider's signing key. Signatures come from **Anvil's unlocked accounts**; they are not distributed to independently operated monitor hosts.
- All three probes run on the **same local machine**. This is not independent monitoring, Byzantine safety, trusted timestamps, or real cloud provisioning.
- The response deadline check compares to chain block time. It is **not** an attestation of timely physical HTTP receipt; the synthetic time jumps must **not** be reported as genuine elapsed time.
- If execution stops partway through, transactions already mined are permanent in the running Anvil state. The output `run.json` records progress and transaction hashes; rerunning `--execute` creates a *new* lease. A failure is not a reason to reset Anvil or deploy a new contract.
- Local test validation is offline. This patch cannot be fully end-to-end tested without your running Anvil; send any terminal traceback and `run.json` checkpoint if it stops.
