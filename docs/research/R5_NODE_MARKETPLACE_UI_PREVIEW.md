# R5 Ubuntu role-local marketplace preview — implementation checkpoint

**Status:** source and offline regression tests committed; **not yet validated by the operator's Python suite, not deployed, not a transaction-sending browser UI**.

## Ownership and environment

- Consumer/provider/monitor machine hosts its own **loopback-only** `http://127.0.0.1:8765/ui` page. The global dashboard does not issue participant actions.
- The node UI retains existing authenticated draft preferences and now offers a **transaction preview** for its configured role(s), using the exact R5 `tools/sse_node_marketplace.py` contract planner.
- A local owner token is required to call `POST /v1/transaction-plans`. Calls fail closed when the node does not have public network contract addresses or when the role is not owned by this node.
- This endpoint **never contacts Ethereum RPC, sends funds, signs transactions, reads wallet keys, or starts providers/monitors**. It responds with `previewOnly=true`, `canBroadcastHere=false`, `ethereumTransactionsSent=false`.
- The initial bootstrap now accepts optional **public** `--board` and `--committee-pool` paired arguments, in addition to the existing `--settlement` and `--chain-id`. If both are provided, systemd configures the node-local UI with `SSE_CHAIN_ID`, `SSE_BOARD_ADDRESS`, `SSE_SETTLEMENT_ADDRESS` and `SSE_COMMITTEE_POOL_ADDRESS`. Neither signing secrets nor RPC credentials belong in systemd unit text.
- With no board/pool, previous first-boot behavior remains available and the preview endpoint returns an explicit unavailable response.

## Operational limitations

The local node must independently manage its transaction signer and use the separate `sse_node_marketplace.py --execute` command with an explicit spend limit for genuine transfers. That existing path is a **lab-only** signer adapter. Node-local approval/transaction submission from the browser is **not** implemented; neither is a production signer, on-chain event indexer, autonomous bidding scheduler, protocol finality verification or remote VM installation.

A real browser on another device cannot directly reach a loopback-bound service on a remote VM. Future work must provide an authenticated overlay proxy without exposing this token or allowing unauthenticated internet access.

## Offline acceptance

```bash
python -m unittest discover -s tests -p 'test_sse_vm_overlay.py' -v
python -m unittest discover -s tests -p 'test_sse_node_marketplace_ui.py' -v
python -m unittest discover -s tests -p 'test_sse_bootstrap_marketplace_ui.py' -v
python -m unittest discover -s tests -q
```

The new branch includes the test fix for the previously reported fake `Path` command argument. The corrected test mocks the actual filesystem operation and expects the literal POSIX file path in Tailscale's `--auth-key=file:` argument.

Do not enable the `--apply` installer or execute actual transaction commands against placeholder addresses. All new code remains experimental until tests are green and a verified Ubuntu/Anvil deployment is available.
