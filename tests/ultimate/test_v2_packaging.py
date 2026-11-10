"""Deterministic ZIP packaging, checksum verification and tamper rejection."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import zipfile
import pytest
from tools import package_v2


def _fixture(tmp_path: Path, monkeypatch):
    root = tmp_path/'project'
    root.mkdir()
    (root/'README.md').write_text('OMEGA v2\n')
    (root/'third_party').mkdir()
    src = tmp_path/'uploads'
    src.mkdir()
    with zipfile.ZipFile(src/'upstream.zip','w') as z:
        z.writestr('src/LICENSE','MIT\n')
    digest = hashlib.sha256((src/'upstream.zip').read_bytes()).hexdigest()
    (root/'third_party/UPLOADED_SOURCE_ARCHIVES.json').write_text(json.dumps({
        'archives':[{'archive':'upstream.zip','sha256':digest}]}))
    monkeypatch.setattr(package_v2,'ROOT',root)
    monkeypatch.setattr(package_v2,'ARCHIVES',('upstream.zip',))
    return root,src


def test_v2_package_deterministic_and_verifiable(tmp_path: Path, monkeypatch):
    root,src = _fixture(tmp_path,monkeypatch)
    first = package_v2.package(tmp_path/'a.zip',src)
    second = package_v2.package(tmp_path/'b.zip',src)
    assert first['crc'] == 'PASS'
    assert first['sha256'] == second['sha256']
    with zipfile.ZipFile(tmp_path/'a.zip') as z:
        names=z.namelist()
        assert 'OMEGA_STUDIO_ULTIMATE_v2.0.0/README.md' in names
        assert 'OMEGA_STUDIO_ULTIMATE_v2.0.0/third_party/source_archives/upstream.zip' in names
        manifest=z.read('OMEGA_STUDIO_ULTIMATE_v2.0.0/MANIFEST_SHA256.txt').decode()
        assert hashlib.sha256(b'OMEGA v2\n').hexdigest() in manifest


def test_v2_package_rejects_changed_upstream_and_existing_output(tmp_path: Path, monkeypatch):
    root,src = _fixture(tmp_path,monkeypatch)
    (src/'upstream.zip').write_bytes(b'tampered')
    with pytest.raises(ValueError,match='SHA-256 mismatch'):
        package_v2.package(tmp_path/'bad.zip',src)
    (tmp_path/'existing.zip').write_bytes(b'old')
    with pytest.raises(ValueError,match='outside source tree'):
        package_v2.package(tmp_path/'existing.zip',src)
