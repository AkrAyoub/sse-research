#!/usr/bin/env python3
"""Crash-resistant SSE provider direct-work replay and receipt journal (SQLite).

This private, owner-controlled off-chain journal records signed consumer work
requests, provider replies and verified receipt envelopes. It stores no wallet
key and authorizes no EVM payment. Reservations are durable BEFORE computing
a response: after a crash they block duplicate processing rather than guessing
whether a previous computation occurred. Manual reconciliation is then required.

Files need an owner-only directory and mode 0600 on Ubuntu. These guarantees
do NOT make the DB Byzantine immutable or externally available evidence.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import stat
from pathlib import Path

from sse_direct_delivery import json_bytes

NONCE = re.compile(r"0x[0-9a-f]{64}\Z")


class DirectJournalError(ValueError):
    pass


def _key(key):
    if (type(key) not in (tuple, list) or len(key) != 3 or
            type(key[0]) is not int or type(key[1]) is not int or
            not 1 <= key[0] < 2**63 or not 0 <= key[1] < 2**63 or
            type(key[2]) is not str or not NONCE.fullmatch(key[2])):
        raise DirectJournalError("invalid direct-work journal key")
    return key[0], key[1], key[2]


class DirectJournal:
    def __init__(self, path):
        path = Path(path)
        if not path.is_absolute() or path.is_symlink() or ".." in path.parts:
            raise DirectJournalError("journal path must be absolute and not a symlink")
        parent = path.parent
        if not parent.is_dir() or parent.is_symlink():
            raise DirectJournalError("journal parent must already be an ordinary directory")
        if os.name == "posix":
            st = parent.stat()
            if (st.st_uid != os.geteuid() or
                    stat.S_IMODE(st.st_mode) & 0o077):
                raise DirectJournalError("journal directory must be owner-only")
        if not path.exists():
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os,"O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                fd = os.open(path, flags, 0o600)
                os.close(fd)
            except FileExistsError:
                pass
        if path.is_symlink() or not path.is_file():
            raise DirectJournalError("unsafe journal file")
        if os.name == "posix":
            st = path.stat()
            if (st.st_uid != os.geteuid() or
                    stat.S_IMODE(st.st_mode) != 0o600 or
                    st.st_nlink != 1):
                raise DirectJournalError("journal file requires one link, owner-only 0600")
        self.path = path
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS direct_exchange (
                lease_id INTEGER NOT NULL,
                epoch_id INTEGER NOT NULL,
                nonce TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('RESERVED','RESPONDED','RECEIVED')),
                consumer_request BLOB NOT NULL,
                provider_response BLOB,
                consumer_receipt BLOB,
                PRIMARY KEY (lease_id,epoch_id,nonce)
            )""")
            db.commit()

    def _connect(self):
        try:
            db = sqlite3.connect(self.path,timeout=5,isolation_level=None)
            db.execute("PRAGMA synchronous=FULL")
            return db
        except sqlite3.Error as exc:
            raise DirectJournalError("journal database unavailable") from exc

    def reserve(self, key, consumer_request):
        lease,epoch,nonce = _key(key)
        data=json_bytes(consumer_request)
        try:
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("""INSERT INTO direct_exchange
                    (lease_id,epoch_id,nonce,status,consumer_request)
                    VALUES (?,?,?,'RESERVED',?)""",(lease,epoch,nonce,data))
                db.commit()
        except sqlite3.IntegrityError as exc:
            raise DirectJournalError("duplicate or already reserved work order") from exc
        except sqlite3.Error as exc:
            raise DirectJournalError("could not reserve signed work order") from exc

    def record_response(self,key,response):
        lease,epoch,nonce = _key(key)
        body=json_bytes(response)
        try:
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                changed=db.execute("""UPDATE direct_exchange SET
                    provider_response=?,status='RESPONDED' WHERE
                    lease_id=? AND epoch_id=? AND nonce=? AND status='RESERVED'""",
                    (body,lease,epoch,nonce)).rowcount
                if changed != 1:
                    raise DirectJournalError("work reservation missing or already completed")
                db.commit()
        except sqlite3.Error as exc:
            raise DirectJournalError("could not record provider response") from exc

    def pending_receipt(self,key):
        lease,epoch,nonce = _key(key)
        try:
            with self._connect() as db:
                row=db.execute("""SELECT status,consumer_request,provider_response
                    FROM direct_exchange WHERE lease_id=? AND epoch_id=? AND nonce=?""",
                    (lease,epoch,nonce)).fetchone()
        except sqlite3.Error as exc:
            raise DirectJournalError("could not read work journal") from exc
        if row is None or row[0] != "RESPONDED" or row[2] is None:
            raise DirectJournalError("receipt not expected or already recorded")
        try:
            return json.loads(row[1]),json.loads(row[2])
        except (ValueError,UnicodeError,TypeError) as exc:
            raise DirectJournalError("corrupt recorded work messages") from exc

    def record_receipt(self,key,consumer_receipt):
        lease,epoch,nonce = _key(key)
        body=json_bytes(consumer_receipt)
        try:
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                changed=db.execute("""UPDATE direct_exchange SET
                    consumer_receipt=?,status='RECEIVED' WHERE
                    lease_id=? AND epoch_id=? AND nonce=? AND status='RESPONDED'""",
                    (body,lease,epoch,nonce)).rowcount
                if changed != 1:
                    raise DirectJournalError("receipt not expected or already recorded")
                db.commit()
        except sqlite3.Error as exc:
            raise DirectJournalError("could not record consumer receipt") from exc

    def counts(self):
        try:
            with self._connect() as db:
                rows=db.execute("""SELECT status,COUNT(*) FROM direct_exchange
                    GROUP BY status""").fetchall()
        except sqlite3.Error as exc:
            raise DirectJournalError("could not inspect journal") from exc
        return {state:int(count) for state,count in rows}
