#!/usr/bin/env python3
"""SSE V4 candidate ABI layer: calldata builders, view decoders, event decoding.

SOURCE-ONLY (2026-11-27): never executed. Hand-written from the Solidity
sources (contracts/SSEAdaptiveMarketV4.sol, SSEServiceBoardV4.sol,
SSEMonitorRegistryV4.sol, SSEStandbyCommittee.sol,
SSEAdaptiveVoteLedgerV4Candidate.sol). After the owner compiles, DRV-V4-ABI
must diff these signatures against `forge inspect <C> abi`.
No network access here; callers inject `ask(method, params)`.
"""
from eth_abi import decode, encode
from eth_utils import keccak

MODULES = ("market", "board", "registry", "standby", "ledger")

# ---------------------------------------------------------------- structs
LEASE_FIELDS = (
    ("consumer", "address"), ("provider", "address"), ("phase", "uint8"), ("providerAccepted", "bool"),
    ("conditionalQuorumPolicy", "bool"), ("responseAdmitsReceipt", "bool"), ("seats", "uint16"),
    ("standbys", "uint16"), ("faultTolerance", "uint16"), ("acceptDeadline", "uint64"),
    ("confirmationRoundSeconds", "uint64"), ("responseSeconds", "uint64"), ("monitoringSeconds", "uint64"),
    ("evidenceSeconds", "uint64"), ("idleSeconds", "uint64"), ("lastProgressAt", "uint64"),
    ("requestId", "uint256"), ("bidIndex", "uint256"), ("epochFee", "uint256"), ("maxEpochs", "uint256"),
    ("nextEpoch", "uint256"), ("closedEpochs", "uint256"), ("serviceRemaining", "uint256"),
    ("monitorBudget", "uint256"), ("monitorBudgetTransferred", "bool"), ("perReportReward", "uint256"),
    ("entropyBlock", "uint256"), ("populationCut", "uint256"), ("profileHash", "bytes32"),
    ("policyHash", "bytes32"), ("artifactCommitment", "bytes32"), ("endpointHash", "bytes32"),
    ("offerHash", "bytes32"), ("termsHash", "bytes32"))
MARKET_EPOCH_FIELDS = (
    ("requestHash", "bytes32"), ("responseHash", "bytes32"), ("fee", "uint256"), ("nonce", "uint256"),
    ("exists", "bool"), ("resolved", "bool"), ("acknowledged", "bool"), ("accounted", "bool"),
    ("evidenceClose", "uint64"))
SCIENTIFIC_EPOCH_FIELDS = (
    ("requestHash", "bytes32"), ("mask", "uint8"), ("evidenceClosed", "bool"), ("residualAllocated", "bool"),
    ("providerCredit", "uint256"), ("consumerCredit", "uint256"), ("unresolved", "uint256"))
REQUEST_FIELDS = (
    ("consumer", "address"), ("status", "uint8"), ("fixedEpochs", "uint32"), ("maxEpochs", "uint32"),
    ("seats", "uint16"), ("standbys", "uint16"), ("faultTolerance", "uint16"), ("biddingClose", "uint64"),
    ("profileHash", "bytes32"), ("policyHash", "bytes32"), ("artifactCommitment", "bytes32"),
    ("maxEpochFee", "uint256"), ("perReportReward", "uint256"), ("awardedBid", "uint256"))
BID_FIELDS = (
    ("provider", "address"), ("withdrawn", "bool"), ("epochs", "uint32"), ("expiry", "uint64"),
    ("epochFee", "uint256"), ("endpointHash", "bytes32"), ("offerHash", "bytes32"))
TERMS_FIELDS = (
    ("acceptSeconds", "uint64"), ("confirmationRoundSeconds", "uint64"), ("responseSeconds", "uint64"),
    ("monitoringSeconds", "uint64"), ("evidenceSeconds", "uint64"), ("idleSeconds", "uint64"),
    ("reservationFee", "uint256"), ("exposureBudget", "uint256"), ("conditionalQuorumPolicy", "bool"),
    ("responseAdmitsReceipt", "bool"))
