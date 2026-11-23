# R171 — Real VM4709 anonymous public native discovery confirmed

## Operator-observed evidence

Pinned R170 revision: `df3df85190789cc14fe6920a248f6a7545a44197`.

VM4707:

- Python tests: **Ran 1131 tests in 17.518s, OK (skipped=3)**.
- Fresh R156 genuine local Besu/Lighthouse public record refreshed the same GitHub issue #42 comment **7097016936** (no comment flood).
- `--diagnose-public`: `publicCommentsReturned=1`, `markedNativeComments=1`, `freshValidNativeComments=1`, `publicReadbackProven=true`.
- `--discover`: `candidateNodeCount=1`, `chainId=31340`, actual current Beacon ENR and execution enode returned, no hardcoded VM P2P address entered by operator.
- Correctly recorded: `actualNativePeersAuthenticated=false`, `peerReachabilityVerified=false`, `independentDiscoveryInfrastructureVerified=false`.

**Separate real VM4709** (Ubuntu 24.04.4 LTS, a previously uninstalled research VM):

- Anonymously cloned public `AkrAyoub/sse-research` via HTTPS and switched to the **same** reviewed pinned R170 SHA.
- Executed R168 `--discover` with no GitHub login and retrieved the same real original chain31340 native enode and Beacon ENR.
- Again returned `candidateNodeCount=1`, `chainId=31340`, `temporaryCentralizedRendezvous=true`.
- No wallet copied, no original validator restarted or chain genesis replaced.

This is a **verified cross-VM discovery milestone**, not verified cross-VM EL/CL native peering, finality or PoS validator activation. The user also executed an anonymous clone/discovery command on VM4707; do not miscount this as a separate third node. VM4709 independently executed the command afterward.

## Immediate real deployment step

The source-reviewed R170 runtime path in R151 can use this actual public source to pass non-synthetic EL/CL seed identities to real R137 Besu/Lighthouse containers. Only new VM4709 should execute the privileged installer. First refresh the real VM4707 short-lived public record. On VM4709 check it can still discover fresh records, then run the **pinned** R170 `scripts/sse_install.py --commit` as root, choose **observer** or **full_node** at the one menu, never select validator/provider/consumer/monitor while their actual provisioning remains incomplete. The installer will install signed host prerequisites and launch real pinned Docker clients, not a simulator. Do not mistake container creation for synchronized chain.

**Important failure handling:** R147 writes the private source selection state before R151's privileged package/client runtime completes; partially failed host provisioning can leave create-once state/resources that require inspection. Never blindly rerun or delete owner data. On VM4709, capture the full error and inspect stopped Docker state before considering any controlled retry. This is an open fail-safe/recovery engineering limitation. No source-level tests or prior nominal plans prove that this first real R151 clean-VM deployment will succeed.

## Architecture remaining

GitHub issue #42 is a temporary single-provider, time-limited discovery availability service, not independent permissionless native discovery. Its 600-second node record needs recurring refresh. Original immutable in-content public genesis hash and internal member hashes remain pinned and checked. Native peer handshake, same finalized Beacon checkpoint, separate external infrastructure and ongoing discovery freshness are still unverified. No manually pinned VM IP/enode, key cloning, admin admission list or new genesis is acceptable.

The final intended network also requires independently activated validators with actual TEST ETH funding/deposits, funded on-chain SSE provider/consumer/monitor economics, measured work and SLAs and a defensible scientific paper. Those are not met by this cross-VM discovery milestone.
