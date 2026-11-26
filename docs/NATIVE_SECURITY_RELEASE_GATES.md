# Native consensus and decentralization release gates

## Scope
Retain original Ethereum EL/CL proof-of-stake chain31340; no synthetic mining, reset, permissioned validator allowlist or mandatory centralized RPC. TEST ETH has no market value; do not claim mainnet economic security. Native consensus and SSE monitor committees are distinct security domains.

## Observed evidence
VM4707 validator index2 and VM4709 index1 active since epoch1212; operator logs show successful signed block publication and attestations (VM4707 slots43094/43095 and attestation43093; VM4709 slots43096/43098/43099 and attestation43103). Both containers restart unless-stopped. Three active validators at 32 ETH effective balance each. Both nodes agreed finalized height41424. Publication logs alone do not prove canonical inclusion of each block or reward amounts. Repeated proposer duty dependent-root warnings require comparison to canonical block roots and missed slots rather than assuming actual chain reorgs.

## Release gates
1. Automatic permissionless onboarding: fresh external operators with locally generated keys, immutable genesis/chain manifest, multiple discoverable bootstrap peers, no fixed participant IP, no privileged approval, no mandatory shared RPC, verified sync and native deposits. Document NAT/relay/vendor dependencies and weak-subjectivity trust.
2. Native rewards: finalized beacon reward API for attestations and blocks, actual balances and withdrawal records, execution priority fee recipient audit, no synthetic rewards or assumed APR.
3. Native security: retain slashing protection databases, test offline penalties and recovery on original chain within safe stake bounds; destructive equivocation/slashing experiments only on explicitly isolated disposable chain with separate keys/genesis. Verify finality, canonicality, fork choice and rejected invalid transactions.
4. Experimental expansion target seven equally weighted validators across independent operators and infrastructure/failure domains, preferably ten in larger experiments; target not a proof or admission requirement. Measure actual effective stake concentration by disclosed operator and infrastructure, distinguish unknown ownership. No identity count presented as Sybil resistance. At seven equal validators, ceil(2N/3)=5 and strict Byzantine bound floor((N-1)/3)=2.
5. Remove mandatory single operator services, audit centralized funding/genesis allocations and faucet abuse. Free TEST ETH cannot supply real economic attack cost; no claim of unconditional Sybil resistance. No real-money conversion or token sale.
6. Separate SSE monitor layer: capacity/collateral, globally fair sampling with explicit randomness assumptions, concurrent assignments, provable misconduct and qualified negative evidence, no punishment for uncertainty alone.
7. Publish measured duties, rewards, effective stake distribution, peer reachability, finality lag, missed slots, fault and recovery evidence in public read-only dashboard. Privileged local operations remain owner authorized; no account login requirement.
8. Preserve original chain and evidence; do not duplicate validator keys or restart live validators casually. New VMs after installer ready; obtain independent operator participation, not just extra VMs controlled by one person.

Acceptance requires actual cross-infrastructure tests, not merely code or documentation. Production-grade economic security and operator independence cannot be guaranteed by a testnet implementation.
