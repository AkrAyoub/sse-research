# R294 — REAL new VM4711 ⇄ VM4714 controllerless public IPv6 TCP/UDP; next old↔new direct overlay packets

## Actual real packet evidence, 2026-11-24

At pinned Git SHA `5aabf950dde51cacb7f3b6c403778638a0572b57`,
owner VM4711 **ran 12/12 R55 source tests PASS** then executed
`tools/sse_pos_r55_zerotier_ipv6_transport.py --check
fca0:2328:77f8:9326:689f::1` on its own genuine
`fca0:2328:77a9:8951:acf0::1` controllerless 6plane
IPv6 address. Real response fields:

- `realRemoteTcpPayloadRoundTrip=true`, measured actual **346.55 ms**.
- `realRemoteUdpPayloadRoundTrip=true`, measured actual **0.91 ms**.
- `realBothTransportPayloadRoundTrips=true`.
- UDP local bound source port29002 permitted response destination under
  the actual open ad-hoc network port filter.

On **different host VM4714**, owner ran separate 12/12 R55
source tests PASS, `--plan` confirmed its real assigned
`fca0:2328:77f8:9326:689f::1` on public network
`ff2328775f000000`, and `--server` bound only this IPv6
TCP29000/UDP29001. Actual owner server independently
reported `realRemoteTcpRequestReceived=true`,
`realRemoteUdpRequestReceived=true`,
`bothTransportRequestsReceived=true` and exited,
as R55 source's first-pair lifetime requires.

This is **genuine successful on-wire IPv6 TCP+UDP packet exchange** between
two distinct new VMs over the SAME original open-join network,
not VM-private 10.50.56.x application traffic nor SSH forwarding.
The underlay may still use common cloud infrastructure and
ZeroTier vendor planet/relay; physical ISP independence,
native Besu/Lighthouse peer handshakes on these application VMs,
paid V2 lease, monitor voting and SLA are NOT proven.

Actual owner evidence: `evidence/r294_vm4711_vm4714_actual_public_overlay_tcp_udp_confirmed.json`.

## Is it connected to VM4706/4707/4709 too?

**Yes at the shared ZeroTier network-membership level:** old
VM4706, VM4707 and VM4709 use the SAME controllerless
public network `ff2328775f000000`, and new VM4711–14
all independently report OK/PUBLIC membership on that exact network.
The original network has *no controller enrollment gate*.
The original three VMs operate the real native canonical
chain31340 Besu/Lighthouse consensus network; new role-agent-only
VMs do not run native EL/CL simply from joining overlay.

Historical actual OLD native proof:
`docs/R225_VM4707_VM4709_FINALIZED_EPOCH602_MATCH_SKEW_RESTRICTION.md`:
VM4707 and VM4709 each independently reported real native
two EL + two CL peers, same finalized checkpoint epoch602
and root, and same genesis (timestamp skew 181.223808s
was just beyond 180s formal paired-capture threshold;
earlier epoch571 comparison passed). Historical outside
cloud WSL R55 → VM4707 actual IPv6 TCP+UDP also succeeded.

**NOT YET evidenced:** a current R55 real packet from any
NEW VM4711–14 to any OLD VM4706/4707/4709.
Shared overlay membership is network association, not
the same thing as a verified contemporaneous direct host
communication path; nor is an app-only role host automatically
an authenticated Besu/Lighthouse native peer.

## Next two new monitor packet checks (R55 existing exact source)

VM4714:
```bash
(
  set -euo pipefail
  cd "$HOME/sse-v2-standby-source"
  python3 -B tools/sse_pos_r55_zerotier_ipv6_transport.py --plan
  python3 -B tools/sse_pos_r55_zerotier_ipv6_transport.py --server
)
```
Run one VM4712 client **while** this listener remains open:
```bash
(
  set -euo pipefail
  cd "$HOME/sse-v2-standby-source"
  python3 -B -m unittest discover -s tests \
    -p 'test_sse_pos_r55_zerotier_ipv6_transport.py' -q
  python3 -B tools/sse_pos_r55_zerotier_ipv6_transport.py \
    --check 'fca0:2328:77f8:9326:689f::1'
)
```
If real TCP+UDP both pass, repeat **new separate VM4714 server**,
and run the same R55 client from VM4713. Do not attempt
both clients during one R55 server run: it exits after first pair.
Do not rerun ZeroTier installation/join, edit SSH authorized_keys,
open worker port8877, restart Docker or original EL/CL.

