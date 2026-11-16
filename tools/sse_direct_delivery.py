#!/usr/bin/env python3
"""SSE R5/R7 direct consumer <-> WINNING provider exchange.

No marketplace bypass: a signed request is valid ONLY after an admitted,
funded, accepted lease names this specific consumer and provider. The chain
inspector must be pinned to an EIP-1898 block hash. Off-chain EIP-712 messages
bind work request, result bytes and consumer acknowledgment. Solidity V1's
ProviderResponse signature covers the original on-chain challenge only; it
is NOT misrepresented as a signature over compute-result bytes.

Physical delivery times, quality, network-partition failure and consumer
honesty are not certified. This module sends no Ethereum transactions.
"""
from __future__ import annotations

import json
import re
import time
from urllib.parse import urlsplit
from urllib.request import Request, ProxyHandler, HTTPRedirectHandler, build_opener
from urllib.error import HTTPError, URLError

from sse_challenge import bytes32, expected_response_hash, keccak256
from sse_sla_manifest import compare_to_lease, policy_hash, validate_policy
from compute_workload import compute_result
from typed_evidence import Domain, typed_message, verify_provider_response

REQ_TYPE = "SSEConsumerWorkRequest"
RESULT_TYPE = "SSEProviderWorkResult"
RECEIPT_TYPE = "SSEConsumerWorkReceipt"
REQUEST_SCHEMA = "sse-direct-request-v1"
RESPONSE_SCHEMA = "sse-direct-response-v1"
RECEIPT_SCHEMA = "sse-direct-receipt-v1"
RESPONSE_DOMAIN = "SSEWorkExchange"
DOMAIN_VERSION = "1"
MAX_WIRE = 8192
HASH = re.compile(r"0x[0-9a-f]{64}\Z")
SIGNATURE = re.compile(r"0x[0-9a-fA-F]{130}\Z")
ADDR = re.compile(r"0x[0-9a-fA-F]{40}\Z")
UINT = (1 << 256) - 1

LAYOUTS = {
    REQ_TYPE: [("leaseId", "uint256"), ("epochId", "uint256"),
               ("requestHash", "bytes32"), ("slaPolicyHash", "bytes32"),
               ("consumer", "address"), ("provider", "address"), ("nonce", "bytes32")],
    RESULT_TYPE: [("leaseId", "uint256"), ("epochId", "uint256"),
                  ("requestHash", "bytes32"), ("slaPolicyHash", "bytes32"),
                  ("consumer", "address"), ("provider", "address"),
                  ("resultHash", "bytes32"), ("nonce", "bytes32")],
    RECEIPT_TYPE: [("leaseId", "uint256"), ("epochId", "uint256"),
                   ("requestHash", "bytes32"), ("consumer", "address"),
                   ("provider", "address"), ("resultHash", "bytes32"),
                   ("nonce", "bytes32")],
}


class ExchangeError(ValueError):
    pass


def _obj(data, keys):
    if type(data) is not dict or set(data) != set(keys):
        raise ExchangeError("wrong or unknown direct-exchange fields")
    return data


def _address(value):
    if type(value) is not str or not ADDR.fullmatch(value) or int(value, 16) == 0:
        raise ExchangeError("invalid exchange address")
    return value.lower()


def _digest(value):
    if type(value) is not str or not HASH.fullmatch(value) or value == "0x" + "00" * 32:
        raise ExchangeError("invalid canonical nonzero digest")
    return value


def _uint(value, positive=False):
    if type(value) is not int or not (1 if positive else 0) <= value <= UINT:
        raise ExchangeError("invalid EIP-712 numeric field")
    return value


def _unique(pairs):
    obj = {}
    for k, v in pairs:
        if k in obj:
            raise ExchangeError("duplicate JSON field")
        obj[k] = v
    return obj


def json_bytes(item):
    try:
        raw = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                         allow_nan=False).encode("ascii")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ExchangeError("invalid exchange JSON") from exc
    if not 1 <= len(raw) <= MAX_WIRE:
        raise ExchangeError("exchange envelope too large")
    return raw


def parse_bytes(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_WIRE:
        raise ExchangeError("invalid exchange message size")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ExchangeError("nonfinite JSON")))
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ExchangeError("invalid exchange JSON") from exc


