"""Disk-backed block fingerprints and bounded random-access reads.

Spectral phase fingerprints are diagnostic. This design cannot eliminate I/O
latency or surpass physical storage limits; SHA-256 verifies block integrity.
"""
from __future__ import annotations
import hashlib
import math
from pathlib import Path
import sqlite3
from .streamer import WindowedReader


class HolographicMemoryWeaver:
    def __init__(self, index_path: Path, *, block_size: int = 65536):
        if not 4096 <= block_size <= 4 * 1024 * 1024:
            raise ValueError('Invalid block size')
        self.index_path = Path(index_path)
        self.block_size = block_size

    @staticmethod
    def _phase(block_digest: bytes) -> str:
        # Bounded spectral sketch of 32 digest bytes, independent of file size.
        real = sum(byte * math.cos(2 * math.pi * i / 32) for i, byte in enumerate(block_digest))
        imag = sum(byte * math.sin(2 * math.pi * i / 32) for i, byte in enumerate(block_digest))
        return f'{math.atan2(imag, real):.9f}'

    def _connect(self) -> sqlite3.Connection:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.index_path, timeout=10)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL, block_size INTEGER NOT NULL, sha256 TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS blocks (path TEXT NOT NULL, number INTEGER NOT NULL, sha256 TEXT NOT NULL, phase TEXT NOT NULL, PRIMARY KEY(path, number))')
        return db

    @staticmethod
    def _checked(path: Path) -> tuple[Path, object]:
        if path.is_symlink() or not path.is_file():
            raise ValueError('File must be a regular non-symlink file')
        resolved = path.resolve(strict=True)
        return resolved, resolved.stat()

    def index(self, source: Path) -> dict:
        source, before = self._checked(Path(source))
        digest = hashlib.sha256()
        records = 0
        with self._connect() as db:
            with db:
                db.execute('DELETE FROM blocks WHERE path=?', (str(source),))
                with WindowedReader(source, window_size=self.block_size) as reader:
                    for number, block in enumerate(reader.iter_chunks()):
                        block_digest = hashlib.sha256(block).digest()
                        digest.update(block)
                        db.execute('INSERT INTO blocks VALUES (?,?,?,?)',
                                   (str(source), number, block_digest.hex(), self._phase(block_digest)))
                        records += 1
                after = source.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError('Source changed during indexing')
                db.execute('INSERT OR REPLACE INTO files VALUES (?,?,?,?,?)',
                           (str(source), before.st_size, before.st_mtime_ns, self.block_size, digest.hexdigest()))
        return {'blocks': records, 'bytes': before.st_size, 'sha256': digest.hexdigest(),
                'index': str(self.index_path), 'method': 'disk-backed-block-hash-and-phase'}

    def read_verified(self, source: Path, offset: int, length: int) -> bytes:
        if not isinstance(offset, int) or not isinstance(length, int) or offset < 0 or not 0 <= length <= 1024 * 1024:
            raise ValueError('Invalid read request')
        source, before = self._checked(Path(source))
        with self._connect() as db:
            meta = db.execute('SELECT size,mtime_ns,block_size FROM files WHERE path=?', (str(source),)).fetchone()
            if not meta or (before.st_size, before.st_mtime_ns, self.block_size) != tuple(meta):
                raise ValueError('Source changed or index absent')
            if offset >= before.st_size or length == 0:
                return b''
            end = min(before.st_size, offset + length)
            start_block = offset // self.block_size
            end_block = (end - 1) // self.block_size
            chunks = []
            with WindowedReader(source, window_size=self.block_size) as reader:
                for number in range(start_block, end_block + 1):
                    block = reader.read_at(number * self.block_size, self.block_size)
                    row = db.execute('SELECT sha256 FROM blocks WHERE path=? AND number=?', (str(source), number)).fetchone()
                    if not row or hashlib.sha256(block).hexdigest() != row[0]:
                        raise ValueError('Block integrity mismatch')
                    chunks.append(block[max(offset - number * self.block_size, 0):
                                        min(end - number * self.block_size, len(block))])
            after = source.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError('Source changed during read')
            return b''.join(chunks)
