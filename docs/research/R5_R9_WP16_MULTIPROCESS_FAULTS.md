# WP-16 — Distinct-process provider/monitor experiments with reproducible local faults

**Status: implementation accepted in hosted GitHub Actions.**

## Research motivation and boundary

WP-15 finally deployed the funded V2 lease, pool, mock-VRF adapter, local provider and historical evidence archive against a **real Anvil RPC**. However, its signed provider and monitor activities were executed in one Python process, so it had not demonstrated agent process separation, crash isolation, failure injection or later recovery by another independently keyed signer.

WP-16 uses the same deployed V2 contracts but runs **three separate OS process roles** on one host:

1. A parent consumer/orchestrator process opens and funds the lease, drives contract selection/confirmation on Anvil, coordinates fault cases and checks balances.
2. A child HTTP provider process on `127.0.0.1` signs the exact pinned HTTP challenge with a designated Anvil provider key read only from `SSE_WP16_LAB_PROVIDER_KEY`. The process supports bounded delay and HTTP 503 faults.
3. A separate child monitor process reads the current Anvil state using the strict WP-13 EIP-1898 V2 authority adapter, authenticates its own selected/confirmed ticket and the provider EIP-712 response, and commits the original historical block reference plus both signed records with WP-14's atomic SQLite archive. It gets its key only from `SSE_WP16_LAB_MONITOR_KEY`.

**All processes run on the same machine and communicate over numeric IPv4 loopback.** Process isolation is real; independent machine/network administration, WAN TLS and availability assumptions are **not** established. The consumer's upstream contract transactions use Anvil's intentionally unlocked public development accounts, and the coordinator is a fake lab VRF source.

## Exact participant interactions

```text
                  [ANVIL 31337 — real deployed EVM]
                         |                  ^
                         | real RPC         | signed transactions
                         v                  |
[Consumer / experiment orchestrator, PID-A]
  - launches WP15 prepare-only: funds lease, requests V2 pool assignment
  - registers 8 monitor accounts, selects 4, collects on-chain confirmations
  - activates lease, admits one unresolved epoch
  - records deployment addresses, SLA/profile/request/endpoint code commitments
         |                                           |
         | launches separately                       | launches separately
         v                                           v
[Provider child, PID-B]                     [Monitor child, PID-C]
  - fixed localhost /v1/challenge              - reads chainId and actual V2 state
  - EIP-712 provider signature                 - EIP-1898 pinned to a block hash
  - healthy / delay / 503 fault                - reconstructs selected confirmed seats
         |                                      - checks funded pending epoch, SLA, profile
         |---- signed HTTP bytes or fault ----> - verifies provider + monitor EIP-712
                                                - atomic SQLite raw + historical block
                                                - reports success/failure class
         |                                           |
         +---------------------> orchestrator <------+
                                 |
                          verifies on-chain
                          providerWithdrawable == 0
                                 |
                     after deadline: release pool
                       and stop epoch admissions
                                 |
                    current authorization FAILS
                    historical entries still PASS
                    tampered stored bytes FAIL
```

No monitor response or local transport error submits a settlement transaction. The V2 controller still requires exact **bilateral EIP-712 allocations** to move pending funds.

## Seven fault cases and acceptance expectations

| Case | Provider process | Monitor | Expected evidence archive | Meaning |
|---|---|---|---|---|
| healthy | Valid signer and complete HTTP response | Selected A | One new signed RAW record | Correctly authenticated local response at this monitor |
| delayed_timeout | HTTP handler sleeps 1.6s | Selected A; HTTP timeout 0.35s | No new record | Monitor-local timeout only; does not establish consumer failure |
| http_503 | Provider returns 503 | Selected A | No new record | Visible provider HTTP fault, not independent SLA nonperformance |
| provider_offline | No provider process listening | Selected A | No new record | Connection refusal, not consumer nonreceipt proof |
| wrong_provider_signature | Different Anvil key signs expected fields | Selected A | No new record | Response rejected as not signed by committed provider |
| unselected_monitor | Valid provider response | Unselected account 10 | No new record | Monitor private key cannot override on-chain committee membership |
| recovered_selected_monitor | Valid provider recovers | Different selected monitor B | Second new signed RAW record | Subsequent successful capture and independent signer provenance |

All cases use a fresh nonce. The SQLite record count must be **1 through the five fault cases**, and then **2 after recovery**. The process IDs for consumer, provider and monitor must be distinct whenever the provider is running. RPC, provider and monitor keys are scoped to a freshly empty Anvil chain with its publicly known default test mnemonic.

### Historical integrity follow-up

After the seven experiments, WP-16 advances the Anvil clock to the pool service deadline, calls pool expiry and ends admissions. At that point **current authorization fails**; both previously archived records must still verify using their independently anchored original historical block.

One stored provider byte envelope is then overwritten with `{}` directly via SQLite, and historical verification must reject it. Restoring the exact original signed bytes must make the record verifiable again.

