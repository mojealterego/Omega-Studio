"""Tests of bounded JSON ingestion without executing the CLI as a subprocess."""
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from verify_ztf_intake import _read_bounded_object


def test_reject_duplicate_json_keys(tmp_path):
    p = tmp_path / 'm.json'
    p.write_text('{"base":"x", "base":"y"}', encoding='utf-8')
    with pytest.raises(ValueError, match='Duplicate'):
        _read_bounded_object(p)


def test_reject_nan_and_oversize(tmp_path):
    p = tmp_path / 'm.json'
    p.write_text('{"x": NaN}', encoding='utf-8')
    with pytest.raises(ValueError, match='Non-finite'):
        _read_bounded_object(p)
    p.write_bytes(b'x'*101)
    with pytest.raises(ValueError, match='too large'):
        _read_bounded_object(p, max_bytes=100)