## Exact safe optional OLD VM4707 ⇄ NEW VM4711 test

Original VM4707 is the **old nonsigning full EL+CL peer**
previously used for actual R55 WSL external IPv6 success,
not the original validator. The original R55 code
does not touch existing EL/CL containers; it merely
opens separate host 6plane IPv6 TCP29000/UDP29001
sockets for ≤600sec. On **VM4707** do not checkout
new source, restart native clients, reinstall ZeroTier
or access private keys.

First discover which copy of the previously R55-tested
script is already installed on VM4707:
- `$HOME/sse_pos_r55_zerotier_ipv6_transport.py` from
  the original R55 owner-host trial, or
- `$HOME/sse-research/tools/sse_pos_r55_zerotier_ipv6_transport.py`.

Require the exact previously observed R55 public-script
SHA256 checksum:
`6d9054564f64897aae99232cdc4a00e7af0288d26fc5a43e0c15cc7504321136`.
Fail closed if neither file exists or checksum does not match.
This is a **public non-secret** harmless echo script,
not VM4707 EOA/BLS material or other chain files.

Then on VM4707 owner terminal:
```bash
(
  set -euo pipefail
  echo "== ORIGINAL OLD NONSIGNING VM4707 =="
  test "$(id -un)" = "ayoubakrvm4707"
  F="$HOME/sse_pos_r55_zerotier_ipv6_transport.py"
  if [ ! -f "$F" ]; then
    F="$HOME/sse-research/tools/sse_pos_r55_zerotier_ipv6_transport.py"
  fi
  test -f "$F"
  test "$(sha256sum "$F" | awk '{print $1}')" = \
    "6d9054564f64897aae99232cdc4a00e7af0288d26fc5a43e0c15cc7504321136"
  echo "== REAL OLD VM PUBLIC IPV6 PREVIEW =="
  python3 -B "$F" --plan
  echo "== 10 MINUTE TEMPORARY OLD VM IPV6 ECHO SERVER =="
  python3 -B "$F" --server
)
```
This runs the R55 echo on the original VM4707 (separate
from its active native Besu/Lighthouse containers),
accepting ONE first-pair TCP+UDP client. It will
stop automatically after the pair or 600 seconds,
whichever comes first.

Only if `--plan` returns the same current source-verified
VM4707 `fca0:2328:77b8:6578:a55::1`, run from NEW
VM4711 terminal, while the VM4707 server is open:
```bash
(
  set -euo pipefail
  cd "$HOME/sse-v2-standby-source"
  python3 -B tools/sse_pos_r55_zerotier_ipv6_transport.py \
    --check 'fca0:2328:77b8:6578:a55::1'
)
```
If the old VM's actual local 6plane address has changed,
use the NEW observed `--plan` IP, never a stale fixed
private cloud address. If R55 SHA mismatch or file absent,
**stop and report; do not make changes to original VM4707**
just to force the test.

This one old⇄new test, if independently confirmed at
both endpoints, would establish REAL contemporaneous
new host ↔ previously synchronized old native full node
IPv6 transport. It would **not** mean the new
application-only VM runs its own Besu/Lighthouse peer,
nor would it mean off-VM/ISP direct underlay transport
was established.

## Next actual SSE economy

Original VM4714 raw Docker worker still runs legitimate
deterministic CPU SHA workloads only behind host
`127.0.0.1:8877`. Verified real overlay TCP+UDP
is just the network substrate. Do NOT publish unsigned
port8877 on open ad-hoc overlay. A new publicly
authenticated lease-bound provider endpoint needs
real finalized funded chain31340 V2 lease,
resource+policy hash commitment, real selected
and bonded monitor committee, validated pre-signed
EIP712 reply and a real TLS origin; existing R232/R234
already strictly reject missing prerequisites.
The four new separate application EOA test-ETH
grant transactions are still UNAUTHORIZED/UNSENT;
the original three approved grants are finalized.
