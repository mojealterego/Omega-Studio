"""Read-only safetensors container validator and optional streaming SHA-256.

The validator never reconstructs weights from text or rewrites model files.
It checks exact tensor shapes, dtypes, offsets, coverage and duplicate JSON keys.
It does not prove that an adapter is semantically compatible with a base model.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
from typing import Any


class SafetensorsValidationError(ValueError):
    """The file does not satisfy the bounded safetensors container contract."""


_DTYPE_BYTES: dict[str, int] = {
    'BOOL': 1, 'U8': 1, 'I8': 1,
    'F8_E4M3FN': 1, 'F8_E5M2': 1, 'F8_E4M3FNUZ': 1, 'F8_E5M2FNUZ': 1,
    'F16': 2, 'BF16': 2, 'U16': 2, 'I16': 2,
    'F32': 4, 'U32': 4, 'I32': 4,
    'F64': 8, 'U64': 8, 'I64': 8,
}


@dataclass(frozen=True, slots=True)
class TensorRecord:
    name: str
    dtype: str
    shape: tuple[int, ...]
    start: int
    end: int

    @property
    def byte_length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class SafetensorsReport:
    file_bytes: int
    header_bytes: int
    payload_bytes: int
    tensors: tuple[TensorRecord, ...]
    metadata: dict[str, str]
    sha256: str | None

    @property
    def tensor_count(self) -> int:
        return len(self.tensors)


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise SafetensorsValidationError(f'Duplicate JSON object key: {key!r}')
        obj[key] = value
    return obj


def _reject_constant(value: str) -> None:
    raise SafetensorsValidationError(f'Non-finite JSON constant: {value}')


def _parse_header(header: bytes, payload_bytes: int, max_tensors: int) -> tuple[tuple[TensorRecord, ...], dict[str, str]]:
    if not header.startswith(b'{'):
        raise SafetensorsValidationError('Header must start with a JSON object')
    try:
        data = json.loads(header.decode('utf-8'), object_pairs_hook=_unique_json_object,
                          parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise SafetensorsValidationError('Malformed JSON header') from exc
    if not isinstance(data, dict):
        raise SafetensorsValidationError('Header must be a JSON object')
    metadata = data.pop('__metadata__', {})
    if not isinstance(metadata, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in metadata.items()
    ):
        raise SafetensorsValidationError('__metadata__ must map strings to strings')
    if len(data) > max_tensors:
        raise SafetensorsValidationError('Tensor count exceeds max_tensors')

    tensors: list[TensorRecord] = []
    for name, entry in data.items():
        if not name or not isinstance(entry, dict) or set(entry) != {'dtype', 'shape', 'data_offsets'}:
            raise SafetensorsValidationError(f'Invalid tensor descriptor for {name!r}')
        dtype = entry['dtype']
        shape = entry['shape']
        offsets = entry['data_offsets']
        if not isinstance(dtype, str) or dtype not in _DTYPE_BYTES:
            raise SafetensorsValidationError(f'Unsupported tensor dtype for {name!r}')
        if not isinstance(shape, list) or any(type(d) is not int or d < 0 for d in shape):
            raise SafetensorsValidationError(f'Invalid tensor shape for {name!r}')
        if (not isinstance(offsets, list) or len(offsets) != 2
                or any(type(n) is not int for n in offsets)):
            raise SafetensorsValidationError(f'Invalid offsets for {name!r}')
        start, end = offsets
        if start < 0 or end < start or end > payload_bytes:
            raise SafetensorsValidationError(f'Tensor {name!r} is outside the payload')
        elements = 1
        for dim in shape:
            elements *= dim
            if elements * _DTYPE_BYTES[dtype] > payload_bytes:
                raise SafetensorsValidationError(f'Tensor {name!r} exceeds payload size')
        if (end - start) != elements * _DTYPE_BYTES[dtype]:
            raise SafetensorsValidationError(f'Byte count does not match shape for {name!r}')
        tensors.append(TensorRecord(name, dtype, tuple(shape), start, end))

    # The safetensors payload is entirely indexed; overlapping or unindexed bytes
    # are not silently accepted. Zero-byte tensors can share a boundary.
    cursor = 0
    for tensor in sorted(tensors, key=lambda t: (t.start, t.end)):
        if tensor.start != cursor:
            raise SafetensorsValidationError('Overlapping or unindexed tensor payload')
        cursor = tensor.end
    if cursor != payload_bytes:
        raise SafetensorsValidationError('Trailing unindexed bytes in payload')
    return tuple(tensors), metadata


def inspect_safetensors(
    path: str | os.PathLike[str], *, hash_file: bool = False,
    max_header_bytes: int = 16 * 1024 * 1024, max_tensors: int = 100_000,
) -> SafetensorsReport:
    """Validate a local regular file without loading tensor data into memory.

    Optional SHA-256 is computed with a bounded streaming buffer. A symlink is
    refused to avoid redirection through untrusted model-cache paths.
    """
    if (type(max_header_bytes) is not int or max_header_bytes < 8
            or type(max_tensors) is not int or max_tensors <= 0):
        raise SafetensorsValidationError('Invalid inspection resource limits')
    target = Path(path)
    try:
        before = target.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise SafetensorsValidationError('Path must be a regular, non-symlink file')
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(target, flags)
    except OSError as exc:
        raise SafetensorsValidationError('Cannot open the model file safely') from exc
    try:
        with os.fdopen(fd, 'rb') as source:
            current = os.fstat(source.fileno())
            if not stat.S_ISREG(current.st_mode) or (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
                raise SafetensorsValidationError('File changed between validation and open')
            if current.st_size < 10:
                raise SafetensorsValidationError('File is too small for a safetensors header')
            prefix = source.read(8)
            if len(prefix) != 8:
                raise SafetensorsValidationError('Truncated header length')
            header_bytes = struct.unpack('<Q', prefix)[0]
            if header_bytes < 2 or header_bytes > max_header_bytes or header_bytes % 8:
                raise SafetensorsValidationError('Invalid or excessive safetensors header length')
            if header_bytes > current.st_size - 8:
                raise SafetensorsValidationError('Truncated JSON header')
            header = source.read(header_bytes)
            if len(header) != header_bytes:
                raise SafetensorsValidationError('Truncated JSON header')
            payload_bytes = current.st_size - 8 - header_bytes
            tensors, metadata = _parse_header(header, payload_bytes, max_tensors)
            digest = None
            if hash_file:
                source.seek(0)
                hasher = hashlib.sha256()
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    hasher.update(chunk)
                digest = hasher.hexdigest()
            after = os.fstat(source.fileno())
            if (current.st_size, current.st_mtime_ns, current.st_ino) != (
                after.st_size, after.st_mtime_ns, after.st_ino
            ):
                raise SafetensorsValidationError('File changed during inspection')
            return SafetensorsReport(current.st_size, header_bytes, payload_bytes, tensors, metadata, digest)
    except OSError as exc:
        raise SafetensorsValidationError('I/O error during safetensors inspection') from exc
