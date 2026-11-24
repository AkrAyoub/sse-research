#!/usr/bin/env python3
"""R256: original-chain31340 REAL read-only V2 constructor deployment gas quote.

Use the actual Foundry compiled initcode for SSEAdaptiveMarketV2, which
itself deploys SSEAdaptiveVoteLedger. Never forge an ABI, guess a gas amount,
use a copied signer, publish any key, sign or broadcast a transaction.
This is a quote ONLY, and can operate while the R255 funding transfer is
included but not yet finalized. Do not mistake it for deployment consent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from sse_pos_r206_adaptive_v2_deployment_audit import rpc as rpc_transport
from sse_pos_r247_v2_compiled_abi_parity import load_artifact, audit as audit_abi

RPC = "http://127.0.0.1:28545"
CHAIN = 31340
GENESIS = "0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf"
APP = "0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0"
EXPECTED_MARKET_ABI = "e7ad167851a912a52d30ef1a08f6fdeedad24fa06c9fb99b8bc2ef2385faadb0"
EXPECTED_LEDGER_ABI = "f94b65c8dfda90c52b4aede0c96e16110b663868bd8dce4a79039523f6c64d8e"
EXPECTED_MARKET_INITCODE_BYTES = 31577
EXPECTED_MARKET_RUNTIME_BYTES = 19263
EXPECTED_LEDGER_RUNTIME_BYTES = 10668
HEXQ = re.compile(r"0x[0-9a-fA-F]+\Z")
BYTECODE = re.compile(r"0x(?:[0-9a-fA-F]{2})+\Z")


class Refused(ValueError):
    pass


def q(raw, name):
    if type(raw) is not str or not HEXQ.fullmatch(raw):
        raise Refused("bad native RPC quantity for " + name)
    return int(raw, 16)


def pin_artifacts(market, ledger, bond_wei):
    if type(bond_wei) is not int or not 0 < bond_wei < 2**256:
        raise Refused("explicit positive 256-bit minimum monitor bond required")
    result = audit_abi(market, ledger)
    if (result["market"]["compiledAbiSha256"] != EXPECTED_MARKET_ABI or
        result["ledger"]["compiledAbiSha256"] != EXPECTED_LEDGER_ABI):
        raise Refused("actual compiled V2 ABI is not exact R249 audited source")
    constructors = [entry for entry in market["abi"]
                    if type(entry) is dict and entry.get("type") == "constructor"]
    if (len(constructors) != 1 or
        [arg.get("type") for arg in constructors[0].get("inputs", [])] != ["uint256"] or
        constructors[0].get("stateMutability") != "nonpayable"):
        raise Refused("market compiled constructor ABI changed")
    for label, artifact, expected_bytes in (
        ("market", market, EXPECTED_MARKET_RUNTIME_BYTES),
        ("ledger", ledger, EXPECTED_LEDGER_RUNTIME_BYTES),
    ):
        envelope = artifact.get("deployedBytecode")
        if type(envelope) is not dict:
            raise Refused(label + " actual compiled runtime missing")
        raw = envelope.get("object")
        if type(raw) is not str or not BYTECODE.fullmatch(raw):
            raise Refused(label + " runtime contains unresolved addresses")
        if len(raw[2:]) // 2 != expected_bytes:
            raise Refused(label + " runtime size changed from R249 pinned build")
        if envelope.get("linkReferences"):
            raise Refused(label + " compiled runtime has unresolved external libraries")
    bytecode = market.get("bytecode")
    if type(bytecode) is not dict:
        raise Refused("actual market creation bytecode absent")
    code = bytecode.get("object")
    if type(code) is not str or not BYTECODE.fullmatch(code):
        raise Refused("market initcode missing/invalid/unlinked")
    if bytecode.get("linkReferences"):
        raise Refused("market has unresolved library link references")
    if len(code[2:]) // 2 != EXPECTED_MARKET_INITCODE_BYTES:
        raise Refused("market initcode changed from R249 measured build")
    # Solidity constructor(uint256 bondWei) has a SINGLE static 32-byte arg.
    encoded = code + f"{bond_wei:064x}"
    if (len(encoded[2:]) // 2 > 49152 or
        hashlib.sha256(bytes.fromhex(encoded[2:])).hexdigest() ==
        hashlib.sha256(bytes.fromhex(code[2:])).hexdigest()):
        raise Refused("bad EIP3860 constructor initcode envelope")
    return encoded


def quote(rpc_url, compiled_market, compiled_ledger, bond_wei, *, transport=rpc_transport):
    if rpc_url != RPC:
        raise Refused("only VM4707 owner-local real execution RPC approved")
    initcode = pin_artifacts(compiled_market, compiled_ledger, bond_wei)
    ask = lambda method, params: transport(rpc_url, method, params)
    if q(ask("eth_chainId", []), "chain ID") != CHAIN:
        raise Refused("wrong chain ID")
    g = ask("eth_getBlockByNumber", ["0x0", False])
    if type(g) is not dict or str(g.get("hash", "")).lower() != GENESIS:
        raise Refused("wrong original execution genesis")
    latest = ask("eth_getBlockByNumber", ["latest", False])
    finalized = ask("eth_getBlockByNumber", ["finalized", False])
    if type(latest) is not dict or type(finalized) is not dict:
        raise Refused("native latest or finalized execution head unavailable")
    head = q(latest.get("number"), "latest height")
    final = q(finalized.get("number"), "finalized height")
    block_gas = q(latest.get("gasLimit"), "block gas limit")
    if not 0 < block_gas <= 30_000_000 or not 0 <= final <= head:
        raise Refused("implausible execution gas bound or finalized height")
    base = latest.get("baseFeePerGas")
    if base is not None:
        base_wei = q(base, "base fee")
    else:
        base_wei = None
    current_balance = q(ask("eth_getBalance", [APP, "latest"]), "latest deployer balance")
    final_balance = q(ask("eth_getBalance", [APP, "finalized"]), "finalized deployer balance")
    code_existing = ask("eth_getCode", [APP, "latest"])
    if code_existing != "0x":
        raise Refused("app deployer unexpectedly has contract code")
    price = q(ask("eth_gasPrice", []), "gas price")
    if price <= 0:
        raise Refused("actual node returned no positive gas price")
    estimate = q(ask("eth_estimateGas", [{"from": APP,
                                          "data": initcode,
                                          "value": "0x0"}]),
                 "actual market+ledger creation estimate")
    if not 0 < estimate <= block_gas:
        raise Refused("actual constructor estimate exceeds block gas limit")
    padded = estimate * 125 // 100 + 5000
    if padded > block_gas:
        raise Refused("estimated padded deployment gas exceeds block limit")
    max_cost = padded * price
    return {
        "schema": "SSE_R256_REAL_ORIGINAL_CHAIN_V2_DEPLOYMENT_GAS_QUOTE_V1",
        "chainId": CHAIN,
        "originalExecutionGenesisVerified": True,
        "marketCompilerAbiMatchedR249": True,
        "ledgerCompilerAbiMatchedR249": True,
        "marketCompiledInitcodeBytes": EXPECTED_MARKET_INITCODE_BYTES,
        "constructorIncludesInternalLedgerCreation": True,
        "minimumBondWeiQuoteScenarioOnly": str(bond_wei),
        "immutableMonitorBondPolicyChosenOrApproved": False,
        "deploymentSigner": APP,
        "latestExecutionHeight": head,
        "finalizedExecutionHeight": final,
        "currentBalanceWeiAtLatest": str(current_balance),
        "balanceWeiAtFinalized": str(final_balance),
        "actualNodeGasPriceWei": str(price),
        "actualNodeBaseFeeWeiPerGas": str(base_wei) if base_wei is not None else None,
        "actualNodeEstimatedConstructorGas": estimate,
        "paddedGasLimitScenario": padded,
        "upperFeeQuoteWeiAtCurrentGasPrice": str(max_cost),
        "estimatedPaddedFeeCoveredByCurrentLatestBalance": current_balance >= max_cost,
        "estimatedPaddedFeeCoveredByFinalizedBalance": final_balance >= max_cost,
        "blockGasLimit": block_gas,
        "quoteOnlyNoPrivateKeysNoTransactionNoDeployment": True,
        "noDeploymentConsentInferred": True,
        "notAnAuthorizationOrGuaranteedFutureGasPrice": True,
    }


def main(argv=None):
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rpc", choices=(RPC,), required=True)
    p.add_argument("--minimum-bond-wei", type=int, required=True,
                   help="positive illustrative bond value, never automatically approved")
    p.add_argument("--market-artifact", type=Path,
                   default=root/"out/SSEAdaptiveMarketV2.sol/SSEAdaptiveMarketV2.json")
    p.add_argument("--ledger-artifact", type=Path,
                   default=root/"out/SSEAdaptiveVoteLedger.sol/SSEAdaptiveVoteLedger.json")
    args = p.parse_args(argv)
    try:
        market = load_artifact(args.market_artifact)
        ledger = load_artifact(args.ledger_artifact)
        print(json.dumps(quote(args.rpc, market, ledger, args.minimum_bond_wei),
                         indent=2, sort_keys=True))
        print("R256_ACTUAL_NATIVE_V2_CREATION_GAS_QUOTE_ONLY_COMPLETED=true")
        return 0
    except (Refused, OSError, TypeError, ValueError, KeyError) as exc:
        print("R256_V2_DEPLOYMENT_QUOTE_REFUSED: "+str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
