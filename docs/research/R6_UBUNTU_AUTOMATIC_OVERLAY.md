# R6 — Ubuntu mesh enrollment primitive (research implementation)

**Status:** source implemented, offline tests authored; no real VM, Tailscale tailnet, authentication broker or RPC connection validated.

## Design boundary

All participant machines are Ubuntu VMs. Windows is not part of the deployed network. Each VM owns its role configuration and wallet signing. The independent dashboard is for network-wide read-only observability and limited operational settings; consumer/provider bidding and pricing belong to the corresponding VM-local UI.

Node discovery uses an outbound-only Tailscale overlay in the first Ubuntu lab, with stable node IDs and authenticated mesh addresses. An administrator first configures a tailnet, a restrictive `tag:sse-node` ACL and an authorized provisioning broker that issues short-lived tagged keys. No manual per-VM login to Tailscale is needed after that one-time setup.

## Primitive implemented

`tools/sse_vm_overlay.py` defaults to a read-only plan. On Ubuntu root `--apply` it checks a root-owned 0600 key file under `/run/sse` or `/etc/sse`, invokes the installed Tailscale client with `--auth-key=file:...` (not a literal key in argv), checks JSON online status and removes a successfully consumed one-time key. It does not install Tailscale or mint enrollment keys, cannot register an on-chain monitor and does not deploy/sign Ethereum transactions.

Example PLAN only (placeholder path must later be provisioned by enrollment broker):

```bash
python3 tools/sse_vm_overlay.py --node-id provider-vm-01 --roles provider --auth-key-file /run/sse/one-time.key
```

**Do not run `--apply` until** the secure broker, signed package source, correctly scoped Tailscale ACL/tag ownership and Ubuntu test machine are ready. Incomplete/failed enrollment must not be represented as joining SSE on chain.

## Follow-on work (critical)

1. Add broker endpoint with approved one-time node enrollment credentials; mint tagged short-lived Tailscale auth keys from broker-held OAuth, never include OAuth secrets in a public script.
2. Install Tailscale from an operator-approved pinned Ubuntu package source within the SSE bootstrap and automatically call this primitive.
3. Add node-local role UI and APIs and a separate network-only observer console; never centralize consumer/provider signing in the dashboard.
4. Add signed-release polling, immutable staged updates, mixed-version/active-lease safety, health validation and rollback.
5. Test two Ubuntu VMs without public/static IPs, overlay discovery, failure/reconnection, peer HTTP probes, independent wallets and on-chain network interactions.

Record offline tests with `python -m unittest discover -s tests -p test_sse_vm_overlay.py -v`; actual Ubuntu integration remains unverified.
