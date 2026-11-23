# R225 — REAL original chain31340 VM4707+VM4709 finalized epoch602 same root; formal 180s skew gate not satisfied

**Observed 2026-11-23 UTC:** operator submitted fresh VM4709 actual R141
read-only EL+CL capture from exact source
`a34716418f5c4f7afe79fda4d6622d314275dc1f`. The already
verified VM4707 R224 capture was independently obtained earlier.

| Field | VM4707 | VM4709 |
| --- | --- | --- |
| capturedAtUtc | 2026-11-23T16:39:06.445864+00:00 | 2026-11-23T16:42:07.669672+00:00 |
| nodeId, report label | vm4707-observer | vm4709-observer |
| chainId | 31340 | 31340 |
| executionBlockNumber | 17783 | 17798 |
| beaconHeadSlot | 19394 | 19409 |
| executionNativePeers | 2 | 2 |
| beaconNativePeers | 2 | 2 |
| finalizedEpoch | **602** | **602** |
| finalizedRoot | **exact same** | **exact same** |

Finalized root (both):
`0x9d140067a9049103fc482221713f2f0c46cf7d0a89593bef4d6e19fb0dddecd7`.

Original execution genesis hash (both):
`0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf`.

Original Beacon genesis validators root (both):
`0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd`.

All locally observed flags on BOTH nodes:
`executionSyncing=false`, `beaconSyncing=false`,
`executionOffline=false`, `optimistic=false`,
`localClientApisRead=true`, `dockerChanged=false`,
`transactionSubmitted=false`, `validatorKeyRead=false`,
`independentOperatorVerified=false`,
`publicInternetNativeP2pVerified=false`,
`remotePhysicalResourceVerified=false`.
The operator's VM4709 terminal reported
`R224_VM4709_LIVE_CHECK_COMPLETED=true`.

## Correct acceptance status

- **PASS observational comparison:** the two **actual separately
  installed** VM4707 / VM4709 execution+consensus nodes independently
  reported the same native PoS finalized epoch602 and exact root,
  original genesis identities, nonzero native EL+CL peers and
  non-optimistic non-syncing state. This is not a mock.
- **NOT FORMALLY PASS for R141 180-second time-skew bound:**
  observed capture skew = **181.223808 seconds**, exceeding the
  strict 180s threshold by **1.223808 seconds**. Neither tool
  `--compare` result nor a near-simultaneous re-capture was
  submitted. Do not write `OBSERVED_CONSISTENT_CHECKPOINTS` for
  this exact pair. R192 earlier epoch571 pair **did** meet that
  formal requirement at 5.828319s and remains valid.
- A new pair captured within 180s may be collected as a final
  strict cross-VM checkpoint audit; exact epoch/root must still match.
  No need to interrupt initial application deployment preparation
  merely because the timestamp window exceeded 180s by ~1.2s.
- Operator and ISP independence, external unprivileged open Internet
  admission without overlay, genuinely independent second validator
  and physical SSE SLA remain unproven.
- No V2 market deployment, signer creation or native TEST ETH
  transfer is performed or authorized by any of these read-only tests.

## Architecture: VM update compatibility (per owner question)

- A GitHub commit is **source**, not a change to running node software.
- Solidity V2 contracts will be created ONCE as a native chain31340
  transaction after separate authorization; all synchronized nodes
  observe them via canonical state; no re-deploy on each VM.
- Application/role agent changes require releasing to EACH affected
  agent host; documentation/test-only changes do not require updates;
  EL/CL binary and node configuration changes require planned
  compatible rolls with live finality and no validator double-sign.
- Original VM4706 BLS keys, validator, historical chain genesis and
  existing VM4707/VM4709 node containers must remain untouched.

## Next action

Proceed with read-only original owner VM4706 app-EOA custody/tooling
preflight, review objective TEST-only bond/funding policy and exact
signed transaction plan. Require explicit owner approval before ANY
wallet generation, native test-ETH funding, deployment, monitor bond,
resource bid or escrow transaction.
