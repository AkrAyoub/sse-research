# R46: Real native Internet P2P rollout — chain31340

STATUS: PLAN ONLY; NOT AUTHORIZATION TO RESTART THE WORKING G2 LAB.

## Confirmed Step52 baseline

VM4706 observed 81/81 tests passing, real EL block 178, Lighthouse head slot 396, finalized epoch 8, Beacon not syncing, and original Lighthouse VC running. The canonical standard ungated Ethereum deposit runtime is verified live at genesis and head, 6,358 bytes, SHA256 5aaa8327c5765ec883224895ca02cade2871e12dad0197bdc791efc91c7ef18d. One operator/fault domain only; NO public native P2P.

The current topology cannot accept independent Internet peers. Replacement Besu sse31340-g2-el-r40 has P2P explicitly disabled and runs in Docker's INTERNAL bridge sse31340-g2-internal. Existing Lighthouse bn/VC also run there. Only host-loopback read RPC ports were published; no EL TCP/UDP devp2p and Beacon TCP/UDP discovery ports were opened. The original failed EL container is stopped and preserved. The single real R32 encrypted validator signing key and slashing-protection database must never be copied or duplicated.

## Actual networking and dynamic addressing design

Public Ethereum EL uses authenticated native devp2p TCP peers and UDP discovery; Lighthouse consensus uses native libp2p transport plus discv5 UDP discovery and usually QUIC UDP. Representative default ports are EL 30303 TCP+UDP, CL 9000 TCP+UDP and 9001 UDP. Verify exact flags on pinned Besu 26.11.1 and Lighthouse v8.3.3 before executing any migration. ONLY expose needed P2P ports, never the EL Engine API JWT port 8551, validator signing API, original key files, unrestricted RPC or private services. Keep RPC bound to localhost or an authenticated proxy.

Dynamic IPs are acceptable for ordinary operators, and a public seed may use a changing address with an up-to-date DNS record. However, changing DNS does NOT traverse CGNAT, open firewall inbound UDP, or prove authenticated P2P peering. At least one real publicly reachable EL+CL seed is needed to bootstrap native Internet peers; existing project public-release policy requires two genuinely independently operated public seed nodes before claiming robust permissionless public release. Lighthouse ENRs are signed and carry endpoint information; distribute updated ENRs after dynamic address changes. Nodes with no public inbound IP can sometimes connect outbound to public peers, but at least some bootstrap nodes need real TCP/UDP Internet ingress.

## Sequential safety gates

GATE 0 (R46 now): Execute only the read-only owner tool tools/sse_pos_g2_wan_preflight_r46.py with exact checked-out GitHub SHA. It validates original immutable PUBLIC genesis/config/SSZ and classifies the actual current Docker network/port bindings, public-IP vs private/CGNAT interface presence without printing host IPs. It does NOT change containers, sign messages, test an external connection or claim an independent operator.

GATE 1: Establish a genuine Internet-routable TCP+UDP edge, ideally publicly accessible IPv4 or IPv6 with permitted inbound port mapping and dynamic DNS. If current owner VM is behind CGNAT without public UDP ingress, use a truly publicly reachable native P2P seed host or proper routable port-forwarding; a private VPN or HTTP-only tunnel cannot be advertised as public Ethereum native P2P. Validate real external TCP AND UDP from independent ISP, then actual devp2p and Beacon discv5/libp2p handshakes. No handshakes have yet been seen.

GATE 2: Only after Internet ingress is feasible, review a controlled maintenance script, preserving original chain31340 EL execution database, canonical genesis/SSZ/full Lighthouse config and current Engine JWT. Stop the SINGLE existing VC before changing the live Beacon or Besu networking. Verify only one process can access original EL DB or the signing key, then republish EL+CL P2P listeners onto an appropriate NON-INTERNAL network with limited firewall ports, native discovery and accurate dynamic external endpoint advertisement. Restore real Besu chain31340 Engine auth, Beacon original genesis, and only then resume the SAME original VC and slashing DB. Do NOT run the old R35/R40/R41 apply scripts again. No new genesis and no new original-key clone. A brief controlled loss of finality during maintenance is not a second chain.

GATE 3: Bring a completely independent non-signing observer EL+CL pair online on a different physical/admin machine and network. Download only PUBLIC chain31340 artifacts: EL genesis SHA256 22eb6c58288113b9c3671970967151012665137b345237b5c24060dc988b1ee8, real Lighthouse SSZ SHA256 8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82, pinned full Lighthouse configuration SHA256 3e750d7d02e3ed83747f95cc09ff3299185f56f1777dfeb1f126b17881297b6e, deployment-block marker and real standard deposit code. Use entirely new independent EL+CL node P2P identities/data dirs, locally held Engine JWT, and NO original signing keys. Verify true cross-Internet native peer counts, correct genesis and chain ID, EL height and finalized Beacon epochs from this external observer with no owner admission invite.

GATE 4: A second genuinely independent owner independently generates/holds its OWN new encrypted BLS validator key and slashing-protection DB, submits its own legitimate 32 UNVALUED TEST ETH deposit into the live verified ungated contract, waits for real Beacon deposit recognition and validator activation, and signs actual proposal/attestation duties. No synthetic deposits, fake validators, guaranteed activations, admin permission, or reused owner keys. Consumers/providers/monitors may join permissionlessly when their respective actual resource, bond and contract rules are met.

PUBLIC RELEASE GATE: Honor existing fail-closed tools/sse_public_network_preflight.py manifest requiring two different public seed operators and exact PUBLIC release commitments. DNS resolution and TCP connect do not prove consensus handshakes, public UDP, independent hardware, or decentralized resilience. This project must never call the single-owner G2 lab a public permissionless network.

## Source-control and custody invariants

Tracked implementation only through the connected GitHub repository. Owner VM fetches an immutable source SHA with its read-only key. No GitHub Actions. Never display, upload, recreate, overwrite or copy the R32 mnemonic, signer keystore passwords, BLS private key, original slashing DB or original Engine JWT. Preserve real chain ID 31340 and ALL original public genesis and execution/consensus state. Maintain the original live signer until an explicitly reviewed P2P migration.
