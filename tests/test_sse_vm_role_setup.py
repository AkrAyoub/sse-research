"""Offline fail-closed VM role operator regression tests.

No VM state, live RPC, wallet funds, or real chain are modified.
"""
from __future__ import annotations

import json
import os
import socket
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_vm_role_setup as s

POOL = "0x" + "33" * 20
BOARD = "0x" + "11" * 20
SETTLEMENT = "0x" + "22" * 20
CONSUMER = "0x" + "44" * 20
MONITOR = "0x" + "55" * 20


class FakeRPC:
    def __init__(self, balance=0, active=False, bond=0):
        self.balance = balance
        self.active = active
        self.bond = bond
        self.sent = []

    def request(self, method, args):
        if method == "eth_chainId":
            return hex(31337)
        if method == "eth_accounts":
            return [s.DEV_FUNDER]
        if method == "eth_getBalance":
            return hex(self.balance)
        if method == "eth_getCode":
            return "0x6001"
        if method == "eth_call":
            data = args[0]["data"]
            sig = data[:10]
            if sig == s._selector("candidates(address)"):
                words = [self.bond, 0, 0, 0, int(self.active), int(self.active)]
                return "0x" + "".join(value.to_bytes(32, "big").hex() for value in words)
            if sig == s._selector("minimumBond()"):
                return "0x" + (10**9).to_bytes(32, "big").hex()
            if sig == s._selector("candidateCount()"):
                return "0x" + int(self.active).to_bytes(32, "big").hex()
        if method == "eth_sendTransaction":
            self.sent.append(args[0])
            return "0x" + "ab" * 32
        if method == "eth_getTransactionReceipt":
            return {"status": "0x1"}
        raise AssertionError(method)


def manifest():
    return {"schema": "sse-node-roles-v1", "nodeId": socket.gethostname(),
            "roles": ["consumer", "monitor", "observer"],
            "wallets": {"consumer": CONSUMER, "monitor": MONITOR}}


class OperatorTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "POSIX wallet ACL, hostname and machine binding require Ubuntu")
    def test_role_wallets_never_overwrite_and_use_distinct_addresses(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "secrets"
            out = s.init_wallets(target, socket.gethostname(),
                                 "consumer,monitor,observer",
                                 "at least sixteen characters", "at least sixteen characters")
            self.assertEqual(out["result"], "LOCAL_WALLETS_ENCRYPTED")
            self.assertNotEqual(out["wallets"]["consumer"], out["wallets"]["monitor"])
            self.assertEqual(target.stat().st_mode & 0o777, 0o700)
            for name in ("consumer.json", "monitor.json", "roles.json"):
                self.assertEqual((target / name).stat().st_mode & 0o777, 0o600)
            loaded = s.load_manifest(target)
            self.assertEqual(loaded["wallets"], {k:v.lower() for k,v in out["wallets"].items()})
            with self.assertRaises(s.SetupError):
                s.init_wallets(target, socket.gethostname(), "monitor",
                               "at least sixteen characters", "at least sixteen characters")

    @unittest.skipUnless(os.name == "posix", "POSIX wallet ACL, hostname and machine binding require Ubuntu")
    def test_duplicate_portal_hostnames_get_distinct_node_id(self):
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first"
            second = Path(temp) / "second"
            a = s.init_wallets(first, None, "observer",
                               "at least sixteen characters", "at least sixteen characters")
            b = s.init_wallets(second, None, "observer",
                               "at least sixteen characters", "at least sixteen characters")
            self.assertEqual(a["hostname"], b["hostname"])
            self.assertNotEqual(a["nodeId"], b["nodeId"])
            self.assertTrue(a["nodeId"].startswith("sse-"))
            self.assertEqual(s.load_manifest(first)["nodeId"], a["nodeId"])
            self.assertEqual((first / "node-binding.json").stat().st_mode & 0o777, 0o600)
            with patch.object(s, "machine_fingerprint", return_value="0" * 64):
                with self.assertRaises(s.SetupError):
                    s.load_manifest(first)

    def test_invalid_init_rejected_before_keys_created(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "private"
            for roles in ("consumer,consumer", "provider,invalid", "monitor,"):
                with self.subTest(roles=roles), self.assertRaises(Exception):
                    s.init_wallets(directory, socket.gethostname(), roles,
                                   "at least sixteen characters", "at least sixteen characters")
            self.assertFalse(directory.exists())

    @unittest.skipUnless(os.name == "posix", "POSIX wallet ACL, hostname and machine binding require Ubuntu")
    def test_wrong_manifest_hostname_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "roles.json").write_text(json.dumps({
                "schema": "sse-node-roles-v1", "nodeId": "another-vm",
                "roles": ["observer"], "wallets": {}
            }))
            (directory / "roles.json").chmod(0o600)
            self.assertRaises(s.SetupError, s.load_manifest, directory)

    @unittest.skipUnless(os.name == "posix", "POSIX wallet ACL, hostname and machine binding require Ubuntu")
    def test_world_readable_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "roles.json").write_text(json.dumps({
                "schema": "sse-node-roles-v1", "nodeId": socket.gethostname(),
                "roles": ["observer"], "wallets": {}
            }))
            (directory / "roles.json").chmod(0o644)
            with self.assertRaises(s.SetupError):
                s.load_manifest(directory)

    def test_local_funding_preview_not_a_transfer(self):
        rpc = FakeRPC(balance=0)
        out = s.fund_lab(manifest(), rpc, 31337, 10**16, False)
        self.assertEqual(out["result"], "LAB_FUNDING_PREVIEW")
        self.assertEqual(len(out["transfers"]), 2)
        self.assertFalse(out["ethereumTransactionsSent"])
        self.assertEqual(rpc.sent, [])

    def test_funding_explicit_and_idempotent(self):
        rpc = FakeRPC(balance=0)
        out = s.fund_lab(manifest(), rpc, 31337, 10**16, True)
        self.assertEqual(out["result"], "LAB_FUNDED")
        self.assertEqual(len(rpc.sent), 2)
        self.assertEqual(rpc.sent[0]["value"], hex(10**16))
        with self.assertRaises(s.SetupError):
            s.fund_lab(manifest(), rpc, 11155111, 10**16, True)
        self.assertEqual(len(rpc.sent), 2)
        funded = FakeRPC(balance=10**16)
        s.fund_lab(manifest(), funded, 31337, 10**16, True)
        self.assertEqual(funded.sent, [])

    def test_chain_status_reads_real_candidate_fields_shape(self):
        out = s.chain_status(manifest(), FakeRPC(balance=10**16,
                             active=True, bond=10**9), 31337, POOL)
        self.assertEqual(out["monitor"]["bondWei"], 10**9)
        self.assertTrue(out["monitor"]["active"])
        self.assertEqual(out["monitor"]["minimumBondWei"], 10**9)
        self.assertEqual(out["monitor"]["candidateCount"], 1)

    def test_monitor_dry_run_does_not_unlock_or_broadcast(self):
        rpc = FakeRPC(balance=10**16)
        with tempfile.TemporaryDirectory() as temp:
            out = s.register_monitor(manifest(), Path(temp), rpc,
                                     chain_id=31337, board=BOARD,
                                     settlement=SETTLEMENT, pool=POOL,
                                     bond_wei=10**9, max_total_wei=0,
                                     broadcast=False)
            self.assertEqual(out["result"], "MONITOR_REGISTRATION_PREVIEW")
            self.assertFalse(out["plan"]["ethereumTransactionsSent"])
            self.assertEqual(rpc.sent, [])
            with self.assertRaises(s.SetupError):
                s.register_monitor(manifest(), Path(temp), rpc,
                                   chain_id=31337, board=BOARD,
                                   settlement=SETTLEMENT, pool=POOL,
                                   bond_wei=1, max_total_wei=0, broadcast=False)

    def test_existing_bond_prevents_duplicate_monitor_registration(self):
        rpc = FakeRPC(balance=10**16, active=True, bond=10**9)
        with self.assertRaises(s.SetupError):
            s.register_monitor(manifest(), Path("/unused"), rpc,
                               chain_id=31337, board=BOARD,
                               settlement=SETTLEMENT, pool=POOL,
                               bond_wei=10**9, max_total_wei=10**16,
                               broadcast=True, password="never-used")


if __name__ == "__main__":
    unittest.main()
