"""Transactional tamper-evident audit chain with owner-supplied HMAC key."""
from __future__ import annotations
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import time


class LedgerIntegrityError(RuntimeError):
    """Stored audit records differ from the authenticated chain."""


def _canonical(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


class IntegrityLedger:
    """SQLite WAL, BEGIN IMMEDIATE serialization, HMAC-SHA256 chain; no external anchor."""
    GENESIS = '0' * 64

    def __init__(self, path: Path, *, key: bytes):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError('Ledger HMAC key must be at least 32 bytes')
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._key = key
        with self._db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS ledger (
                seq INTEGER PRIMARY KEY, event TEXT NOT NULL, payload TEXT NOT NULL,
                at_ns INTEGER NOT NULL, previous TEXT NOT NULL, digest TEXT NOT NULL)''')

    def _db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA busy_timeout=30000')
        return db

    def _digest(self, seq: int, event: str, payload: str, at_ns: int, previous: str) -> str:
        record = _canonical({'seq': seq, 'event': event, 'payload': payload,
                             'at_ns': at_ns, 'previous': previous})
        return hmac.new(self._key, record.encode('utf-8'), hashlib.sha256).hexdigest()

    def append(self, event: str, payload: dict) -> dict:
        if not isinstance(event, str) or not 1 <= len(event) <= 128:
            raise ValueError('Event name must contain 1..128 characters')
        if not isinstance(payload, dict):
            raise ValueError('Audit payload must be a JSON object')
        try:
            encoded = _canonical(payload)
        except (TypeError, ValueError) as exc:
            raise ValueError('Audit payload must be JSON serializable') from exc
        if len(encoded.encode('utf-8')) > 1_000_000:
            raise ValueError('Audit payload exceeds 1 MB')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT seq,digest FROM ledger ORDER BY seq DESC LIMIT 1').fetchone()
            seq = (row[0] + 1) if row else 1
            previous = row[1] if row else self.GENESIS
            at_ns = time.time_ns()
            digest = self._digest(seq, event, encoded, at_ns, previous)
            db.execute('INSERT INTO ledger VALUES(?,?,?,?,?,?)',
                       (seq, event, encoded, at_ns, previous, digest))
        return {'seq': seq, 'digest': digest, 'previous': previous}

    def events(self):
        with self._db() as db:
            rows = db.execute('SELECT seq,event,payload,at_ns,previous,digest FROM ledger ORDER BY seq').fetchall()
        return [{'seq': r[0], 'event': r[1], 'payload': json.loads(r[2]),
                 'at_ns': r[3], 'previous': r[4], 'digest': r[5]} for r in rows]

    def verify(self) -> dict:
        previous = self.GENESIS
        count = 0
        with self._db() as db:
            for seq, event, payload, at_ns, prior, digest in db.execute(
                    'SELECT seq,event,payload,at_ns,previous,digest FROM ledger ORDER BY seq'):
                count += 1
                expected = self._digest(seq, event, payload, at_ns, prior)
                if seq != count or prior != previous or not hmac.compare_digest(expected, digest):
                    raise LedgerIntegrityError(f'Audit chain invalid at sequence {seq}')
                previous = digest
        return {'valid': True, 'records': count, 'head': previous,
                'algorithm': 'HMAC-SHA256'}


def load_or_create_key(path: Path) -> bytes:
    """Create a private 256-bit key once, using exclusive creation and no symlink traversal."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        fd = None
    if fd is not None:
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(os.urandom(32))
                f.flush()
                os.fsync(f.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
    if path.is_symlink():
        raise ValueError('Audit key cannot be a symbolic link')
    if os.name != 'nt' and path.stat().st_mode & 0o077:
        raise ValueError('Audit key must not be group/world accessible')
    key = path.read_bytes()
    if len(key) != 32:
        raise ValueError('Audit key must contain exactly 32 bytes')
    return key
