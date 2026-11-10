"""Versioned owner-signed exchange contract for future Digital-Life integration."""
from __future__ import annotations
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from pathlib import Path
import time


class ContractError(ValueError):
    """Invalid, expired, replayed or unauthorized envelope."""


def _canonical(obj: object) -> bytes:
    try:
        return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (ValueError, TypeError) as exc:
        raise ContractError('Invalid JSON payload') from exc


def negotiate_version(local: list[str], remote: list[str]) -> str:
    shared = set(local) & set(remote)
    if not shared or not all(re.fullmatch(r'\d+\.\d+', x) for x in shared):
        raise ContractError('No mutually supported protocol version')
    return max(shared, key=lambda x: tuple(map(int, x.split('.'))))


class ReplayGuard:
    """SQLite nonce store, transactional uniqueness per tenant and protocol."""
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS seen(
                tenant TEXT NOT NULL, nonce TEXT NOT NULL, expires_at INTEGER NOT NULL,
                PRIMARY KEY(tenant,nonce))''')

    def _db(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.execute('PRAGMA busy_timeout=20000')
        db.execute('PRAGMA journal_mode=WAL')
        return db

    def admit(self, tenant: str, nonce: str, *, now: int, expires_at: int) -> bool:
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM seen WHERE expires_at<?', (now,))
            try:
                db.execute('INSERT INTO seen VALUES(?,?,?)', (tenant, nonce, expires_at))
            except sqlite3.IntegrityError:
                return False
        return True


class SignedEnvelope:
    VERSION = '1.0'
    MAX_PAYLOAD = 256 * 1024
    MAX_TTL = 600
    _TOKEN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$')

    @classmethod
    def issue(cls, tenant: str, kind: str, payload: dict, *, key: bytes,
              now: int | None = None, ttl: int = 120, nonce: str | None = None) -> dict:
        if not isinstance(key, bytes) or len(key) < 32:
            raise ContractError('Signing key must be at least 32 bytes')
        if not isinstance(tenant, str) or not cls._TOKEN.fullmatch(tenant):
            raise ContractError('Invalid tenant identifier')
        if not isinstance(kind, str) or not cls._TOKEN.fullmatch(kind):
            raise ContractError('Invalid event kind')
        if not isinstance(payload, dict) or len(_canonical(payload)) > cls.MAX_PAYLOAD:
            raise ContractError('Payload exceeds size limit or is not an object')
        if not isinstance(ttl, int) or not 1 <= ttl <= cls.MAX_TTL:
            raise ContractError('Invalid message TTL')
        if nonce is None:
            nonce = secrets.token_hex(16)
        if not isinstance(nonce, str) or not re.fullmatch(r'[0-9a-f]{32}', nonce):
            raise ContractError('Invalid nonce')
        now = int(time.time()) if now is None else int(now)
        unsigned = {'version': cls.VERSION, 'tenant': tenant, 'kind': kind,
                    'payload': payload, 'issued_at': now, 'expires_at': now + ttl,
                    'nonce': nonce}
        unsigned['signature'] = hmac.new(key, _canonical(unsigned), hashlib.sha256).hexdigest()
        return unsigned

    @classmethod
    def verify(cls, envelope: dict, *, key: bytes, now: int | None = None,
               tenant: str, replay_guard: ReplayGuard | None = None) -> dict:
        if not isinstance(envelope, dict) or set(envelope) != {
                'version', 'tenant', 'kind', 'payload', 'issued_at', 'expires_at', 'nonce', 'signature'}:
            raise ContractError('Malformed envelope')
        if envelope['version'] != cls.VERSION:
            raise ContractError('Unsupported protocol version')
        if envelope['tenant'] != tenant:
            raise ContractError('Cross-tenant exchange denied')
        if not isinstance(envelope['kind'], str) or not cls._TOKEN.fullmatch(envelope['kind']):
            raise ContractError('Invalid event kind')
        if not isinstance(envelope['nonce'], str) or not re.fullmatch(r'[0-9a-f]{32}', envelope['nonce']):
            raise ContractError('Invalid nonce')
        if not isinstance(envelope['payload'], dict) or len(_canonical(envelope['payload'])) > cls.MAX_PAYLOAD:
            raise ContractError('Invalid payload')
        if not isinstance(envelope['issued_at'], int) or not isinstance(envelope['expires_at'], int):
            raise ContractError('Invalid timestamps')
        now = int(time.time()) if now is None else int(now)
        if now > envelope['expires_at'] or now < envelope['issued_at'] - 30 or not 1 <= envelope['expires_at'] - envelope['issued_at'] <= cls.MAX_TTL:
            raise ContractError('Message expired or outside time window')
        if not isinstance(key, bytes) or len(key) < 32:
            raise ContractError('Invalid verification key')
        sig = envelope['signature']
        if not isinstance(sig, str) or not re.fullmatch(r'[0-9a-f]{64}', sig):
            raise ContractError('Invalid signature encoding')
        unsigned = {k: v for k, v in envelope.items() if k != 'signature'}
        expected = hmac.new(key, _canonical(unsigned), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise ContractError('Invalid message signature')
        if replay_guard and not replay_guard.admit(tenant, envelope['nonce'], now=now,
                                                  expires_at=envelope['expires_at']):
            raise ContractError('Message replay rejected')
        return envelope['payload']
