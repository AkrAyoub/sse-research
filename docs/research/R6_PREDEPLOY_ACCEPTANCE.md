# R6 pre-deployment Ubuntu source acceptance

This experimental feature branch is **NOT accepted as a live VM deployment**. Its scripts must not be applied to real VMs until the following checks pass, the code is reviewed and a secure broker endpoint/tailnet is configured.

## Offline
Run from the repository root with Python 3.12 and pinned `requirements.txt`:

```bash
python -m unittest discover -s tests -p 'test_sse_vm_bootstrap.py' -v
python -m unittest discover -s tests -p 'test_sse_bootstrap_mesh_integration.py' -v
python -m unittest discover -s tests -p 'test_sse_node_console.py' -v
python -m unittest discover -s tests -p 'test_sse_vm_overlay.py' -v
python -m unittest discover -s tests -p 'test_sse_vm_enroll.py' -v
python -m unittest discover -s tests -p 'test_sse_mesh_broker.py' -v
python -m unittest discover -s tests -p 'test_sse_release_verify.py' -v
python -m unittest discover -s tests -q
forge build
forge test -vv
```

These tests do NOT prove that Tailscale was installed, that a broker is reachable, that the GitHub repository is publicly downloadable, that a VM is correctly configured, or that a chain settlement is physically true.

## Critical unimplemented integrations
- Approved reproducible signed Tailscale apt packaging and automatic installation on plain Ubuntu. The overlay scripts currently require a preinstalled `tailscale` binary.
- Explicitly authorized HTTPS enrollment server plus its scoped OAuth credentials, restricted `tag:sse-node` ACL and secure one-time token issuance workflow.
- The onboarding website still pins **97bd3d4**, which does not include these experimental extensions. Do NOT update the public pin until tests and provenance review pass.
- Public releases, signature key distribution, source-history secret scan, and version-compatible **download, staging, rollback and safe automatic activation**. The release verifier is read-only, not a running-code updater.
- Independent node wallets, role-local transactions, provider orchestration, monitor archives, and operational dashboards.
- Read-only chain observatory and per-node observability; global dashboard is not a controller for consumer/provider/monitor actions.

## Node ownership and dashboards
Each Ubuntu VM serves its *own* UI on loopback at `/ui`, selected by roles. For now it can persist authenticated, node-local draft numeric preferences that are explicitly marked **not applied to runtime or blockchain**. The independent global dashboard handles network observation and limited network metadata only. To reach the VM UI from the operator's browser, use a future authenticated overlay proxy; do not bind its HTTP service publicly.

## Next physical acceptance
Run on a disposable Ubuntu VM after provisioning a genuine chain RPC/contract and approved release. Record actual installer and systemd results, then validate 2+ independent Ubuntu VMs behind NAT with one shared RPC, private role-local UI, and correlated-failure experiments. The full four-monitor signatory independence goal remains separate.
