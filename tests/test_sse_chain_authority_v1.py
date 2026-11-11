"""WP-08C adversarial tests for a pinned, explicitly trusted RPC chain view."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "monitor-agent"))

from sse_challenge import keccak256, expected_response_hash
from sse_chain_read import ChainReadError, _function_call, _domain_separator, LEASE_FIELDS, EPOCH_FIELDS
from sse_chain_authority_v1 import (
    AuthoritySpec, ChainAuthorityError, read_chain_authority,
    verify_against_chain, capture_with_chain_authority,
)
from sse_evidence_wire_v1 import (
    EvidenceScope, ObservationRecord, ObservationKind, AuthenticationError,
    sign_observation, ZERO_HASH,
)

CHAIN_ID = 31337
SETTLEMENT = "0x" + "a1" * 20
POOL = "0x" + "b2" * 20
PROVIDER = "0x" + "c3" * 20
CONSUMER = "0x" + "d4" * 20
MONITORS = tuple("0x" + f"{i:040x}" for i in range(100, 104))
SLA = "0x" + "11" * 32
RESOURCE = "0x" + "22" * 32
REQUEST = "0x" + "33" * 32
BLOCK_HASH = "0x" + "44" * 32
SETTLEMENT_CODE = "0x600160005560046000"
POOL_CODE = "0x600260005560076000"
KEY = "0x" + "07" * 32


def keccak_code(code: str) -> str:
    return "0x" + keccak256(bytes.fromhex(code[2:])).hex()


def scope(**change):
    kw = dict(chain_id=CHAIN_ID, settlement=SETTLEMENT, lease_id=2, epoch_id=1,
              sla_policy_hash=SLA, resource_profile_hash=RESOURCE, request_hash=REQUEST)
    kw.update(change)
    return EvidenceScope(**kw)


def authority(**change):
    data = dict(scope=scope(), committee_contract=POOL,
                settlement_code_hash=keccak_code(SETTLEMENT_CODE),
                committee_code_hash=keccak_code(POOL_CODE))
    data.update(change)
    return AuthoritySpec(**data)


def encode_word(value, kind):
    if kind == "address":
        return int(value, 16).to_bytes(32, "big")
    if kind == "bytes32":
        return bytes.fromhex(value[2:])
    if kind == "bool":
        return int(value).to_bytes(32, "big")
    return int(value).to_bytes(32, "big")


def encode_struct(fields, values) -> str:
    result = []
    for name, kind in fields:
        if kind == "address[4]":
            result.extend(encode_word(addr, "address") for addr in values[name])
        else:
            result.append(encode_word(values[name], kind))
    return "0x" + b"".join(result).hex()


class FakePinnedRPC:
    """Fully controlled RPC responses. Tests protocol encoding, NOT real-chain trust."""
    def __init__(self):
        self.calls = []
        self.chain_id = CHAIN_ID
        self.block_hash = BLOCK_HASH
        self.after_hash = BLOCK_HASH
        self.timestamp = 1150
        self.number = 99
        self.code = {SETTLEMENT: SETTLEMENT_CODE, POOL: POOL_CODE}
        self.pool = POOL
        self.reverse = SETTLEMENT
        self.next_lease = 4
        self.assignment_status = 2
        self.roster = MONITORS
        self.reject_pinned = False
        self.lease = {
            "consumer": CONSUMER, "provider": PROVIDER, "monitors": MONITORS,
            "assignmentId": 5,
            "serviceEndpointHash": "0x" + "aa" * 32,
            "resourceProfileHash": RESOURCE, "slaPolicyHash": SLA,
            "marketplaceRequestId": 7, "totalEscrow": 75,
            "uncommittedEscrow": 50, "refundedUnusedEscrow": 0,
            "epochFee": 25, "reservationFee": 0, "exposureBudget": 25,
            "currentExposure": 25, "nextEpochId": 2, "maxEpochs": 3,
            "responsePeriod": 30, "monitoringGrace": 60,
            "evidenceWindow": 60, "monitorConfirmations": 4, "state": 3,
        }
        self.epoch = {
            "requestHash": REQUEST, "responseHash": expected_response_hash(REQUEST),
            "fee": 25, "reservationFee": 0, "responseDeadline": 1100,
            "monitoringClose": 1200, "evidenceClose": 1300,
            "providerCredited": 0, "consumerCredited": 0,
            "unresolvedExposure": 25, "successVotes": 0, "failureVotes": 0,
            "exists": True, "acknowledged": False, "responseAuthenticated": False,
            "monitoringSealed": False, "evidenceClosed": False, "outcome": 0,
        }
        self._by_selector = {
            _function_call("domainSeparator()"): lambda: _domain_separator(CHAIN_ID, SETTLEMENT),
            _function_call("committeePool()"): lambda: "0x" + encode_word(self.pool, "address").hex(),
            _function_call("settlement()"): lambda: "0x" + encode_word(self.reverse, "address").hex(),
            _function_call("nextLeaseId()"): lambda: "0x" + encode_word(self.next_lease, "uint256").hex(),
            _function_call("getLease(uint256)", (2,)): lambda: encode_struct(LEASE_FIELDS, self.lease),
            _function_call("getEpoch(uint256,uint256)", (2, 1)): lambda: encode_struct(EPOCH_FIELDS, self.epoch),
            _function_call("assignmentStatus(uint256)", (5,)): lambda: "0x" + encode_word(self.assignment_status, "uint256").hex(),
            _function_call("getCommittee(uint256)", (5,)): lambda: "0x" + b"".join(encode_word(v, "address") for v in self.roster).hex(),
        }
        self.returned_once = False

    def request(self, method, params):
        self.calls.append((method, params))
        if method == "eth_chainId":
            return hex(self.chain_id)
        if method == "eth_getBlockByNumber":
            tag = params[0]
            if tag == "finalized" or tag == "safe" or tag == "latest":
                return {"number": hex(self.number), "hash": self.block_hash,
                        "timestamp": hex(self.timestamp)}
            return {"number": hex(self.number), "hash": self.after_hash,
                    "timestamp": hex(self.timestamp)}
        if method in ("eth_getCode", "eth_call"):
            if self.reject_pinned:
                raise ValueError("unsupported EIP-1898 blockHash tag")
            block_ref = params[-1]
            if not isinstance(block_ref, dict) or block_ref != {
                    "blockHash": self.block_hash, "requireCanonical": True}:
                raise AssertionError("unbound RPC query")
            if method == "eth_getCode":
                return self.code[params[0]]
            selector = params[0]["data"]
            if selector not in self._by_selector:
                raise AssertionError("unexpected contract method " + selector)
            return self._by_selector[selector]()
        raise AssertionError("unexpected RPC " + method)


class ChainAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.rpc = FakePinnedRPC()
        self.spec = authority()

    def test_valid_snapshot_matches_two_contracts_and_epoch(self):
        snap = read_chain_authority(self.rpc, self.spec)
        self.assertEqual(snap.provider, PROVIDER)
        self.assertEqual(snap.consumer, CONSUMER)
        self.assertEqual(snap.monitors, MONITORS)
        self.assertEqual(snap.block_hash, BLOCK_HASH)
        self.assertEqual(snap.assignment_id, 5)
        self.assertEqual(snap.verification_context().authorized_monitors, frozenset(MONITORS))
        self.assertIn('"blockHash":', snap.canonical_bytes().decode())
        self.assertRegex(snap.commitment(), r"^0x[0-9a-f]{64}$")
        self.assertIn("RPC responses are not independently authenticated", snap.fields()["limitations"][0])

    def test_every_state_call_pinned_to_same_exact_block_hash(self):
        read_chain_authority(self.rpc, self.spec)
        pinned = [p[-1] for m, p in self.rpc.calls if m in ("eth_call", "eth_getCode")]
        self.assertGreater(len(pinned), 8)
        self.assertEqual(pinned, [{"blockHash": BLOCK_HASH, "requireCanonical": True}] * len(pinned))

    def test_wrong_chain_id_rejected(self):
        self.rpc.chain_id = 1
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_wrong_settlement_runtime_fingerprint_rejected(self):
        self.rpc.code[SETTLEMENT] = "0x6000"
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_wrong_committee_runtime_fingerprint_rejected(self):
        self.rpc.code[POOL] = "0x6000"
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_expected_fingerprint_is_required(self):
        with self.assertRaises(ChainAuthorityError):
            authority(settlement_code_hash=ZERO_HASH)

    def test_zero_code_rejected(self):
        self.rpc.code[POOL] = "0x"
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_untrusted_caller_cannot_change_committee_address(self):
        self.rpc.pool = "0x" + "56"*20
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_reverse_pool_to_settlement_binding_is_required(self):
        self.rpc.reverse = "0x" + "56"*20
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_nonexistent_lease_rejected(self):
        self.rpc.next_lease = 2
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_offered_accepted_and_closed_lease_cannot_authorize_new_report(self):
        for state in (0, 1, 4):
            with self.subTest(state=state):
                self.rpc.lease["state"] = state
                with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_missing_one_monitor_confirmation_rejected(self):
        self.rpc.lease["monitorConfirmations"] = 3
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_duplicate_committee_identity_rejected(self):
        self.rpc.lease["monitors"] = (MONITORS[0],) * 4
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_provider_cannot_be_monitor(self):
        self.rpc.lease["monitors"] = (PROVIDER, *MONITORS[:3])
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_wrong_assignment_status_rejected(self):
        self.rpc.assignment_status = 4
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_committee_roster_must_match_settlement(self):
        self.rpc.roster = tuple(reversed(MONITORS))
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_scope_sla_and_resource_bindings_required(self):
        for field in ("slaPolicyHash", "resourceProfileHash"):
            with self.subTest(field=field):
                self.rpc.lease[field] = "0x" + "fa"*32
                with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)
                self.rpc.lease[field] = SLA if field == "slaPolicyHash" else RESOURCE

    def test_missing_epoch_rejected(self):
        self.rpc.epoch["exists"] = False
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_future_epoch_rejected(self):
        self.rpc.lease["nextEpochId"] = 1
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_wrong_request_commitment_rejected(self):
        self.rpc.epoch["requestHash"] = "0x" + "67"*32
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_wrong_expected_response_rejected(self):
        self.rpc.epoch["responseHash"] = "0x" + "67"*32
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_closed_monitoring_or_evidence_rejected(self):
        self.rpc.epoch["monitoringSealed"] = True
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)
        self.rpc.epoch["monitoringSealed"] = False
        self.rpc.epoch["evidenceClosed"] = True
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_monitoring_clock_closed_rejected(self):
        self.rpc.timestamp = 1201
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_reorg_between_anchor_and_return_rejected(self):
        self.rpc.after_hash = "0x" + "77"*32
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)

    def test_eip1898_unsupported_must_not_fallback_to_latest(self):
        self.rpc.reject_pinned = True
        with self.assertRaises(ChainAuthorityError): read_chain_authority(self.rpc, self.spec)
        self.assertFalse(any(m == "eth_call" and p[1] == "latest" for m,p in self.rpc.calls))

    def test_nonfinalized_requires_explicit_optin(self):
        for tag in ("latest", "safe"):
            with self.subTest(tag=tag):
                with self.assertRaises(ChainAuthorityError): authority(block_tag=tag)
                snap = read_chain_authority(self.rpc, authority(block_tag=tag, allow_unfinalized=True))
                self.assertEqual(snap.requested_tag, tag)

    def test_invalid_inputs_fail_closed(self):
        with self.assertRaises(ChainAuthorityError): authority(block_tag="pending")
        with self.assertRaises(ChainAuthorityError): authority(committee_contract="0x" + "00"*20)
        with self.assertRaises(ChainAuthorityError): authority(allow_unfinalized="yes")
        with self.assertRaises(ChainAuthorityError): read_chain_authority(None, self.spec)

    def test_noncanonical_abi_bool_rejected(self):
        self.rpc.epoch["exists"] = 2
        with self.assertRaises(ChainReadError): read_chain_authority(self.rpc, self.spec)

    def test_chain_read_does_not_send_any_transaction(self):
        read_chain_authority(self.rpc, self.spec)
        self.assertNotIn("eth_sendRawTransaction", [m for m,_ in self.rpc.calls])
        self.assertNotIn("eth_sendTransaction", [m for m,_ in self.rpc.calls])

    def test_chain_capture_wires_derived_provider_and_roster(self):
        with patch("sse_http_signed_delivery_v1.capture_response", return_value="captured") as fn:
            snap, saved = capture_with_chain_authority(
                self.rpc, self.spec, "http://127.0.0.1:8878", KEY, object(), nonce="0x"+"88"*32)
            self.assertEqual(saved, "captured")
            args = fn.call_args.args
            self.assertEqual(args[2], PROVIDER)
            self.assertEqual(args[5].authorized_monitors, frozenset(MONITORS))
            self.assertEqual(snap.scope, self.spec.scope)


try:
    from eth_account import Account
    HAS_ETH = True
except ImportError:
    HAS_ETH = False


@unittest.skipUnless(HAS_ETH, "Ethereum packages required for EIP-712 test")
class SignedAuthorityTests(unittest.TestCase):
    def test_authorized_monitor_signature_is_accepted_and_outsider_rejected(self):
        rpc = FakePinnedRPC()
        monitor_key = KEY
        monitor = Account.from_key(monitor_key).address.lower()
        rpc.lease["monitors"] = (monitor, *MONITORS[1:])
        rpc.roster = rpc.lease["monitors"]
        rec = ObservationRecord(
            scope(), ObservationKind.RESPONSE_SEEN, expected_response_hash(REQUEST),
            "0x"+"bb"*32, 1100, 1150, "0x"+"cc"*32)
        good = sign_observation(rec, monitor_key)
        snap, verified = verify_against_chain(rpc, authority(), good)
        self.assertEqual(verified.signer, monitor)
        self.assertEqual(snap.block_hash, BLOCK_HASH)
        rpc.lease["monitors"] = MONITORS
        rpc.roster = MONITORS
        with self.assertRaises(AuthenticationError):
            verify_against_chain(rpc, authority(), good)


if __name__ == "__main__":
    unittest.main()
