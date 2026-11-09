"""EIP-712 messages compatible with SSESettlement v1.

Only signature attribution and byte integrity are established here. They do not
prove HTTP delivery, monitor independence, or truthful external timestamps.
This adapter is deliberately small pending the R4 shared signing SDK.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sse_challenge import bytes32, keccak256, expected_response_hash
from sse_chain_read import _domain_separator

ADDRESS = re.compile(r'0x[0-9a-fA-F]{40}\Z')
ZERO_HASH = '0x' + '00' * 32


@dataclass(frozen=True)
class Domain:
    chain_id: int
    contract: str

    def __post_init__(self):
        if type(self.chain_id) is not int or not 0 < self.chain_id < 2**256:
            raise ValueError('invalid chain ID')
        if not isinstance(self.contract, str) or not ADDRESS.fullmatch(self.contract):
            raise ValueError('invalid SSE settlement address')

    def separator(self) -> bytes:
        return bytes32(_domain_separator(self.chain_id, self.contract))

    def fields(self) -> dict:
        return {'name': 'SSESettlement', 'version': '1', 'chainId': self.chain_id,
                'verifyingContract': self.contract}


def typed_message(domain: Domain, primary_type: str, message: dict) -> dict:
    """Construct exact Solidity v1 typed-data schema, not a generic string signature."""
    layouts = {
        'ProviderResponse': [
            ('leaseId', 'uint256'), ('epochId', 'uint256'),
            ('requestHash', 'bytes32'), ('responseHash', 'bytes32')],
        'MonitorVote': [
            ('leaseId', 'uint256'), ('epochId', 'uint256'),
            ('requestHash', 'bytes32'), ('outcome', 'uint8'),
            ('responseHash', 'bytes32'), ('evidenceHash', 'bytes32')],
    }
    if primary_type not in layouts:
        raise ValueError('unsupported SSE typed message')
    fields = layouts[primary_type]
    if not isinstance(message, dict) or set(message) != {name for name, _ in fields}:
        raise ValueError('wrong typed message fields')
    for name, kind in fields:
        value = message[name]
        if kind == 'bytes32':
            bytes32(value)
        elif type(value) is not int or not 0 <= value < (1 << (8 if kind == 'uint8' else 256)):
            raise ValueError(f'invalid {name} value')
    return {
        'types': {
            'EIP712Domain': [
                {'name': 'name', 'type': 'string'}, {'name': 'version', 'type': 'string'},
                {'name': 'chainId', 'type': 'uint256'}, {'name': 'verifyingContract', 'type': 'address'}],
            primary_type: [{'name': name, 'type': kind} for name, kind in fields],
        },
        'primaryType': primary_type,
        'domain': domain.fields(),
        'message': message,
    }


def _account_api():
    try:
        from eth_account import Account
        from eth_account.messages import encode_typed_data
    except ImportError as exc:
        raise RuntimeError('Ethereum signature support missing: install requirements.txt') from exc
    return Account, encode_typed_data


def signer_address(private_key: str) -> str:
    Account, _ = _account_api()
    return Account.from_key(private_key).address


def verify_provider_response(domain: Domain, provider: str, payload: dict, signature: str) -> bool:
    if not isinstance(provider, str) or not ADDRESS.fullmatch(provider):
        raise ValueError('invalid provider address')
    if not isinstance(signature, str) or not re.fullmatch(r'0x[0-9a-fA-F]{130}', signature):
        return False
    Account, encode_typed_data = _account_api()
    try:
        data = typed_message(domain, 'ProviderResponse', payload)
        recovered = Account.recover_message(encode_typed_data(full_message=data), signature=signature)
        return recovered.lower() == provider.lower()
    except Exception:  # malformed recoverable signatures must fail closed
        return False


def signed_vote(private_key: str, domain: Domain, lease_id: int, epoch_id: int,
                request_hash: str, outcome: int, response_hash: str,
                observation: dict, provider_response: dict | None = None) -> dict:
    if outcome not in (1, 2) or type(outcome) is not int:
        raise ValueError('only Success/Failure are accepted by current Solidity v1')
    if outcome == 1 and response_hash.lower() != expected_response_hash(request_hash):
        raise ValueError('SUCCESS requires the exact challenge response commitment')
    if outcome == 2 and response_hash != ZERO_HASH:
        raise ValueError('FAILURE cannot claim an authenticated response')
    if not isinstance(observation, dict):
        raise ValueError('observation must be an object')
    evidence = {
        'schema': 'sse-monitor-evidence-v1', 'chainId': domain.chain_id,
        'settlement': domain.contract, 'leaseId': lease_id, 'epochId': epoch_id,
        'requestHash': request_hash, 'outcome': outcome,
        'responseHash': response_hash, 'observation': observation,
        'providerResponse': provider_response,
        'limitations': ['local clock not cryptographically attested',
                        'signatures do not prove physical receipt or monitor independence'],
    }
    raw = json.dumps(evidence, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=True, allow_nan=False).encode('ascii')
    evidence_hash = '0x' + keccak256(b'SSE_MONITOR_EVIDENCE_V1\x00' + raw).hex()
    message = {
        'leaseId': lease_id, 'epochId': epoch_id, 'requestHash': request_hash,
        'outcome': outcome, 'responseHash': response_hash, 'evidenceHash': evidence_hash,
    }
    data = typed_message(domain, 'MonitorVote', message)
    Account, encode_typed_data = _account_api()
    account = Account.from_key(private_key)
    signature = Account.sign_message(encode_typed_data(full_message=data), private_key=private_key)
    return {**evidence, 'monitor': account.address, 'evidenceHash': evidence_hash,
            'typedData': data, 'monitorSignature': '0x' + bytes(signature.signature).hex()}
