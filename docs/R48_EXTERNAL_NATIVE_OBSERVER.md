# R48 — independent NON-SIGNING native Ethereum EL/CL observer (staged)

Status: CONNECTED GITHUB SOURCE ONLY. No external node, bootnode, native Internet handshake, dynamic-DNS ingress, or second signer has been observed or deployed by this stage.

## Real owner chain snapshot and original public archive

Owner VM4706 actual Step54: 90 focused G2 tests + 9 public-bundle tests passed; the real Besu/Lighthouse/BLS VC chain31340 continued with execution height 223, Beacon head slot 441, finalized epoch 9. The original 4 public chain inputs plus a public manifest were exported and verified to the owner-only public-artifact archive:

- Owner path: ~/.local/share/sse-r47-chain31340-public-artifacts/chain31340-public-native-observer-v1.tar.gz
- Owner-observed archive size: 16,218 bytes
- Owner-observed archive SHA256: 1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7
- Original real 2,737,436-byte Lighthouse genesis.ssz SHA256: 8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82
- EL genesis JSON SHA256: 22eb6c58288113b9c3671970967151012665137b345237b5c24060dc988b1ee8
- Complete pinned Lighthouse config SHA256: 3e750d7d02e3ed83747f95cc09ff3299185f56f1777dfeb1f126b17881297b6e
- Public deposit_contract_block.txt SHA256: 9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa
- Live standard ungated Ethereum deposit runtime SHA256: 5aaa8327c5765ec883224895ca02cade2871e12dad0197bdc791efc91c7ef18d

No owner wallet, validator EIP-2335 keystore, password, Engine JWT, slashing DB or node private key is part of the TAR. Original VM4706 G2 real network remains privately isolated, Besu P2P DISABLED, no native Internet bootnode.

## Real Internet-native discovery, no static public IP on every participant

For execution, use Besu native discovery-v5 ENR bootstraps via --discovery-mode=BOTH and --bootnodes=... . For consensus, use Lighthouse native --boot-nodes=<signed CL ENR>. These two ENRs must be actual reachable chain31340 seeds once the owner network exposes native devp2p/discv5/libp2p.

Important upstream nuance: Besu enode hostname support with --Xdns-enabled is an experimental permissioned-network feature, not a default requirement for permissionless Internet Ethereum. R48 therefore uses signed native ENRs, not fictitious enode://...@dynamic-dns syntax. ENRs can be refreshed/distributed when public seed addresses rotate. DNS alone cannot unblock CGNAT, native UDP, or firewall ingress; the network needs at least one reachable EL+CL seed (and the project public-release policy requires two independent public seed operators). Lighthouse normal peers behind NAT may use outbound P2P without inbound port mapping.

## R48 developer-stage external operator launcher

Source: tools/sse_pos_r48_external_observer.py. It uses the EXACT pinned public archive SHA and verify_bundle allowlist; requires independently installed pinned Besu 26.11.1 and Lighthouse v8.3.3 linux/amd64 Docker images with the original pinned image IDs. It REFUSES execution on the existing G2 signing host or if a previous observer container/data dir already exists. No signer client or validator key is created. It installs fresh external observer EL+BN state with an independent local JWT, a Docker non-internal egress bridge and host LOOPBACK-only JSON-RPC/Beacon ports 28545/25052. No public authenticated Engine API or signing ports, no artificially created genesis. Uses signed ENR bootstrap on both EL+CL, avoids inbound P2P publication initially (outbound-only client under NAT).

The --plan mode is strictly read-only, prints exact source+archive image proof and states that it has NOT proven ENR cryptographic authenticity, public reachability, peering, finality or administrative independence. --apply requires BOTH real EL and CL seed ENRs plus a separate external operator TTY confirmation START-EXTERNAL-31340-OBSERVER. It creates exactly TWO containers (EL and BN), never a Lighthouse validator client or a second original key. A partially started deployment is preserved for diagnosis and MUST NOT be repeated blindly. Source-only tests cannot stand in for actual native peer handshakes or syncing.

### External host prerequisites

1. The machine must be a truly physically and administratively independent Linux x86_64 host, running Docker and capable of sudo -n docker. It should NOT have any original G2 or R27 signer data. This is a RESEARCH validation target, not a container on the same owner VM/cloud account.
2. Receive ONLY the owner-observed PUBLIC archive, verify SHA256 1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7 before use. Transfer through explicit legitimate file sharing, public HTTPS artifact distribution, or a verified physical medium. Never share any owner private directory.
3. Obtain exact reviewed GitHub source SHA and pinned image manifests. The current AkrAyoub/sse-research GitHub repository is PRIVATE. **THIS IS A PUBLIC RELEASE BLOCKER**: full permissionless onboarding must NOT depend on an invitation to a private developer repository. Before public announcement, publish a separately accessible reviewed source/installer and immutable public genesis artifacts to an open public repository or HTTPS release location. No user public artifact endpoint is currently configured, and no release asset is uploaded by R48.
4. Verify official client images by immutable digest (see config/pos_client_image_pins.json). The R48 preflight refuses absent/wrong pinned image IDs; it does not silently pull mutable tags. For first R48 development validation, authorized external test operator may clone the private dev repo; that is developer-only, not evidence of permissionlessness.
5. Obtain a true reachable EL devp2p signed ENR and a separately signed CL Beacon discovery ENR from the original real seed(s). Strings are not independently signature-verified by R48 source tests. No such reachable public seeds have yet been observed, so --apply is NOT authorized now.

### Developer-stage commands on a DIFFERENT host (not VM4706)

    SHA=<immutable reviewed GitHub commit>
    git fetch origin feature/r19-fresh-external-node-preflight
    git switch --detach "$SHA"
    test "$(git rev-parse HEAD)" = "$SHA"
    python3 -B -m unittest discover -s tests -p 'test_sse_pos_r48_external_observer.py' -q
    python3 -B tools/sse_pos_r47_public_observer_bundle.py --verify /path/to/copied/chain31340-public-native-observer-v1.tar.gz --expected-commit "$SHA"
    python3 -B tools/sse_pos_r48_external_observer.py --plan --bundle /path/to/copied/chain31340-public-native-observer-v1.tar.gz --expected-commit "$SHA"

Only AFTER real public bootstrap ENRs, independent host identity and external network are actually available:

    python3 -B tools/sse_pos_r48_external_observer.py --apply --bundle /path/to/copied/chain31340-public-native-observer-v1.tar.gz --execution-seed-enr "$REAL_PUBLIC_EXECUTION_ENR" --beacon-seed-enr "$REAL_PUBLIC_CONSENSUS_ENR" --expected-commit "$SHA"

The --apply command is NOT the next command for VM4706. It is deliberately fail-closed until both native bootstraps exist. Never put the owner original validator on that external host.

## Next network engineering blocker, not a lack of test code

Step53 showed VM4706 has only PRIVATE interface addresses and an internal Docker network, Besu P2P disabled. Even with a valid archive, an independent observer cannot sync until the original chain becomes reachable via real native P2P. Provision a publicly routable TCP+UDP edge (dynamically addressed is fine with correct endpoint updates), explicitly review the controlled single-VC stopped maintenance migration on VM4706, preserve EL+CL DB/real SSZ+JWT and original slashing database, and prove native external handshake from a different operator ISP. THEN run R48 external observer and independently validate chain height/head/finalized epochs. Two public independent bootnode operators and an independently held second 32 TEST ETH validator are later acceptance gates.

All tracked code edits remain in GitHub, no GitHub Actions. This staged code does not change the live chain. NEVER call this development-stage candidate a public permissionless release.
