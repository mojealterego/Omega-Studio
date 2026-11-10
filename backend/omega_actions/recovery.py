"""Transactional at-least-once work queue with fenced leases and idempotent results."""
from __future__ import annotations
import json
from pathlib import Path
import sqlite3
import time


class DurableLeaseQueue:
    """Leases fence stale workers; consumers must make external effects idempotent."""
    def __init__(self, path: Path, max_attempts: int = 3):
        if not 1 <= max_attempts <= 100:
            raise ValueError('Invalid maximum attempts')
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_attempts = max_attempts
        with self._db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS work(
                id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL,
                attempts INTEGER NOT NULL, owner TEXT, lease_until INTEGER,
                created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, result TEXT)''')
            db.execute('CREATE INDEX IF NOT EXISTS work_status ON work(status,created_at)')

    def _db(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.execute('PRAGMA busy_timeout=20000')
        db.execute('PRAGMA journal_mode=WAL')
        return db

    def submit(self, job_id: str, payload: dict, *, now: int | None = None) -> bool:
        if not isinstance(job_id, str) or not 1 <= len(job_id) <= 128 or not isinstance(payload, dict):
            raise ValueError('Invalid job id or payload')
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode('utf-8')) > 1024 * 1024:
            raise ValueError('Work payload exceeds 1 MB')
        now = int(time.time()) if now is None else int(now)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM work WHERE id=?', (job_id,)).fetchone()
            if row:
                if row[0] != encoded:
                    raise ValueError('Idempotency key collision with different payload')
                return False
            db.execute('INSERT INTO work VALUES(?,?,?,?,?,?,?,?,?)',
                       (job_id, encoded, 'queued', 0, None, None, now, now, None))
        return True

    def claim(self, worker: str, *, now: int | None = None, lease_seconds: int = 30) -> dict | None:
        if not isinstance(worker, str) or not 1 <= len(worker) <= 128 or not 1 <= lease_seconds <= 86400:
            raise ValueError('Invalid worker or lease')
        now = int(time.time()) if now is None else int(now)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT id,payload,attempts FROM work WHERE status=? ORDER BY created_at,id LIMIT 1', ('queued',)).fetchone()
            if row is None:
                return None
            job_id, payload, attempts = row
            db.execute('UPDATE work SET status=?,attempts=?,owner=?,lease_until=?,updated_at=? WHERE id=?',
                       ('running', attempts + 1, worker, now + lease_seconds, now, job_id))
        return {'id': job_id, 'payload': json.loads(payload), 'attempts': attempts + 1,
                'lease_until': now + lease_seconds}

    def heartbeat(self, job_id: str, worker: str, *, now: int | None = None, lease_seconds: int = 30) -> bool:
        now = int(time.time()) if now is None else int(now)
        with self._db() as db:
            changed = db.execute('UPDATE work SET lease_until=?,updated_at=? WHERE id=? AND status=? AND owner=? AND lease_until>?',
                                 (now + lease_seconds, now, job_id, 'running', worker, now)).rowcount
        return bool(changed)

    def complete(self, job_id: str, worker: str, result: dict, *, now: int | None = None) -> bool:
        now = int(time.time()) if now is None else int(now)
        encoded = json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False)
        with self._db() as db:
            changed = db.execute('UPDATE work SET status=?,result=?,owner=NULL,lease_until=NULL,updated_at=? WHERE id=? AND status=? AND owner=? AND lease_until>?',
                                 ('succeeded', encoded, now, job_id, 'running', worker, now)).rowcount
        return bool(changed)

    def fail(self, job_id: str, worker: str, *, now: int | None = None) -> bool:
        now = int(time.time()) if now is None else int(now)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT attempts,lease_until FROM work WHERE id=? AND status=? AND owner=?',
                             (job_id, 'running', worker)).fetchone()
            if not row or row[1] <= now:
                return False
            status = 'failed' if row[0] >= self.max_attempts else 'queued'
            db.execute('UPDATE work SET status=?,owner=NULL,lease_until=NULL,updated_at=? WHERE id=?',
                       (status, now, job_id))
        return True

    def recover(self, *, now: int | None = None) -> int:
        now = int(time.time()) if now is None else int(now)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            exhausted = db.execute('UPDATE work SET status=?,owner=NULL,lease_until=NULL,updated_at=? WHERE status=? AND lease_until<=? AND attempts>=?',
                                   ('failed', now, 'running', now, self.max_attempts)).rowcount
            retryable = db.execute('UPDATE work SET status=?,owner=NULL,lease_until=NULL,updated_at=? WHERE status=? AND lease_until<=? AND attempts<?',
                                   ('queued', now, 'running', now, self.max_attempts)).rowcount
        return exhausted + retryable

    def result(self, job_id: str) -> dict | None:
        with self._db() as db:
            row = db.execute('SELECT status,attempts,result FROM work WHERE id=?', (job_id,)).fetchone()
        return None if row is None else {'status': row[0], 'attempts': row[1],
                                        'result': json.loads(row[2]) if row[2] else None}
