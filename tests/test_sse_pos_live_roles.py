"""R18 safe live PoS31339 roles: tests with LOCAL mock RPC, no broadcasts."""
from __future__ import annotations
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_live_roles as roles
from sse_pos_deploy_receipts import COMMITTEE,FAUCET,GENESIS

RPC="http://127.0.0.1:32770"


def _words(*values):
    return "0x"+"".join(f"{v:064x}" for v in values)


class FakeRPC:
    def __init__(self):
        self.chain=roles.CHAIN
        self.genesis=GENESIS
        self.balances={}
        self.registered={}
        self.txs=[]
    def __call__(self,method,params):
        if method=="eth_chainId":return hex(self.chain)
        if method=="eth_getBlockByNumber":
            if params[0]=="0x0":return {"hash":self.genesis}
            return {"baseFeePerGas":"0x7","number":"0x400"}
        if method=="eth_getBalance":
            return hex(self.balances.get(params[0].lower(),0))
        if method=="eth_call":
            data=params[0]["data"]
            if data==roles._selector("minimumBond()"):
                return _words(roles.EXPECTED_MIN_BOND)
            if data==roles._selector("candidateCount()"):
                return _words(sum(1 for x in self.registered.values() if x))
            if data.startswith(roles._selector("candidates(address)")):
                addr="0x"+data[-40:].lower()
                status=self.registered.get(addr,False)
                return _words(roles.EXPECTED_MIN_BOND if status else 0,0,0,0,
                              int(status),int(status))
        if method=="eth_getTransactionCount":return "0x0"
        if method=="eth_gasPrice":return "0x8"
        if method=="eth_estimateGas":return "0x5208" if params[0]["data"]=="0x" else "0x189c0"
        if method=="eth_sendRawTransaction":
            raw=bytes.fromhex(params[0][2:])
            self.txs.append(params[0])
            from eth_utils import keccak
            return "0x"+keccak(raw).hex()
        if method=="eth_getTransactionReceipt":
            return {"status":"0x1","transactionHash":params[0],
                    "blockNumber":"0x401","gasUsed":"0x5208"}
        raise AssertionError("unexpected RPC method "+method)


def generate_metadata(folder:Path):
    addresses={}
    keys=("faucet",)+roles.ROLES
    for i,role in enumerate(keys):
        addr=FAUCET.lower() if role=="faucet" else "0x"+f"{i:040x}"
        addresses[role]=addr
        file=folder/(role+".keystore.json")
        file.write_text(json.dumps({
            "crypto":{"cipher":"aes-128-ctr","padding":"x"*100},
            "version":3,"address":addr[2:],
        }))
        if os.name=="posix":file.chmod(0o600)
    return addresses


