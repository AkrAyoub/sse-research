"""WP-08F consensus-API *reported* finalized execution view cross-check.

This is a strictly read-only local laboratory guard. A trusted Beacon REST
server reports finalized data; no SSZ Merkle proof, BLS sync committee
signature, Ethereum consensus light client, or remote TLS authentication is
implemented. The result MUST NOT be called cryptographically proven finality,
physical SLA fulfillment or authority to release escrow.

The execution client is checked for a bounded chain of block-hash parent links
from the beacon-reported finalized execution block to a signed monitor anchor.
Two execution RPC views can be compared; neither can prove independence.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

from sse_chain_read import ChainReadError, _hex_integer
from sse_wp08d_provenance import BlockAnchor, ProvenanceError, valid_block_hash

NONZERO_HASH_RE = re.compile(r"0x[0-9a-f]{64}\Z")
MAX_BEACON_BYTES = 8 * 1024 * 1024
MAX_ANCESTRY_DEPTH = 128
SUPPORTED_FORKS = frozenset(("bellatrix", "capella", "deneb", "electra", "fulu"))


class BeaconFinalityError(ProvenanceError):
    """Untrusted, malformed or inconsistent consensus-API finality assertion."""


def _decimal(value, field):
    if (type(value) is not str or not value or
            (len(value) > 1 and value[0] == "0") or
            not value.isascii() or not value.isdecimal()):
        raise BeaconFinalityError(f"noncanonical beacon {field}")
    return int(value, 10)


def _rpc_header(rpc, method, params):
    try:
        item = rpc.request(method, params)
    except (ChainReadError, ValueError, OSError) as exc:
        raise BeaconFinalityError(f"execution RPC {method} unavailable") from exc
    if (type(item) is not dict or type(item.get("hash")) is not str or
            not valid_block_hash(item["hash"].lower()) or
            type(item.get("parentHash")) is not str or
            not NONZERO_HASH_RE.fullmatch(item["parentHash"].lower())):
        raise BeaconFinalityError("execution RPC returned missing/invalid block header")
    try:
        number = _hex_integer(item.get("number"))
        timestamp = _hex_integer(item.get("timestamp"))
    except (ChainReadError, ValueError) as exc:
        raise BeaconFinalityError("execution block has malformed height or time") from exc
    return item["hash"].lower(), item["parentHash"].lower(), number, timestamp


@dataclass(frozen=True)
class BeaconReportedFinalizedExecution:
    """Unverified consensus-API claim, anchored to configured genesis root."""
    genesis_validators_root: str
    beacon_slot: int
    execution_block_number: int
    execution_block_hash: str
    execution_timestamp: int

    def __post_init__(self):
        if (not valid_block_hash(self.genesis_validators_root) or
                not valid_block_hash(self.execution_block_hash) or
                type(self.beacon_slot) is not int or self.beacon_slot < 1 or
                type(self.execution_block_number) is not int or
                self.execution_block_number < 1 or
                type(self.execution_timestamp) is not int or self.execution_timestamp < 0):
            raise BeaconFinalityError("invalid consensus API finalized execution claim")


class LoopbackBeaconREST:
    """No proxy, redirect, DNS, remote URL, or HTTP credentials. Still TRUSTED."""

    def __init__(self, url: str, expected_genesis_validators_root: str,
                 timeout: float = 5.0):
        try:
            u = urlsplit(url)
            port = u.port
        except (ValueError, TypeError) as exc:
            raise BeaconFinalityError("invalid beacon endpoint") from exc
        if (u.scheme != "http" or u.hostname != "127.0.0.1" or
                port is None or not 1 <= port <= 65535 or
                u.path not in ("", "/") or u.query or u.fragment or
                u.username or u.password):
            raise BeaconFinalityError("beacon REST only accepts http://127.0.0.1:PORT")
        if not valid_block_hash(expected_genesis_validators_root):
            raise BeaconFinalityError("explicit nonzero expected genesis validators root required")
        if type(timeout) not in (int, float) or not 0 < timeout <= 30:
            raise BeaconFinalityError("invalid beacon query timeout")
        self.url = f"http://127.0.0.1:{port}"
        self.genesis_root = expected_genesis_validators_root
        self.timeout = float(timeout)

    def _request(self, path: str):
        class RejectRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = build_opener(ProxyHandler({}), RejectRedirect())
        request = Request(self.url + path, headers={"Accept": "application/json"},
                          method="GET")
        try:
            with opener.open(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise BeaconFinalityError("beacon HTTP status is not 200")
                raw = response.read(MAX_BEACON_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise BeaconFinalityError("beacon endpoint unavailable or redirected") from exc
        if not raw or len(raw) > MAX_BEACON_BYTES:
            raise BeaconFinalityError("beacon response exceeds bounded size")
        def no_duplicates(items):
            result = {}
            for k, v in items:
                if k in result:
                    raise BeaconFinalityError("duplicate beacon JSON property")
                result[k] = v
            return result
        try:
            return json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates,
                              parse_constant=lambda v: (_ for _ in ()).throw(
                                  BeaconFinalityError("nonfinite beacon JSON")))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise BeaconFinalityError("malformed beacon JSON") from exc

    def get_reported_finalized_execution(self) -> BeaconReportedFinalizedExecution:
        """Require configured genesis root and non-optimistic finalized REST view.

        API /eth/v2/beacon/blocks/finalized is standard, but it is NOT a
        consensus proof: the REST server may fabricate all returned values.
        """
        genesis = self._request("/eth/v1/beacon/genesis")
        if (type(genesis) is not dict or type(genesis.get("data")) is not dict or
                genesis["data"].get("genesis_validators_root") != self.genesis_root):
            raise BeaconFinalityError("beacon genesis validators root mismatch")
        result = self._request("/eth/v2/beacon/blocks/finalized")
        if (type(result) is not dict or result.get("finalized") is not True or
                result.get("execution_optimistic") is not False or
                result.get("version") not in SUPPORTED_FORKS):
            raise BeaconFinalityError("beacon execution is not explicitly finalized and non-optimistic")
        try:
            message = result["data"]["message"]
            body = message["body"]
            payload = body["execution_payload"]
            slot = _decimal(message["slot"], "slot")
            number = _decimal(payload["block_number"], "block_number")
            timestamp = _decimal(payload["timestamp"], "timestamp")
            execution_hash = payload["block_hash"]
        except (KeyError, TypeError) as exc:
            raise BeaconFinalityError("finalized beacon block lacks supported execution payload") from exc
        return BeaconReportedFinalizedExecution(
            self.genesis_root, slot, number, execution_hash, timestamp)


@dataclass(frozen=True)
class FinalityCrossCheck:
    """Trust-qualified result: not cryptographically proven consensus finality."""
    anchored_execution_block: int
    beacon_reported_execution_block: int
    ancestry_depth: int
    execution_rpc_views: int
    beacon_genesis_pinned: bool = True
    consensus_rest_trusted: bool = True
    pos_finality_proven: bool = False
    physical_service_verified: bool = False


def cross_check_reported_finality(anchor: BlockAnchor,
                                  claimed: BeaconReportedFinalizedExecution,
                                  rpc, *, second_rpc=None,
                                  max_ancestry_depth: int = MAX_ANCESTRY_DEPTH
                                  ) -> FinalityCrossCheck:
    """Walk historical execution-block parent links, fail on any disagreement.

    For production, require a separately verified consensus proof and an
    independently operated execution client. This merely checks agreement
    between inputs supplied by configured services, never chain validity.
    """
    if not isinstance(anchor, BlockAnchor) or not isinstance(
            claimed, BeaconReportedFinalizedExecution):
        raise BeaconFinalityError("validated anchor and beacon claim required")
    if type(max_ancestry_depth) is not int or not 0 <= max_ancestry_depth <= 128:
        raise BeaconFinalityError("bounded finality ancestry depth required")
    depth = claimed.execution_block_number - anchor.block_number
    if depth < 0:
        raise BeaconFinalityError("beacon finalized block precedes the anchored evidence")
    if depth > max_ancestry_depth:
        raise BeaconFinalityError("finalized-claim ancestry distance exceeds safety limit")
    if second_rpc is not None and (
            second_rpc is rpc or
            getattr(second_rpc, "url", None) == getattr(rpc, "url", None)):
        raise BeaconFinalityError("second execution view must use a different RPC endpoint")

    for node in ((rpc,) if second_rpc is None else (rpc, second_rpc)):
        try:
            chain_id = _hex_integer(node.request("eth_chainId", []))
        except (ChainReadError, ValueError, OSError) as exc:
            raise BeaconFinalityError("execution RPC chain ID could not be checked") from exc
        if chain_id != anchor.chain_id:
            raise BeaconFinalityError("execution chain ID differs from evidence")
        current_hash = claimed.execution_block_hash
        for step in range(depth + 1):
            hash_a, parent_hash, number, ts = _rpc_header(
                node, "eth_getBlockByHash", [current_hash, False])
            expected_number = claimed.execution_block_number - step
            if hash_a != current_hash or number != expected_number:
                raise BeaconFinalityError("execution header ancestry or block height mismatch")
            height_hash, _, height_number, height_time = _rpc_header(
                node, "eth_getBlockByNumber", [hex(expected_number), False])
            if (height_hash != hash_a or height_number != number or height_time != ts):
                raise BeaconFinalityError("execution block not canonical at numeric height")
            if step == 0 and ts != claimed.execution_timestamp:
                raise BeaconFinalityError("beacon-reported execution timestamp mismatch")
            if step == depth:
                if hash_a != anchor.block_hash or ts != anchor.block_timestamp:
                    raise BeaconFinalityError("evidence block is not ancestor of claimed finality block")
            else:
                current_hash = parent_hash
    return FinalityCrossCheck(anchor.block_number, claimed.execution_block_number,
                              depth, 1 if second_rpc is None else 2)
