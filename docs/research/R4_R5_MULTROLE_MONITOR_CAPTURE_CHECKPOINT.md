# R4/R5 — Multi-role monitor evidence from the funded marketplace

**Status: source and tests committed on research branch, but NOT YET EXECUTED ON THE OPERATOR'S MACHINE.** The previous checkpoint `e5196d9` passed 633 Python tests (627 passed, six skipped), built the Docker compute image, and passed the opt-in combined Anvil+Docker selected-provider workflow. The separate one-container Docker test was skipped due to a transient/unavailable engine check; its execution is not accepted as passed.

## One node can have several roles

A **node is an independently operated Ubuntu VM**, and its **roles are local capabilities**, not globally privileged accounts. The bootstrap previously allowed `--roles consumer,provider,monitor,observer`, but only installed a read-only status/preview console; it did not start autonomous role daemons. This increment introduces an **explicit** small public `sse-node-roles-v1` manifest and a role-owned one-shot monitor capture tool, without turning the dashboard into a signer or controller.

Example *public, non-secret* role manifest on one Ubuntu node:

```json
{
  "schema": "sse-node-roles-v1",
  "nodeId": "vm-compute-and-monitor",
  "roles": ["provider", "monitor", "observer"],
  "wallets": {
    "provider": "0x1111111111111111111111111111111111111111",
    "monitor": "0x2222222222222222222222222222222222222222"
  }
}
```

These are illustrative public wallet IDs, **not deployed/approved keys**. Each role uses a **different private signer** and the monitor code refuses an assignment when the node's disclosed provider or consumer wallet matches **either** party to that lease. It also requires the monitor's own wallet to appear among the **four selected and confirmed** Ethereum addresses from a pinned chain inspection.

**Crucial limitation:** separate addresses and locally declared roles DO NOT prove independence of owners or machines. A dishonest node can conceal a wallet it controls. Sybil/operator identity, capacity and physical fault-domain attestation remain open research/production tasks.

## Monitor-visible provider challenge: gated on real consumer receipt

The winning provider's `services/provider-agent/direct_work_service.py` now exposes **`POST /v1/challenge`** alongside the previously tested `/v1/work` and `/v1/receipt`. Unlike the old standalone lab provider, this handler:

1. Refuses to sign until a **consumer-signed receipt was verified and stored** for that lease and epoch (SQLite in real `--serve`, memory only in lab fixtures).
2. Pins an on-chain snapshot and checks the active **funded marketplace** lease, selected provider wallet, epoch/request hash, SLA policy hash, resource profile hash and exact endpoint commitment.
3. Requires four assigned/confirmed monitors, open monitoring/evidence window, and no sealed evidence.
4. Returns a **Solidity V1 ProviderResponse EIP-712 signature** for the exact admitted challenge. This signature is **NOT** a signature over Docker result bytes; the separate off-chain `SSEProviderWorkResult` signature still binds the actual deterministic compute result. Neither proves a physically certified SLA.

The challenge is intentionally **not** an arbitrary sign-anything endpoint. Malformed, wrong-lease, wrong-wallet or pre-receipt requests are refused.

## R4 signed raw evidence on the monitor node

`services/monitor-agent/monitor_capture_once.py` is **dry-run by default**, which validates role, SLA and resource manifests without contacting RPC or sending HTTP. An explicit `--capture` on the monitor's own VM:

1. Reads its own owner-controlled signer file (not another node's secret), and verifies its public address against the node's monitor role manifest.
2. Obtains a read-only **block-hash-pinned** view from the configured RPC. The RPC view is trusted as an external input—not an independently verified Ethereum PoS finality proof.
3. Verifies that the node is not a local consumer/provider counterparty and that its monitor wallet is **selected and confirmed** for this real funded lease.
4. Reuses `sse_wp08c_chain_binding`, `sse_http_signed_delivery_v1`, `sse_evidence_wire_v1`, `EvidenceArchive` and signed R4 chain provenance. Validates the provider's EIP-712 signature, signs the monitor's own raw HTTP observation and block identity, and persists those records in the monitor-owned SQLite archive.
5. **Does not** create an on-chain vote, settle escrow, infer missed consumer delivery from an HTTP timeout, slash provider/monitor bonds, or verify independent operator identity.

### Private transport

For local tests, numeric `http://127.0.0.1:<port>` is allowed. For independently hosted Ubuntu nodes, only a lease-committed `https://<device>.<tailnet>.ts.net` origin is allowed. The underlying urllib opener deliberately disables redirects and environment HTTP(S) proxies; TLS uses normal certificate validation. The upstream provider must be exposed by **authenticated Tailscale Serve HTTPS with correct tailnet ACLs**, not a publicly forwarded non-TLS port. Enabling an HTTPS origin in source **does not install Tailscale or deploy a monitor VM**. Raw evidence capture over private HTTPS is also prohibited without explicit pinned-chain binding/provenance.

This is a one-shot capture tool, **not yet an autonomous monitor daemon** that watches assignments, handles retries, or gathers independently certified negative evidence. Timeouts remain indeterminate.

### Safe review and validation

```bash
git status --short
git fetch origin research/r4-r5-multirole-monitor-challenge-no-ci
git switch --detach origin/research/r4-r5-multirole-monitor-challenge-no-ci
git rev-parse --short HEAD
python -m unittest discover -s tests -p 'test_sse_monitor_multirole.py' -v
python -m unittest discover -s tests -p 'test_sse_direct_journal.py' -v
python -m unittest discover -s tests -q
```

The new offline suite includes actual EIP-712 provider and monitor signatures, a loopback HTTP `/v1/challenge` exchange, rejection of attempts before consumer receipt, raw observation archival, multi-role counterparty conflict tests, canonical Tailscale HTTPS allowlisting and a **fresh dry-run CLI**. These sources/tests are **not yet operator-validated**.

Optionally repeat the real funded integration after `forge build`:

```bash
SSE_RUN_ANVIL_INTEGRATION=1 python -m unittest discover -s tests -p 'test_sse_direct_delivery_anvil.py' -v
```

It now additionally tests a **real selected monitor** obtaining the winning provider's signed challenge, saving an EIP-712 monitor observation and signed block-hash anchor in a separate SQLite archive, and verifying the stored evidence. It deliberately checks that no monitor vote was sent. This Anvil path uses actual selected EOA addresses on **one development host**; it is not a multi-VM operator-independence test.

### Next practical work

- A node-local **role supervisor**/systemd user separation for provider, consumer, monitor and observer services, safe updates and restart policy
- Autonomous monitor chain event scheduler (discover selection, confirm on-chain via owner-controlled approval, schedule probes by admitted epoch)
- Independent Ubuntu VMs, Tailscale enrollment/Serve ACLs, cross-host multi-role fault injection
- Witness operator independence, observation quality and physical receipt/adjudication, preserving N/F/S uncertainty
- Per-service latency/availability/compute-provisioning monitoring, storage/API/OCI SLA adapters, and dashboard raw evidence indexing
- Do not automate on-chain failure votes or money-releasing settlement until evidence qualification is reviewed