REQUEST_INPUT_FIELDS = (
    ("profileHash", "bytes32"), ("policyHash", "bytes32"), ("artifactCommitment", "bytes32"),
    ("maxEpochFee", "uint256"), ("biddingClose", "uint64"), ("fixedEpochs", "uint32"), ("maxEpochs", "uint32"),
    ("seats", "uint16"), ("standbys", "uint16"), ("faultTolerance", "uint16"), ("perReportReward", "uint256"))
COMMITTEE_FIELDS = (
    ("consumer", "address"), ("provider", "address"), ("eligibilitySnapshotRoot", "bytes32"), ("seats", "uint256"),
    ("quorum", "uint256"), ("requiredFaultTolerance", "uint256"), ("confirmationDeadline", "uint64"),
    ("initialized", "bool"), ("ready", "bool"), ("confirmationExpired", "bool"), ("rewardPerReport", "uint256"),
    ("originalReportBudget", "uint256"), ("unspentReportBudget", "uint256"), ("maxPayableEpochs", "uint256"),
    ("openedEpochs", "uint256"), ("sealedEpochs", "uint256"), ("reportingClosed", "bool"))
LEDGER_EPOCH_FIELDS = (
    ("requestHash", "bytes32"), ("responseHash", "bytes32"), ("responseDeadline", "uint64"),
    ("monitoringClose", "uint64"), ("successVotes", "uint256"), ("failureVotes", "uint256"),
    ("totalVotes", "uint256"), ("exists", "bool"), ("responseAuthenticated", "bool"),
    ("monitoringSealed", "bool"), ("outcome", "uint8"))
ASSIGNMENT_FIELDS = (
    ("phase", "uint8"), ("deadline", "uint64"), ("roundSeconds", "uint64"), ("quorum", "uint256"),
    ("confirmedCount", "uint256"), ("nextStandby", "uint256"), ("primary", "address[]"), ("standby", "address[]"))

LEASE_PHASES = ("None", "PendingDraw", "Forming", "Active", "Closed", "Cancelled")
REQUEST_STATUS = ("None", "Open", "Awarded", "Cancelled")
STANDBY_PHASES = ("None", "Confirming", "Ready", "Expired")
OUTCOMES = ("None", "Success", "Failure")
CANCEL_REASONS = {1: "DRAW_EXPIRED", 2: "INSUFFICIENT_MONITORS", 3: "COMMITTEE_UNFORMED", 4: "UNACCEPTED"}


def tuple_type(fields):
    return "(" + ",".join(t for _, t in fields) + ")"


def as_dict(fields, values):
    out = {}
    for (name, kind), v in zip(fields, values):
        if kind == "bytes32":
            v = "0x" + bytes(v).hex()
        elif kind == "address":
            v = v.lower()
        elif kind == "address[]":
            v = [a.lower() for a in v]
        out[name] = v
    return out


def as_tuple(fields, d):
    out = []
    for name, kind in fields:
        if name not in d:
            raise ValueError("missing field " + name)
        v = d[name]
        if kind == "bytes32":
            v = bytes.fromhex(v[2:]) if isinstance(v, str) else bytes(v)
            if len(v) != 32:
                raise ValueError(name + " must be 32 bytes")
        elif kind == "bool":
            if type(v) is not bool:
                raise ValueError(name + " must be bool")
        elif kind.startswith("uint"):
            bits = int(kind[4:])
            if type(v) is not int or not 0 <= v < 2 ** bits:
                raise ValueError(name + " out of range")
        out.append(v)
    return tuple(out)


# ---------------------------------------------------------------- calldata
def selector(signature):
    return keccak(text=signature)[:4]