def typed(exchange_type, message, chain_id, settlement):
    if exchange_type not in LAYOUTS:
        raise ExchangeError("unknown off-chain EIP-712 message type")
    _uint(chain_id, positive=True)
    contract = _address(settlement)
    fields = LAYOUTS[exchange_type]
    _obj(message, [name for name, _ in fields])
    for name, kind in fields:
        value = message[name]
        if kind == "address":
            _address(value)
        elif kind == "bytes32":
            _digest(value)
        elif kind == "uint256":
            _uint(value, positive=(name == "leaseId"))
        else:
            raise ExchangeError("unsupported EIP-712 type")
    return {
        "types": {"EIP712Domain": [
            {"name": "name", "type": "string"},
            {"name": "version", "type": "string"},
            {"name": "chainId", "type": "uint256"},
            {"name": "verifyingContract", "type": "address"},
        ], exchange_type: [{"name": name, "type": kind} for name, kind in fields]},
        "primaryType": exchange_type,
        "domain": {"name": RESPONSE_DOMAIN, "version": DOMAIN_VERSION,
                   "chainId": chain_id, "verifyingContract": contract},
        "message": message,
    }


def sign(exchange_type, message, chain_id, settlement, signer):
    from eth_account.messages import encode_typed_data
    from eth_account import Account
    signed = Account.sign_message(
        encode_typed_data(full_message=typed(exchange_type, message, chain_id, settlement)),
        private_key=signer.key)
    return "0x" + bytes(signed.signature).hex()


def verify(exchange_type, message, chain_id, settlement, signature, expected_signer):
    from eth_account.messages import encode_typed_data
    from eth_account import Account
    _address(expected_signer)
    if type(signature) is not str or not SIGNATURE.fullmatch(signature):
        raise ExchangeError("malformed exchange signature")
    try:
        recovered = Account.recover_message(
            encode_typed_data(full_message=typed(exchange_type, message, chain_id, settlement)),
            signature=signature).lower()
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ExchangeError("invalid exchange signature") from exc
    if recovered != expected_signer.lower():
        raise ExchangeError("signature does not belong to leased participant")


def _scope(inspection, policy, endpoint):
    validate_policy(policy)
    compare_to_lease(policy, inspection, endpoint=endpoint)
    if type(endpoint) is not str or not endpoint:
        raise ExchangeError("service endpoint commitment required")
    lease, epoch = inspection["lease"], inspection["epoch"]
    if (epoch["requestHash"] != epoch["requestHash"].lower() or
            epoch.get("responseHash") != expected_response_hash(epoch["requestHash"])):
        raise ExchangeError("admitted challenge is invalid")
    return {
        "leaseId": inspection["leaseId"], "epochId": inspection["epochId"],
        "requestHash": _digest(epoch["requestHash"]),
        "slaPolicyHash": policy_hash(policy),
        "consumer": _address(lease["consumer"]), "provider": _address(lease["provider"]),
    }


def prepare_request(inspection, policy, endpoint, consumer_signer, nonce):
    scope = _scope(inspection, policy, endpoint)
    if _address(consumer_signer.address) != scope["consumer"]:
        raise ExchangeError("request signer was not the winning lease's consumer")
    message = {**scope, "nonce": _digest(nonce)}
    return {"schema": REQUEST_SCHEMA, "message": message,
            "signature": sign(REQ_TYPE, message, policy["chainId"], policy["settlement"],
                              consumer_signer)}


def authenticate_request(envelope, inspection, policy, endpoint, provider_signer):
    scope = _scope(inspection, policy, endpoint)
    if _address(provider_signer.address) != scope["provider"]:
        raise ExchangeError("this VM is not the winning provider")
    _obj(envelope, ("schema", "message", "signature"))
    if envelope["schema"] != REQUEST_SCHEMA:
        raise ExchangeError("unknown consumer request version")
    msg = envelope["message"]
    _obj(msg, (*scope.keys(), "nonce"))
    if any(msg[k] != v for k, v in scope.items()):
        raise ExchangeError("request does not match admitted chosen-provider lease")
    _digest(msg["nonce"])
    verify(REQ_TYPE, msg, policy["chainId"], policy["settlement"], envelope["signature"],
           scope["consumer"])
    return msg


