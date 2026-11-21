# R47 — Authentic public chain31340 observer artifacts (NO signing keys)

**Status:** Implemented through connected GitHub source. Runtime evidence from owner VM required; no Internet seed or independent node launched by R47.

## Why

The original chain31340 is actually finalized on Besu 26.11.1 + Lighthouse v8.3.3. Owner VM4706 is behind private addressing with NO native P2P port bindings and currently runs inside Docker --internal. An independent observer must first receive verifiable PUBLIC chain metadata without receiving the original wallet, validator key, keystore password, JWT or slashing database.

The independently inspected owner Step53 actual EL block height=202, Beacon head slot=420 and positive finalized epoch=9 with all 103 G2/public-network policy tests passing. Those data remain on one physically controlled owner VM and are NOT evidence of publicly reachable peers.

## Genuine public artifact package

Source: tools/sse_pos_r47_public_observer_bundle.py, EXACT detached GitHub SHA only. Archive contains precisely:

- chain31340-public/genesis.json — original real Besu EL genesis, pinned SHA256 22eb6c58288113b9c3671970967151012665137b345237b5c24060dc988b1ee8
- chain31340-public/config.yaml — **complete working** canonical Lighthouse v8.3.3 CL configuration, pinned SHA256 3e750d7d02e3ed83747f95cc09ff3299185f56f1777dfeb1f126b17881297b6e
- chain31340-public/genesis.ssz — original genuine 2,737,436-byte Beacon state, pinned SHA256 8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82
- chain31340-public/deposit_contract_block.txt — 0 deployment marker, pinned SHA256 9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa
- chain31340-public/manifest.json — nonsecret public provenance, client versions, chain 31340, original SSZ genesis time, deposit contract address and canonical 6,358-byte standard ungated runtime SHA256 5aaa8327c5765ec883224895ca02cade2871e12dad0197bdc791efc91c7ef18d

Exactly five allowlisted archive entries; no recursive directory export. Contents and manifest are authenticated against pinned GitHub source. No owner-specific signer credentials are read or exposed. The owner export creates one tar.gz in private, owner-only mode 0700 directory ~/.local/share/sse-r47-chain31340-public-artifacts with archive mode 0600. The archive contains PUBLIC material only, and can later be uploaded to a trusted HTTPS/public GitHub release or transferred to a physically external independent machine after explicitly checking the bundle hash.

## Exact owner commands (only on VM4706, after clean SHA fetch)

    python3 -B -m unittest discover -s tests -p 'test_sse_pos_r47_public_observer_bundle.py' -q
    python3 -B tools/sse_pos_r47_public_observer_bundle.py --plan --expected-commit "$SHA"
    python3 -B tools/sse_pos_r47_public_observer_bundle.py --build --expected-commit "$SHA"

Build is one-time O_EXCL: if an output directory/archive already exists, it REFUSES rather than overwriting. Verify the reported SHA256 and archive contents using:

    python3 -B tools/sse_pos_r47_public_observer_bundle.py --verify "$HOME/.local/share/sse-r47-chain31340-public-artifacts/chain31340-public-native-observer-v1.tar.gz" --expected-commit "$SHA"

The verifier can run on an independently administered machine with the same exact GitHub source checked out, without any owner private G2 directory or wallet. Its read-only verification does NOT extract the archive. No node is started; DNS, P2P, stake and independent signer are NOT verified by this step.

## Next honest real-network gates

1. Owner Step54 establishes that archive actually built and independently validated from real existing files, while current EL/CL/VC remain running.
2. Establish at least one genuinely publicly reachable execution+consensus bootstrap host with dynamic-DNS/updated-ENR support and real native TCP+UDP ingress. VM4706 has neither direct public IP nor published P2P today; merely copying public genesis files cannot change that. Avoid CGI/HTTP-only tunnels presented as native P2P.
3. Build a separate NON-SIGNING native Besu+Lighthouse observer using only the public bundle. It must use own EL/CL node identity and owner-independent local Engine JWT; must never receive owner BLS keystore or slashing DB. New node starts only once real enode/ENR plus external P2P path are known; validate actual devp2p peer handshake, Beacon peer count and matching finalized checkpoints.
4. Conduct a reviewed owner VM migration from its internal Docker bridge to genuine P2P after seed reachable, with original EL database, Beacon state, and exactly one original signer preserved. No second genesis or new chain and no duplicate validator.
5. Only then admit an independent validator using its OWN 32 unvalued TEST ETH deposit + own encrypted BLS key and original chain's actual activation protocol. Full public release additionally requires two genuinely independently operated native bootstraps as codified in tools/sse_public_network_preflight.py.

Never claim decentralization solely from exported files or successful local API responses. No GitHub Actions; tracked changes only through GitHub connector. Preserve original source branch and live EL/BN/VC through this public-only preparation.
