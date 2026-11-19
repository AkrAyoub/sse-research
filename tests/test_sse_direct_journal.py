"""Durable provider replay/receipt state: offline SQLite and restart tests."""
from __future__ import annotations

import json
import sqlite3
import subprocess
from contextlib import closing
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_direct_journal import DirectJournal,DirectJournalError
from sse_direct_wire import WireError, wire_json_bytes

KEY=(1,0,"0x"+"ab"*32)
ORDER={"schema":"sse-direct-request-v1","message":{"leaseId":1,"epochId":0},
       "signature":"0x"+"cd"*65}
RESULT={"schema":"sse-direct-response-v1","result":{"digest":"abc"}}
RECEIPT={"schema":"sse-direct-receipt-v1","signature":"0x"+"ef"*65}


class DirectJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"provider-evidence.sqlite"

    def test_reboot_persists_request_result_and_receipt(self):
        a=DirectJournal(self.path)
        a.reserve(KEY,ORDER)
        self.assertEqual(a.counts(),{"RESERVED":1})
        self.assertFalse(a.has_verified_receipt(1,0))
        a.record_response(KEY,RESULT)
        self.assertFalse(a.has_verified_receipt(1,0))
        b=DirectJournal(self.path)  # Simulated process restart.
        self.assertEqual(b.pending_receipt(KEY),(ORDER,RESULT))
        b.record_receipt(KEY,RECEIPT)
        self.assertTrue(DirectJournal(self.path).has_verified_receipt(1,0))
        self.assertFalse(DirectJournal(self.path).has_verified_receipt(1,1))
        self.assertEqual(DirectJournal(self.path).counts(),{"RECEIVED":1})
        with self.assertRaises(DirectJournalError):
            b.pending_receipt(KEY)
        with self.assertRaises(DirectJournalError):
            b.reserve(KEY,ORDER)

    def test_crash_between_reserve_and_result_blocks_replay(self):
        a=DirectJournal(self.path)
        a.reserve(KEY,ORDER)
        b=DirectJournal(self.path)
        with self.assertRaises(DirectJournalError):
            b.reserve(KEY,ORDER)
        with self.assertRaises(DirectJournalError):
            b.pending_receipt(KEY)
        self.assertEqual(b.counts(),{"RESERVED":1})

    def test_receipt_not_accepted_without_response(self):
        a=DirectJournal(self.path)
        a.reserve(KEY,ORDER)
        with self.assertRaises(DirectJournalError):
            a.record_receipt(KEY,RECEIPT)
        self.assertEqual(a.counts(),{"RESERVED":1})

    def test_duplicate_response_and_receipt_fail(self):
        j=DirectJournal(self.path)
        j.reserve(KEY,ORDER)
        j.record_response(KEY,RESULT)
        with self.assertRaises(DirectJournalError):
            j.record_response(KEY,RESULT)
        j.record_receipt(KEY,RECEIPT)
        with self.assertRaises(DirectJournalError):
            j.record_receipt(KEY,RECEIPT)

    def test_wrong_or_untrusted_keys_refused(self):
        j=DirectJournal(self.path)
        for bad in ((0,0,KEY[2]),(1,-1,KEY[2]),(True,0,KEY[2]),
                    (1,0,"0xdead"),(1,0,KEY[2]+"bad"),[1,0]):
            with self.subTest(key=bad),self.assertRaises(DirectJournalError):
                j.reserve(bad,ORDER)

    def test_nonabsolute_and_nonexistent_parent_refused(self):
        with self.assertRaises(DirectJournalError):
            DirectJournal(Path("not-absolute.sqlite"))
        with self.assertRaises(DirectJournalError):
            DirectJournal(self.path.parent/"does-not-exist"/"a.sqlite")

    def test_import_in_fresh_isolated_interpreter(self):
        # Suite ordering must not be allowed to provide typed_evidence
        # implicitly via another test's sys.path modification.
        code = (
            "import sys; from pathlib import Path; "
            "sys.path.insert(0, " + repr(str(ROOT / "tools")) + "); "
            "from sse_direct_journal import DirectJournal; "
            "assert 'sse_direct_delivery' not in sys.modules; "
            "assert 'typed_evidence' not in sys.modules; "
            "print('journal-import-isolated: OK')"
        )
        completed = subprocess.run([sys.executable, "-I", "-c", code],
                                   capture_output=True, text=True, timeout=15,
                                   check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("journal-import-isolated: OK", completed.stdout)

    def test_stored_json_bytes_are_canonical_and_bounded(self):
        sample = {"z": "word", "a": [2, 3]}
        expected = json.dumps(sample, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=True, allow_nan=False).encode("ascii")
        self.assertEqual(wire_json_bytes(sample), expected)
        with self.assertRaises(WireError):
            wire_json_bytes({"large": "x" * 9000})
        with self.assertRaises(WireError):
            wire_json_bytes({"invalid": float("nan")})
        journal = DirectJournal(self.path)
        with self.assertRaises(DirectJournalError):
            journal.reserve(KEY, {"large": "x" * 9000})
        self.assertEqual(journal.counts(), {})

    def test_duplicate_sqlite_key_is_atomic(self):
        j=DirectJournal(self.path)
        j.reserve(KEY,ORDER)
        # sqlite3.Connection.__exit__ commits/rolls back but does NOT close.
        # Explicit close is mandatory before TemporaryDirectory cleanup on Windows.
        with closing(sqlite3.connect(self.path)) as con:
            count=con.execute("SELECT COUNT(*) FROM direct_exchange").fetchone()[0]
        self.assertEqual(count,1)
        with self.assertRaises(sqlite3.ProgrammingError):
            con.execute("SELECT 1")


if __name__=="__main__":
    unittest.main()
