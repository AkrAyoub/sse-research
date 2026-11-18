#!/usr/bin/env python3
"""Generate key-free Besu QBFT genesis and a preregistered benchmark matrix.

Use independently generated validator node addresses and public test accounts.
Never generates, stores or transfers keys. Existing Anvil 31337 is untouched.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

ADDR = re.compile(r"0x[0-9a-fA-F]{40}\Z")
MIX_HASH = "0x63746963616c2062797a616e74696e65206661756c7420746f6c6572616e6365"
DEFAULT_CHAIN_ID = 31338
DEFAULT_BLOCK_REWARD_WEI = 10**13


class ConfigError(ValueError):
    pass


def eth_address(value: str) -> str:
    if not isinstance(value, str) or not ADDR.fullmatch(value) or int(value, 16) == 0:
        raise ConfigError("expected nonzero 20-byte public Ethereum address")
    return value.lower()


def rlp_encode(item: bytes | list) -> bytes:
    """Minimal Ethereum RLP encoding; no third-party dependencies."""
    if isinstance(item, list):
        payload = b"".join(rlp_encode(part) for part in item)
        prefix = 0xC0
    elif isinstance(item, bytes):
        payload = item
        prefix = 0x80
        if len(payload) == 1 and payload[0] < 0x80:
            return payload
    else:
        raise ConfigError("RLP accepts bytes or lists only")
    if len(payload) < 56:
        return bytes([prefix + len(payload)]) + payload
    length = len(payload).to_bytes((len(payload).bit_length() + 7) // 8, "big")
    return bytes([prefix + 55 + len(length)]) + length + payload


def qbft_extra_data(validators: list[str]) -> str:
    if len(validators) != 4 or len(set(validators)) != 4:
        raise ConfigError("baseline requires exactly four distinct validators")
    data = [b"\x00" * 32,
            [bytes.fromhex(v[2:]) for v in sorted(validators)],
            [], b"", []]
    return "0x" + rlp_encode(data).hex()


def genesis(validators: list[str], *, chain_id: int = DEFAULT_CHAIN_ID,
            block_period: int = 5, gas_limit: int = 15_000_000,
            reward_wei: int = DEFAULT_BLOCK_REWARD_WEI,
            funded: list[str] | None = None) -> dict:
    validators = [eth_address(v) for v in validators]
    funded = [eth_address(v) for v in (funded or [])]
    if chain_id < 1 or chain_id in (1, 31337) or chain_id >= 2**64:
        raise ConfigError("use an isolated non-mainnet, non-Anvil chain ID")
    if block_period not in (5, 12) or gas_limit not in (15_000_000, 30_000_000, 60_000_000):
        raise ConfigError("use a preregistered benchmark interval and gas limit")
    if reward_wei not in (0, DEFAULT_BLOCK_REWARD_WEI):
        raise ConfigError("use a preregistered synthetic block reward")
    if len(funded) != len(set(funded)):
        raise ConfigError("duplicate public genesis account")
    return {
        "config": {
            "chainId": chain_id,
            "berlinBlock": 0,
            "londonBlock": 0,
            "shanghaiTime": 0,
            "cancunTime": 0,
            "qbft": {
                "blockperiodseconds": block_period,
                "epochlength": 30000,
                "requesttimeoutseconds": block_period * 2,
                "blockreward": str(reward_wei),
            },
        },
        "nonce": "0x0",
        "timestamp": "0x0",
        "gasLimit": hex(gas_limit),
        "difficulty": "0x1",
        "mixHash": MIX_HASH,
        "coinbase": "0x0000000000000000000000000000000000000000",
        "extraData": qbft_extra_data(validators),
        "alloc": {a[2:]: {"balance": "100000000000000000000"} for a in sorted(funded)},
    }


def trials() -> dict:
    return {
        "schema": "sse-qbft-scientific-matrix-v1",
        "purpose": "Compare block capacity, network liveness and reward distribution, not PoW mining or PoS issuance",
        "preRegisteredVariables": {
            "blockPeriodSeconds": [5, 12],
            "blockGasLimit": [15_000_000, 30_000_000, 60_000_000],
            "validatorOutages": [0, 1, 2],
            "rewardWeiPerProposedBlock": [0, DEFAULT_BLOCK_REWARD_WEI],
            "offeredLoadPercentOfGasTarget": [25, 50, 75, 100, 125],
            "replicationsPerCondition": 5,
            "warmupBlocks": 100,
            "measurementBlocks": 600,
        },
        "measures": [
            "proposerByBlock", "blocksPerMinute", "observedInterBlockSeconds",
            "gasUsedPerBlock", "gasLimitPerBlock", "encodedBlockBytes",
            "submittedTransactions", "includedTransactions", "receiptLatencyMs",
            "qbftRoundChanges", "validatorSeals", "chainHeadAgreement",
            "consensusStallSeconds", "validatorMemoryRSS", "validatorCPUPercent",
            "perValidatorRewardBalanceDeltaWei", "SSESettlementContractGasUsed",
        ],
        "samplingPolicy": "Compare all arms under the same seeded workload trace. Randomize run order, do not alter consensus timestamps; disclose shared infrastructure.",
        "integrity": "Record client binary/container SHA256, genesis hash, chainId, validator keys' public addresses, host identity, UTC clock and raw per-block RPC evidence.",
        "notes": [
            "QBFT proposers rotate rather than compete in proof-of-work.",
            "Four validators tolerate one offline validator in the ordinary QBFT fault bound.",
            "Reward is an artificial mint to the proposer; fees and basefee burn must be measured separately.",
            "Values are preregistered research baselines, not measured optimal defaults.",
            "Run each changed genesis as a separate isolated network; never silently change existing genesis.",
        ],
    }


def write_new(path: Path, value: dict) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


def main() -> int:
    p = argparse.ArgumentParser(description="SSE experimental key-free QBFT genesis generator")
    p.add_argument("--validator", action="append", required=True, help="public Besu validator node address, supply exactly four")
    p.add_argument("--fund", action="append", default=[], help="public EOA to allocate 100 test ETH")
    p.add_argument("--chain-id", type=int, default=DEFAULT_CHAIN_ID)
    p.add_argument("--block-period", type=int, default=5)
    p.add_argument("--gas-limit", type=int, default=15_000_000)
    p.add_argument("--reward-wei", type=int, default=DEFAULT_BLOCK_REWARD_WEI)
    p.add_argument("--out-dir", type=Path, required=True, help="existing private directory; never overwrite files")
    a = p.parse_args()
    try:
        if (not a.out_dir.is_dir() or a.out_dir.is_symlink()
                or a.out_dir.stat().st_mode & 0o022):
            raise ConfigError("output must be existing trusted non-writable-by-others directory")
        g = genesis(a.validator, chain_id=a.chain_id, block_period=a.block_period,
                    gas_limit=a.gas_limit, reward_wei=a.reward_wei, funded=a.fund)
        for n in ("genesis.json", "benchmark-plan.json"):
            if (a.out_dir / n).exists() or (a.out_dir / n).is_symlink():
                raise ConfigError("refusing to overwrite existing experiment artifacts")
        write_new(a.out_dir / "genesis.json", g)
        write_new(a.out_dir / "benchmark-plan.json", trials())
        print(json.dumps({"result": "QBFT_ARTIFACTS_WRITTEN_NO_SECRETS", "chainId": a.chain_id,
                          "validators": len(a.validator), "genesis": str(a.out_dir / "genesis.json"),
                          "benchmarkPlan": str(a.out_dir / "benchmark-plan.json"),
                          "deploymentPerformed": False, "transactionsSent": False}, sort_keys=True))
        return 0
    except (ConfigError, OSError, ValueError) as e:
        print("SSE_QBFT_CONFIG_REFUSED: " + str(e), file=__import__('sys').stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
