"""WP-13 V2 pinned-RPC authority tests.

The RPC here is synthetic and can be adversarial. No Ethereum state-proof,
consumer receipt, or genuine physical-delivery qualification is tested.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "services" / "monitor-agent"))

from sse_challenge import expected_response_hash, keccak256
from sse_chain_read import _function_call
from sse_evidence_wire_v1 import (
    EvidenceScope, ObservationKind, ObservationRecord,
    AuthenticationError, sign_observation,
)
from sse_v2_chain_authority_v1 import (
    V2AuthorityError, V2AuthoritySpec, V2_LEASE_FIELDS, V2_EPOCH_FIELDS,
    V2_ASSIGNMENT_FIELDS, V2_TICKET_FIELDS,
    read_v2_authority, verify_v2_observation, capture_v2_response,
    _v2_domain_separator,
)

CHAIN = 31337
CONTROLLER = "0x" + "aa" * 20
POOL = "0x" + "bb" * 20
CONSUMER = "0x" + "cc" * 20
PROVIDER = "0x" + "dd" * 20
SEATS = ["0x" + f"{100 + i:040x}" for i in range(4)]
SLA = "0x" + "11" * 32
PROFILE = "0x" + "22" * 32
REQUEST = "0x" + "33" * 32
BLOCK = "0x" + "44" * 32
ENDPOINT = "http://127.0.0.1:8899"
CONTROLLER_CODE = "0x6001600055"
POOL_CODE = "0x6002600055"
KEY = "0x" + "07" * 32


def code_hash(code: str) -> str:
    return "0x" + keccak256(bytes.fromhex(code[2:])).hex()


def word(v, kind: str) -> bytes:
    if kind == "address":
        return int(v, 16).to_bytes(32, "big")
    if kind == "bytes32":
        return bytes.fromhex(v[2:])
    return int(v).to_bytes(32, "big")


def encoded(fields, values) -> str:
    return "0x" + b"".join(word(values[name], kind) for name, kind in fields).hex()


def scope(**changes) -> EvidenceScope:
    data = dict(chain_id=CHAIN, settlement=CONTROLLER, lease_id=1, epoch_id=0,
                sla_policy_hash=SLA, resource_profile_hash=PROFILE, request_hash=REQUEST)
    data.update(changes)
    return EvidenceScope(**data)


def spec(**changes) -> V2AuthoritySpec:
    data = dict(scope=scope(), pool=POOL, endpoint=ENDPOINT,
                controller_code_hash=code_hash(CONTROLLER_CODE),
                pool_code_hash=code_hash(POOL_CODE))
    data.update(changes)
    return V2AuthoritySpec(**data)


class FakeV2RPC:
    """Exact EIP-1898 request assertions; deliberately no trust in fake state."""
    def __init__(self):
        self.calls = []
        self.chain_id = CHAIN
        self.block_hash = BLOCK
        self.rechecked_hash = BLOCK
        self.block_number = 50
        self.time = 1100
        self.codes = {CONTROLLER: CONTROLLER_CODE, POOL: POOL_CODE}
        self.reject_pinned = False
        self.bad_response = {}
        self.members = SEATS.copy()
        self.controller_pool = POOL
        self.pool_controller = CONTROLLER
        self.next_lease_id = 2
        self.status = 5
        self.selected_count = 4
        self.confirmed_count = 4
        self.service_deadline = 2000
        self.assignment = {
            "size": 4, "quorum": 3, "reserves": 2,
            "consumer": CONSUMER, "provider": PROVIDER,
        }
        self.lease = {
            "consumer": CONSUMER, "provider": PROVIDER,
            "endpointHash": "0x" + keccak256(ENDPOINT.encode()).hex(),
            "profileHash": PROFILE, "slaPolicyHash": SLA,
            "assignmentId": 7, "escrow": 300, "fee": 100,
            "maxEpochs": 3, "exposureBudget": 100, "nextEpochId": 1,
            "pending": 100, "uncommitted": 200,
            "consumerCredited": 0, "providerCredited": 0,
            "unusedRefunded": 0, "epochWindow": 100,
            "acceptanceDeadline": 1010, "state": 2,
        }
        self.epoch = {
            "requestHash": REQUEST, "fee": 100, "deadline": 1500,
            "providerShare": 0, "consumerShare": 0,
            "nonce": 0, "admitted": True, "allocated": False,
        }
        self.tickets = {
            seat: dict(joined=True, paid=True, everSelected=True,
                       confirmed=True, noShow=False)
            for seat in self.members
        }

    def request(self, method, params):
        self.calls.append((method, params))
        if method == "eth_chainId":
            return hex(self.chain_id)
        if method == "eth_getBlockByNumber":
            tag = params[0]
            if tag in ("finalized", "latest", "safe"):
                return {"number": hex(self.block_number), "hash": self.block_hash,
                        "timestamp": hex(self.time)}
            return {"number": hex(self.block_number), "hash": self.rechecked_hash,
                    "timestamp": hex(self.time)}
        if method not in ("eth_getCode", "eth_call"):
            raise AssertionError("unrecognized RPC call " + method)
        if self.reject_pinned:
            raise ValueError("EIP-1898 unsupported")
        pinned = params[-1]
        if pinned != {"blockHash": self.block_hash, "requireCanonical": True}:
            raise AssertionError("un-pinned or wrong-hash RPC read")
        if method == "eth_getCode":
            return self.codes[params[0]]
        call = params[0]
        target = call["to"]
        data = call["data"]
        selector = data[:10]
        args = [int(data[i:i+64], 16) for i in range(10, len(data), 64)]
        if selector in self.bad_response:
            return self.bad_response[selector]
        def matches(signature):
            return selector == _function_call(signature)[:10]
        def uint(v):
            return "0x" + word(v, "uint256").hex()
        def addr(v):
            return "0x" + word(v, "address").hex()
        if target == CONTROLLER:
            if matches("domainSeparator()"):
                return _v2_domain_separator(CHAIN, CONTROLLER)
            if matches("pool()"):
                return addr(self.controller_pool)
            if matches("nextLeaseId()"):
                return uint(self.next_lease_id)
            if matches("getLease(uint256)"):
                if args != [1]:
                    raise AssertionError("unrecognized lease ID")
                return encoded(V2_LEASE_FIELDS, self.lease)
            if matches("getEpoch(uint256,uint256)"):
                if args != [1, 0]:
                    raise AssertionError("unrecognized epoch ID")
                return encoded(V2_EPOCH_FIELDS, self.epoch)
        if target == POOL:
            if matches("controller()"):
                return addr(self.pool_controller)
            if matches("status(uint256)"):
                return uint(self.status)
            if matches("assignmentTerms(uint256)"):
                return encoded(V2_ASSIGNMENT_FIELDS, self.assignment)
            if matches("selectedCount(uint256)"):
                return uint(self.selected_count)
            if matches("confirmedCount(uint256)"):
                return uint(self.confirmed_count)
            if matches("serviceDeadline(uint256)"):
                return uint(self.service_deadline)
            if matches("seatAt(uint256,uint256)"):
                return addr(self.members[args[1]])
            if matches("tickets(uint256,address)"):
                member = "0x" + f"{args[1]:040x}"
                return encoded(V2_TICKET_FIELDS, self.tickets[member])
        raise AssertionError("unexpected contract method " + data)


class V2AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.rpc = FakeV2RPC()
        self.config = spec()

    def rejects(self):
        with self.assertRaises(V2AuthorityError):
            read_v2_authority(self.rpc, self.config)

    def test_full_snapshot_uses_v2_abi_and_commitments(self):
        snap = read_v2_authority(self.rpc, self.config)
        self.assertEqual(snap.provider, PROVIDER)
        self.assertEqual(snap.consumer, CONSUMER)
        self.assertEqual(snap.assignment_id, 7)
        self.assertEqual(snap.monitors, tuple(SEATS))
        self.assertEqual(snap.quorum, 3)
        self.assertEqual(snap.reserves, 2)
        self.assertEqual(snap.scope.request_hash, REQUEST)
        self.assertEqual(snap.block_hash, BLOCK)
        self.assertRegex(snap.commitment(), r"^0x[0-9a-f]{64}$")
        self.assertEqual(len(snap.context().authorized_monitors), 4)
        self.assertEqual(snap.fields()["notice"],
                         "RPC_ASSUMPTION_BOUND_RAW_OBSERVATION_NOT_CONSUMER_DELIVERY")

    def test_all_contract_calls_and_code_reads_are_pinned(self):
        read_v2_authority(self.rpc, self.config)
        calls = [(m, a) for m, a in self.rpc.calls if m in ("eth_call", "eth_getCode")]
        self.assertGreater(len(calls), 18)
        self.assertTrue(all(args[-1] == {
            "blockHash": BLOCK, "requireCanonical": True} for _, args in calls))

    def test_wrong_chain_id_rejected(self):
        self.rpc.chain_id = 1
        self.rejects()

    def test_wrong_controller_code_fingerprint_rejected(self):
        self.rpc.codes[CONTROLLER] = "0x6003"
        self.rejects()

    def test_wrong_pool_code_fingerprint_rejected(self):
        self.rpc.codes[POOL] = "0x6004"
        self.rejects()

    def test_contract_code_missing_rejected(self):
        self.rpc.codes[POOL] = "0x"
        self.rejects()

    def test_expected_code_fingerprints_required(self):
        with self.assertRaises(V2AuthorityError):
            spec(pool_code_hash="0x" + "00"*32)

    def test_v1_controller_domain_rejected(self):
        from sse_chain_read import _domain_separator
        self.rpc.bad_response[_function_call("domainSeparator()")[:10]] = _domain_separator(CHAIN, CONTROLLER)
        self.rejects()

    def test_wrong_pool_binding_rejected_both_directions(self):
        self.rpc.controller_pool = "0x" + "ab"*20
        self.rejects()
        self.rpc.controller_pool = POOL
        self.rpc.pool_controller = "0x" + "ab"*20
        self.rejects()

    def test_missing_lease_rejected(self):
        self.rpc.next_lease_id = 1
        self.rejects()

    def test_leases_without_live_state_rejected(self):
        for state in (0, 1, 3, 4, 5):
            with self.subTest(state=state):
                self.rpc.lease["state"] = state
                self.rejects()

    def test_provider_cannot_equal_consumer(self):
        self.rpc.lease["provider"] = CONSUMER
        self.rejects()

    def test_sla_and_profile_mismatches_rejected(self):
        for key in ("profileHash", "slaPolicyHash"):
            with self.subTest(key=key):
                old = self.rpc.lease[key]
                self.rpc.lease[key] = "0x" + "55"*32
                self.rejects()
                self.rpc.lease[key] = old

    def test_endpoint_hash_mismatch_rejected(self):
        self.rpc.lease["endpointHash"] = "0x" + "ee"*32
        self.rejects()

    def test_nonloopback_endpoints_rejected_before_rpc(self):
        with self.assertRaises(V2AuthorityError):
            spec(endpoint="https://example.com/")
        with self.assertRaises(V2AuthorityError):
            spec(endpoint="http://127.0.0.1:8899/secret")

    def test_arbitrary_lease_balance_breaks_conservation(self):
        self.rpc.lease["uncommitted"] += 1
        self.rejects()

    def test_overexposure_rejected(self):
        self.rpc.lease["pending"] = 101
        self.rejects()

    def test_wrong_or_nonactive_pool_status_rejected(self):
        self.rpc.status = 4  # Confirming, not Active
        self.rejects()
        self.rpc.status = 6  # Aborted
        self.rejects()

    def test_assignment_parties_must_match_lease(self):
        self.rpc.assignment["provider"] = CONSUMER
        self.rejects()

    def test_invalid_quorum_or_committee_bound_rejected(self):
        self.rpc.assignment["quorum"] = 2
        self.rejects()
        self.rpc.assignment["quorum"] = 3
        self.rpc.assignment["size"] = 17
        self.rejects()

    def test_not_all_monitors_confirmed_rejected(self):
        self.rpc.confirmed_count = 3
        self.rejects()

    def test_duplicate_seat_and_interested_party_rejected(self):
        self.rpc.members[3] = self.rpc.members[0]
        self.rejects()
        self.rpc.members[3] = PROVIDER
        self.rejects()

    def test_ticket_not_confirmed_or_paid_rejected(self):
        for field in ("joined", "paid", "everSelected", "confirmed"):
            with self.subTest(field=field):
                self.rpc.tickets[SEATS[0]][field] = False
                self.rejects()
                self.rpc.tickets[SEATS[0]][field] = True
        self.rpc.tickets[SEATS[0]]["noShow"] = True
        self.rejects()

    def test_noncanonical_abi_bool_rejected(self):
        selector = _function_call("tickets(uint256,address)")[:10]
        values = dict(self.rpc.tickets[SEATS[0]])
        values["confirmed"] = 2
        self.rpc.bad_response[selector] = encoded(V2_TICKET_FIELDS, values)
        self.rejects()

    def test_epoch_not_admitted_rejected(self):
        self.rpc.epoch["admitted"] = False
        self.rejects()

    def test_epoch_already_allocated_rejected(self):
        self.rpc.epoch["allocated"] = True
        self.rejects()

    def test_wrong_request_commitment_rejected(self):
        self.rpc.epoch["requestHash"] = "0x" + "aa"*32
        self.rejects()

    def test_wrong_epoch_fee_or_pending_balance_rejected(self):
        self.rpc.epoch["fee"] = 101
        self.rejects()
        self.rpc.epoch["fee"] = 100
        self.rpc.lease["pending"] = 99
        self.rpc.lease["uncommitted"] = 201
        self.rejects()

    def test_epoch_and_service_deadlines_rejected(self):
        self.rpc.time = 1501
        self.rejects()
        self.rpc.time = 1100
        self.rpc.epoch["deadline"] = 2001
        self.rejects()
        self.rpc.epoch["deadline"] = 1500
        self.rpc.service_deadline = 1099
        self.rejects()

    def test_reorg_between_read_and_return_rejected(self):
        self.rpc.rechecked_hash = "0x" + "77"*32
        self.rejects()

    def test_unsupported_blockhash_pinning_never_falls_back(self):
        self.rpc.reject_pinned = True
        self.rejects()
        self.assertFalse(any(
            m == "eth_call" and p[-1] == "latest" for m, p in self.rpc.calls))

    def test_safe_latest_require_opt_in(self):
        for tag in ("safe", "latest"):
            with self.subTest(tag=tag):
                with self.assertRaises(V2AuthorityError):
                    spec(block_tag=tag)
                snap = read_v2_authority(
                    self.rpc, spec(block_tag=tag, allow_unfinalized=True))
                self.assertEqual(snap.requested_tag, tag)

    def test_read_only_never_submits_transaction(self):
        read_v2_authority(self.rpc, self.config)
        self.assertFalse(any(m.startswith("eth_send") for m, _ in self.rpc.calls))

    def test_capture_wrapper_passes_derived_identities_and_endpoint(self):
        from typed_evidence import Domain
        with patch("sse_http_signed_delivery_v1.capture_response",
                   return_value="persisted-raw-response") as capture:
            snap, result = capture_v2_response(
                self.rpc, self.config, KEY, object(), nonce="0x" + "aa"*32)
            self.assertEqual(result, "persisted-raw-response")
            args = capture.call_args.args
            self.assertEqual(args[0], ENDPOINT)
            self.assertIsInstance(args[1], Domain)
            self.assertEqual(args[2], PROVIDER)
            self.assertEqual(args[3], snap.scope)
            self.assertEqual(args[5].authorized_monitors, frozenset(SEATS))
            self.assertEqual(args[1].contract.lower(), CONTROLLER)
            self.assertEqual(capture.call_args.kwargs["nonce"], "0x" + "aa"*32)


try:
    from eth_account import Account
    ETH_AVAILABLE = True
except ImportError:
    ETH_AVAILABLE = False


@unittest.skipUnless(ETH_AVAILABLE, "eth-account required for EIP-712 test")
class V2SignedObservationTests(unittest.TestCase):
    def test_selected_signature_authenticates_not_a_physical_fact(self):
        rpc = FakeV2RPC()
        monitor_address = Account.from_key(KEY).address.lower()
        rpc.members[0] = monitor_address
        rpc.tickets[monitor_address] = dict(
            joined=True, paid=True, everSelected=True, confirmed=True, noShow=False)
        rec = ObservationRecord(
            scope(), ObservationKind.RESPONSE_SEEN,
            expected_response_hash(REQUEST), "0x" + "ee"*32,
            1100, 1200, "0x" + "99"*32,
        )
        envelope = sign_observation(rec, KEY)
        snap, verified = verify_v2_observation(rpc, spec(), envelope)
        self.assertEqual(verified.signer, monitor_address)
        self.assertEqual(verified.record.scope, snap.scope)
        self.assertNotIn("QualifiedFact", str(type(verified)))
        rpc.members[0] = SEATS[0]
        with self.assertRaises(AuthenticationError):
            verify_v2_observation(rpc, spec(), envelope)


if __name__ == "__main__":
    unittest.main()