def calldata(signature, types=(), args=()):
    return "0x" + (selector(signature) + encode(list(types), list(args))).hex()


def b32(v):
    v = bytes.fromhex(v[2:]) if isinstance(v, str) else bytes(v)
    if len(v) != 32:
        raise ValueError("bytes32 required")
    return v


# Each builder returns (module, calldata, valueWei). Values are computed from
# chain-read data by the caller; builders never guess money amounts.
def create_request(r):
    t = tuple_type(REQUEST_INPUT_FIELDS)
    return "board", calldata("createRequest(" + t + ")", (t,), (as_tuple(REQUEST_INPUT_FIELDS, r),)), 0


def cancel_request(request_id):
    return "board", calldata("cancelRequest(uint256)", ("uint256",), (request_id,)), 0


def place_bid(request_id, epoch_fee, epochs, expiry, endpoint_hash, offer_hash):
    return "board", calldata("placeBid(uint256,uint256,uint32,uint64,bytes32,bytes32)",
        ("uint256", "uint256", "uint32", "uint64", "bytes32", "bytes32"),
        (request_id, epoch_fee, epochs, expiry, b32(endpoint_hash), b32(offer_hash))), 0


def withdraw_bid(request_id, index):
    return "board", calldata("withdrawBid(uint256,uint256)", ("uint256", "uint256"), (request_id, index)), 0


def award_and_fund(request_id, bid_index, terms, request, bid):
    value = bid["epochFee"] * bid["epochs"] + request["seats"] * bid["epochs"] * request["perReportReward"]
    t = tuple_type(TERMS_FIELDS)
    return "market", calldata("awardAndFund(uint256,uint256," + t + ")", ("uint256", "uint256", t),
        (request_id, bid_index, as_tuple(TERMS_FIELDS, terms))), value


AWARD_AND_FUND_SIG = "awardAndFund(uint256,uint256," + tuple_type(TERMS_FIELDS) + ")"


def decode_award_and_fund(data):
    """Decode direct awardAndFund calldata -> (requestId, bidIndex, terms dict).
    Raises ValueError for any other selector or malformed input. The result is
    NOT trusted by itself: callers must recompute termsHash and compare it with
    the finalized on-chain lease.termsHash before acting on it."""
    raw = bytes.fromhex(data[2:] if data.startswith("0x") else data)
    if len(raw) < 4 or raw[:4] != selector(AWARD_AND_FUND_SIG):
        raise ValueError("not a direct awardAndFund call")
    t = tuple_type(TERMS_FIELDS)
    try:
        rid, bid_index, tv = decode(["uint256", "uint256", t], raw[4:])
    except Exception as exc:  # eth_abi raises several decoding error types
        raise ValueError("malformed awardAndFund calldata") from exc
    return rid, bid_index, as_dict(TERMS_FIELDS, tv)


def lease_call(name, lease_id):
    if name not in ("drawCommittee", "activateCommittee", "cancelExpiredDraw", "cancelUnformed",
                    "cancelUnaccepted", "closeLease", "forceCloseIdle"):
        raise ValueError("unknown lease call")
    return "market", calldata(name + "(uint256)", ("uint256",), (lease_id,)), 0


def accept_lease(lease_id, terms_hash):
    return "market", calldata("acceptLease(uint256,bytes32)", ("uint256", "bytes32"), (lease_id, b32(terms_hash))), 0


def start_epoch(lease_id, request_hash):
    return "market", calldata("startEpoch(uint256,bytes32)", ("uint256", "bytes32"), (lease_id, b32(request_hash))), 0


def epoch_call(name, lease_id, epoch_id):
    if name not in ("finalizeEpoch", "closeEpochEvidence"):
        raise ValueError("unknown epoch call")
    return "market", calldata(name + "(uint256,uint256)", ("uint256", "uint256"), (lease_id, epoch_id)), 0


