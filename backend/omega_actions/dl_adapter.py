"""Fail-closed Digital-Life local contract adapter and reversible migration journal."""
from __future__ import annotations
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
import time
from .dl_contract import SignedEnvelope, ReplayGuard, ContractError, negotiate_version


class MigrationError(RuntimeError):
    """Invalid migration state or owner authorization."""


class DigitalLifeAdapter:
    """Encode and decode authenticated local messages; performs no external I/O."""
    CAPABILITIES = {
        'ci.request': {'workflow': str, 'workspace': str},
        'ci.result': {'run_id': str, 'status': str},
        'model.metadata': {'name': str, 'sha256': str, 'format': str},
        'research.summary': {'subject': str, 'digest': str},
    }

    def __init__(self, tenant: str, *, key: bytes, replay_path: Path):
        self.tenant = tenant
        self.key = key
        self.guard = ReplayGuard(replay_path)

    @classmethod
    def _validate(cls, capability: str, data: dict) -> None:
        schema = cls.CAPABILITIES.get(capability)
        if schema is None:
            raise ContractError('Capability is not allowlisted')
        if not isinstance(data, dict) or set(data) != set(schema):
            raise ContractError('Invalid capability data fields')
        for field, typ in schema.items():
            if not isinstance(data[field], typ) or not 1 <= len(data[field]) <= 4096:
                raise ContractError('Invalid capability field')
        if capability == 'ci.result' and data['status'] not in ('success', 'failure', 'cancelled'):
            raise ContractError('Invalid CI result state')
        if capability == 'model.metadata' and (not re.fullmatch(r'[0-9a-f]{64}', data['sha256']) or
                                                data['format'] != 'gguf'):
            raise ContractError('Invalid model integrity metadata')
        if capability == 'research.summary' and not re.fullmatch(r'[0-9a-f]{64}', data['digest']):
            raise ContractError('Invalid research digest')

    def encode(self, capability: str, data: dict, *, now: int | None = None,
               nonce: str | None = None) -> dict:
        self._validate(capability, data)
        return SignedEnvelope.issue(self.tenant, 'omega.studio.exchange.v1',
                                    {'capability': capability, 'data': data},
                                    key=self.key, now=now, nonce=nonce)

    def decode(self, envelope: dict, *, now: int | None = None) -> dict:
        data = SignedEnvelope.verify(envelope, key=self.key, tenant=self.tenant,
                                     now=now, replay_guard=self.guard)
        if set(data) != {'capability', 'data'}:
            raise ContractError('Invalid exchange body')
        self._validate(data['capability'], data['data'])
        return data


class MigrationJournal:
    """SQLite two-phase admission; activation changes only local migration metadata."""
    _IDENTIFIER = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$')

    def __init__(self, path: Path, *, key: bytes):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError('Owner authorization key must contain at least 32 bytes')
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.key = key
        with self._db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS migrations (
                profile TEXT PRIMARY KEY, source TEXT NOT NULL, target TEXT NOT NULL,
                digest TEXT NOT NULL, phase TEXT NOT NULL, updated_at INTEGER NOT NULL)''')

    def _db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA busy_timeout=30000')
        return db

    def _record(self, profile: str) -> dict:
        with self._db() as db:
            row = db.execute('SELECT source,target,digest,phase,updated_at FROM migrations WHERE profile=?',
                             (profile,)).fetchone()
        if row is None:
            raise MigrationError('Unknown migration profile')
        return {'profile': profile, 'source': row[0], 'target': row[1],
                'digest': row[2], 'phase': row[3], 'updated_at': row[4]}

    def plan(self, profile: str, source: str, target: str, *, digest: str) -> dict:
        if not isinstance(profile, str) or not self._IDENTIFIER.fullmatch(profile):
            raise MigrationError('Invalid profile name')
        if not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise MigrationError('Invalid artifact SHA-256')
        if not re.fullmatch(r'\d+\.\d+', source) or not re.fullmatch(r'\d+\.\d+', target) or source == target:
            raise MigrationError('Invalid source/target protocol versions')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                db.execute('INSERT INTO migrations VALUES(?,?,?,?,?,?)',
                           (profile, source, target, digest, 'planned', int(time.time())))
            except sqlite3.IntegrityError as exc:
                raise MigrationError('Migration profile already exists') from exc
        return self._record(profile)

    def _transition(self, profile: str, expected: str, target: str) -> dict:
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            changed = db.execute('UPDATE migrations SET phase=?,updated_at=? WHERE profile=? AND phase=?',
                                 (target, int(time.time()), profile, expected)).rowcount
            if changed != 1:
                raise MigrationError(f'Migration transition {expected} -> {target} denied')
        return self._record(profile)

    def start_shadow(self, profile: str) -> dict:
        return self._transition(profile, 'planned', 'shadow')

    def approval_token(self, profile: str) -> str:
        record = self._record(profile)
        if record['phase'] != 'shadow':
            raise MigrationError('Only shadow migrations can request approval')
        material = json.dumps([record[k] for k in ('profile', 'source', 'target', 'digest')],
                              separators=(',', ':')).encode('utf-8')
        return hmac.new(self.key, material, hashlib.sha256).hexdigest()

    def approve(self, profile: str, token: str) -> dict:
        if not isinstance(token, str) or not hmac.compare_digest(token, self.approval_token(profile)):
            raise MigrationError('Invalid owner approval token')
        return self._transition(profile, 'shadow', 'approved')

    def activate(self, profile: str) -> dict:
        return self._transition(profile, 'approved', 'active')

    def rollback(self, profile: str) -> dict:
        return self._transition(profile, 'active', 'rolled_back')
