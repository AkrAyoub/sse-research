# R49 — Real public native EL+CL seed (non-signing, independent edge)

Status: GitHub source only; NO public seed has been started. Owner VM4706 G2 signing chain31340 is still intact and isolated. There is NO verified public TCP/UDP edge in the project yet.

## Proven owner chain

Owner VM Step55 actual: all 110 source tests pass (90 G2, 9 public artifact, 11 external observer). Real EL block 266, Beacon head slot 484, finalized epoch 11, original BN+VC running, canonical standard ungated deposit runtime verified. Original four-public-files TAR from Step54, 16,218 bytes SHA256 1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7, contains true real EL genesis JSON, full Lighthouse config, genuine SSZ Beacon genesis and deploy block marker, and NO keys/JWT/slashing DB.

## Real protocol prerequisites

Native Besu execution P2P: TCP 30303 for authenticated RLPx/devp2p, UDP 30303 for discovery-v5. Native Lighthouse consensus P2P: TCP 9000 libp2p, UDP 9000 discv5, UDP 9001 QUIC. Expose these P2P ports only. Never expose EL Engine API 8551, EIP-2335 signer/keystores/validator signing API, EL HTTP RPC 8545 or Beacon REST 5052 to open Internet as part of this seed launcher.

One publicly routable entrypoint is needed to get started, not one static IP per node. A global public IPv4 may be dynamic. The seed launcher takes the current advertised global IPv4; if it changes, the edge mapping and signed advertised Besu/Lighthouse endpoints must be refreshed in a REVIEWED reconfiguration operation. Merely pointing dynamic DNS at another address does not automatically update signed Ethereum ENRs, nor does it create NAT/CGNAT port forwarding. Lighthouse's auto discovery can sometimes detect endpoint changes, but manual --enr-address pins the initial IP; this research seed deliberately does not claim automatic IP change recovery yet.

### Minimal truly public edge

An independently controlled Linux x86_64 edge/VM, Docker 29 compatible, direct public IPv4 or upstream managed mapping/port forwarding with real TCP/UDP ingress, and host/cloud firewall that permits only: 30303 TCP+UDP, 9000 TCP+UDP, 9001 UDP. If cloud network uses NAT, have the provider's public IP and actual L4 mappings proven from a separate external network. Do not treat 'curl http://localhost', DNS lookup, a provider management console, or local Docker 'Up' as inbound Internet proof.

An unvalued TEST ETH seed does NOT need an independent BLS validator key. Its EL/CL pair will be at the original genesis until the existing owner chain connects via native P2P. Thus, no block-height/finality match is claimed before owner G2 networking is migrated. Owner G2 does not need a static IP for outgoing peer connections.

## R49 source

tools/sse_pos_r49_public_seed.py (source-only 10 tests) requires exact clean SHA of current developer GitHub checkout, original public archive with EXACT owner-observed SHA256 and original 4 file digests, pinned immutable Besu 26.11.1 + Lighthouse v8.3.3 image digests, and a CURRENT globally routable advertised IPv4. Its --plan is read-only; it refuses the owner signing VM or any existing seed directory/container/network.

The --apply operation is NOT authorized now. It additionally requires a separate externally owned host, independently reviewed TCP+UDP public edge, explicit --external-tcp-udp-forwarding-reviewed and interactive consent CREATE-31340-NONSIGNING-PUBLIC-SEED. It creates a fresh local EL+CL data directory and local Engine JWT (never copies original R32 keys), a NON-INTERNAL egress bridge and TWO real, NON-SIGNING client containers. Explicitly publishes only the five P2P Docker port bindings, uses Besu --p2p-host with --nat-method=NONE and native discv5, Lighthouse signed ENR address/ports and --allow-insecure-genesis-sync for research-only non-signing initial genesis synchronization. **Weak subjectivity:** genesis-sync must be independently cross-checked against owner finalized Beacon checkpoint; without such evidence this seed is not a trusted production beacon.

All client container creation is create-once. If partially launched, preserve state and diagnose; do NOT rerun apply blindly. Launcher makes no claim of genuine UDP ingress, devp2p/libp2p handshake, independent fault domain, dynamic IP continuity, or current head/finality. No duplicate original EL DB or BLS key can run on the seed by this script.

### Developer-only instructions on the SEPARATE public edge, NOT owner VM4706

1. Legitimately obtain the original PUBLIC archive and verify its exact SHA256. Bring the reviewed pinned client images by immutable digest and obtain source from the developer private GitHub repository (or subsequently published verified public release); do not share the original owner SSH read-only key or BLS keys.
2. Run the 10 R49 source tests after immutable checkout on the external seed.
3. Run:

    python3 -B tools/sse_pos_r49_public_seed.py --plan --expected-commit "$SHA" --bundle /path/to/real-public-chain31340-archive.tar.gz --advertise-ip "$CURRENT_GLOBAL_IPV4"

4. ONLY after actual TCP+UDP port forwarding/firewall and independent remote edge check, and an external operator's consent, use --apply with additional flag --external-tcp-udp-forwarding-reviewed. Not before. Do not paste secret credentials.
5. Capture/verify native Besu execution ENR and Lighthouse BN ENR on that host WITHOUT exposing raw signed keys, passwords or Engine JWT; share only actual PUBLIC ENR strings to original owner and independent observer.
6. Separately review owner VM G2 controlled maintenance to enable outbound Besu + Lighthouse P2P on its preserved DB/SSZ/CL configuration. Stop the ONE validator before reconfiguring, preserve slashing protection and original JWT, and restart ONE signer only after both real EL+Beacon genesis gates pass. DO NOT rerun earlier R35/R40/R41 launch scripts.
7. Only when actual EL peers, Beacon peers and matching finalized checkpoints are independently measured on separate physical Internet hosts can R48 non-signing external observer be declared joined.

The repository is currently PRIVATE: this R49 developer-stage seed is NOT a finished permissionless public distribution. Publish reviewed source/installer and immutable original PUBLIC genesis archive on an accessible public HTTPS/release channel before inviting arbitrary external participants. Project release policy later demands two independently owned public seeds and an independently held BLS validator with real TEST ETH deposit and activation before claiming decentralized network.

Official provenance: Besu public-networks options 'p2p-host', 'p2p-interface', 'nat-method=NONE', 'discovery-mode=BOTH'; Besu Configure Ports; Lighthouse v8.3.3 beacon_node/src/cli.rs supports --enr-address, --enr-udp-port, --enr-tcp-port, --enr-quic-port, --listen-address, --port, --discovery-port, --quic-port and --allow-insecure-genesis-sync. R49 does not alter the real original chain.