def authenticate_response(lease_id, epoch_id, response_hash, signature):
    return "market", calldata("authenticateProviderResponse(uint256,uint256,bytes32,bytes)",
        ("uint256", "uint256", "bytes32", "bytes"), (lease_id, epoch_id, b32(response_hash), bytes(signature))), 0


def submit_ack(lease_id, epoch_id, signature):
    return "market", calldata("submitAcknowledgment(uint256,uint256,bytes)", ("uint256", "uint256", "bytes"),
        (lease_id, epoch_id, bytes(signature))), 0


ALLOCATION_FIELDS = (("unresolvedAmount", "uint256"), ("providerShare", "uint256"),
                     ("consumerShare", "uint256"), ("nonce", "uint256"), ("expiry", "uint256"))


def resolve_residual(lease_id, epoch_id, allocation, consumer_signature, provider_signature):
    t = tuple_type(ALLOCATION_FIELDS)
    values = as_tuple(ALLOCATION_FIELDS, allocation)
    if lease_id <= 0 or values[0] == 0 or values[1] + values[2] != values[0]:
        raise ValueError("invalid residual allocation")
    if any(not isinstance(sig, (bytes, bytearray)) or len(sig) != 65
           for sig in (consumer_signature, provider_signature)):
        raise ValueError("two 65-byte EOA signatures required")
    return "market", calldata("resolveResidual(uint256,uint256," + t + ",bytes,bytes)",
        ("uint256", "uint256", t, "bytes", "bytes"),
        (lease_id, epoch_id, values, bytes(consumer_signature), bytes(provider_signature))), 0


def withdraw(module):
    if module not in ("market", "registry", "ledger"):
        raise ValueError("module has no withdraw")
    return module, calldata("withdraw()"), 0


def register_monitor(capacity, bond_wei):
    return "registry", calldata("register(uint256)", ("uint256",), (capacity,)), bond_wei


def update_bond(new_capacity, topup_wei):
    return "registry", calldata("updateBond(uint256)", ("uint256",), (new_capacity,)), topup_wei


def registry_call(name):
    if name not in ("requestExit", "completeExit"):
        raise ValueError("unknown registry call")
    return "registry", calldata(name + "()"), 0


def standby_call(name, lease_id):
    if name not in ("confirm", "advance"):
        raise ValueError("unknown standby call")
    return "standby", calldata(name + "(uint256)", ("uint256",), (lease_id,)), 0


def submit_vote_direct(lease_id, epoch_id, outcome, evidence_hash):
    if outcome not in (1, 2):
        raise ValueError("outcome must be 1 or 2")
    return "ledger", calldata("submitVoteDirect(uint256,uint256,uint8,bytes32)",
        ("uint256", "uint256", "uint8", "bytes32"), (lease_id, epoch_id, outcome, b32(evidence_hash))), 0


# ---------------------------------------------------------------- views
def view(ask, address, signature, types=(), args=(), out=("uint256",), tag="finalized"):
    raw = ask("eth_call", [{"to": address, "data": calldata(signature, types, args)}, tag])
    if not isinstance(raw, str) or not raw.startswith("0x"):
        raise ValueError("bad eth_call result")
    return decode(list(out), bytes.fromhex(raw[2:]))


def read_struct(ask, address, signature, types, args, fields, tag="finalized"):
    return as_dict(fields, view(ask, address, signature, types, args, (tuple_type(fields),), tag)[0])


