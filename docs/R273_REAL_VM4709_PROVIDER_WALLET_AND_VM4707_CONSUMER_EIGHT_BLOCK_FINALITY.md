# R273 — VM4709 physical provider host has real encrypted EOA; VM4707 consumer funded latest, 8 EL blocks from finality

Actual operator logs on 2026-11-24 prove two independent runtime events.

## VM4707 — exact first consumer funding transaction succeeded, canonical, near-final

- R271 actual 5 focused tests PASS at Git SHA `4eafadae5e27a6bc5ff6467c3a76996858dbdcb5` and actual live R271 one-shot read-only PASS.
- Exact one-time actual owner-authorized consumer funding tx `0x9f3a13cb295b5ba2f642804a30c391b9cce266784a83dd293d0dd7fb7d1f9fdd`: successful and canonical included at EL block **25564**.
- Original chain31340; actual EL head **25697**, finalized EL block **25556**; the receipt remains **8 blocks short** of finality.
- Consumer real `latest` balance `10000000000000000 wei` (**0.01 TEST ETH**), balance at finalized height `0`. This is real TEST ETH, not a simulated balance.
- Beacon head slot **27309**, epoch **853**; finalized epoch **849**, lag4; original Beacon genesis root verified and not optimistic.
- **No Monitor 1 nonce2** and **no Monitor 2 nonce3** funding has been sent. R267 safety gate is correct. Never replay consumer nonce1, remove attempt marker, bypass finality or restart validators.

## VM4709 — real Docker PoS node present and new resource-provider key created

- Owner actually ran R272 **7 focused tests PASS** on real VM4709 at Git SHA `a52050f89a7bce7e811eced98ab3e57aa7303db6`.
- R272 actual host read-only probe PASS with **4 logical CPUs**, **11,272,003,584 bytes MemAvailable**, **97,732,464,640 bytes free disk**, source username `ayoubakrvm4709`.
- Unprivileged `docker ps` was denied due to UNIX socket permissions `uid0/gid112 mode0660`. This is **NOT** a daemon failure: actual `sudo -n docker --host unix:///var/run/docker.sock ps` succeeded and showed BOTH real native original-chain31340 containers:
  - `sse31340-r137-node-8be265272c35f3d8c3a0-bn`: Up 30 hours
  - `sse31340-r137-node-8be265272c35f3d8c3a0-el`: Up About an hour (healthy)
- Owner created isolated Python virtual environment under `$HOME/.local/share/sse-v2-app-only/pyvenv`, installed actual pinned requirements (`eth-account==0.14.0`, `pycryptodome==3.23.0`, `eth-abi==5.2.0`); `eth_account` absent in SYSTEM Python is NOT an outstanding blocker for the new venv.
- Owner ran `tools/sse_pos_test_wallet.py --role adaptive-v2-provider --apply` in private owner-local 0700 directory. Actual encrypted new **provider EOA**:
  `0xBbd4F07be80E1f4c40A1b470A180C0F38352bEaf`,
  keystore `/home/ayoubakrvm4709/.local/share/sse-v2-app-only/adaptive-v2-provider.keystore.json`.
  Output `walletCreated:true`, `encryptedWithPassphrase:true`, `privateKeyPrinted:false`, `passphraseStored:false`, `testFundsCreated:false`, `ethereumTransactionsSent:false`. No secrets committed or copied between hosts.
- No provider wallet funding, onchain bid, advertised public authenticated HTTPS resource, Docker compute worker, provider-signed reply, independent service SLA or fee settlement yet.

**Critical operational blocker**: Although privileged `sudo docker ps` works, existing provider worker runtime `services/provider-agent/v2_compute_response_server.py` calls `tools/sse_compute_docker.py:inspect_container()` using **unprivileged `docker container inspect`** on every request. That WOULD FAIL with the observed current Docker socket permissions. Do NOT misrepresent sudo read-only inspection as a ready continuously running nonroot compute provider; do NOT casually add the owner to privileged `docker` group, loosen socket mode, or move/restart PoS containers. Prepare a properly isolated rootless worker or a strictly limited read-only Docker status broker before serving public workloads.

## Next exact continuation

### Consumer -> Monitor 1 nonce2

The original R267 sender source at Git SHA
`4eafadae5e27a6bc5ff6467c3a76996858dbdcb5` has already been tested with nine focused owner VM4707 regressions at an earlier matching R267 code. It is safe to run on the original exact private checkout, **only once if it successfully sends**. It first validates the prior actual consumer tx (exact fields, successful status, current canonical inclusion, and execution finalized height), then only when successful asks for the Monitor1 exact EOA value **0.005 TEST ETH**, nonce **2**, 21000 gas * 1000 wei and hidden passphrase. If finality is still lagging, this is a no-effect refusal. No polling and no automatic retry after marker creation. Later Monitor2 nonce3 similarly requires Monitor1 success and finality.

### Real VM4709 worker setup planning

Actual source worker pieces exist:
`Dockerfile.sse-compute` builds a real Python CPU-worker container, `tools/compute_workload.py` runs 8192 actual SHA256 rounds bound to lease+epoch+requestHash, and `services/provider-agent/compute_http_service.py` serves HTTP `/v1/compute`. The finalized-real-lease EIP712 provider wrapper `services/provider-agent/v2_compute_response_server.py` **cannot** be started before a funded, finalized real lease/epoch; nor can it pass its strict per-request Docker audit until an owner-approved nonroot Docker inspection path is available. Worker image must have exact pinned digest in resource commitment, strict resource limits, no root privileges, no public plaintext port and an authenticated HTTPS reverse proxy. **No worker has been built or run yet.**

Public machine/operator evidence remains restricted: three VM4707 consumer+monitor role identities are not independent; a VM4709 provider EOA is on another real host but may share administrative infrastructure; no arbitrary untrusted public Internet admission proven. All role transactions beyond the specific approved consumer/monitors funding allocations need new explicit owner authorization.
