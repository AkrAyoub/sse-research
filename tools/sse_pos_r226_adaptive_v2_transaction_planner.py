#!/usr/bin/env python3
"""R226: exact ABI calldata planner for the LIVE chain31340 adaptive SSE V2.

Default is strictly offline: NO signer, broadcast, HTTP, Docker, or private key.
The optional --manifest / --rpc preflight executes R206 READ-ONLY canonical
finalized runtime/receipt/binding checks. A plan is NOT an authorized tx or
proof of an SLA; role labels do not authenticate the on-chain msg.sender.
V1 tools/sse_node_marketplace.py MUST NOT be substituted for this ABI.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass

from sse_challenge import keccak256
from sse_pos_r206_adaptive_v2_deployment_audit import (
    Refused as AuditRefused, load as load_manifest,
    rpc as audit_rpc, verify as verify_deployment,
)

CHAIN = 31340
GENESIS = "0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf"
ADDR = re.compile(r"0x[0-9a-fA-F]{40}\Z")
HEX32 = re.compile(r"0x[0-9a-fA-F]{64}\Z")
SIGNATURE = re.compile(r"0x[0-9a-fA-F]{130}\Z")
ROLES = frozenset(("consumer", "provider", "monitor", "observer"))
FIELDS = (
    ("endpointHash", "bytes32"), ("epochs", "uint256"),
    ("monitorBudgetWei", "uint256"), ("perMonitorEpochRewardWei", "uint256"),
    ("requiredFaultTolerance", "uint256"), ("gasBoundSeats", "uint256"),
    ("confirmationSeconds", "uint64"), ("responseSeconds", "uint64"),
    ("monitoringSeconds", "uint64"),
)

# action: (permitted owner role or "*", immutable contract key, canonical
# Solidity signature, named ABI parameters in exact position).
METHODS = {
    "monitor-register": ("monitor", "market", "registerMonitor()", ()),
    "monitor-exit": ("monitor", "market", "exitMonitor()", ()),
    "request": ("consumer", "market",
                "requestResource(bytes32,bytes32,uint256,uint64)",
                (("profileHash","bytes32"), ("policyHash","bytes32"),
                 ("maxEpochFeeWei","uint256"), ("biddingClose","uint64"))),
    "bid": ("provider", "market", "placeBid(uint256,uint256)",
            (("requestId","uint256"), ("epochFeeWei","uint256"))),
    "fund": ("consumer", "market",
             "chooseBidAndFund(uint256,uint256,(bytes32,uint256,uint256,uint256,uint256,uint256,uint64,uint64,uint64))",
             (("requestId","uint256"),("bidIndex","uint256"),("terms","terms"))),
    "draw": ("*", "market", "drawCommittee(uint256)", (("leaseId","uint256"),)),
    "cancel-expired-draw": ("*", "market", "cancelExpiredDraw(uint256)",
                            (("leaseId","uint256"),)),
    "cancel-unconfirmed": ("*", "market", "cancelUnconfirmed(uint256)",
                           (("leaseId","uint256"),)),
    "cancel-unaccepted": ("*", "market", "cancelUnaccepted(uint256)",
                          (("leaseId","uint256"),)),
    "accept": ("provider", "market", "acceptLease(uint256)",
               (("leaseId","uint256"),)),
    "start-epoch": ("consumer", "market", "startEpoch(uint256,bytes32)",
                    (("leaseId","uint256"),("requestHash","bytes32"))),
    "authenticate-response": ("provider", "market",
                              "authenticateProviderResponse(uint256,uint256,bytes32,bytes)",
                              (("leaseId","uint256"),("epochId","uint256"),
                               ("responseHash","bytes32"),("signature","bytes"))),
    "finalize-epoch": ("*", "market", "finalizeEpoch(uint256,uint256)",
                       (("leaseId","uint256"),("epochId","uint256"))),
    "resolve-inconclusive": ("*", "market",
                            "resolveInconclusive(uint256,uint256,uint256,uint256,uint256,uint256,bytes,bytes)",
                            (("leaseId","uint256"),("epochId","uint256"),
                             ("consumerShareWei","uint256"),("providerShareWei","uint256"),
                             ("nonce","uint256"),("expiry","uint256"),
                             ("consumerSig","bytes"),("providerSig","bytes"))),
    "close-lease": ("consumer", "market", "closeLease(uint256)",
                    (("leaseId","uint256"),)),
    "market-withdraw": ("*", "market", "withdraw()", ()),
    "confirm-seat": ("monitor", "ledger", "confirmSeat(uint256)",
                     (("leaseId","uint256"),)),
    "vote": ("monitor", "ledger",
             "submitVoteDirect(uint256,uint256,uint8,bytes32)",
             (("leaseId","uint256"),("epochId","uint256"),
              ("outcome","uint8"),("evidenceHash","bytes32"))),
    "signed-vote": ("monitor", "ledger",
                    "submitSignedVote(uint256,uint256,uint8,bytes32,bytes)",
                    (("leaseId","uint256"),("epochId","uint256"),
                     ("outcome","uint8"),("evidenceHash","bytes32"),
                     ("signature","bytes"))),
    "ledger-withdraw": ("*", "ledger", "withdraw()", ()),
}


class Refused(ValueError):
    pass


def number(value, label, bits=256, minimum=0):
    if type(value) is not int or not minimum <= value < 2 ** bits:
        raise Refused("invalid unsigned " + label)
    return value


def checked_address(value):
    if type(value) is not str or not ADDR.fullmatch(value) or int(value, 16) == 0:
        raise Refused("invalid nonzero deployed contract address")
    return value.lower()


def fixed32(value, label):
    if type(value) is not str or not HEX32.fullmatch(value) or int(value, 16) == 0:
        raise Refused("invalid nonzero " + label)
    return bytes.fromhex(value[2:])


def signature_bytes(value, label):
    if type(value) is not str or not SIGNATURE.fullmatch(value):
        raise Refused("expected 65-byte Ethereum " + label)
    raw = bytes.fromhex(value[2:])
    # OZ ECDSA.recover bytes requires canonical v=27/28. This does not
    # validate recovery, low-s, signer identity or EIP-712 domain.
    if raw[64] not in (27, 28):
        raise Refused("noncanonical recovery id for " + label)
    return raw


def word(value, kind, label):
    if kind == "bytes32":
        return fixed32(value, label)
    bits = {"uint8":8, "uint64":64, "uint256":256}.get(kind)
    if bits is None:
        raise Refused("unsupported ABI type")
    return number(value, label, bits).to_bytes(32, "big")


def terms_words(terms):
    if type(terms) is not dict or set(terms) != {key for key, _ in FIELDS}:
        raise Refused("V2 Terms fields do not match exact contract ABI")
    epochs = number(terms["epochs"], "epochs", minimum=1)
    if epochs > 64:
        raise Refused("more epochs than V2 maximum")
    for field in ("monitorBudgetWei", "perMonitorEpochRewardWei",
                  "requiredFaultTolerance", "gasBoundSeats"):
        number(terms[field], field, minimum=1)
    seats = number(terms["gasBoundSeats"], "gasBoundSeats")
    faults = number(terms["requiredFaultTolerance"], "requiredFaultTolerance")
    if seats < 3 * faults + 1 or seats > 64:
        raise Refused("committee bound cannot tolerate claimed faults")
    confirmation = number(terms["confirmationSeconds"], "confirmationSeconds", 64)
    response = number(terms["responseSeconds"], "responseSeconds", 64)
    monitoring = number(terms["monitoringSeconds"], "monitoringSeconds", 64)
    if not 3600 <= confirmation <= 604800 or not 1 <= response <= 604800 or not 1 <= monitoring <= 604800:
        raise Refused("invalid V2 deadline bounds")
    # Actual seats are determined by the frozen on-chain candidate count, not
    # this planner. Never infer global network size from gasBoundSeats.
    return b"".join(word(terms[key], kind, key) for key, kind in FIELDS)


def encode_arguments(spec, params):
    head_count = sum(9 if kind == "terms" else 1 for _,kind in spec)
    head = []
    tail = b""
    for name,kind in spec:
        value = params[name]
        if kind == "terms":
            head.append(terms_words(value))
        elif kind == "bytes":
            raw = signature_bytes(value, name)
            head.append((32 * head_count + len(tail)).to_bytes(32, "big"))
            tail += len(raw).to_bytes(32, "big") + raw + bytes((-len(raw)) % 32)
        else:
            head.append(word(value, kind, name))
    return b"".join(head) + tail


@dataclass(frozen=True)
class Plan:
    action: str
    role: str
    target: str
    calldata: str
    value_wei: int
    manifest_verified: bool
    full_security_review: bool = False

    def public(self):
        return {
            "schema": "SSE_R226_ADAPTIVE_V2_UNSIGNED_TX_PLAN_V1",
            "chainId": CHAIN, "executionGenesisHash": GENESIS,
            "action": self.action, "declaredRole": self.role,
            "to": self.target, "data": self.calldata,
            "valueWei": str(self.value_wei),
            "finalizedDeploymentAndBindingsVerified": self.manifest_verified,
            "signerOrRoleAuthorizationVerified": False,
            "leaseAndCommitteePreconditionsVerified": False,
            "monitorPhysicalIndependenceVerified": False,
            "realSlaVerified": False,
            "gasAndSpendBudgetVerified": False,
            "transactionSignedOrSubmitted": False,
            "securityAuditComplete": self.full_security_review,
        }


def build(action, role, params, market, ledger, *, verified=False):
    if action not in METHODS or role not in ROLES:
        raise Refused("unknown V2 action or declared role")
    allowed, destination, signature, spec = METHODS[action]
    if allowed != "*" and role != allowed:
        raise Refused("role not permitted to prepare this transaction")
    if type(params) is not dict:
        raise Refused("params must be a JSON object")
    extra = {"bondWei"} if action == "monitor-register" else (
        {"bidEpochFeeWei"} if action == "fund" else set()
    )
    if set(params) != {name for name,_ in spec} | extra:
        raise Refused("unexpected or missing V2 action parameters")
    market = checked_address(market)
    ledger = checked_address(ledger)
    if market == ledger:
        raise Refused("market and ledger addresses must differ")
    value = 0
    if action == "monitor-register":
        value = number(params["bondWei"], "bondWei", minimum=1)
    elif action == "fund":
        bid_fee = number(params["bidEpochFeeWei"], "bidEpochFeeWei", minimum=1)
        t = params["terms"]
        if type(t) is not dict:
            raise Refused("expected V2 Terms object")
        # The consumer pays bid fee per epoch PLUS the complete monitor pool.
        # This quote is NOT verified against the current on-chain bid unless
        # optional finalized runtime verification is explicitly requested.
        term_bytes = terms_words(t)
        value = bid_fee * int.from_bytes(term_bytes[32:64], "big") + t["monitorBudgetWei"]
        number(value, "funded escrow", minimum=1)
    elif action == "request":
        number(params["maxEpochFeeWei"], "maxEpochFeeWei", minimum=1)
        number(params["biddingClose"], "biddingClose", 64, minimum=1)
    elif action == "bid":
        number(params["requestId"], "requestId", minimum=1)
        number(params["epochFeeWei"], "epochFeeWei", minimum=1)
    if action in ("vote", "signed-vote") and params["outcome"] not in (1,2):
        raise Refused("outcome must be 1=Success or 2=Failure")
    if action == "resolve-inconclusive":
        if params["consumerShareWei"] + params["providerShareWei"] <= 0:
            raise Refused("empty residual allocation")
        number(params["expiry"], "expiry", minimum=1)
    data = "0x" + (keccak256(signature.encode("ascii"))[:4] + encode_arguments(spec, params)).hex()
    return Plan(action, role, market if destination == "market" else ledger, data, value, verified)


def verify_funded_bid(plan, params, manifest, rpc_url, *, transport=audit_rpc):
    if plan.action != "fund":
        return
    # The actual bid is a two-word static struct (provider,address; fee,uint256)
    # and is queried at the SAME finalized block as R206 code evidence.
    chain_result = verify_deployment(manifest, rpc_url, transport=transport)
    height = chain_result["finalizedExecutionHeight"]
    bid_data = "0x" + (keccak256(b"getBid(uint256,uint256)")[:4]
                 + number(params["requestId"], "requestId").to_bytes(32,"big")
                 + number(params["bidIndex"], "bidIndex").to_bytes(32,"big")).hex()
    raw = transport(rpc_url,"eth_call",[{"to":manifest["market"]["address"],"data":bid_data},hex(height)])
    if type(raw) is not str or not re.fullmatch(r"0x[0-9a-fA-F]{128}\Z",raw):
        raise Refused("finalized bid read is not two ABI words")
    provider = int(raw[2:66],16)
    fee = int(raw[66:],16)
    if provider == 0 or fee != params["bidEpochFeeWei"]:
        raise Refused("finalized on-chain bid absent or fee mismatches escrow quote")


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--action",choices=sorted(METHODS),required=True)
    p.add_argument("--role",choices=sorted(ROLES),required=True)
    p.add_argument("--params-json",required=True,help="public parameters ONLY; no secret keys")
    p.add_argument("--market",required=True)
    p.add_argument("--ledger",required=True)
    p.add_argument("--manifest",help="optional finalized R206 deployment manifest")
    p.add_argument("--rpc",help="approved localhost JSON-RPC, requires --manifest")
    a=p.parse_args(argv)
    try:
        if bool(a.manifest) != bool(a.rpc):
            raise Refused("--manifest and --rpc must be supplied together")
        params=json.loads(a.params_json)
        plan=build(a.action,a.role,params,a.market,a.ledger)
        verified=False
        if a.manifest:
            manifest=load_manifest(__import__("pathlib").Path(a.manifest))
            if (checked_address(a.market) != checked_address(manifest["market"]["address"]) or
                checked_address(a.ledger) != checked_address(manifest["ledger"]["address"])):
                raise Refused("CLI target address mismatches attested runtime")
            verify_deployment(manifest,a.rpc)
            if a.action == "monitor-register" and plan.value_wei < int(manifest["minimumBondWei"]):
                raise Refused("monitor bond is smaller than finalized immutable minimum")
            if a.action == "fund":
                verify_funded_bid(plan,params,manifest,a.rpc)
            verified=True
        print(json.dumps(build(a.action,a.role,params,a.market,a.ledger,verified=verified).public(),
                         sort_keys=True,indent=2))
        return 0
    except (Refused,AuditRefused,KeyError,TypeError,ValueError,OSError,OverflowError) as exc:
        print("R226_UNSIGNED_ADAPTIVE_V2_PLAN_REFUSED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
