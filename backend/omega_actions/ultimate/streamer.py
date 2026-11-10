"""Bounded mmap reader and kernel-assisted file copier for large local assets."""
from __future__ import annotations
import hashlib
import mmap
import os
from pathlib import Path
import tempfile


class WindowedReader:
    """Random access to arbitrarily large addressable files with bounded mapping size.

    Memory mapping consumes at most ``window_size + mmap.ALLOCATIONGRANULARITY``
    virtual address space per read; it cannot remove filesystem latency or disk limits.
    """
    def __init__(self, path: str | Path, window_size: int = 1024 * 1024):
        if not 4096 <= window_size <= 64 * 1024 * 1024:
            raise ValueError('window_size must be between 4 KiB and 64 MiB')
        self.path = Path(path)
        self.window_size = window_size
        self._fd = None
        self.size = 0

    def __enter__(self) -> 'WindowedReader':
        if self._fd is not None:
            raise RuntimeError('Reader already open')
        self._fd = os.open(self.path, os.O_RDONLY)
        self.size = os.fstat(self._fd).st_size
        return self

    def __exit__(self, *_):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def read_at(self, offset: int, length: int) -> bytes:
        if self._fd is None:
            raise RuntimeError('Reader is closed')
        if offset < 0 or length < 0 or length > self.window_size:
            raise ValueError('Invalid offset or requested read exceeds memory bound')
        if offset >= self.size or length == 0:
            return b''
        length = min(length, self.size - offset)
        gran = mmap.ALLOCATIONGRANULARITY
        aligned = offset - offset % gran
        shift = offset - aligned
        with mmap.mmap(self._fd, shift + length, access=mmap.ACCESS_READ, offset=aligned) as view:
            return view[shift:shift + length]

    def iter_chunks(self):
        if self._fd is None:
            raise RuntimeError('Reader is closed')
        for offset in range(0, self.size, self.window_size):
            yield self.read_at(offset, min(self.window_size, self.size - offset))

    def digest(self) -> str:
        h = hashlib.sha256()
        for part in self.iter_chunks():
            h.update(part)
        return h.hexdigest()


def copy_file(source: str | Path, destination: str | Path, chunk_size: int = 1024 * 1024) -> dict:
    """Atomic bounded-memory copy; use sendfile when supported, verify SHA-256."""
    if not 512 <= chunk_size <= 64 * 1024 * 1024:
        raise ValueError('Invalid chunk_size')
    src = Path(source).resolve(strict=True)
    dst = Path(destination).resolve(strict=False)
    if src == dst:
        raise ValueError('Source and destination must differ')
    dst.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with src.open('rb') as input_file, tempfile.NamedTemporaryFile(dir=dst.parent, prefix='.omega-copy-', delete=False) as output:
            temp_name = Path(output.name)
            size = os.fstat(input_file.fileno()).st_size
            offset = 0
            if hasattr(os, 'sendfile'):
                while offset < size:
                    count = os.sendfile(output.fileno(), input_file.fileno(), offset, min(chunk_size, size-offset))
                    if count <= 0:
                        raise OSError('sendfile stopped before EOF')
                    offset += count
            else:
                while True:
                    block = input_file.read(chunk_size)
                    if not block:
                        break
                    output.write(block)
                    offset += len(block)
            output.flush()
            os.fsync(output.fileno())
        with WindowedReader(src, window_size=max(4096, chunk_size)) as reader:
            expected = reader.digest()
        with WindowedReader(temp_name, window_size=max(4096, chunk_size)) as reader:
            actual = reader.digest()
        if expected != actual:
            raise IOError('SHA-256 verification failed')
        os.replace(temp_name, dst)
        temp_name = None
        return {'bytes': offset, 'sha256': actual, 'destination': str(dst)}
    finally:
        if temp_name is not None:
            temp_name.unlink(missing_ok=True)
