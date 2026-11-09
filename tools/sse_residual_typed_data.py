"""Construct EIP-712 messages for a mutually signed SSE residual allocation.

This module does not sign messages or hold private keys. Sign using the consumer
and provider wallets independently; then relay both signatures to the settlement
contract. The on-chain contract itself supplies the authoritative unresolved
amount. The values here MUST match its current state at submission time.

Usage:
  python tools/sse_residual_typed_data.py \
    --chain-id 31337 --settlement 0x... --lease-id 1 --epoch-id 0 \
    --unresolved 5 --provider-share 2 --consumer-share 3 \
    --nonce 1 --expiry 1893456000
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")


def _uint(name: str, value: int, *, nonzero: bool = False) -> int:
    if type(value) is not int or value < (1 if nonzero else 0) or value >= 2**256:
        raise ValueError(f"{name} must be a valid uint256" + (" > 0" if nonzero else ""))
    return value


def residual_typed_data(
    *, chain_id: int, settlement: str, lease_id: int, epoch_id: int,
    unresolved: int, provider_share: int, consumer_share: int,
    nonce: int, expiry: int,
) -> dict[str, Any]:
    """Return signTypedData_v4 JSON with the exact Solidity type/field order.

    ``chainId`` and ``verifyingContract`` form the EIP-712 signing domain.
    A signature from only one party does not authorize releasing the residual.
    """
    if not isinstance(settlement, str) or not _ADDRESS.fullmatch(settlement):
        raise ValueError("settlement must be a 20-byte hex Ethereum address")
    _uint("chain_id", chain_id, nonzero=True)
    _uint("lease_id", lease_id, nonzero=True)
    _uint("epoch_id", epoch_id)
    _uint("unresolved", unresolved, nonzero=True)
    _uint("provider_share", provider_share)
    _uint("consumer_share", consumer_share)
    _uint("nonce", nonce)
    _uint("expiry", expiry, nonzero=True)
    if provider_share > unresolved or consumer_share != unresolved - provider_share:
        raise ValueError("provider and consumer shares must sum exactly to unresolved escrow")
    domain = [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"},
    ]
    message = [
        {"name": "leaseId", "type": "uint256"},
        {"name": "epochId", "type": "uint256"},
        {"name": "unresolvedAmount", "type": "uint256"},
        {"name": "providerShare", "type": "uint256"},
        {"name": "consumerShare", "type": "uint256"},
        {"name": "nonce", "type": "uint256"},
        {"name": "expiry", "type": "uint256"},
    ]
    return {
        "types": {"EIP712Domain": domain, "ResidualAgreement": message},
        "primaryType": "ResidualAgreement",
        "domain": {
            "name": "SSESettlement", "version": "1", "chainId": chain_id,
            "verifyingContract": settlement,
        },
        "message": {
            "leaseId": lease_id, "epochId": epoch_id,
            "unresolvedAmount": unresolved,
            "providerShare": provider_share, "consumerShare": consumer_share,
            "nonce": nonce, "expiry": expiry,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("chain-id", "lease-id", "epoch-id", "unresolved", "provider-share", "consumer-share", "nonce", "expiry"):
        parser.add_argument("--" + flag, type=int, required=True)
    parser.add_argument("--settlement", required=True)
    args = parser.parse_args()
    payload = residual_typed_data(
        chain_id=args.chain_id, settlement=args.settlement,
        lease_id=args.lease_id, epoch_id=args.epoch_id, unresolved=args.unresolved,
        provider_share=args.provider_share, consumer_share=args.consumer_share,
        nonce=args.nonce, expiry=args.expiry,
    )
    print(json.dumps(payload, indent=2, sort_keys=False))


if __name__ == "__main__":
    main()
