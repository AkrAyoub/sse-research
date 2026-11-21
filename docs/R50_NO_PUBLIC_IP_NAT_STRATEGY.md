# R50 — No public IP: real NAT-egress feasibility without losing chain31340

Status: GitHub SOURCE ONLY; next owner VM4706 read-only test. R50 does NOT provision any Internet seed, publicly available RPC, additional validator, tunnel or independent operator.

## The infrastructure constraint, as actually reported

Owner VM Step56 observed original real Besu execution height 287, Lighthouse head slot 505, finalized epoch 11, Beacon not syncing, canonical ungated Ethereum deposit runtime valid; R49's 10 focused tests pass. Besu original live EL+BN+same VC are intact. Owner specifically stated that **NO SERVER WITH A PUBLIC IP is available now** but additional private-address VMs can be provisioned (similar or smaller specs). VM4706's earlier R46 audit showed private interface addresses, a Docker --internal bridge and Besu P2P disabled, no P2P inbound port binding.

### The hard native protocol requirement

A NEW native peer behind NAT can initiate outbound real Besu devp2p TCP and Lighthouse libp2p/discv5 traffic to truly reachable bootnodes. No static IPv4 address is needed on every participant. But a global, open-to-anyone, fully permissionless Internet network CANNOT bootstrap entirely from mutually NAT-isolated hosts unless at least one real globally reachable edge, legitimate port mapping or an external peer/gateway exists. Spawning 2, 5 or 20 more private VMs behind the SAME NAT/provider does not create a routable native Internet bootstrap. It also does not prove independent fault domains. **Do not equate more VMs, private VPN, public HTTP RPC, DDNS, STUN outbound reflection or Docker 'Up' with authenticated native public P2P.**

Authoritative references: Besu Configure Ports requires execution native TCP+UDP, Lighthouse Advanced Networking documents its NAT behavior and inbound P2P ports, RFC 5389/8489 STUN specifies outbound NAT mapping only. Native connections use EL 30303 TCP+UDP, CL 9000 TCP+UDP and optionally 9001 UDP QUIC. STUN can reveal an outbound gateway's public mapping but CANNOT show that arbitrary inbound packets reach the validator, nor that the provider forwards native traffic.

## Feasible routes, ordered

1. **Best when the provider supports it:** request or configure an actual Internet ingress allocation / floating or ephemeral public IPv4 or routable global IPv6 / managed public TCP+UDP load balancer mapping on a NON-SIGNING bootstrap edge. A FIXED address is NOT necessary; refresh signed ENRs on address changes. The actual provider dashboard/administrator must certify whether external TCP+UDP 30303, 9000 and optionally 9001 can reach that edge. Until then capability is UNKNOWN; do not fabricate a cloud-specific gateway or IP.
2. **Otherwise:** use an external independently operated community seed with publicly reachable native TCP+UDP that runs the SAME original chain31340 EL+CL, or subscribe to a third-party service that genuinely forwards both raw TCP and UDP at the Ethereum P2P layer from a public endpoint to private VM clients. Check genuine remote protocol handshakes, advertised ENRs and actual finality, and document the relay's single-point-of-failure and service terms. HTTP-only tunnels or private-overlay-only join paths are not an equivalent public bootstrap.
3. **Only as an intermediate real multi-node lab:** create additional VM instances behind the same infrastructure NAT with no signer duplication. They can run real non-signing EL+CL clients and validate authentic inter-VM native peering IF the provider offers direct private L3 reachability and suitable firewall policy. But such a lab is NOT open to independently operated arbitrary Internet nodes and is NOT evidence of censorship-resistant permissionless network.
4. **End state:** publicly downloadable reviewed (NOT private-GitHub-only) immutable original genesis+config+SSZ, at least one live real TCP+UDP bootnode initially and two distinct independent seeds for public release; preserve single original VC/slashing DB during controlled P2P migration; independently administered observer on different Internet network syncs real EL/CL and positive finalized epochs; separately held second BLS signer makes a real 32 UNVALUED TEST ETH deposit/activation. Actual provider/monitor/consumer resources and SLAs come later, no simulated substitute.

## R50 owner-only diagnostic now available

tools/sse_pos_r50_no_public_ip_nat_probe.py requires exact immutable detached SHA, original real chain/G2 private Docker and currently correct Beacon genesis from existing R46 owner read-only checks.

- --plan: ZERO outbound network probes, ZERO writes/Docker mutations, prints only classification.
- --probe-outbound: explicit opt-in to real TCP connect to **Cloudflare 1.1.1.1:443** (no HTTP request) and one RFC5389 STUN Binding request over UDP to **Google stun.l.google.com:19302**. Both remote services inherently see the requester's NAT public egress IP, so this is a privacy consideration. The script prints NO public IP, NAT mapping/port, or transaction nonce; it only returns success/failure booleans. UDP response validity checks fixed STUN magic cookie, transaction ID and bounded XOR-MAPPED-ADDRESS. A failed UDP test could be network blocking, DNS loss or remote service unavailability; it does NOT prove UDP impossible. A successful test proves only outbound UDP to that endpoint, not arbitrary UDP devp2p or external ingress.

Run read-only R50 tests and --plan first. The --probe-outbound command is opt-in and intentionally separate. Neither touches the original VC or changes chain31340, and both return provider ingress capability as UNKNOWN_NOT_PROBED.

The architecture decision AFTER genuine measurements is not "how many additional VMs?" but "what actual reachable seed/gateway will allow arbitrary outside operators to discover and connect via native public P2P?" If no ingress path exists anywhere and no external operator can supply it, public permissionless native Ethereum joining is NOT technically achieved. Continue safely with the current real single-operator chain, not a false public release.

## Safety and source-control

All changes only via the GitHub connector; owner VM read-only GitHub checkout, no GitHub Actions. Never rerun R35/R40/R41 one-time apply commands, regenerate genesis, HD wallet, signer mnemonic/password, Engine JWT, EIP2335 key, or slashing DB. Never open Engine API or signing endpoints to the Internet.