# ---------------------------------------------------------------- events
# name: (module, [(field, type, indexed)])
EVENTS = {
    "RequestCreated": ("board", [("requestId", "uint256", True), ("consumer", "address", True),
        ("profileHash", "bytes32", False), ("policyHash", "bytes32", False), ("artifactCommitment", "bytes32", False),
        ("maxEpochFee", "uint256", False), ("biddingClose", "uint64", False)]),
    "RequestMonitoring": ("board", [("requestId", "uint256", True), ("seats", "uint16", False),
        ("standbys", "uint16", False), ("faultTolerance", "uint16", False), ("perReportReward", "uint256", False),
        ("fixedEpochs", "uint32", False), ("maxEpochs", "uint32", False)]),
    "RequestCancelled": ("board", [("requestId", "uint256", True)]),
    "BidPlaced": ("board", [("requestId", "uint256", True), ("index", "uint256", True), ("provider", "address", True),
        ("epochFee", "uint256", False), ("epochs", "uint32", False), ("expiry", "uint64", False),
        ("endpointHash", "bytes32", False), ("offerHash", "bytes32", False)]),
    "BidWithdrawn": ("board", [("requestId", "uint256", True), ("index", "uint256", True)]),
    "BidAwarded": ("board", [("requestId", "uint256", True), ("index", "uint256", True), ("provider", "address", True)]),
    "LeaseFunded": ("market", [("leaseId", "uint256", True), ("requestId", "uint256", True),
        ("provider", "address", True), ("bidIndex", "uint256", False), ("termsHash", "bytes32", False)]),
    "DrawCommitted": ("market", [("leaseId", "uint256", True), ("entropyBlock", "uint256", False),
        ("populationCut", "uint256", False)]),
    "CommitteeDrawn": ("market", [("leaseId", "uint256", True), ("entropy", "bytes32", True),
        ("seats", "uint256", False), ("standbys", "uint256", False)]),
    "CommitteeActivated": ("market", [("leaseId", "uint256", True), ("seats", "uint256", False), ("quorum", "uint256", False)]),
    "ProviderAccepted": ("market", [("leaseId", "uint256", True)]),
    "LeaseCancelled": ("market", [("leaseId", "uint256", True), ("reason", "uint8", False), ("refundedWei", "uint256", False)]),
    "EpochStarted": ("market", [("leaseId", "uint256", True), ("epochId", "uint256", True),
        ("requestHash", "bytes32", False), ("responseDeadline", "uint64", False), ("monitoringClose", "uint64", False),
        ("evidenceClose", "uint64", False)]),
    "ProviderResponseVerified": ("market", [("leaseId", "uint256", True), ("epochId", "uint256", True),
        ("responseHash", "bytes32", False)]),
    "ReceiptAccepted": ("market", [("leaseId", "uint256", True), ("epochId", "uint256", True), ("fromResponse", "bool", False)]),
    "EntitlementsUpdated": ("market", [("leaseId", "uint256", True), ("epochId", "uint256", True),
        ("histories", "uint8", False), ("providerDelta", "uint256", False), ("consumerDelta", "uint256", False),
        ("unresolved", "uint256", False)]),
    "EpochConcluded": ("market", [("leaseId", "uint256", True), ("epochId", "uint256", True), ("outcome", "uint8", False)]),
    "EvidenceClosed": ("market", [("leaseId", "uint256", True), ("epochId", "uint256", True)]),
    "InconclusiveAllocated": ("market", [("leaseId", "uint256", True), ("epochId", "uint256", True),
        ("consumerShare", "uint256", False), ("providerShare", "uint256", False)]),
    "LeaseClosed": ("market", [("leaseId", "uint256", True), ("returnedServiceWei", "uint256", False),
        ("idleExpiry", "bool", False)]),
    "MonitorRegistered": ("registry", [("monitor", "address", True), ("entryIndex", "uint256", True),
        ("bond", "uint256", False), ("capacity", "uint256", False)]),
    "MonitorBondUpdated": ("registry", [("monitor", "address", True), ("bond", "uint256", False), ("capacity", "uint256", False)]),
    "MonitorExitRequested": ("registry", [("monitor", "address", True), ("reservedRemaining", "uint256", False)]),
    "MonitorBondReleased": ("registry", [("monitor", "address", True), ("bond", "uint256", False)]),
    "SeatsReserved": ("registry", [("leaseId", "uint256", True), ("ordered", "address[]", False), ("attempts", "uint256", False)]),
    "SeatReleased": ("registry", [("leaseId", "uint256", True), ("monitor", "address", True)]),
    "Initialized": ("standby", [("leaseId", "uint256", True), ("seats", "uint256", False), ("quorum", "uint256", False),
        ("reserves", "uint256", False), ("deadline", "uint64", False)]),
    "Confirmed": ("standby", [("leaseId", "uint256", True), ("monitor", "address", True)]),
    "Promoted": ("standby", [("leaseId", "uint256", True), ("removed", "address", True), ("replacement", "address", True)]),
    "Ready": ("standby", [("leaseId", "uint256", True)]),
    "Expired": ("standby", [("leaseId", "uint256", True)]),
    "CommitteeFrozen": ("ledger", [("leaseId", "uint256", True), ("snapshotRoot", "bytes32", True),
        ("seats", "uint256", False), ("quorum", "uint256", False)]),
    "EpochOpened": ("ledger", [("leaseId", "uint256", True), ("epochId", "uint256", True), ("requestHash", "bytes32", False)]),
    "ResponseAuthenticated": ("ledger", [("leaseId", "uint256", True), ("epochId", "uint256", True), ("responseHash", "bytes32", False)]),
    "VoteRecorded": ("ledger", [("leaseId", "uint256", True), ("epochId", "uint256", True), ("monitor", "address", True),
        ("outcome", "uint8", False), ("evidenceHash", "bytes32", False)]),
    "MonitoringSealed": ("ledger", [("leaseId", "uint256", True), ("epochId", "uint256", True), ("outcome", "uint8", False)]),
    "ReportRewardEarned": ("ledger", [("leaseId", "uint256", True), ("epochId", "uint256", True),
        ("monitor", "address", True), ("amount", "uint256", False)]),
    "ReportingClosed": ("ledger", [("leaseId", "uint256", True), ("unspentRefunded", "uint256", False)]),
    "Withdrawal": ("*", [("account", "address", True), ("amount", "uint256", False)]),
}


