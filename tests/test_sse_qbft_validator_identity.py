"""Offline QBFT key format, stable public identities, no VM key reuse."""
import ipaddress
import os
from pathlib import Path
import secrets
import stat
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_qbft_validator_identity import (IdentityError, init_local, inspect_local,
                                          node_key_record, read_private_key)

class NodeKeyTests(unittest.TestCase):
    def test_public_node_key_is_unique_and_matches_eth_address(self):
        a=node_key_record((1).to_bytes(32,"big"),"validator-1","100.101.102.103")
        b=node_key_record((2).to_bytes(32,"big"),"validator-2","100.101.102.104")
        self.assertNotEqual(a["validatorAddress"],b["validatorAddress"])
        self.assertNotEqual(a["enode"],b["enode"])
        self.assertEqual(len(a["enodePublicKey"]),128)
        self.assertEqual(len(a["validatorAddress"]),42)
        self.assertFalse(a["privateKeyIncluded"])
        self.assertFalse(a["physicalIndependenceProved"])
    def test_refuses_old_dhcp_and_non_validator_roles(self):
        for ip in ("10.50.56.14","127.0.0.1","8.8.8.8"):
            with self.subTest(ip=ip),self.assertRaises(IdentityError):
                node_key_record((1).to_bytes(32,"big"),"validator-1",ip)
        for role in ("monitor","validator-5","validator-1; rm -rf /"):
            with self.subTest(role=role),self.assertRaises(IdentityError):
                node_key_record((1).to_bytes(32,"big"),role,"100.101.102.103")
    def test_zero_and_curve_overflow_fail_closed(self):
        with self.assertRaises(IdentityError):
            node_key_record(bytes(32),"validator-1","100.101.102.103")
        with self.assertRaises(IdentityError):
            node_key_record(b"short","validator-1","100.101.102.103")
    @unittest.skipUnless(os.name=="posix" and sys.platform=="linux","local key custody is POSIX/Linux only")
    def test_create_once_then_inspect_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)/"private"
            directory.mkdir(mode=0o700)
            pub=directory/"validator-1.public.json"
            first=init_local(directory,public_file=pub,
                             node_id="validator-1",overlay_ipv4="100.101.102.103")
            self.assertEqual(first,inspect_local(directory,public_file=pub))
            self.assertEqual(stat.S_IMODE((directory/"node.key").stat().st_mode),0o600)
            self.assertEqual(len(read_private_key(directory/"node.key")),32)
            with self.assertRaises(IdentityError):
                init_local(directory,public_file=pub,node_id="validator-1",
                           overlay_ipv4="100.101.102.103")
            self.assertEqual(first,inspect_local(directory,public_file=pub))
    @unittest.skipUnless(os.name=="posix" and sys.platform=="linux","local key custody is POSIX/Linux only")
    def test_symlink_or_overpermissive_directory_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)/"private"
            directory.mkdir(mode=0o755)
            with self.assertRaises(IdentityError):
                init_local(directory,public_file=directory/"public.json",
                           node_id="validator-1",overlay_ipv4="100.101.102.103")
            self.assertFalse((directory/"node.key").exists())

if __name__=="__main__":
    unittest.main()
