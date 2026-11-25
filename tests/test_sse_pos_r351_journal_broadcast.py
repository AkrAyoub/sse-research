"""R351b local journal fault-injection tests; no network or real wallet."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r242_v2_owner_local_send as m
from test_sse_pos_r242_v2_owner_local_send import P,OFFER,MANIFEST,APP

class TestJournalBroadcast(unittest.TestCase):
    def test_durable_before_uncertain_send_and_refuse_retry(self):
        from eth_account import Account
        from types import SimpleNamespace
        signed=SimpleNamespace(hash=bytes.fromhex("ab"*32),raw_transaction=b"test-only")
        account=SimpleNamespace(address=APP,sign_transaction=lambda tx:signed)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"journal"
            calls=[]
            def transport(url,method,params):
                if method=="eth_getTransactionCount":
                    return "0x3"
                if method=="eth_estimateGas":
                    return "0x10000"
                if method=="eth_sendRawTransaction":
                    calls.append(method)
                    entry=json.loads((root/(APP+"-3.json")).read_text())
                    self.assertEqual(entry["transactionHash"],"0x"+"ab"*32)
                    self.assertEqual(entry["nonce"],3)
                    raise OSError("simulated lost acknowledgement")
                raise AssertionError(method)
            def submit():
                return m.submit_once(P,OFFER,MANIFEST,"http://127.0.0.1:28545",
                    Path("/unused"),confirm=lambda _:m.AUTHORIZE,
                    get_password=lambda _:"test-only",tty=False,transport=transport,
                    journal_dir=root)
            with patch.object(m,"safe_keystore",return_value={}),patch.object(Account,"decrypt",return_value=b"test-only"),patch.object(Account,"from_key",return_value=account),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(OSError,"lost acknowledgement"):
                    submit()
                with patch.object(m,"reconcile",return_value={"status":"UNKNOWN_NO_RECEIPT","terminal":False}):
                    with self.assertRaisesRegex(m.Refused,"unresolved prior"):
                        submit()
            self.assertEqual(calls,["eth_sendRawTransaction"])

    def test_lock_released_after_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"journal"
            with self.assertRaises(RuntimeError):
                with m.journal_lock(root,APP):
                    raise RuntimeError("test interruption")
            with m.journal_lock(root,APP):
                pass

if __name__=="__main__":
    unittest.main()
