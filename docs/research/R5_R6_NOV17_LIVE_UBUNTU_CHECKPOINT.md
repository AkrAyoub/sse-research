# SSE R5/R6/R8/R9 live Ubuntu checkpoint — 2026-11-17

**Status:** verified operator-reported VM command transcripts from the SSE research
lab, not final end-to-end research acceptance. This records evidence
separately from the original phase-percent planning estimates in
`PHASES_TRACKER.csv`. No numerical percentage is changed by this document.

## Machine inventory (portal-hostnames are NOT unique)

| Existing Ubuntu hostname | Portal Linux user | Private IP | Assigned application role |
|---|---|---|---|
| `patch-dil-template-s2-service-base-g68-20260628-044954` | `ayoubakrvm4693` | `10.50.56.8` | Consumer + Monitor + Observer |
| `patch-dil-template-s1-service-base-g68-20260628-050503` | `ayoubakrvm4695` | `10.50.56.20` | Blockchain / RPC |
| `patch-dil-template-s2-service-base-g68-20260628-044954` | `ayoubakrvm4696` | `10.50.56.2` | Provider + Observer (intended; runtime not started) |

The provider VM reports the **same hostname** as the consumer/monitor VM.
Use portal user + private IP / verified SSH host key to distinguish machines.
R7 onboarding source now generates a separate random persistent node identity;
this was tested with mocked same-hostname scenarios, not yet provisioned on
the provider VM.

## Confirmed protocol development-chain evidence

- VM 4695: Ubuntu, Foundry/Anvil 1.9.0, 4 vCPU and 11 GiB RAM. Loopback
  RPC `127.0.0.1:8545`, chain ID 31337. `sse-anvil.service`
  reported `active` and `enabled`. Reboot/restore not yet tested.
- VM 4693: Python baseline suite reported 698 discovered, 695 passed,
  3 skipped, no failures. Foundry Solidity `forge build` compiled
  56 files successfully **with compiler/lint warnings pending review**.
- SSH private network: TCP 22 on VM 4695 reachable from 4693; pinned
  Ed25519 host key verified; `sse-rpc-tunnel.service` reported `active`
  and `enabled`, and forwarded chain ID `0x7a69` successfully.
- Three actual Anvil contracts deployed and mutually bound:
  `OpenMonitorCommittee` 0x5FbDB2315678afecb367f032d93F642f64180aa3,
  `SSESettlement` 0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512,
  `OpenResourceBoard` 0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0.
  Committee opted into delayed-block entropy, **not VRF**. Settlement
  EIP-712 domain and bytecode passed remote read-only join preflight.
- VM 4693: separate encrypted consumer and monitor wallets were
  locally generated and funded from known Anvil developer accounts.
  Monitor 0xCa8978d722fAe6738D00cDE24961F7C4240B42e3 registered
  with 1 Gwei bond in block 10; transaction
  0x2d6c57fe440a0147bb4d51e2badf1da23ba0aa2f16df7f0bd6cf95240daaf741.
  On-chain candidateCount=1 and active=true. This candidate **must not**
  monitor a lease owned by its co-located consumer identity.
  Plaintext runtime signer was subsequently removed.
- R7 VM operator test suite passed 10/10 on Ubuntu, and R7 SSH release
  handoff mock/offline tests passed 6/6 at commit
  `5d2985bed015a04f75ff833894b22f320785dc42`.
  **No actual new-VM SSH release transfer has yet been performed.**
- VM 4693 could reach VM 4696's reported private IP 10.50.56.2 on TCP 22.
  The subsequent SSH host fingerprint and machine-id commands were
  displayed under an `ayoubakrvm4693` shell prompt, NOT the intended
  provider `ayoubakrvm4696` prompt. Therefore the provider host key
  fingerprint has **not** yet been verified; do not pin that output
  as the provider identity without rechecking on the correct machine.

## Phase tracker impact — evidence vs acceptance

- **R0:** reproducible baseline remains accepted; Ubuntu regression
  evidence increased. Historical progress **100%**.
- **R2/R3:** contracts deployed and one bonded monitor accepted; does
  not establish security audit, fair committee, four selected eligible
  monitors, VRF, live evidence/votes or settlement payout validation.
  Historical percentages **R2 26%, R3 38%** unchanged.
- **R4:** signed evidence/code exists; independent physical service
  fact and finality remain unproven; historical **38%** unchanged.
- **R5:** one node-owned signed monitor transaction over remote RPC,
  but no autonomous complete participant service or inter-VM lease;
  historical **10%** retained pending acceptance review.
- **R6:** working Anvil service/SSH tunnel and R7 wallet + handoff
  tooling tested offline. Still no tested zero-key, first-boot,
  role-complete enrollment of a NEW VM; historical **5%** retained.
- **R7:** Docker daemon confirmed on intended provider machine;
  no provider SLA workload yet exercised; historical **15%** retained.
- **R8:** live-chain events exist but animated distributed UI and full
  index/reindex acceptance missing; historical **10%** retained.
- **R9:** multi-VM private connectivity established; no independently
  repeated, multisigner multi-VM scientific trials; historical **5%**.
- **R10/R11, P0–P6:** no phase acceptance changes from these
  infrastructure actions.

## Immediate critical path

1. Re-verify VM 4696 actual identity and ED25519 host fingerprint
   from its own portal SSH session. Re-use no SSH/GitHub key other than
   dedicated, restricted provisioning credentials.
2. Run real R7 private handoff only against the verified provider identity,
   then create its own provider role wallet and encrypted key store.
3. Configure authenticated RPC reachability and a Docker-backed signed
   provider workload without exposing raw Anvil RPC or public test keys.
4. Add at least four independently operated eligible monitor VMs for a
   lease owned by VM 4693. Distinguish wallet distinctness from
   independence of VM/operator.
5. Capture full signed service/execution evidence, contract vote quorum,
   N/F/S economic settlement and failover/negative trials.
6. Review the 42-item audit ledger, measure gas/fairness and freeze
   a signed reproducible release before final clean-room deployment.

Original source of truth: `docs/research/MASTER_TRACKER.md` and
`docs/research/PHASES_TRACKER.csv`; historical latest arithmetic was
(309 engineering + 180 research)/1900 = **25.74% (~26%)**.
