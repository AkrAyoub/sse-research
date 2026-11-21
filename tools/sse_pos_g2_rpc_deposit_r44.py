#!/usr/bin/env python3
"""R44: classify actual LIVE Besu eth_getCode response with full HTTP framing.

Observation only. Never start or stop Docker services, alter validator files,
regenerate genesis or emit raw bytecode/HTTP error text. All RPC is executed on
the already-running genuine Besu chain31340 container via loopback /dev/tcp.
This fixes the blind spot where the old parser decoded only the first chunk of
a large HTTP Transfer-Encoding: chunked JSON-RPC response, reporting "no result".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time

import sse_pos_g2_internal_health_r42 as health
from sse_pos_deposit_predeploy import standard_reference, DepositPredeployError

EL = health.internal.EL
ORIGINAL = health.internal.ORIGINAL
BN = health.internal.BN
VC = health.internal.VC
DEPOSIT = health.DEPOSIT
MAX_WIRE = health.internal.MAX_RESPONSE
MAX_HEADER = 8192
CHUNK_SIZE_RE = re.compile(rb"^[0-9a-fA-F]{1,10}(?:;[^\r\n]{0,80})?$")

class R44ReadOnlyError(ValueError):
    pass

def unpack_http(raw: bytes) -> tuple[dict, dict | None]:
    """Bounded HTTP decoder with MULTIPLE chunk frames, no untrusted text output."""
    result = {
        "transportStatus": "NO_VALID_HTTP_RESPONSE",
        "httpResponseWireBytes": len(raw),
        "httpResponseBodyBytes": None,
        "chunkCount": None,
        "isChunked": None,
        "httpStatusCode": None,
        "responseJsonObjectParsed": False,
    }
    if len(raw) > MAX_WIRE or len(raw) < 12:
        result["transportStatus"] = "WIRE_SIZE_OUT_OF_RANGE"
        return result, None
    head, delimiter, body = raw.partition(b"\r\n\r\n")
    if not delimiter or len(head) > MAX_HEADER:
        result["transportStatus"] = "HTTP_HEADERS_MISSING_OR_TOO_LARGE"
        return result, None
    status = head.split(b"\r\n", 1)[0]
    bits = status.split()
    if len(bits) < 2 or not bits[0].startswith(b"HTTP/") or not bits[1].isdigit():
        result["transportStatus"] = "HTTP_STATUS_INVALID"
        return result, None
    status_code = int(bits[1])
    result["httpStatusCode"] = status_code
    if status_code != 200:
        result["transportStatus"] = "HTTP_NON_200"
        return result, None
    lines = head.split(b"\r\n")[1:]
    # Header NAMES are fixed signals only, values are never emitted.
    is_chunked = any(
        line.partition(b":")[0].strip().lower() == b"transfer-encoding"
        and b"chunked" in line.partition(b":")[2].lower()
        for line in lines
    )
    result["isChunked"] = is_chunked
    if is_chunked:
        out = bytearray()
        pos = 0
        count = 0
        while True:
            eol = body.find(b"\r\n", pos)
            if eol < 0 or eol - pos > 100:
                result["transportStatus"] = "CHUNK_SIZE_LINE_MISSING"
                return result, None
            size_text = body[pos:eol]
            if not CHUNK_SIZE_RE.fullmatch(size_text):
                result["transportStatus"] = "CHUNK_SIZE_INVALID"
                return result, None
            try:
                length = int(size_text.split(b";", 1)[0], 16)
            except ValueError:
                result["transportStatus"] = "CHUNK_SIZE_INVALID"
                return result, None
            pos = eol + 2
            if length == 0:
                result["chunkCount"] = count
                break
            if pos + length + 2 > len(body) or len(out) + length > MAX_WIRE:
                result["transportStatus"] = "CHUNK_BODY_INCOMPLETE_OR_EXCESSIVE"
                return result, None
            out.extend(body[pos:pos + length])
            pos += length
            if body[pos:pos + 2] != b"\r\n":
                result["transportStatus"] = "CHUNK_TERMINATOR_MISSING"
                return result, None
            pos += 2
            count += 1
            if count > 512:
                result["transportStatus"] = "CHUNK_COUNT_EXCESSIVE"
                return result, None
        body = bytes(out)
    else:
        lengths = [
            line.partition(b":")[2].strip()
            for line in lines
            if line.partition(b":")[0].strip().lower() == b"content-length"
        ]
        if lengths:
            if len(lengths) != 1 or not lengths[0].isdigit():
                result["transportStatus"] = "CONTENT_LENGTH_INVALID"
                return result, None
            size = int(lengths[0])
            if size > MAX_WIRE or len(body) < size:
                result["transportStatus"] = "CONTENT_LENGTH_INCOMPLETE_OR_EXCESSIVE"
                return result, None
            body = body[:size]
    result["httpResponseBodyBytes"] = len(body)
    try:
        obj = json.loads(body)
    except (TypeError, ValueError):
        result["transportStatus"] = "HTTP_200_JSON_DECODE_FAILED"
        return result, None
    if type(obj) is not dict:
        result["transportStatus"] = "HTTP_200_JSON_NOT_OBJECT"
        return result, None
    result["transportStatus"] = "HTTP_200_JSON_OBJECT"
    result["responseJsonObjectParsed"] = True
    return result, obj

def code_report(selector: str, canonical: bytes) -> dict:
    if selector not in ("earliest", "latest"):
        raise R44ReadOnlyError("only earliest/latest read-only code selectors permitted")
    request = health.internal.wire(
        "POST", 8545, "/",
        {"jsonrpc": "2.0", "id": 1, "method": "eth_getCode",
         "params": [DEPOSIT, selector]},
    )
    try:
        wire_bytes = health.internal.docker(
            ["exec", EL, "/bin/bash", "-c", request]
        )
        info, decoded = unpack_http(wire_bytes)
    except health.internal.Refuse:
        info, decoded = {
            "transportStatus": "EXISTING_CONTAINER_DOCKER_EXEC_FAILED",
            "httpResponseWireBytes": None, "httpResponseBodyBytes": None,
            "chunkCount": None, "isChunked": None, "httpStatusCode": None,
            "responseJsonObjectParsed": False,
        }, None
    kind = "NO_JSON_RPC_ENVELOPE"
    err_code = None
    code_length = None
    code_hash = None
    matches = False
    if isinstance(decoded, dict):
        err = decoded.get("error")
        value = decoded.get("result")
        if type(err) is dict:
            kind = "JSON_RPC_ERROR"
            ec = err.get("code")
            if type(ec) is int and -100000 <= ec <= 100000:
                err_code = ec
        elif type(value) is str:
            if value == "0x":
                kind = "EMPTY_BYTECODE"
            elif value.startswith("0x") and len(value) <= 2 + MAX_WIRE * 2:
                try:
                    actual = bytes.fromhex(value[2:])
                    kind = "BYTECODE_RESULT"
                    code_length = len(actual)
                    code_hash = hashlib.sha256(actual).hexdigest()
                    matches = actual == canonical
                except ValueError:
                    kind = "MALFORMED_HEX_BYTECODE"
            else:
                kind = "UNEXPECTED_RESULT_STRING"
        else:
            kind = "JSON_RPC_RESULT_MISSING_OR_NONSTRING"
    return {
        "blockSelector": selector,
        **info,
        "jsonRpcResultCategory": kind,
        "jsonRpcNumericErrorCode": err_code,
        "publicRuntimeBytes": code_length,
        "publicRuntimeSha256": code_hash,
        "matchesPinnedStandardUngatedEthereumDepositRuntime": matches,
        "rawRpcBytesBytecodeOrErrorMessagesEmitted": False,
    }

def observe(sha: str) -> dict:
    health.require_actual_source(sha)
    statuses = {name: health.internal.state(name) for name in (ORIGINAL, EL, BN, VC)}
    if statuses[ORIGINAL].get("Running") is True:
        raise R44ReadOnlyError("original Besu must stay stopped")
    if any(statuses[name].get("Running") is not True for name in (EL, BN, VC)):
        raise R44ReadOnlyError("only probe the existing live one-owner three-client G2")
    if health.rpc("eth_chainId") != hex(31340):
        raise R44ReadOnlyError("current live execution chain identity not 31340")
    canonical = bytes.fromhex(standard_reference()["code"][2:])
    if len(canonical) != 6358 or hashlib.sha256(canonical).hexdigest() != health.CODE_SHA:
        raise R44ReadOnlyError("pinned PUBLIC Ethereum deposit runtime changed")
    return {
        "schema": "SSE_R44_G2_BESU_LIVE_DEPOSIT_JSON_RPC_MULTI_CHUNK_INSPECTION_V1",
        "sourceExactGitSha": sha,
        "observationUnixUtc": int(time.time()),
        "realBesuChain31340Verified": True,
        "originalSingleBeaconAndValidatorClientsRunning": True,
        "expectedCanonicalPublicEthereumDepositSha256": health.CODE_SHA,
        "expectedCanonicalPublicDepositByteLength": len(canonical),
        "rpcReadOnlyCodeAtGenesisAndHead": [
            code_report(selector, canonical) for selector in ("earliest", "latest")
        ],
        "noContainersOrValidatorSlashingDataAltered": True,
        "noRawRpcMessageOrPrivateKeyMaterialEmitted": True,
    }

def main() -> int:
    parser = argparse.ArgumentParser(description="Safe in-Docker JSON-RPC parser for real deposit code")
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(observe(args.expected_commit), indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, R44ReadOnlyError, DepositPredeployError,
            health.old.RecoveryRefused, health.internal.Refuse):
        print("R44_DEPOSIT_RPC_INSPECTION_REFUSED", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
