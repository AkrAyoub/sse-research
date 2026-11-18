# SSE — Four-validator QBFT laboratory (manual, no Actions)

This code stages a real **Hyperledger Besu QBFT peer-to-peer consensus** lab.
It deliberately does **not** replace an existing Anvil deployment, deploy SSE
contracts, or assert production-grade decentralization. Four validator
containers on one VM have independent processes and keys but share one
physical host and Docker fault domain.

## What is different from SSE monitoring?

* Blockchain validators take turns proposing blocks and vote on the chain's
  state. They run the blockchain.
* Consumers purchase computing services, providers offer them, and separately
  selected bonded monitors issue signed SLA observations.
* Monitor votes (e.g., 3-of-4) are application-layer evidence, **not** QBFT
  consensus votes.
* QBFT is proof-of-authority, **not competitive PoW mining**. No mining
  hashrate contest or trustless public validator entry is claimed.
* This increment creates **no native/block or validator rewards**.
  A funded and audited validator compensation design is separate from the
  existing monitor bonds, reward pools and SSE provider settlement.

## Experimental genesis values: hypotheses, not measured optima

* Four initial validators: supports one faulty/unavailable validator with
  BFT assumptions. Losing two can halt finalization.
* 3-second target block period, 6-second initial request timeout:
  follows Besu guidance to start with timeout ~2x block interval.
* 10 million gas block limit: provisional workload experiment setting.
  This is **gas** (a computation budget), not bytes or a guarantee of TPS.
* Chain ID: 20261118. London-at-genesis with zero base fee for lab transactions.
* RPC is bound on the **host** to loopback ports 18545–18548. No external RPC
  port is deliberately published. Node P2P is on an internal Docker bridge.
* A publicly known Anvil development address is pre-funded with test-only
  ether in genesis to enable subsequent **manual** deployment experiments.
  Never use this network as a real-money environment.
* Besu image is tagged 26.6.1. Record its resolved image digest on the
  executing VM; no image or package is downloaded by the Python source
  except Docker pulling the explicitly pinned image during bootstrap.

## Ubuntu VM commands

Run from a checkout of the new GitHub branch, at the repository root. Needs
Python 3.12+, Docker Engine, and Docker Compose v2. Does not need Foundry just
to start the network. Anvil on 8545 is undisturbed.

    git status --short
    python3 -m unittest discover -s tests -p 'test_qbft_lab_config.py' -v
    python3 infra/qbft-lab/qbft_lab.py prepare
    python3 infra/qbft-lab/qbft_lab.py up
    python3 infra/qbft-lab/qbft_lab.py status
    python3 infra/qbft-lab/qbft_lab.py verify
    python3 infra/qbft-lab/qbft_lab.py sample --seconds 30

If verify fails immediately after startup, inspect logs and confirm peers
discover one another. Do not regenerate genesis keys to cure a transient
startup race.

    python3 infra/qbft-lab/qbft_lab.py logs
    python3 infra/qbft-lab/qbft_lab.py down
    python3 infra/qbft-lab/qbft_lab.py up

The down command **does not erase** keys, chain data or evidence. The prepare
command refuses to overwrite existing state. Files live under
.local/qbft-lab/, which stays out of Git. Do not commit those validator keys.

## Failure experiment — only after successful baseline

    docker compose -p sse-qbft-lab -f .local/qbft-lab/compose.yml stop validator4
    python3 infra/qbft-lab/qbft_lab.py status
    docker compose -p sse-qbft-lab -f .local/qbft-lab/compose.yml start validator4
    python3 infra/qbft-lab/qbft_lab.py verify

Record block-height growth with exactly one offline node. The strict verify
command intentionally requires all 4 nodes; status displays a partial
network. Do not infer Byzantine security merely because a process was stopped.

## Scientific evaluation required before changing SSE's chain

1. Record the same-genesis chain ID, four validators, peer counts, shared
   canonical blocks, and progress both in healthy and one-offline states.
2. Repeat 30s+ samples (different seeds/runs) for idle p50/p95 block time
   and time spent stalled, plus CPU, RAM and packet/byte traffic.
3. Use real SSE settlement transactions (separate phase) to measure gas and
   raw encoded transaction size by operation, inclusion latency, finalized
   latency, and observed gas/byte occupancy, each over many trials.
4. Independently sweep initial block periods e.g. 2s, 3s, 5s and gas budgets
   with **fresh networks**, never silently change an existing genesis.
5. Move validators to independent VMs with authenticated restricted P2P,
   durable key management, time sync and verifiable deployment manifests.
6. Choose the finally published block period/gas limit from measurements and
   the required SLA latency/cost targets. Current values are just baselines.

The sample command saves observations under .local/qbft-lab/sample-*.json.
It does not send transactions, measure TPS, establish cloud independence,
or prove the truthfulness of service observations. The historical SSE
Anvil contract addresses and balances do not exist on this new chain.
A separately verified deployment and migration is mandatory.

## Reference sources

- https://docs.besu-eth.org/private-networks/tutorials/qbft
- https://docs.besu-eth.org/private-networks/how-to/configure/consensus/qbft
- https://docs.besu-eth.org/private-networks/how-to/configure/free-gas
- https://docs.besu-eth.org/private-networks/tutorials/quickstart

GitHub is source control only for this work. No GitHub Actions, hosted CI,
workflows, or pull-request automation are used.