def _result(scope, kind):
    if kind == "http_challenge":
        return {"schema": "sse-http-result-v1",
                "responseHash": expected_response_hash(scope["requestHash"])}
    if kind == "deterministic_compute":
        return compute_result(scope["leaseId"], scope["epochId"], scope["requestHash"])
    raise ExchangeError("service type is not executable")


def result_hash(result):
    return "0x" + keccak256(b"SSE_DIRECT_WORK_RESULT_V1\x00" + json_bytes(result)).hex()


def create_response(envelope, inspection, policy, endpoint, provider_signer):
    request = authenticate_request(envelope, inspection, policy, endpoint, provider_signer)
    result = _result(request, policy["serviceKind"])
    digest = result_hash(result)
    msg = {**request, "resultHash": digest}
    # Solidity V1 ProviderResponse signs the challenge/response commitment,
    # not the service-specific result bytes. Use *another* off-chain signature.
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    domain = Domain(policy["chainId"], policy["settlement"])
    v1 = {"leaseId": request["leaseId"], "epochId": request["epochId"],
          "requestHash": request["requestHash"],
          "responseHash": expected_response_hash(request["requestHash"])}
    onchain_sig = Account.sign_message(
        encode_typed_data(full_message=typed_message(domain, "ProviderResponse", v1)),
        private_key=provider_signer.key)
    return {
        "schema": RESPONSE_SCHEMA, "message": msg, "result": result,
        "providerResultSignature": sign(RESULT_TYPE, msg, policy["chainId"],
                                        policy["settlement"], provider_signer),
        "providerV1Signature": "0x" + bytes(onchain_sig.signature).hex(),
        "responseHash": v1["responseHash"],
    }


def validate_response(envelope, request, inspection, policy, endpoint):
    scope = _scope(inspection, policy, endpoint)
    request_msg = authenticate_consumer_request(request, scope, policy)
    _obj(envelope, ("schema", "message", "result", "providerResultSignature",
                    "providerV1Signature", "responseHash"))
    if envelope["schema"] != RESPONSE_SCHEMA:
        raise ExchangeError("unknown provider response version")
    msg = envelope["message"]
    _obj(msg, (*scope.keys(), "nonce", "resultHash"))
    if any(msg[k] != request_msg[k] for k in request_msg):
        raise ExchangeError("provider reply does not match signed consumer request")
    expected_result = _result(scope, policy["serviceKind"])
    if type(envelope["result"]) is not dict or envelope["result"] != expected_result:
        raise ExchangeError("provider returned incorrect SLA workload result")
    if msg["resultHash"] != result_hash(expected_result):
        raise ExchangeError("compute result is not cryptographically bound")
    verify(RESULT_TYPE, msg, policy["chainId"], policy["settlement"],
           envelope["providerResultSignature"], scope["provider"])
    v1 = {"leaseId": scope["leaseId"], "epochId": scope["epochId"],
          "requestHash": scope["requestHash"],
          "responseHash": expected_response_hash(scope["requestHash"])}
    if envelope["responseHash"] != v1["responseHash"]:
        raise ExchangeError("provider response commitment differs from Solidity")
    if not verify_provider_response(Domain(policy["chainId"], policy["settlement"]),
                                    scope["provider"], v1, envelope["providerV1Signature"]):
        raise ExchangeError("invalid Solidity V1 provider signature")
    return msg


def authenticate_consumer_request(envelope, scope, policy):
    _obj(envelope, ("schema", "message", "signature"))
    if envelope["schema"] != REQUEST_SCHEMA:
        raise ExchangeError("unknown signed consumer work order")
    msg = envelope["message"]
    _obj(msg, (*scope.keys(), "nonce"))
    if any(msg[k] != scope[k] for k in scope):
        raise ExchangeError("work order is not bound to selected provider")
    verify(REQ_TYPE, msg, policy["chainId"], policy["settlement"],
           envelope["signature"], scope["consumer"])
    return msg


def create_receipt(request, response, inspection, policy, endpoint, consumer_signer):
    msg = validate_response(response, request, inspection, policy, endpoint)
    if _address(consumer_signer.address) != msg["consumer"]:
        raise ExchangeError("receipt signer not the agreed consumer")
    receipt = {k: msg[k] for k in ("leaseId", "epochId", "requestHash", "consumer",
                                  "provider", "resultHash", "nonce")}
    return {"schema": RECEIPT_SCHEMA, "message": receipt,
            "signature": sign(RECEIPT_TYPE, receipt, policy["chainId"],
                              policy["settlement"], consumer_signer),
            "consumerObservedAtUnixMs": int(time.time() * 1000),
            "timestampTrust": "UNTRUSTED_CONSUMER_CLOCK"}


