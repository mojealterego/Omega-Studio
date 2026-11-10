"""Bounded GGUF header inspection; not a full model integrity validator."""

from pathlib import Path
import struct


class GGUFError(ValueError):
    """Invalid or unsupported GGUF header."""


def inspect_gguf(path: str | Path) -> dict[str, int]:
    """Read only the fixed 24-byte GGUF v2/v3 header.

    Does not parse metadata, tensor offsets or verify model completeness.
    """
    with Path(path).open('rb') as stream:
        header = stream.read(24)
    if len(header) != 24:
        raise GGUFError('truncated GGUF header')
    if header[:4] != b'GGUF':
        raise GGUFError('invalid GGUF magic')
    version, tensors, metadata = struct.unpack('<IQQ', header[4:])
    if version not in (2, 3):
        raise GGUFError('unsupported GGUF version')
    if tensors > 10_000_000 or metadata > 10_000_000:
        raise GGUFError('GGUF count exceeds inspection limit')
    return {'version': version, 'tensor_count': tensors, 'metadata_count': metadata}