The provider's credited balance is checked after **every** experimental case, and again after the pool is released: it remains zero because raw monitor evidence never authorizes a unilateral provider payout.

## Source inventory

- `scripts/wp15_anvil_v2_e2e.py`: adds a `prepare_only=True` option that constructs the funded and live lease, returns a sanitized manifest, and does not launch an in-process provider. Default WP-15 mode remains unchanged and still has its own CI.
- `services/provider-agent/wp16_fault_provider.py`: separate HTTP server process with healthy, injected delay and HTTP 503 modes.
- `services/monitor-agent/wp16_v2_monitor.py`: separate monitor CLI, chain-derived committee and pending epoch verification, provider authentication and atomic evidence persistence; exposes only structured status and no private key.
- `scripts/wp16_multiprocess_fault_lab.py`: creates all child processes, runs seven cases, records elapsed milliseconds and PIDs, verifies durable evidence, checks on-chain provider credit and post-closure historical evidence.
- `.github/workflows/wp16-multiprocess.yml`: reproducible fresh-Anvil CI with sanitized `wp16-multiprocess-faults.json` artifact only; does not upload Anvil startup logs.

## Verified hosted execution

An initial hosted run reached the healthy monitor's EIP-712 capture, created a valid archive entry and exited successfully, but the **orchestrator's own expectation** erroneously treated the success status as if it should exit with code 2. This was corrected by mapping `RAW_OBSERVATION_ARCHIVED_NOT_QUALIFIED` to exit code 0, while all explicitly rejected cases require exit code 2. Neither contracts nor evidence-authorization rules were changed.

Corrected run:
- [WP-16 independent process lab](https://github.com/AkrAyoub/sse-research/actions/runs/43223547248): **7/7 cases passed**; 2 signed RAW records; historic verification and tamper rejection passed; zero provider payout from monitoring.
- [WP-15 inherited real-Anvil scenario](https://github.com/AkrAyoub/sse-research/actions/runs/43223547245): passed unchanged.
- [Inherited Python + Solidity regression CI](https://github.com/AkrAyoub/sse-research/actions/runs/43223547243): Python **410/410** on Ubuntu and Windows, Foundry **124/124**, zero failures/skips.
- [Download machine-readable case/transaction trace](https://github.com/AkrAyoub/sse-research/actions/runs/43223547248/artifacts/13946304169). Trace contains PIDs, status categories, local elapsed durations, archived IDs and transaction receipts; do not interpret local latency numbers as an independent WAN distribution.

## What is not established

- **No remote host independence:** all processes and SQLite/Anvil use one host and the same operating-system administrator. An administrator can influence clocks, network and storage. R9 distributed evaluation is still largely open.
- **No TLS or remote endpoint trust:** the provider remains `http://127.0.0.1:PORT` and is deliberately not reachable via a public interface.
- **No physical delivery proof:** a signed response seen by a monitor is distinct from the consumer receiving correct service; a local timeout is not an objective N/F/S verdict.
- **No real cryptographic VRF:** the funded service's selected committee is generated using the unsafe Anvil-only coordinator substitute, not a live independently verified Chainlink VRF proof.
- **No independent consensus proof:** the Anvil RPC is trusted; `latest` is explicitly unfinalized. Code digests are taken from the experimental deployment itself rather than an external trusted manifest.
- **No automatic dispute resolution:** if the consumer/provider disagree, admitted escrow remains unresolved until both sign a split; the original research objective of safe automatic bound-driven settlement is not satisfied.
- **No user-operated wallet/UI:** the consumer agent uses scripted transactions and public lab keys, not production MetaMask or Scaffold-ETH 2 frontend.

## Recommended next validation gates

1. Review/merge upstream research PR chain **#9 → #10/#11 → #12 → #13 → #14 → #15**, retarget and rerun each base; then retarget this WP-16 PR. V1 WP-08C #8 stays separate until reviewed. Do not merge drafts without code review.
2. Run **at least three administratively independent machines/containers with isolated clock, network and storage trust domains**; migrate from loopback to authenticated remote TLS, fail closed on redirects/proxy abuse and explicitly handle key revocation and clock skew.
3. Run an experimental workload matrix with repeated normal cases, packet loss, disconnection, high-latency paths, partitions, restarts and Byzantine-looking evidence; publish raw event timelines with uncertainty intervals and success/failure classification policy.
4. Deploy a supported **real Chainlink VRF v2.5 coordinator** to a test network, fund the subscription and independently validate the callback/proof verification against official addresses and chain finality assumptions.
5. Design and prove **service-specific qualified facts** or a fair fallback dispute procedure. The physical N/F/S ambiguity model must determine when escrow can move; signature validity alone never justifies payment.
6. Add a versioned V2-native provider-response signing domain, independently anchored append-only archive heads, external audit, gas/cost metrics and a user-facing observatory (optionally Scaffold-ETH 2).

**Research status:** meaningful R5 agent/process and R9 *preliminary fault-harness* progress. It does not complete autonomous independent agents or independent-host distributed evaluation.
