"""R5 participant-owned Ethereum transaction plans: offline-only regression tests.

No actual RPC, wallet file or deployed contract is accessed.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("sse_node_marketplace", ROOT / "tools" / "sse_node_marketplace.py")
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
from sse_challenge import keccak256

BOARD = "0x" + "11" * 20
SETTLEMENT = "0x" + "22" * 20
POOL = "0x" + "33" * 20
PROVIDER = "0x" + "44" * 20
D1 = "0x" + "a1" * 32
D2 = "0x" + "b2" * 32
D3 = "0x" + "c3" * 32


def plan(action, role, **kwargs):
    defaults = {
        "request": dict(profileHash=D1, policyHash=D2, maxEpochFeeWei=25,
                        biddingClose=1800000000),
        "bid": dict(requestId=1, epochFeeWei=10),
        "fund": dict(requestId=1, bidIndex=0, endpointHash=D3,
                     selectedEpochFeeWei=10, reservationFeeWei=3, exposureBudgetWei=10,
                     maxEpochs=2, responsePeriodSeconds=60,
                     monitorGraceSeconds=15, evidenceWindowSeconds=60),
        "accept": dict(leaseId=1),
        "monitor-register": dict(bondWei=10000),
        "monitor-confirm": dict(leaseId=1),
        "admit-epoch": dict(leaseId=1, requestHash=D1),
    }
    params = dict(defaults[action])
    params.update(kwargs)
    return m.make_plan(action, role, chain_id=31337, board=BOARD,
                       settlement=SETTLEMENT, pool=POOL, params=params)


class MockRPC:
    def __init__(self, *, fee=10):
        self.fee = fee
        self.calls = []
        self.broadcasts = []
        self.receipt_hash = None

    def request(self, method, args):
        self.calls.append((method, args))
        if method == "eth_chainId":
            return hex(31337)
        if method == "eth_getCode":
            return "0x60016001"
        if method == "eth_call":
            selector = args[0]["data"][:10].lower()
            if selector == "0x" + keccak256(b"approvedSettlement()")[:4].hex():
                return "0x" + int(SETTLEMENT,16).to_bytes(32,"big").hex()
            if selector == "0x" + keccak256(b"resourceBoard()")[:4].hex():
                return "0x" + int(BOARD,16).to_bytes(32,"big").hex()
            if selector == "0x" + keccak256(b"getBid(uint256,uint256)")[:4].hex():
                return "0x" + int(PROVIDER,16).to_bytes(32,"big").hex() + self.fee.to_bytes(32,"big").hex()
            raise AssertionError("unexpected read selector")
        if method == "eth_estimateGas":
            return "0x186a0"
        if method == "eth_gasPrice":
            return "0x1"
        if method == "eth_getTransactionCount":
            return "0x1"
        if method == "eth_sendRawTransaction":
            self.broadcasts.append(args[0])
            self.receipt_hash = "0x" + keccak256(bytes.fromhex(args[0][2:])).hex()
            return self.receipt_hash
        if method == "eth_getTransactionReceipt":
            return {"transactionHash": self.receipt_hash, "status": "0x1",
                    "blockNumber": "0x8", "gasUsed": "0x186a0"}
        raise AssertionError("unexpected RPC " + method)


class MarketplacePlans(unittest.TestCase):
    def test_role_isolation(self):
        for action, wrong_role in (("request","provider"),("bid","consumer"),
                                   ("fund","provider"),("monitor-register","consumer"),
                                   ("monitor-confirm","provider"),("admit-epoch","monitor")):
            with self.subTest(action=action), self.assertRaises(m.NodeTxError):
                plan(action, wrong_role)

    def test_exact_marketplace_request_selector(self):
        p = plan("request","consumer")
        self.assertEqual(p.target, BOARD)
        self.assertEqual(p.data[:10], "0x" + keccak256(
            b"requestResource(bytes32,bytes32,uint256,uint64)")[:4].hex())
        self.assertEqual(int(p.data[-64:],16),1800000000)
        self.assertEqual(p.value,0)

    def test_provider_bid_and_accept_owned_by_provider(self):
        p = plan("bid","provider")
        self.assertEqual(p.target, BOARD)
        self.assertEqual(int(p.data[-64:],16),10)
        a = plan("accept","provider")
        self.assertEqual(a.target, SETTLEMENT)
        self.assertEqual(a.data[:10],"0x" + keccak256(b"acceptLease(uint256)")[:4].hex())

    def test_funded_consumer_selection_exact_abi_and_value(self):
        p = plan("fund","consumer")
        self.assertEqual(p.value,20)
        self.assertEqual(p.target,BOARD)
        self.assertEqual(len(p.data), 2 + 8 + 10 * 64)
        self.assertEqual(p.data[:10], "0x" + keccak256(
            b"chooseBidAndFundLease(uint256,uint256,address,(bytes32,uint256,uint256,uint256,uint64,uint64,uint64))")[:4].hex())
        words = [int(p.data[10+i*64:10+(i+1)*64],16) for i in range(10)]
        self.assertEqual(words,[1,0,int(SETTLEMENT,16),int(D3,16),3,10,2,60,15,60])

    def test_budget_math_fails_closed(self):
        for bad in ({"maxEpochs":65},{"maxEpochs":0},
                    {"selectedEpochFeeWei":0},{"reservationFeeWei":11},
                    {"exposureBudgetWei":9},{"responsePeriodSeconds":0},
                    {"epochFeeWei":0}):
            action = "bid" if "epochFeeWei" in bad else "fund"
            role = "provider" if action == "bid" else "consumer"
            with self.subTest(bad=bad), self.assertRaises(m.NodeTxError):
                plan(action,role,**bad)

    def test_invalid_digests_and_privileged_extra_args_rejected(self):
        with self.assertRaises(m.NodeTxError):
            plan("request","consumer",profileHash="0x"+"0"*64)
        with self.assertRaises(m.NodeTxError):
            plan("fund","consumer",settlement=PROVIDER)
        with self.assertRaises(m.NodeTxError):
            plan("monitor-register","monitor",privateKey="deadbeef")

    def test_monitor_registration_and_confirmation_do_not_claim_evidence(self):
        p = plan("monitor-register","monitor")
        self.assertEqual(p.target,POOL)
        self.assertEqual(p.value,10000)
        self.assertEqual(p.data[:10],"0x"+keccak256(b"register()")[:4].hex())
        conf = plan("monitor-confirm","monitor")
        self.assertEqual(conf.target,SETTLEMENT)
        self.assertFalse(conf.public()["physicalServiceVerified"])
        self.assertFalse(conf.public()["ethereumTransactionsSent"])

    def test_untrusted_rpc_and_signer_url_rejected(self):
        for url in ("http://example.org:8545","https://u:p@node.example",
                    "https://rpc.example/secret", "https://rpc.example?token=x",
                    "file:///etc/passwd"):
            with self.subTest(url=url),self.assertRaises(m.NodeTxError):
                m.rpc_origin(url)
        self.assertEqual(m.rpc_origin("http://127.0.0.1:8545"),
                         "http://127.0.0.1:8545")

    def test_funding_requires_live_bid_price_and_binding(self):
        p = plan("fund","consumer")
        rpc = MockRPC(fee=15)
        with self.assertRaises(m.NodeTxError):
            m.preflight(rpc,p,expected_selected_fee=10)
        rpc2 = MockRPC(fee=10)
        m.preflight(rpc2,p,expected_selected_fee=10)

    def test_dry_run_cli_does_not_contact_rpc_or_load_wallet(self):
        argv=["--role","provider","--action","bid","--params-json",
              json.dumps({"requestId":1,"epochFeeWei":2}),
              "--chain-id","31337","--board",BOARD,
              "--settlement",SETTLEMENT,"--pool",POOL]
        with patch.object(m,"RPC",side_effect=AssertionError("must remain offline")), \
             patch.object(m,"_load_signer",side_effect=AssertionError("must not touch keys")):
            self.assertEqual(m.main(argv),0)

    def test_approved_live_sign_and_broadcast_mock_only(self):
        from eth_account import Account
        wallet=Account.create()
        rpc=MockRPC()
        p=plan("bid","provider")
        receipt=m.execute(rpc,p,wallet,max_total_wei=1_000_000)
        self.assertEqual(receipt["status"],"MINED_UNFINALIZED")
        self.assertEqual(receipt["action"],"bid")
        self.assertFalse(receipt["evidenceQualified"])
        self.assertEqual(len(rpc.broadcasts),1)

    def test_spend_cap_blocks_signed_broadcast(self):
        from eth_account import Account
        wallet=Account.create()
        rpc=MockRPC()
        p=plan("monitor-register","monitor")
        with self.assertRaises(m.NodeTxError):
            m.execute(rpc,p,wallet,max_total_wei=1)
        self.assertEqual(rpc.broadcasts,[])


if __name__ == "__main__":
    unittest.main()
