# SSE incremental patch B1 — read-only on-chain inspection

This patch adds `tools/sse_chain_read.py`; it changes **no Solidity contracts**, existing HTTP services or dependency files.

## Install

Extract the ZIP **into your existing SSE project root**; it adds the new tool and new test file only. Keep your localhost Anvil RPC running.

## Commands (Git Bash)

```bash
source .venv/Scripts/activate
export RPC_URL="http://127.0.0.1:8545"
export NEW_SSE="0x0DCd1Bf9A1b36cE34237eEaFef220932846BCD82"
python tools/sse_chain_read.py --rpc-url "$RPC_URL" --settlement "$NEW_SSE" --lease-id 1 --epoch-id 0
python -m unittest discover -s tests -v
forge test -vv
```

Expected schema is `sse-onchain-inspection-v1`. You will see `status: EPOCH_FOUND` if lease 1 has an admitted epoch 0, or `status: NO_EPOCH_ADMITTED` if its `nextEpochId` is still zero. The real result depends on your running Anvil state.

The tool validates chain ID 31337, contract code, domain separator, lease existence and status. For admitted epochs, it validates the request/response hash relation, reads the deadline trio, and displays both local wall time and the snapshot block time. **It does not certify response timeliness**, sign votes, or perform new transactions.

The optional `--endpoint http://127.0.0.1:8877` argument checks the exact service endpoint commitment; do not supply it if your existing lease used a different test endpoint hash. A commitment mismatch deliberately exits with status code 2.

Next increment, after seeing your actual lease and epoch values: bind the existing HTTP monitor to the correct on-chain challenge, timing and resource manifest. Never treat the earlier manually chosen `REQUEST_HASH` as on-chain unless the inspection proves it matches.