def event_signature(name):
    return name + "(" + ",".join(t for _, t, _ in EVENTS[name][1]) + ")"


TOPICS = {"0x" + keccak(text=event_signature(n)).hex(): n for n in EVENTS}


def decode_log(log, modules):
    """Decode one eth_getLogs entry. `modules` maps module name -> lower address.
    Returns None for logs that are not SSE V4 events of the expected module."""
    topics = [t.lower() for t in log.get("topics", [])]
    if not topics or topics[0] not in TOPICS:
        return None
    name = TOPICS[topics[0]]
    module, fields = EVENTS[name]
    emitter = log["address"].lower()
    owner = [m for m, a in modules.items() if a == emitter]
    if not owner or (module != "*" and owner[0] != module):
        return None
    indexed = [f for f in fields if f[2]]
    if len(topics) != 1 + len(indexed):
        raise ValueError("topic count mismatch for " + name)
    plain = [f for f in fields if not f[2]]
    data = bytes.fromhex(log["data"][2:]) if log.get("data", "0x") != "0x" else b""
    values = dict(zip([f[0] for f in plain], decode([f[1] for f in plain], data))) if plain else {}
    for (fname, kind, _), topic in zip(indexed, topics[1:]):
        values[fname] = decode([kind], bytes.fromhex(topic[2:]))[0]
    out = {"event": name, "module": owner[0], "blockNumber": int(log["blockNumber"], 16),
           "blockHash": log["blockHash"].lower(), "transactionHash": log["transactionHash"].lower(),
           "logIndex": int(log["logIndex"], 16)}
    for fname, kind, _ in fields:
        v = values[fname]
        if kind == "bytes32":
            v = "0x" + bytes(v).hex()
        elif kind == "address":
            v = v.lower()
        elif kind == "address[]":
            v = [a.lower() for a in v]
        out[fname] = v
    return out
