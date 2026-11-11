# WP-08B — Signed HTTP evidence through independent local processes

**Scope:** research-only **positive observation** path, not a new Solidity payout rule or remotely verifiable SLA. No changes to the deployed SSE V1 contracts. The first test environment is loopback HTTP. HTTPS remote operation, actual lease authorization, canonical chain finality and truthful physical event clocks are later acceptance gates.

## Why this increment

WP-08A defines a signed monitor observation, but the old localhost HTTP provider does not produce the EIP-712 `ProviderResponse` that `signed_probe` requires. WP-08B connects those real components and persists evidence across process restarts. It intentionally avoids treating provider-signature success as proof of delivery to the contracted consumer.

## Exact path implemented

```
operator supplies one pinned (chain, SSESettlement, lease, epoch, request) tuple
    |
    v
signed_http_service.py  --loopback only, provider key read from environment
    | expected_response_hash(requestHash), SSESettlement v1 ProviderResponse EIP-712 signature
    v
HTTP /v1/challenge (same field names consumed by existing signed_probe)
    | response bytes bounded to 4,096, retained exactly
    v
evidence_capture.py / sse_http_signed_delivery_v1.py
    | parse strict JSON; verify V1 provider signature and scope
    | create monitor WP-08A ObservationRecord(RESPONSE_SEEN)
    | payloadHash commits to exact received bytes; report-time interval is untrusted
    | sign WP-08A EIP-712 SSEObservation
    v
EvidenceArchive(SQLite)
    | atomically reverify both provider and monitor signatures + raw payload hash
    | unique (chain, settlement, lease, epoch, monitor, nonce); idempotent duplicates
    | recheck both signatures and raw bytes on retrieval; survives process restart
    v
WP-07 RawObservation only; ALL {N,F,S} remain for physical consumer delivery SLA
```

**No direct `QualifiedFact` construction, on-chain vote, or escrow credit is authorized by this increment.** The legacy V1 3-of-4 behavior is unchanged.

## Why two separate signatures?

- **Provider V1 `ProviderResponse`:** `SSESettlement` domain, chain ID and settlement contract; message contains `leaseId`, `epochId`, `requestHash`, `responseHash`. This is the preexisting Solidity-compatible EIP-712 type; the provider key is controlled by the laboratory process. The provider signature does **not** commit to SLA/resource hashes and cannot prove physical receipt or computer-resource delivery. The test responder pins an exact challenge to avoid being a universal signing oracle.
- **Monitor WP-08A `SSEObservation`:** signs the exact monitoring scope including SLA and resource commitments and `payloadHash` of the provider's **raw HTTP body bytes**, as well as observation kind and untrusted clock interval. Its domain is intentionally different from Solidity V1 and must not be passed as a V1 on-chain vote. Monitor authorization is a *caller-supplied trusted set*, not independently fetched from finalized chain state.
- **Archive:** persist both signed statements and unmodified provider HTTP bytes, reverify them on retrieval. A writable disk operator can still delete the archive or rewrite history. SQLite transactions are crash-consistent, not Byzantine immutable; later work needs external commitment and replication.

## Local reproduction (Git Bash / Windows)

Start from repository root, with `.venv-r0` installed using `requirements.txt` and Foundry available. These commands use **known unsafe lab-only keys**; NEVER use actual funded account keys.

Terminal A:

```bash
export SSE_WP08B_PROVIDER_KEY="0x$(printf '21%.0s' {1..32})"
./.venv-r0/Scripts/python.exe services/provider-agent/signed_http_service.py \
  --port 8878 --chain-id 31337 --settlement "0x$(printf 'cd%.0s' {1..20})" \
  --lease-id 4 --epoch-id 2 --request-hash "0x$(printf '01%.0s' {1..32})"
```

Terminal B:

```bash
export SSE_WP08B_MONITOR_KEY="0x$(printf '22%.0s' {1..32})"
export SSE_WP08B_PROVIDER_ADDR="$(./.venv-r0/Scripts/python.exe -c 'from eth_account import Account; print(Account.from_key("0x"+"21"*32).address)')"
./.venv-r0/Scripts/python.exe services/monitor-agent/evidence_capture.py \
  --endpoint http://127.0.0.1:8878 \
  --chain-id 31337 --settlement "0x$(printf 'cd%.0s' {1..20})" \
  --lease-id 4 --epoch-id 2 \
  --sla-policy-hash "0x$(printf '02%.0s' {1..32})" \
  --resource-profile-hash "0x$(printf '03%.0s' {1..32})" \
  --request-hash "0x$(printf '01%.0s' {1..32})" \
  --provider "$SSE_WP08B_PROVIDER_ADDR" --archive "$HOME/sse-wp08b-evidence.sqlite"
```

The address, hash and deadline values are **synthetic** and do not correspond to a funded chain lease. These commands demonstrate interoperability, not authorization. `evidence_capture.py` prints the new evidence commitment and explicitly disclaims consumer delivery.

## Tests and acceptance

- `python -m unittest discover -s tests -p 'test_sse_http_signed_delivery_v1.py' -v`
- `python -m unittest discover -s tests -v`
- `forge test -vv`
- Tests include independent provider/monitor OS subprocesses, existing V1 signed-probe compatibility, pinned challenge rejection, malformed signatures, wrong scope, duplicate JSON, provider-response tampering, unauthorized monitor, nonce collision, restart persistence, archive corruption, and negative network response **not** being minted as proof of contractual failure.
- Actual counts, OS compatibility, skips, and CI must be recorded after execution; do not infer success merely from the existence of test code.

## Open decisions / follow-on (WP-08C / R3 / P1)

1. **Finalized chain binding:** Query expected provider, lease/epoch/request commitments, selected-confirmed monitor keys, policy hash and resource hash using chain identity plus independently authenticated chain state. RPC configuration alone is not a finality proof.
2. **Durable verifiable evidence availability:** Content-addressed archive with cross-host replication and immutable on-chain/off-chain checkpoints, atomic nonce storage, retention and evidence dispute recovery.
3. **Physical delivery certificates:** Monitor seeing a valid provider reply does *not* prove that the intended consumer received a correct response on time. Qualifying physical facts requires separate semantics, trusted clocks and suitable attestation assumptions.
4. **True distributed operation:** Keep localhost restriction until HTTP/TLS authentication, hostname/SSRF policy and network integration are reviewed; then run separate NAT/cloud nodes with realistic delays and failures.
5. **R3 scalability:** Expandable registry, unbiased/verifiable selection, flexible committee size/quorum, Sybil resistance, replacement for no-show monitors and consumer-independent bond release remain unsolved. Four monitors in current V1 are not the target architecture.
6. **Current technical limits:** Provider signing key is in an environment variable on a lab process, signed response is precomputed for the pinned request, and archive DB may be erased or replaced. Neither proves request was physically received by the service.
