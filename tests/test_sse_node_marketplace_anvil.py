"""R5 opt-in REAL Anvil integration of node-owned signed marketplace transactions.

This is not a multi-VM test. It uses Anvil's famous PUBLIC TEST MNEMONIC,
temporary loopback-only RPC, actual Foundry bytecode, actual EVM transaction
receipts and independently signed local EOA transactions for each participant.

Run only on a development machine after \`forge build\`:
  SSE_RUN_ANVIL_INTEGRATION=1 python -m unittest discover \
    -s tests -p 'test_sse_node_marketplace_anvil.py' -v

This integration test is intentionally skipped in regular offline test suites.
It never connects to Sepolia or a remote chain, publishes a port, sends real
value, or leaves an Anvil process running after the test.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sse_challenge import keccak256
from sse_node_marketplace import RPC, execute, make_plan

CHAIN = 31337
MNEMONIC = "test test test test test test test test test test test junk"
ARTIFACTS = tuple(ROOT / "out" / (name + ".sol") / (name + ".json")
                  for name in ("OpenMonitorCommittee", "SSESettlement", "OpenResourceBoard"))
ENABLE = os.environ.get("SSE_RUN_ANVIL_INTEGRATION") == "1"
AVAILABLE = shutil.which("anvil") is not None and all(f.is_file() for f in ARTIFACTS)


def _word(v):
    if type(v) is int and 0 <= v < 2**256:
        return v.to_bytes(32, "big")
    if type(v) is str and v.startswith("0x"):
        data = bytes.fromhex(v[2:])
        if len(data) in (20, 32):
            return data.rjust(32, b"\x00")
    raise AssertionError("bad static test ABI input")


def _data(signature, *args):
    return "0x" + (keccak256(signature.encode("ascii"))[:4] +
                   b"".join(_word(x) for x in args)).hex()


def _unlocked(rpc, sender, target, calldata, value=0):
    tx = {"from": sender, "data": calldata, "gas": hex(9_000_000)}
    if target is not None:
        tx["to"] = target
    if value:
        tx["value"] = hex(value)
    txhash = rpc.request("eth_sendTransaction", [tx])
    if type(txhash) is not str or len(txhash) != 66:
        raise AssertionError("Anvil did not return a transaction hash")
    for _ in range(60):
        r = rpc.request("eth_getTransactionReceipt", [txhash])
        if r is not None:
            if r.get("status") != "0x1":
                raise AssertionError("Anvil setup transaction reverted")
            return r
        time.sleep(.1)
    raise AssertionError("Anvil setup transaction receipt timed out")


def _deploy(rpc, owner, name, *args):
    artifact = ROOT / "out" / (name + ".sol") / (name + ".json")
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    bytecode = payload["bytecode"]["object"]
    if not isinstance(bytecode, str) or not bytecode.startswith("0x"):
        raise AssertionError("Foundry build bytecode missing")
    receipt = _unlocked(rpc, owner, None, bytecode + "".join(_word(x).hex() for x in args))
    contract = receipt.get("contractAddress")
    if type(contract) is not str or len(contract) != 42:
        raise AssertionError("Anvil contract deployment returned no address")
    return contract.lower()


def _address_words(result):
    if type(result) is not str or not result.startswith("0x") or len(result) != 2 + 4 * 64:
        raise AssertionError("bad committee ABI response")
    return ["0x" + result[2+i*64:2+(i+1)*64][-40:].lower() for i in range(4)]


def _loopback_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@unittest.skipUnless(ENABLE, "explicit Anvil integration opt-in required")
@unittest.skipUnless(AVAILABLE, "Anvil binary and Foundry artifacts required")
class RealAnvilNodeMarketplace(unittest.TestCase):
    def test_individual_signers_execute_marketplace_and_open_epoch(self):
        from eth_account import Account
        Account.enable_unaudited_hdwallet_features()
        port = _loopback_port()
        proc = subprocess.Popen(
            ["anvil", "--silent", "--host", "127.0.0.1", "--port", str(port),
             "--chain-id", str(CHAIN), "--accounts", "10", "--mnemonic", MNEMONIC],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            rpc = RPC("http://127.0.0.1:" + str(port))
            for _ in range(100):
                if proc.poll() is not None:
                    self.fail("temporary Anvil exited early")
                try:
                    if int(rpc.request("eth_chainId", []), 16) == CHAIN:
                        break
                except (OSError, ValueError):
                    pass
                time.sleep(.1)
            else:
                self.fail("temporary Anvil did not become available")
            owners = [
                Account.from_mnemonic(MNEMONIC, account_path=f"m/44'/60'/0'/0/{i}")
                for i in range(8)
            ]
            unlocked = [x.lower() for x in rpc.request("eth_accounts", [])]
            self.assertEqual([w.address.lower() for w in owners], unlocked[:8])
            consumer, provider = owners[:2]
            monitors = owners[2:7]
            min_bond = 10**9

            pool = _deploy(rpc, consumer.address, "OpenMonitorCommittee",
                           consumer.address, min_bond, 86400, 3600)
            settlement = _deploy(rpc, consumer.address, "SSESettlement", pool)
            board = _deploy(rpc, consumer.address, "OpenResourceBoard")
            contracts = {"chain_id": CHAIN, "board": board,
                         "settlement": settlement, "pool": pool}
            for to, call in (
                (pool, _data("bindSettlement(address)", settlement)),
                (settlement, _data("bindResourceBoard(address)", board)),
                (board, _data("bindSettlement(address)", settlement)),
            ):
                _unlocked(rpc, consumer.address, to, call)

            recorded = []
            def role_tx(action, role, params, wallet):
                plan = make_plan(action, role, params=params, **contracts)
                result = execute(rpc, plan, wallet,
                                 max_total_wei=10**18,
                                 selected_bid_fee=params.get("selectedEpochFeeWei"))
                self.assertEqual(result["status"], "MINED_UNFINALIZED", result)
                self.assertEqual(result["role"], role)
                self.assertEqual(result["action"], action)
                self.assertFalse(result["evidenceQualified"])
                recorded.append(result["transactionHash"])
                return result

            # Five distinct signed monitor candidates. Four will be selected.
            for wallet in monitors:
                role_tx("monitor-register", "monitor", {"bondWei": min_bond}, wallet)
            candidate_count = rpc.request("eth_call", [
                {"to": pool, "data": _data("candidateCount()")}, "latest"])
            self.assertEqual(int(candidate_count, 16), 5)

            ts = int(rpc.request("eth_getBlockByNumber", ["latest", False])["timestamp"], 16)
            profile = "0x" + keccak256(b"node-marketplace-actual-anvil-profile").hex()
            policy = "0x" + keccak256(b"node-marketplace-actual-anvil-sla").hex()
            endpoint = "0x" + keccak256(b"http://provider-vm.internal:8080").hex()
            req = "0x" + keccak256(b"anvil-challenge-epoch-0").hex()
            close = ts + 60
            role_tx("request", "consumer", {
                "profileHash": profile, "policyHash": policy,
                "maxEpochFeeWei": 40, "biddingClose": close,
            }, consumer)
            role_tx("bid", "provider", {"requestId": 1, "epochFeeWei": 25}, provider)
            bids = rpc.request("eth_call", [
                {"to": board, "data": _data("bidCount(uint256)", 1)}, "latest"])
            self.assertEqual(int(bids, 16), 1)
            latest = int(rpc.request("eth_getBlockByNumber", ["latest", False])["timestamp"], 16)
            rpc.request("evm_increaseTime", [max(0, close - latest + 1)])
            rpc.request("evm_mine", [])

            role_tx("fund", "consumer", {
                "requestId": 1, "bidIndex": 0, "selectedEpochFeeWei": 25,
                "endpointHash": endpoint, "reservationFeeWei": 5,
                "exposureBudgetWei": 25, "maxEpochs": 1,
                "responsePeriodSeconds": 600, "monitorGraceSeconds": 300,
                "evidenceWindowSeconds": 300,
            }, consumer)
            lease_count = rpc.request("eth_call", [
                {"to": settlement, "data": _data("nextLeaseId()")}, "latest"])
            self.assertEqual(int(lease_count, 16), 2)
            from sse_chain_read import inspect_chain
            lease = inspect_chain(rpc, settlement, 1, 0, expected_chain_id=CHAIN)["lease"]
            self.assertEqual(lease["totalEscrow"], 25)
            self.assertEqual(lease["epochFee"], 25)
            self.assertEqual(lease["marketplaceRequestId"], 1)
            self.assertEqual(lease["provider"], provider.address.lower())
            self.assertEqual(lease["consumer"], consumer.address.lower())

            role_tx("accept", "provider", {"leaseId": 1}, provider)
            # Legacy source-controlled entropy is explicitly LAB ONLY.
            # It is not unbiased VRF and is not a production security claim.
            assignment_id = lease["assignmentId"]
            _unlocked(rpc, consumer.address, pool,
                      _data("fulfillRandomness(uint256,uint256)", assignment_id, 123456))
            _unlocked(rpc, consumer.address, settlement,
                      _data("finalizeMonitorCommittee(uint256)", 1))
            committee_result = rpc.request("eth_call", [
                {"to": pool, "data": _data("getCommittee(uint256)", assignment_id)}, "latest"])
            selected = _address_words(committee_result)
            self.assertEqual(len(set(selected)), 4)
            by_address = {a.address.lower(): a for a in monitors}
            self.assertTrue(set(selected).issubset(by_address))
            for member in selected:
                role_tx("monitor-confirm", "monitor", {"leaseId": 1},
                        by_address[member])
            ready = inspect_chain(rpc, settlement, 1, 0, expected_chain_id=CHAIN)["lease"]
            self.assertEqual(ready["stateName"], "Ready")
            self.assertEqual(ready["monitorConfirmations"], 4)

            role_tx("admit-epoch", "consumer",
                    {"leaseId": 1, "requestHash": req}, consumer)
            after = inspect_chain(rpc, settlement, 1, 0, expected_chain_id=CHAIN)
            self.assertEqual(after["lease"]["stateName"], "Active")
            self.assertEqual(after["lease"]["nextEpochId"], 1)
            self.assertTrue(after["epoch"]["exists"])
            self.assertEqual(after["epoch"]["requestHash"], req)
            # Simulate FAILURE without pretending this is real off-chain
            # qualification: no provider acknowledgment or response is sent.
            # Each selected monitor submits a distinct on-chain signed vote.
            from sse_chain_read import inspect_chain
            epoch = after["epoch"]
            observed_time = int(rpc.request("eth_getBlockByNumber", [
                "latest", False])["timestamp"], 16)
            rpc.request("evm_increaseTime", [
                max(0, epoch["responseDeadline"] - observed_time + 1)])
            rpc.request("evm_mine", [])
            for i, member in enumerate(selected[:3]):
                evidence = "0x" + keccak256(
                    ("LAB_ONLY_MONITOR_FAILURE_" + str(i)).encode("ascii")).hex()
                role_tx("monitor-vote", "monitor", {
                    "leaseId": 1, "epochId": 0, "outcome": 2,
                    "evidenceHash": evidence,
                }, by_address[member])
            voted_state = inspect_chain(rpc, settlement, 1, 0,
                                        expected_chain_id=CHAIN)
            self.assertEqual(voted_state["epoch"]["failureVotes"], 3)
            self.assertEqual(voted_state["epoch"]["successVotes"], 0)
            observed_time = int(rpc.request("eth_getBlockByNumber", [
                "latest", False])["timestamp"], 16)
            rpc.request("evm_increaseTime", [
                max(0, epoch["monitoringClose"] - observed_time + 1)])
            rpc.request("evm_mine", [])
            role_tx("seal-epoch", "monitor",
                    {"leaseId": 1, "epochId": 0}, by_address[selected[0]])
            role_tx("settle-epoch", "monitor",
                    {"leaseId": 1, "epochId": 0}, by_address[selected[0]])
            settled = inspect_chain(rpc, settlement, 1, 0,
                                    expected_chain_id=CHAIN)
            ep = settled["epoch"]
            self.assertEqual(ep["outcomeName"], "Failure")
            # SSE N/F ambiguity: no acknowledgment, failure quorum.
            # p(N)=reservation fee 5, p(F)=0:
            # lower=0, upper=5, refund=25-5=20, retained=5.
            self.assertEqual(ep["providerCredited"], 0)
            self.assertEqual(ep["consumerCredited"], 20)
            self.assertEqual(ep["unresolvedExposure"], 5)
            observed_time = int(rpc.request("eth_getBlockByNumber", [
                "latest", False])["timestamp"], 16)
            rpc.request("evm_increaseTime", [
                max(0, epoch["evidenceClose"] - observed_time + 1)])
            rpc.request("evm_mine", [])
            role_tx("close-evidence", "monitor",
                    {"leaseId": 1, "epochId": 0}, by_address[selected[0]])
            closed = inspect_chain(rpc, settlement, 1, 0,
                                   expected_chain_id=CHAIN)
            self.assertTrue(closed["epoch"]["evidenceClosed"])
            self.assertEqual(closed["epoch"]["unresolvedExposure"], 5)
            role_tx("close-lease", "consumer", {"leaseId": 1}, consumer)
            role_tx("release-committee", "monitor", {"leaseId": 1},
                    by_address[selected[0]])
            credit_before = rpc.request("eth_call", [
                {"to": settlement, "data":
                 _data("withdrawable(address)", consumer.address)}, "latest"])
            self.assertEqual(int(credit_before, 16), 20)
            role_tx("withdraw", "consumer", {}, consumer)
            credit_after = rpc.request("eth_call", [
                {"to": settlement, "data":
                 _data("withdrawable(address)", consumer.address)}, "latest"])
            self.assertEqual(int(credit_after, 16), 0)
            self.assertEqual(len(recorded), 23)
            self.assertEqual(len(set(recorded)), len(recorded))
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
