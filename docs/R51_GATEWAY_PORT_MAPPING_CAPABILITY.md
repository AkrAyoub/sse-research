# R51 — Real chain31340 gateway-level port-mapping capability audit

**State:** GitHub source staged only; no VM4706 gateway probing has been performed by R51. Original EL+Beacon+VC are NOT modified by R51. Do not run any old one-time R35/R40/R41 apply or re-import original validator keys.

## Actual Step57 evidence, VM4706, 2026-11-21

Owner ran SHA 4a65ba42bec682bf1f80204f7b877563156b2ef3 and 8/8 R50 tests PASSED. Non-mutating R50 external network probe reached Cloudflare 1.1.1.1:443 over TCP and Google's STUN service stun.l.google.com:19302 over UDP, with RFC5389 Binding Success response matching request nonce and a global IPv4 NAT egress mapping. No raw NAT IP/port was printed. Real native Ethereum handshakes and inbound public port forwarding **NOT PROVEN**. VM4706 has only private interface IPs, no directly assigned global IPv4/IPv6, Docker --internal bridge, EL P2P disabled. At same unix observation 1795225539, genuine EL chain ID31340 block **309**, Lighthouse head slot **527**, finalized epoch **12**, Beacon not syncing, original BN+single VC running and canonical 6358-byte deposit runtime verified. This is a real one-owner PoS chain, not yet public independent native P2P.

Owner can provision more *private* provider VMs, but no public-IP server currently available. Creating more private VMs does NOT produce actual Internet ingress on its own. Outbound connectivity is encouraging for behind-NAT validators or observers *once a real public seed exists*. The remaining question is whether the provider's default L3 NAT gateway supports public port mapping.

## R51 source design

tools/sse_pos_r51_gateway_mapping_capability.py implements --plan and --probe-gateway with 11 source tests. It invokes existing immutable Git SHA exact source, G2 real EL+Beacon/VC and private Docker bridge gates from R46, verifies host's default IPv4 route to exactly one LOCAL private/CGNAT gateway, never prints gateway/source/public IP or mapped ports. No Docker, BLS credentials, JWT, slashing files or live PoS data changed.

--plan only checks route metadata without network packet transmission.

--probe-gateway is a new separate EXPLICIT opt-in that sends exactly TWO nonmutating RFC inquiries over local UDP/5351:

1. PCP RFC6887 version 2 ANNOUNCE opcode **0**, requested lifetime **0**, correct IPv4-mapped IPv6 local client address. The ANNOUNCE opcode checks PCP server availability and does NOT create a MAP or PEER firewall/NAT entry.
2. NAT-PMP RFC6886 version 0 PUBLIC ADDRESS opcode **0**. It is NOT the UDP/TCP port-mapping opcode 1/2. It may report whether the gateway has an externally mapped global IPv4, but actual IP bytes and ports are never displayed.

Each protocol uses its own ephemeral UDP socket, 2-second bounded receive; a reply is validated as belonging to the expected protocol. A timeout is inconclusive: cloud NAT providers may suppress PCP/NAT-PMP even while offering managed mappings or a load balancer. PCP success is **not** permission for public port forwarding; a private gateway could sit behind another NAT. NAT-PMP global-address success still does NOT prove external inbound reachability, security group configuration, active native devp2p/discv5 peers, or permissionless public onboarding. R51 never issues a MAP/PEER or creates a permanent listener.

## Decision after R51

- If PCP/NAT-PMP responds: look up provider's actual port-mapping controls or the gateway's supported allocation policy. Only after a separately authorized, carefully scoped mapping operation and independent outside TCP/UDP test can seed ingress be considered. Do NOT open original Engine/validator APIs.
- If both timeout: do not equate timeout with blocked inbound forever. Ask provider about external L4 forwarding, global IPv6, floating/dynamic IPv4, or managed TCP+UDP gateway. No known public endpoint in this project yet.
- If provider cannot offer ingress: obtain at least one external independently operated genuine public native EL/CL seed or actual L4 UDP+TCP forwarding provider (not HTTP-only tunnel). The research goal of arbitrary independently operated public Ethereum nodes CANNOT be met solely by more same-provider private VMs.
- If none yet: preserve finalizing G2; optionally add a genuinely real non-signing second internal EL+CL observer as an honest temporary LAN PoS lab, clearly not independent Internet participation. Never duplicate the owner VC or its BLS signing key.

No one currently needs to buy static IPs for every node. A dynamic reachable seed (with refreshed signed ENR and DNS) supports ordinary NAT'd outbound peers. Full public release additionally requires openly downloadable reviewed client source+original public genesis archive, which current PRIVATE GitHub repository cannot provide without access grants, as well as separate independent operators, peer handshakes, real validator deposits and finality.
