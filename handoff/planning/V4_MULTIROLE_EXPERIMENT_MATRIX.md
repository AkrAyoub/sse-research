# V4 revised 14-host experiment plan (2026-11-27)

Proposed lab roles, not admission restrictions. No changes yet on actual hosts.
All ten immediate application participants may be monitors, with provider,
consumer and keeper overlap; each lease excludes its own consumer and provider
addresses from the monitor draw. Same-wallet exclusion is not operator exclusion.

| Host | Initial application roles / purpose |
|---|---|
| 4706 | Preserve genesis validator/funding custody |
| 4707 | Existing validator; consumer, monitor, keeper |
| 4708 | Inventory required; candidate full node, provider, monitor, keeper |
| 4709 | Existing validator/RPC relay; preserve until relay upgrade |
| 4711 | Monitor, keeper |
| 4712 | Monitor, consumer |
| 4713 | Monitor, keeper |
| 4714 | Provider, monitor |
| 4715 | Monitor, keeper |
| 4717 | Provider, monitor |
| 4718 | Provider, monitor |
| 4719 | Consumer, monitor, keeper |
| 4720 | Monitor, keeper |
| 4721 | Nonsigning native full node; provider/monitor candidate after secure checkpoint sync and measured headroom |

Ten immediate monitor identities, three potential providers, three consumers,
six keepers; none asserted active. Provider roles require actual isolated worker
provisioning and measured headroom; capacity stays zero until verified.
Initial monitor capacity one, then increase explicitly following concurrent
probe measurements. Capacity counts concurrent leases, not votes per lease.
Keeper transitions have no bounty or privileged coordinator. Simulate before
send does not eliminate cross-node races; measure reverts/gas and progress.

## Planned experiments (no synthetic live evidence)
- Vary eligible roster M and n,b,s: n=4,b=1,q=3; n=7,b=2,q=5;
  n=10,b=3,q=7. Need n+s distinct eligible addresses after exclusions and
  saturation. Ten registered identities yield eight eligible if both
  counterparties are registered; n=7,s=1 or n=4,s=2/4 feasible before
  additional reservations. n=7,s=2 needs 11 registered in that case;
  n=10,s=2 needs 14; n=10,s=4 needs 16.
- Provider competition 1/2/3+, consumers 1/2/3+, concurrent leases,
  actual CPU/memory isolation, distinct workers, capacity refusal, latency,
  throughput and bids.
- Keeper availability K=0/1/2/4/6 with selfKeep disabled/enabled explicitly;
  transition completion, outages, repeated sends/reverts, gas per accepted
  transition, nonce and canonical outcomes.
- Formation: standby promotion, insufficient roster, saturation, withdrawal,
  bounded draw exhaustion. n>=3b+1 conditional on at most b Byzantine
  selected members. Future blockhash is proposer-influenceable, not VRF.
- Sybil/collusion: controlled distinct wallets of one adversarial lab operator,
  vary roster fraction and selected faults. Separate same-owner scaling from
  independent-operator runs. Free test ETH does not prove economic resistance.
- Network: fresh verified weak-subjectivity checkpoint sync, compare finalized
  roots across EL/CL nodes; relay outage/failover, delays, partitions, peer
  churn, validator availability and finality. Single relay/rendezvous remain
  dependencies, not decentralized discovery.
- Evidence: honest success, authenticated wrong output, silence as uncertainty,
  conflicting votes, replay, withheld response, exposure admission/residual
  reconciliation. Preserve actual receipts, workload/probe logs and role map.
- No absolute attack-proof claim. Operator independence, fair randomness,
  slashable economic stake, discovery and checkpoint/RPC trust need evidence.

VM4721 Lighthouse refuses stale genesis outside weak subjectivity period;
do not bypass --ignore-ws-check. Need verified recent finalized checkpoint
on original chain; preserve existing Besu and old nonsigning BN data.
VM4708 not yet inventoried. Prior relay/preparation commands not executed.
No funding or registration authorization.
