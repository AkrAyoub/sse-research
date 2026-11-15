# R8: Independent read-only blockchain explorer (first integration slice)

**Status:** source committed, offline tests authored, **not yet run by operator**. No VM, deployment, RPC, remote node, wallet, or Ethereum transaction was touched by this branch.

## Scope and authority

The independent SSE network dashboard is an observer and basic network-config surface. It does **not** own participant identity or control consumer bids, provider pricing, monitor votes, node workloads or role-local wallet custody. Participant transactions are prepared and approved in the respective Ubuntu VM-local interface, not here.

New authenticated read-only chain endpoints in `apps/control-plane/api.py`:

- `GET /v1/chain/overview` — chain ID, latest head, configured contract addresses and whether they have code
- `GET /v1/chain/blocks?limit=10` — last up to 20 blocks, headers, transactions, gas usage
- `GET /v1/chain/transactions/{hash}` — receipt, gas, inclusion depth and raw event topics (no role impersonation)
- `GET /v1/chain/events?start_block=N&end_block=M` — bounded 256-block window over configured SSE contract allowlist

The dashboard provides a textual blockchain explorer view and is safe to inspect with the **read-only** API token. All calls use allowlisted JSON-RPC **read** methods. No signing, no broadcast, no access to wallet keys, no remote shell. Browser renders RPC-origin text using DOM `textContent`, not raw HTML injection.

### Configuration

On the **separately hosted network dashboard** (not the consumer/provider/monitor VMs):

```bash
export SSE_CONTROL_TOKEN='<operator-admin-token>'
export SSE_READ_TOKEN='<observer-readonly-token>'
export SSE_OBSERVER_RPC_URL='https://<APPROVED-ETHEREUM-RPC-ORIGIN>'
export SSE_OBSERVER_CHAIN_ID='11155111'
export SSE_OBSERVER_CONTRACTS='<COMMA-SEPARATED-DEPLOYED-BOARD,SETTLEMENT,COMMITTEE-ADDRESSES>'
```

Anvil on Ubuntu can be reached via a separately configured authenticated HTTPS/overlay reverse proxy. `127.0.0.1` refers to whichever machine runs this dashboard, **never to the Windows dev machine or some other Ubuntu VM**.

No observer endpoints are active unless the required RPC, chain ID and addresses are configured. RPC requests are bounded in size/time, disallow redirects, reject user-supplied arbitrary RPC methods and constrain event queries to allowlisted contracts. Responses remain provisional because a single RPC cannot independently prove canonical history/finality.

**Not yet included:** ABI topic decoding and settlement timelines, persistent reorg-aware event indexing, synchronized off-chain evidence archive, live stream/websocket probe logs, automatic node discovery/heartbeat into dashboard, historical benchmarking and operator configuration approvals. The UI is an initial read-only explorer, not an accepted R8 exit gate.

### Testing

```bash
python -m unittest discover -s tests -p 'test_sse_chain_observer.py' -v
python -m unittest discover -s tests -p 'test_sse_dashboard_chain_routes.py' -v
python -m unittest discover -s tests -p 'test_sse_vm_overlay.py' -v
python -m unittest discover -s tests -p 'test_sse_node_marketplace_ui.py' -v
python -m unittest discover -s tests -p 'test_sse_bootstrap_marketplace_ui.py' -v
python -m unittest discover -s tests -q
```

All newly written tests are offline/mock-based; no real RPC or browser integration acceptance is claimed. Foundry's 127 previously passed test results were reported separately by the operator and have not been rerun on this branch.
