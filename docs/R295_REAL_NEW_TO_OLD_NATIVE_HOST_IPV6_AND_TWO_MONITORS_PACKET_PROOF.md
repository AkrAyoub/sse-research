# R295 — REAL new monitor VM4711 ↔ OLD chain31340 full node VM4707, and VM4712 ↔ provider VM4714 over original public open controllerless IPv6

## Owner logs from 2026-11-25

**REAL old-to-new generation connectivity is NOW VERIFIED**, rather than merely inferred from membership in the same ZeroTier network.

- OLD VM4707 owner invoked pinned original R55 script `--plan`, which confirmed its *actual current* overlay IPv6 `fca0:2328:77b8:6578:a55::1`, network `ff2328775f000000`, `OK PUBLIC`, interface `ztrb6cq527`. Its bounded R55 `--server` bound only the overlay IPv6 TCP29000/UDP29001, and independently reported both actual remote payloads received with valid ACKs: `realRemoteTcpRequestReceived=true`, `realRemoteUdpRequestReceived=true`, `bothTransportRequestsReceived=true`.
- NEW VM4711 owner separately executed R55 `--check fca0:2328:77b8:6578:a55::1` from its actual local overlay IPv6 `fca0:2328:77a9:8951:acf0::1`. Independently reported **both true**, real TCP RTT **356.75ms**, real UDP RTT **0.85ms**.
- NEW VM4712 owner independently executed R55 `--check fca0:2328:77f8:9326:689f::1`, from its actual IPv6 `fca0:2328:77b9:dc2a:748a::1`, to provider VM4714. Independently reported **both true**, real TCP RTT **349.99ms**, real UDP RTT **0.60ms**. VM4714 owner ran matching R55 server and separately observed `bothTransportRequestsReceived=true`.
- Earlier R294 NEW VM4711 ↔ provider VM4714 already recorded real R55 TCP RTT **346.55ms** and UDP RTT **0.91ms**, with matching independent server ACKs.

All these use **actual TCP+UDP IPv6 packets to the original publicly joinable controllerless open overlay `ff2328775f000000`**. No application test used a `10.50.56.x` cloud private IP, source-IP SSH authorization or tunneling. However the ZeroTier encapsulated underlay for machines hosted by the same cloud remains unknown; this is **not** independently verified ISP separation.

Crucial distinction: VM4707 (old node) already ran independently installed, genuinely synchronized Besu and Lighthouse on original chain31340, with same previously observed finalized epoch/root as old VM4709 (R225). R295 R55 echoed packets on VM4707 **without modifying those existing native clients**, and did not cause the *new role agent VM4711* itself to run Besu/Lighthouse. The current R55 old↔new packet test does NOT re-prove current native EL+CL peer/finality state; old R225 observation is historic.

Owner evidence `evidence/r295_actual_old_vm4707_new_vm4711_and_vm4712_vm4714_ipv6_tcp_udp_ack.json`.

## One remaining monitor-to-provider transport trial

**VM4713 → VM4714 is the only missing pair in the original three-monitor provider transport matrix.**

Start on VM4714 (new provider, already on same real public open overlay) from previously reviewed existing source checkout:

```bash
(
  set -euo pipefail
  test "$(id -un)" = "ayoubakrvm4714"
  cd "$HOME/sse-v2-standby-source"
  python3 -B tools/sse_pos_r55_zerotier_ipv6_transport.py --plan
  python3 -B tools/sse_pos_r55_zerotier_ipv6_transport.py --server
)
```

While the server is active (maximum 600 seconds and stops after first valid TCP+UDP pair), on VM4713:

```bash
(
  set -euo pipefail
  test "$(id -un)" = "ayoubakrvm4713"
  cd "$HOME/sse-v2-standby-source"
  python3 -B -m unittest discover -s tests \
    -p 'test_sse_pos_r55_zerotier_ipv6_transport.py' -q
  python3 -B tools/sse_pos_r55_zerotier_ipv6_transport.py \
    --check 'fca0:2328:77f8:9326:689f::1'
)
```

If provider `--plan` reports a changed local address, use that actual observed IPv6 rather than a stale address. Report BOTH VM4713 and VM4714 actual outputs. No new GitHub code needed for genuine R55 packets; no private IP, SSH, PoS, wallet or Docker changes. If the tool times out, treat as real failure and inspect overlay routes/peer paths read-only.

## Subsequent actual on-chain resource/SLA work

Transport is now PROVEN between both generations of VM operators and two of the three app monitors. This is the right network substrate, but no new paid SSE contract/lease is inferred.

Existing R232 `tools/sse_pos_r232_v2_monitor_probe.py` **already enforces** a finalized selected/confirmed monitor EOA, original-chain V2 committed provider HTTPS origin and EIP712 signed provider reply. Existing R234 `services/provider-agent/v2_compute_response_server.py` **already enforces** the funded finalized lease/profile/policy/committee and actual Docker physical work, and binds HTTP loopback only, requiring an authenticated TLS reverse proxy. Neither can be bypassed by exposing VM4714's raw localhost `127.0.0.1:8877`. These sources block until genuine V2 chain deployment/lease evidence exists; do not produce fake SLA scores.

Four new VM4711–14 application EOAs remain **unfunded**; R282's quote to fund 0.005 native TEST ETH each, combined max **0.020000000084 TEST ETH** including gas, is **not separately owner-approved**, so no new native transaction or bond can be sent. Three prior separately authorized original-role funding transfers were finalized. The running original chain31340 PoS clients and VM4714 capped Docker worker remain unchanged.