def verify_receipt(envelope, response, inspection, policy, endpoint):
    scope = _scope(inspection, policy, endpoint)
    _obj(envelope, ("schema", "message", "signature",
                    "consumerObservedAtUnixMs", "timestampTrust"))
    if envelope["schema"] != RECEIPT_SCHEMA or envelope["timestampTrust"] != "UNTRUSTED_CONSUMER_CLOCK":
        raise ExchangeError("invalid consumer delivery receipt")
    msg = envelope["message"]
    _obj(msg, ("leaseId", "epochId", "requestHash", "consumer",
               "provider", "resultHash", "nonce"))
    other = response["message"]
    if (any(msg.get(k) != scope[k] for k in ("leaseId", "epochId", "requestHash",
                                           "consumer", "provider")) or
            msg.get("resultHash") != other.get("resultHash") or
            msg.get("nonce") != other.get("nonce")):
        raise ExchangeError("consumer receipt does not match provider result")
    stamp = envelope["consumerObservedAtUnixMs"]
    if type(stamp) is not int or not 0 <= stamp < (1 << 64):
        raise ExchangeError("invalid consumer clock claim")
    verify(RECEIPT_TYPE, msg, policy["chainId"], policy["settlement"],
           envelope["signature"], scope["consumer"])
    return {"validSignature": True, "consumerClaimsReceived": True,
            "physicalDeadlineCertified": False, "timestampTrust": "UNTRUSTED"}


def validate_endpoint_url(url):
    if type(url) is not str or len(url) > 255:
        raise ExchangeError("invalid direct-service URL")
    parsed = urlsplit(url)
    try:
        port = parsed.port
    except ValueError:
        raise ExchangeError("invalid service port") from None
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ExchangeError("service endpoint must be an origin without embedded secrets")
    if parsed.scheme == "http" and parsed.hostname == "127.0.0.1" and port is not None:
        return url.rstrip("/")
    if (parsed.scheme == "https" and parsed.hostname and
            parsed.hostname.endswith(".ts.net") and port in (None, 443)):
        return url.rstrip("/")
    raise ExchangeError("service requires loopback HTTP or approved Tailscale HTTPS")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ExchangeError("redirect forbidden for provider request")


def post_json(url, obj, timeout=5.0):
    validate_endpoint_url(url)
    if type(timeout) not in (int, float) or not 0 < timeout <= 30:
        raise ExchangeError("bad HTTP timeout")
    payload = json_bytes(obj)
    req = Request(url + "/v1/work", data=payload, method="POST",
                  headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=float(timeout)) as res:
            if res.status != 200 or res.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ExchangeError("provider returned an invalid HTTP response")
            raw = res.read(MAX_WIRE + 1)
    except (HTTPError, URLError, OSError, TimeoutError):
        raise ExchangeError("provider transport failed (not a physical SLA failure)") from None
    return parse_bytes(raw)


def submit_work_request(url, inspection, policy, consumer_signer, nonce):
    request = prepare_request(inspection, policy, url, consumer_signer, nonce)
    response = post_json(url, request)
    receipt = create_receipt(request, response, inspection, policy, url, consumer_signer)
    # Receipt is separately sent to the provider. A failed acknowledgment
    # cannot retroactively negate the consumer's local observation.
    try:
        req = Request(url + "/v1/receipt", data=json_bytes(receipt), method="POST",
                      headers={"Content-Type": "application/json"})
        with build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=5.0) as res:
            ack = parse_bytes(res.read(MAX_WIRE+1))
        if type(ack) is not dict or ack.get("receiptSignatureVerified") is not True:
            raise ExchangeError("provider did not accept consumer receipt")
    except (HTTPError, URLError, OSError, TimeoutError):
        raise ExchangeError("consumer received correct result; receipt delivery unconfirmed") from None
    return {"request": request, "response": response, "receipt": receipt,
            "receiptAcceptedByProvider": True, "onChainSettlementSubmitted": False,
            "physicalDeadlineCertified": False}