class R18RolesTests(unittest.TestCase):
    @unittest.skipUnless(os.name=="posix" and os.geteuid()!=0,
                         "owner-only wallet metadata tests require nonroot POSIX")
    def test_read_only_plan_never_decrypts_or_sends(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);folder.chmod(0o700)
            addrs=generate_metadata(folder)
            rpc=FakeRPC()
            rpc.balances[FAUCET.lower()]=1000000*10**18
            with patch.object(roles,"_attest",return_value=None):
                observed=roles.observe_roles(RPC,folder,rpc=rpc)
            self.assertEqual(observed["chainId"],31339)
            self.assertEqual(observed["registeredActiveCandidateCount"],0)
            self.assertFalse(observed["allFiveDemoMonitorsRegistered"])
            self.assertEqual(observed["roles"]["consumer"]["address"],addrs["consumer"])
            self.assertEqual(len(rpc.txs),0)

    @unittest.skipUnless(os.name=="posix" and os.geteuid()!=0,
                         "owner-only wallet metadata tests require nonroot POSIX")
    def test_funding_uses_only_new_roles_and_skips_positive_balances(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);folder.chmod(0o700)
            addrs=generate_metadata(folder)
            rpc=FakeRPC()
            rpc.balances[FAUCET.lower()]=1000000*10**18
            rpc.balances[addrs["consumer"]]=10**18
            destinations=[]
            def sender(rpc,account,to,value,data="0x"):
                destinations.append((to,value,data))
                return {"receiptSuccessful":True,"to":to,"valueWei":value}
            fakeacc=type("A",(),{"address":FAUCET})()
            with patch.object(roles,"_attest",return_value=None), \
                 patch.object(roles,"_send",side_effect=sender):
                outcome=roles.execute_funding(
                    RPC,folder,rpc=rpc,
                    signer=lambda r,w:fakeacc,confirm=False)
            self.assertEqual(outcome["transactionCount"],6)
            self.assertEqual([x[0] for x in destinations],
                             [addrs[r] for r in roles.ROLES[1:]])
            self.assertTrue(all(x[2]=="0x" for x in destinations))

    @unittest.skipUnless(os.name=="posix" and os.geteuid()!=0,
                         "owner-only wallet metadata tests require nonroot POSIX")
    def test_register_five_bonds_without_faucet_validator_keys(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);folder.chmod(0o700)
            addrs=generate_metadata(folder)
            rpc=FakeRPC()
            rpc.balances[FAUCET.lower()]=1000000*10**18
            for role in roles.MONITORS:
                rpc.balances[addrs[role]]=10**17
            rpc.registered[addrs["monitor01"]]=True
            transactions=[]
            def sender(rpc,account,to,value,data="0x"):
                transactions.append((account.address,to,value,data))
                return {"receiptSuccessful":True,"to":to,"valueWei":value}
            with patch.object(roles,"_attest",return_value=None), \
                 patch.object(roles,"_send",side_effect=sender):
                out=roles.execute_registration(
                    RPC,folder,rpc=rpc,confirm=False,
                    signer=lambda r,w:type("A",(),{"address":w["address"]})())
            self.assertEqual(out["transactionCount"],4)
            self.assertEqual([tx[0] for tx in transactions],
                             [addrs[r] for r in roles.MONITORS[1:]])
            self.assertTrue(all(tx[1].lower()==COMMITTEE.lower() and
                                tx[2]==roles.EXPECTED_MIN_BOND and
                                tx[3]==roles._selector("register()")
                                for tx in transactions))

    @unittest.skipUnless(os.name=="posix" and os.geteuid()!=0,
                         "owner-only wallet metadata tests require nonroot POSIX")
    def test_wallet_missing_or_duplicate_rejected_before_signing(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);folder.chmod(0o700)
            addrs=generate_metadata(folder)
            (folder/"monitor05.keystore.json").unlink()
            with self.assertRaises(roles.RoleError):
                roles.read_wallets(folder)
            generate_metadata(folder)
            first=json.loads((folder/"monitor01.keystore.json").read_text())
            last=folder/"monitor05.keystore.json"
            obj=json.loads(last.read_text())
            obj["address"]=first["address"]
            last.write_text(json.dumps(obj))
            last.chmod(0o600)
            with self.assertRaises(roles.RoleError):
                roles.read_wallets(folder)

    def test_wrong_chain_and_genesis_do_not_allow_any_write(self):
        rpc=FakeRPC();rpc.chain=1
        with self.assertRaises(roles.RoleError):
            roles.chain_check(rpc,RPC,verify_attestation=False)
        rpc.chain=31339;rpc.genesis="0x"+"11"*32
        with self.assertRaises(roles.RoleError):
            roles.chain_check(rpc,RPC,verify_attestation=False)
        self.assertEqual(len(rpc.txs),0)

    def test_live_signer_produces_type2_eip1559_and_observed_receipt(self):
        from eth_account import Account
        a=Account.create(os.urandom(32))
        rpc=FakeRPC()
        rpc.balances[a.address.lower()]=10**18
        output=io.StringIO()
        with redirect_stdout(output):
            receipt=roles._send(rpc,a,"0x"+"12"*20,10**15)
        self.assertEqual(receipt["valueWei"],10**15)
        self.assertEqual(receipt["blockNumber"],1025)
        self.assertEqual(len(rpc.txs),1)
        self.assertTrue(rpc.txs[0].startswith("0x02"))
        self.assertIn("SSE_R18_SIGNED_TX_HASH=",output.getvalue())
        self.assertNotIn(a.key.hex(),output.getvalue())

    def test_real_vm4705_lowercase_recipient_signs_using_eip55_checksum(self):
        # VM4705 live --fund failed BEFORE broadcast:
        # Transaction had invalid fields {'to': '0xaf8105...'}.
        # Unlike the prior numeric-only test address this destination
        # contains letters and has a nontrivial EIP-55 checksum.
        from eth_account import Account
        from eth_utils import to_checksum_address
        account=Account.create(os.urandom(32))
        rpc=FakeRPC()
        rpc.balances[account.address.lower()]=10**18
        lowercase="0xaf810580e49809f337828391725886f40207abcc"
        checksum=to_checksum_address(lowercase)
        self.assertNotEqual(checksum,lowercase)
        with redirect_stdout(io.StringIO()):
            receipt=roles._send(rpc,account,lowercase,10**15)
        self.assertEqual(receipt["to"],checksum)
        self.assertEqual(len(rpc.txs),1)
        self.assertTrue(receipt["receiptSuccessful"])

    def test_real_vm4705_lowercase_committee_register_destination(self):
        from eth_account import Account
        from eth_utils import to_checksum_address
        account=Account.create(os.urandom(32))
        rpc=FakeRPC()
        rpc.balances[account.address.lower()]=10**18
        committee_lower=COMMITTEE.lower()
        with redirect_stdout(io.StringIO()):
            receipt=roles._send(
                rpc,account,committee_lower,roles.EXPECTED_MIN_BOND,
                roles._selector("register()"),
            )
        self.assertEqual(receipt["to"],to_checksum_address(committee_lower))
        self.assertEqual(len(rpc.txs),1)

    def test_fee_cap_or_low_balance_prevents_signing(self):
        from eth_account import Account
        a=Account.create(os.urandom(32))
        rpc=FakeRPC()
        rpc.balances[a.address.lower()]=100
        with self.assertRaises(roles.RoleError):
            roles._send(rpc,a,"0x"+"12"*20,10**15)
        self.assertEqual(len(rpc.txs),0)

    def test_only_loopback_cleartext_rpc_is_accepted(self):
        with self.assertRaises(roles.HealthError):
            roles.observe_roles("http://public.example:32770",
                                Path("/tmp/untrusted"))

if __name__=="__main__":
    unittest.main()
