# R186 — Failed root-pinned Beacon API probe; safe alias-based SSZ export

## Latest real evidence

Owner VM4707 executed R185 3 unit tests OK; the real
`sse_pos_r185_owner_ssz_root_pinned_preflight.py` returned
`R185_CHECKPOINT_PREFLIGHT_REFUSED: owner Beacon API inaccessible`.
R185 suppressed the precise HTTP status, so we cannot state
whether the immutable-root lookup was unsupported, the request
timed out, or another transport issue happened. R186 adds
sanitized HTTP stage detail to R185.

The owner same Beacon REST previously served finalized state SSZ
GET HTTP 200, size 2857456 bytes, and finalized block SSZ GET
HTTP 200, size 1417 bytes; both endpoints were localhost. Existing
VM4709 EL and CL are restarting (permission-changing Besu
entrypoint and Lighthouse weak-subjectivity from stale genesis).
VM4709 Beacon DB is already populated, including a private
P2P identity key that must not be shared. VM4707 and VM4709
native peer TCP ports are reachable, SSH port22 inaccessible
in both directions.

## New implementation

`tools/sse_pos_r186_owner_public_ssz_checkpoint_export.py` creates
exactly one new operator-owned directory containing ONLY:
- `checkpoint-state.ssz` from owner Beacon REST
  `/eth/v2/debug/beacon/states/finalized`.
- `checkpoint-block.ssz` from
  `/eth/v2/beacon/blocks/finalized`.
- `checkpoint-manifest.json` with original chain31340
  genesis validators root, epoch, finalized block root,
  finalized slot, bytes and SHA256 of each complete file.

BEFORE, BETWEEN and AFTER the two SSZ GETs, the exporter
re-reads the owner's **actual finalized epoch and root**, and
refuses any change. It also checks the actual finalized header
block root and slot after downloading. If the finalized
checkpoint moves during any read, the exporter refuses.
Each SSZ GET is bounded in size. It never reads JWT, signer
keys, hidden wallet paths, client databases or exposes REST.
It creates the output directory exclusively; no existing
files are overwritten. It prints no raw SSZ contents.

Security limits: consistency of finalized-root observations
and SHA256 transport integrity do NOT independently prove the
cryptographic SSZ hash-tree-root or Lighthouse consensus
correctness. The receiving pinned Lighthouse instance must
validate the checkpoint against the exact original genesis.
The source owner VM4707 is operator-trusted for this initial
research checkpoint; it is not an independently verified
permissionless network bootstrap authority.

## Immediate owner path

Run pinned R186 unit tests and root-stable exporter against actual
owner Beacon localhost. If successful, OWNER can publish the
three PUBLIC, nonsecret SSZ/manifest assets to one uniquely named
new GitHub Release tag; never replace the immutable original
genesis release. A new node may anonymously download these
public files, verify hashes/genesis/epoch and import to a
FRESH, EMPTY Beacon DB. The current populated VM4709 Beacon
DB and P2P identity must be preserved and never deleted.

This alone does not fix the already-created Besu entrypoint
or replace the restarting Lighthouse container. Existing
client migration must be done separately with exact image,
configuration, data, ports and rollback safeguards. No
verified native ETH peers or VM4709 finality yet.
