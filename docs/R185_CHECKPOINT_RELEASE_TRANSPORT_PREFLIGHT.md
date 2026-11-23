# R185 — real asymmetric peer SSH timeouts, small SSZ and pinned-root export gate

## Observed on actual hosts (2026-11-23)

- VM4707 `sshd` active, listening port22 on all v4/v6 addresses.
- VM4709 `sshd` active, listening port22 on all v4/v6 addresses.
- From VM4709 to VM4707 ZeroTier IPv6 port22: TCP timeout.
- From VM4707 to VM4709 ZeroTier IPv6 port22: TCP timeout.
- In contrast native actual VM4709→VM4707 TCP30404 Besu and TCP9000 Lighthouse were both reachable. Both SSH directions failing does not establish the particular firewall, but rules out immediately transferring SSZ via SSH without route/config changes.
- VM4707 owner Beacon API localhost GET with Accept application/octet-stream confirmed finalized SSZ `state` Content-Length `2857456` bytes, `block` Content-Length `1417` bytes. Earlier HTTP HEAD returned 405 because this API does not support HEAD on these endpoints. There is no need to disable firewall or publish Beacon REST publicly.

## Proposed temporary owner-controlled public checkpoint artifact transport

The state and block SSZ for an existing finalized checkpoint are **PUBLIC chain data**, unlike a wallet mnemonic, private P2P identity, Engine JWT or validator signing keys. A suitably reviewed, publicly accessible immutable GitHub Release asset bundle can transport these two small artifacts from VM4707 to VM4709 for this research deployment. This transport would be optional and centralized for bootstrapping, NOT a permissionless peer-discovery dependency or consensus authority, nor a paid API. GitHub CLI supports `gh release create` with assets and anonymous download of public releases.

Lighthouse official docs support manual `--checkpoint-state` and `--checkpoint-block` SSZ inputs, and require a **fresh Beacon database**. The existing VM4709 Beacon DB contains RocksDB chain/freezer/blob state and a local network identity. It must be preserved; do not purge or replace it.

## Cryptographic and operational requirements before publishing

1. Ask actual VM4707 Beacon API for original genesis root and finalized epoch/root; require original chain31340 root.
2. Request BOTH SSZ artifacts by ONE IMMUTABLE finalized block-root URL, not a moving `/finalized` alias for each request. Some Beacon API implementations may not serve SSZ by block root; this must be empirically tested. R185 introduces an exact read-only bounded preflight which refuses unsupported endpoints.
3. After this passes, stream/download full state and block to an operator-owned nonsecret temporary directory, bind the pair to one finalized block-root+slot, compute sha256 for each and publish a manifest with original genesis root and asset hashes. Fail closed on inconsistent checkpoint.
4. The public GitHub release asset must be explicitly named, immutable (no `--clobber`) and associated to the actual GitHub source commit; don't accidentally make the prior genesis release wrong. Anonymous VM4709 downloader must check exact SHA256 against a trusted manifest, original genesis and finalized root. Hashes alone don't establish cryptographic SSZ block-root verification, which a correctly configured pinned Lighthouse client must also perform.
5. VM4709 must use a new empty Beacon database/root to checkpoint sync while preserving old populated data+P2P identity and original Engine JWT; any replacement of exact Docker containers needs a separate reversible user-approved operation and original security flags. No automatic `--ignore-ws-check`, `--purge-db`, fixed VM IP or open Beacon REST endpoint.

## Current checked-in code

`tools/sse_pos_r185_owner_ssz_root_pinned_preflight.py` invokes only four bounded GET operations against owner localhost 127.0.0.1:25052: genesis, finality, then state and block SSZ by the SINGLE finalized root. It produces nonsecret lengths and checkpoint root; no file or GitHub mutations. Tests inject fake responses solely to validate URL binding and refuse mismatched genesis/genesis-only checkpoint, not to claim real Beacon support or native P2P verification.

This stage does NOT publish a checkpoint yet. VM4709 still has both actual EL and CL containers restarting and NO verified native EL/CL handshake or same finalized root.
