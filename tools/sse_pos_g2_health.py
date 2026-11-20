#!/usr/bin/env python3
"""R35 real chain31340 read-only local EL/CL health, without secret material."""
from __future__ import annotations
import hashlib
import json
import time
from urllib.request import Request, ProxyHandler, build_opener
from urllib.error import URLError

OPENER = build_opener(ProxyHandler({}))
DEPOSIT = "0x00000000219ab540356cbb839cbe05303d7705fa"
CODE_SHA = "5aaa8327c5765ec883224895ca02cade2871e12dad0197bdc791efc91c7ef18d"
EXPECTED_GENESIS_TIME = 1795219212

def request(url: str, data: dict | None = None) -> dict | None:
    try:
        payload = json.dumps(data).encode() if data is not None else None
        req = Request(url, data=payload, headers={"Content-Type": "application/json"},
                      method="POST" if data is not None else "GET")
        with OPENER.open(req, timeout=4) as res:
            if res.status != 200: return None
            answer = json.loads(res.read(500_000))
            return answer if isinstance(answer, dict) else None
    except (OSError, ValueError, TypeError, URLError):
        return None

def rpc(method: str, params: list | None = None):
    answer = request("http://127.0.0.1:18545",
                     {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []})
    return answer.get("result") if isinstance(answer, dict) else None

def beacon(path: str):
    answer = request("http://127.0.0.1:15052" + path)
    return answer.get("data") if isinstance(answer, dict) else None

def integer(x):
    try: return int(x) if str(x).isdecimal() else None
    except (ValueError, TypeError): return None

def observe() -> dict:
    chain = rpc("eth_chainId")
    block = rpc("eth_blockNumber")
    code = rpc("eth_getCode", [DEPOSIT, "latest"])
    gen = beacon("/eth/v1/beacon/genesis")
    head = beacon("/eth/v1/beacon/headers/head")
    final = beacon("/eth/v1/beacon/states/head/finality_checkpoints")
    sync = beacon("/eth/v1/node/syncing")
    try: chain_ok = int(chain, 16) == 31340
    except (ValueError, TypeError): chain_ok = False
    try: height = int(block, 16)
    except (ValueError, TypeError): height = None
    try: code_ok = (isinstance(code, str) and code.startswith("0x") and
                   hashlib.sha256(bytes.fromhex(code[2:])).hexdigest() == CODE_SHA)
    except ValueError: code_ok = False
    genesis = integer(gen.get("genesis_time")) if isinstance(gen, dict) else None
    header = head.get("header", {}) if isinstance(head, dict) else {}
    message = header.get("message", {}) if isinstance(header, dict) else {}
    slot = integer(message.get("slot")) if isinstance(message, dict) else None
    finalized = final.get("finalized", {}) if isinstance(final, dict) else {}
    epoch = integer(finalized.get("epoch")) if isinstance(finalized, dict) else None
    return {
        "schema": "SSE_R35_REAL_CHAIN31340_G2_OBSERVATION_V1",
        "observedUtcUnixSeconds": int(time.time()),
        "elRpcResponding": chain is not None,
        "elChainId31340Verified": chain_ok,
        "executionBlockHeight": height,
        "liveDepositCodeMatchesStandardPinnedRuntime": bool(code_ok),
        "beaconApiResponding": isinstance(gen, dict),
        "beaconGenesisTimeMatchesStep40": genesis == EXPECTED_GENESIS_TIME,
        "beaconHeadSlot": slot,
        "beaconSyncStatusAvailable": isinstance(sync, dict),
        "beaconIsSyncing": sync.get("is_syncing") if isinstance(sync, dict) else None,
        "beaconFinalizedEpoch": epoch,
        "realFinalityObserved": bool(chain_ok and genesis == EXPECTED_GENESIS_TIME and
                                     epoch is not None and epoch > 0),
        "realPostGenesisExecutionBlockObserved": bool(chain_ok and height is not None and height > 0),
        "blsPrivateKeyPossessionIndependentlyVerified": False,
        "publicNativeP2PVerified": False,
        "physicalOperatorFaultDomains": 1,
    }

if __name__ == "__main__":
    print(json.dumps(observe(), sort_keys=True, indent=2))
