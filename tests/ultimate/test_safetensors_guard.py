"""Strict, read-only safetensors validation: real files and hostile headers."""
import hashlib
import json
from pathlib import Path
import struct

import pytest

from omega_actions.ultimate.safetensors_guard import (
    SafetensorsValidationError,
    inspect_safetensors,
)


def _write_container(path: Path, entries: dict, payload: bytes) -> Path:
    header = json.dumps(entries, separators=(',', ':')).encode('utf-8')
    header += b' ' * (-len(header) % 8)
    path.write_bytes(struct.pack('<Q', len(header)) + header + payload)
    return path


def test_valid_mixed_dtype_tensor_layout_and_streaming_sha(tmp_path):
    payload = struct.pack('<2f', 0.25, -1.0) + b'\x80\x3f\x00\x00'  # 2 BF16
    path = _write_container(tmp_path / 'good.safetensors', {
        '__metadata__': {'origin': 'test-fixture'},
        'weights': {'dtype': 'F32', 'shape': [2], 'data_offsets': [0, 8]},
        'bias': {'dtype': 'BF16', 'shape': [2], 'data_offsets': [8, 12]},
    }, payload)
    report = inspect_safetensors(path, hash_file=True)
    assert report.tensor_count == 2
    assert report.payload_bytes == 12
    assert report.file_bytes == path.stat().st_size
    assert report.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert report.metadata == {'origin': 'test-fixture'}
    assert [(t.name, t.dtype, t.shape) for t in report.tensors] == [
        ('weights', 'F32', (2,)), ('bias', 'BF16', (2,))]


def test_accepts_empty_tensors_without_gap(tmp_path):
    path = _write_container(tmp_path / 'empty.safetensors', {
        'zero': {'dtype': 'F32', 'shape': [0, 3], 'data_offsets': [0, 0]},
        'scalar': {'dtype': 'U8', 'shape': [], 'data_offsets': [0, 1]},
    }, b'\x01')
    report = inspect_safetensors(path)
    assert report.tensor_count == 2
    assert report.sha256 is None


@pytest.mark.parametrize('entries,payload', [
    ({'w': {'dtype': 'F32', 'shape': [2], 'data_offsets': [0, 4]}}, b'\0' * 4),  # wrong byte count
    ({'w': {'dtype': 'BOGUS', 'shape': [1], 'data_offsets': [0, 4]}}, b'\0' * 4),
    ({'w': {'dtype': 'F32', 'shape': [-1], 'data_offsets': [0, 4]}}, b'\0' * 4),
    ({'w': {'dtype': 'F32', 'shape': [True], 'data_offsets': [0, 4]}}, b'\0' * 4),
    ({'w': {'dtype': 'F32', 'shape': [1], 'data_offsets': [1, 5]}}, b'\0' * 5),
    ({'w': {'dtype': 'F32', 'shape': [1], 'data_offsets': [0, 4]},
      'x': {'dtype': 'F32', 'shape': [1], 'data_offsets': [2, 6]}}, b'\0' * 6),
    ({'w': {'dtype': 'F32', 'shape': [1], 'data_offsets': [0, 4]}}, b'\0' * 8),  # trailing unindexed
    ({'__metadata__': {'not-a-string': 5}}, b''),
])
def test_rejects_invalid_tensor_headers(tmp_path, entries, payload):
    path = _write_container(tmp_path / 'bad.safetensors', entries, payload)
    with pytest.raises(SafetensorsValidationError):
        inspect_safetensors(path)


def test_rejects_duplicate_json_tensor_keys(tmp_path):
    header = (b'{"w":{"dtype":"F32","shape":[1],"data_offsets":[0,4]},'
              b'"w":{"dtype":"F32","shape":[1],"data_offsets":[0,4]}}')
    header += b' ' * (-len(header) % 8)
    path = tmp_path / 'dupe.safetensors'
    path.write_bytes(struct.pack('<Q', len(header)) + header + b'\0' * 4)
    with pytest.raises(SafetensorsValidationError, match='Duplicate'):
        inspect_safetensors(path)


def test_rejects_truncated_or_oversized_header(tmp_path):
    path = tmp_path / 'bad.safetensors'
    path.write_bytes(struct.pack('<Q', 1 << 30) + b'{}')
    with pytest.raises(SafetensorsValidationError):
        inspect_safetensors(path, max_header_bytes=1024)
    path.write_bytes(b'123')
    with pytest.raises(SafetensorsValidationError):
        inspect_safetensors(path)


def test_rejects_symlink_to_prevent_untrusted_path_redirection(tmp_path):
    target = _write_container(tmp_path / 'target.safetensors', {
        'w': {'dtype': 'U8', 'shape': [1], 'data_offsets': [0, 1]}
    }, b'\x00')
    link = tmp_path / 'link.safetensors'
    link.symlink_to(target)
    with pytest.raises(SafetensorsValidationError):
        inspect_safetensors(link)


