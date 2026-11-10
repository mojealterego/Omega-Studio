"""Bounded block cache and deterministic phase sketch for large local files.

"Holographic" refers only to an optional compact content sketch. This module
cannot eliminate storage latency or exceed device filesystem capacity.
"""
from __future__ import annotations
from collections import OrderedDict
import hashlib
import os
from pathlib import Path


class HolographicMemoryWeaver:
    def __init__(self, path: str | Path, *, block_size: int = 1024 * 1024,
                 cache_blocks: int = 4):
        if not 4096 <= block_size <= 16 * 1024 * 1024 or not 1 <= cache_blocks <= 128:
            raise ValueError('Invalid bounded-cache configuration')
        self.path = Path(path)
        self.block_size = block_size
        self.cache_blocks = cache_blocks
        self._fd: int | None = None
        self._snapshot: tuple[int, ...] | None = None
        self._cache: OrderedDict[int, bytes] = OrderedDict()
        self.size = 0

    @property
    def cached_blocks(self) -> int:
        return len(self._cache)

    def __enter__(self):
        if self._fd is not None:
            raise RuntimeError('Weaver already opened')
        fd = os.open(self.path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        self._fd = fd
        self._snapshot = self._identity(os.fstat(fd))
        self.size = os.fstat(fd).st_size
        return self

    def __exit__(self, *_):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        self._cache.clear()
        self._snapshot = None

    @staticmethod
    def _identity(s: os.stat_result) -> tuple[int, ...]:
        return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns

    def _check(self) -> int:
        if self._fd is None:
            raise RuntimeError('Weaver is closed')
        if self._identity(os.fstat(self._fd)) != self._snapshot:
            self._cache.clear()
            raise OSError('File changed while reading; cache invalidated')
        return self._fd

    def _block(self, index: int) -> bytes:
        fd = self._check()
        if index not in self._cache:
            data = os.pread(fd, self.block_size, index * self.block_size)
            self._cache[index] = data
            if len(self._cache) > self.cache_blocks:
                self._cache.popitem(last=False)
        self._cache.move_to_end(index)
        return self._cache[index]

    def read_at(self, offset: int, length: int) -> bytes:
        if not isinstance(offset, int) or not isinstance(length, int) or offset < 0 or length < 0:
            raise ValueError('Invalid offset or length')
        if length > self.block_size:
            raise ValueError('Read exceeds configured block bound')
        self._check()
        if offset >= self.size or length == 0:
            return b''
        end = min(self.size, offset + length)
        result = bytearray()
        while offset < end:
            block = self._block(offset // self.block_size)
            start = offset % self.block_size
            amount = min(len(block) - start, end - offset)
            if amount <= 0:
                raise OSError('Unexpected end of file')
            result.extend(block[start:start + amount])
            offset += amount
        return bytes(result)

    def phase_sketch(self, block_index: int) -> bytes:
        if not isinstance(block_index, int) or block_index < 0:
            raise ValueError('Invalid block index')
        if block_index * self.block_size >= self.size:
            raise ValueError('Block index outside file')
        return hashlib.sha256(self._block(block_index)).digest()
