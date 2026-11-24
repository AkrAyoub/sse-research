# R293 — REAL VM4711/12/13/14 same open-join ZeroTier IPv6 membership OK PUBLIC; now run existing proven R55 actual TCP+UDP roundtrips

## Actual new VM owner terminal results (2026-11-24)

All FOUR new role host owners supplied genuine ZeroTier client JSON from their own terminal at R291 source, each reporting:
- Daemon `online: true`.
- Network ID exactly `ff2328775f000000` (same as original chain31340 VM4706/VM4707/VM4709), `status: OK`, `type: PUBLIC`, interface `ztrb6cq527`.
- Exactly one actual assigned `fca0::/16` 6plane IPv6 per host:
  - VM4711 monitor: `fca0:2328:77a9:8951:acf0::1/40`, ZeroTier node `a98951acf0`, `tcpFallbackActive=false`.
  - VM4712 monitor: `fca0:2328:77b9:dc2a:748a::1/40`, node `b9dc2a748a`, `tcpFallbackActive=true`.
  - VM4713 monitor: `fca0:2328:7768:1f76:8561::1/40`, node `681f768561`, `tcpFallbackActive=true`.
  - VM4714 provider: `fca0:2328:77f8:9326:689f::1/40`, node `f89326689f`, `tcpFallbackActive=true`.

On VM4711, VM4712, VM4714, earlier owner R291 package/overlay tests were 18+12=30 PASS each (90 tests aggregate). Owner did not supply the R291 test, signed package install or join steps for VM4713, only its genuine current OK PUBLIC membership. Do not infer its installation method.

The four observed membership/IPv6 addresses are **REAL**, not hypothetical. The three active TCP-fallback flags show some transport paths may rely on relay. An actual per-other-peer link can use different underlay routes; flags alone do not prove a particular pair's packet route. These four machines share cloud provider infrastructure and cannot establish separate-ISP independence. The overlay requires ZeroTier planetary roots/relays; independent, truly direct Internet native P2P still remains unfinished.

**No actual new VM4711–13 ⇄ VM4714 IPv6 TCP or UDP payload exchange is yet shown**. Their actual membership is a distinct successful milestone, but not a signed monitor, lease, EL/CL peer, committee, economic payment, resource-use SLA or owner-independent Internet validator.

Evidence in `evidence/r293_four_new_vm_actual_zerotier_open_ipv6_ok_public_membership.json`.

## Correct next test: reuse original previously real-proven R55, unchanged

The same committed `tools/sse_pos_r55_zerotier_ipv6_transport.py` and its 12 safety tests are used for genuine real IPv6 TCP and UDP payloads. That tool already previously succeeded in real independent Linux laptop WSL ⇄ VM4707 IPv6 transport, documented in `docs/R55_ZEROTIER_CROSS_HOST_IPV6_TRANSPORT.md`.

Properties:
- On server VM4714, `--server` calls the real local network membership, then binds **only VM4714's actually current assigned fca0 IPv6**, not global :: or any private infrastructure IPv4, TCP port29000 and UDP port29001 for maximum 600 seconds.
- From one monitor VM at a time, `--check <actual VM4714 fca0 ipv6>` requires SAME OK PUBLIC network membership, rejects local-self IP, connects actual IPv6 TCP29000, sends exact test payload and checks actual reply, and binds UDP source 29002 (ad-hoc network reply-port filtering) to independently test datagram roundtrip with actual reply.
- The client returns success exit 0 ONLY if both real TCP+UDP responses matched; reports actual per-transport RTT. The server returns exit0 ONLY when at least one corresponding TCP and one UDP request received.
- `--server` exits after its **FIRST successful TCP+UDP pair**. Thus to test VM4711, VM4712, VM4713 properly, start a FRESH R55 server on VM4714 for each monitor, one after another, rather than trying to share one invocation simultaneously among three clients.
- Opening these bounded echo listeners on the public overlay is an explicitly operator-invoked, short-lived **real host network action**. It is not a native EL/CL server, worker provider service, permanent public HTTP, Ethereum RPC, Engine8551, Docker socket, wallet, or validator change.
- R55 does not require any project-owner SSH invitation or fixed infrastructure private IP. It does require the operator to know the **currently actual** provider overlay IPv6 for the specific probe; this is a runtime target for a test and is not hardcoded blockchain admission.

### VM4714 — first R55 server, one-time unit tests and preflight

After pinning the newest full reviewed Git SHA printed in chat (no VM source edits):

```bash
(
  set -euo pipefail
  cd "$HOME/sse-v2-standby-source"
  python3 -B -m unittest discover -s tests \
    -p 'test_sse_pos_r55_zerotier_ipv6_transport.py' -q
  python3 -B tools/sse_pos_r55_zerotier_ipv6_transport.py --plan
  echo "== R293 REAL VM4714 IPV6 TCP+UDP SERVER, MAX 600s =="
  python3 -B tools/sse_pos_r55_zerotier_ipv6_transport.py --server
)
```

Leave this terminal running and move to VM4711. The source does not need sudo root for socket binding, but it needs preexisting `sudo -n zerotier-cli -j listnetworks` read permissions, which R291 previously proved.

### VM4711 — first real monitor IPv6 client

Run WHILE VM4714 first server is still listening:

```bash
(
  set -euo pipefail
  cd "$HOME/sse-v2-standby-source"
  python3 -B -m unittest discover -s tests \
    -p 'test_sse_pos_r55_zerotier_ipv6_transport.py' -q
  python3 -B tools/sse_pos_r55_zerotier_ipv6_transport.py --plan
  python3 -B tools/sse_pos_r55_zerotier_ipv6_transport.py \
    --check 'fca0:2328:77f8:9326:689f::1'
)
```

Record actual client AND server terminal output, including success/failure and both transport response flags. A network timeout is real diagnostics, not mock SLA failure. Do not move to a paid monitoring verdict because of transport success.

### VM4712 — SECOND real monitor

After the first VM4714 server exits successfully, run a NEW VM4714 server with `--server`, then on VM4712 execute the exact VM4711 client command with unchanged actual provider overlay IPv6 `fca0:2328:77f8:9326:689f::1`.

### VM4713 — THIRD real monitor

After the second VM4714 server exits, start a THIRD `--server`, then run same `--check 'fca0:2328:77f8:9326:689f::1'` on VM4713.

**No duplicate join, no ZeroTier reinstallation, no private SSH key authorization, no manual cloud private-IP routing, no original native PoS changes.**

If any `--server` fails to bind or a particular monitor times out, stop and inspect real `ss -lntup`, IPv6 overlay member, `sudo -n zerotier-cli peers` (read only), local UFW/firewall status without modifying them; don't claim success or create a second overlay. Do not open the worker's raw `127.0.0.1:8877` to the shared overlay.

## Subsequent genuine application-network milestone

After these real cross-host transport probes, build a provider gateway that binds only its currently observed ZeroTier IPv6, uses audited TLS and EIP712 provider attribution, and routes internal requests only to its existing loopback-only physical Docker CPU worker; real onchain V2 monitor evidence still demands actual funded, finalized leases, correctly selected/confirmed bonded monitors and finalized votes/settlement. The provider's current localhost SHA computation and new peers' overlay membership do NOT already satisfy those requirements.

All previously approved three VM4707 native TEST ETH role grants finalized. The four newer VM4711–14 encrypted Ethereum EOAs remain unfunded; read-only quote to fund four 0.005 native TEST ETH accounts (combined maximum 0.020000000084 incl gas) is NOT owner authorized or broadcast. Do not resubmit old grant nonces.
