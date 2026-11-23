#!/usr/bin/env python3
"""R201 read-only exact-original chain31340 V2 readiness evidence.

NO keys, wallets, Docker changes, deployments or transactions. Reads one
explicit localhost endpoint; does NOT assert an app has been deployed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request

RPC = "http://127.0.0.1:28545"
CHAIN = "0x7a6c"
GENESIS = "0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf"
FUNDED_ACCOUNT = "0x13fb73aace8A11Be2899D047635A757a224Ce00B"
ROOT = "0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd"
HEX = re.compile(r"0x[0-9a-fA-F]+\Z")


class Refused(ValueError):
    pass


def quantity(x):
    if type(x) is not str or not HEX.fullmatch(x):
        raise Refused("bad hexadecimal JSON-RPC quantity")
    return int(x, 16)


def rpc(url, method, params):
    if url != RPC:
        raise Refused("only the verified VM4707 private localhost RPC is allowed")
    request = urllib.request.Request(url, data=json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params
    }).encode(), headers={"Content-Type": "application/json"}, method="POST")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=8) as response:
        if response.status != 200:
            raise Refused("HTTP RPC failure")
        data = response.read(131073)
        if len(data) > 131072:
            raise Refused("oversized RPC response")
    value = json.loads(data)
    if (type(value) is not dict or value.get("jsonrpc") != "2.0"
            or value.get("id") != 1 or "error" in value
            or "result" not in value):
        raise Refused("malformed JSON RPC response")
    return value["result"]


def observe(url=RPC, transport=rpc):
    if url != RPC:
        raise Refused("unexpected RPC URL")
    if transport(url, "eth_chainId", []) != CHAIN:
        raise Refused("wrong chain ID")
    genesis = transport(url, "eth_getBlockByNumber", ["0x0", False])
    if type(genesis) is not dict or str(genesis.get("hash", "")).lower() != GENESIS:
        raise Refused("wrong execution genesis")
    final = transport(url, "eth_getBlockByNumber", ["finalized", False])
    if (type(final) is not dict or quantity(final.get("number")) == 0
            or type(final.get("hash")) is not str
            or not re.fullmatch(r"0x[0-9a-fA-F]{64}", final["hash"])):
        raise Refused("no finalized execution block")
    balance = quantity(transport(url, "eth_getBalance", [FUNDED_ACCOUNT, "finalized"]))
    nonce = quantity(transport(url, "eth_getTransactionCount", [FUNDED_ACCOUNT, "finalized"]))
    latest = transport(url, "eth_getBlockByNumber", ["latest", False])
    if type(latest) is not dict:
        raise Refused("latest block absent")
    gas = quantity(latest.get("gasLimit"))
    basefee = latest.get("baseFeePerGas")
    return {
        "schema": "SSE_R201_ACTUAL_CHAIN31340_ADAPTIVE_DEPLOYMENT_READINESS_V1",
        "status": "ACTUAL_ORIGINAL_CHAIN_FUNDED_SOURCE_OBSERVED_APP_NOT_DEPLOYED_BY_THIS_CHECK",
        "chainId": 31340,
        "executionGenesisHash": GENESIS,
        "executionGenesisVerified": True,
        "beaconGenesisValidatorsRootExpectedNotReadHere": ROOT,
        "finalizedExecutionHeight": quantity(final["number"]),
        "finalizedExecutionBlockHash": final["hash"].lower(),
        "currentExecutionHeight": quantity(latest.get("number")),
        "blockGasLimit": gas,
        "baseFeeWeiPerGas": quantity(basefee) if basefee is not None else None,
        "testOnlyGenesisAccount": FUNDED_ACCOUNT,
        "genesisAccountBalanceWeiAtFinalized": str(balance),
        "genesisAccountNonceAtFinalized": nonce,
        "accountPrivateKeyAccessVerified": False,
        "newAppDeployerKeystoreCreated": False,
        "marketV2Deployed": False,
        "contractRuntimeVerified": False,
        "transactionSignedOrSubmittedByThisTool": False,
        "physicalSlaVerified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpc", choices=[RPC], default=RPC)
    args = parser.parse_args()
    try:
        print(json.dumps(observe(args.rpc), indent=2, sort_keys=True))
        return 0
    except (Refused, ValueError, OSError, TypeError, KeyError) as exc:
        print("R201_READ_ONLY_PREFLIGHT_REFUSED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
