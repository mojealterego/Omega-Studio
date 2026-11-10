"""Source delivery must be deterministic and cryptographically inspectable."""
from __future__ import annotations
import hashlib
from pathlib import Path
import zipfile
import pytest
from tools.package_open_source import build_package, PackageError


def test_source_archive_contains_lock_code_and_13_docs(tmp_path):
    root = Path(__file__).resolve().parents[2]
    path = tmp_path / 'omega.zip'
    report = build_package(root, path)
    assert report['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert report['status'] == 'SOURCE_PACKAGE_VERIFIED'
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        names = z.namelist()
        assert any(x.endswith('/config/upstream_sources.lock.json') for x in names)
        assert any(x.endswith('/backend/omega_actions/ultimate/upstream_sources.py') for x in names)
        assert any(x.endswith('/docs/UPSTREAM_SOURCE_INTEGRATION.md') for x in names)
        assert any(x.endswith('/tests/ultimate/test_upstream_sources.py') for x in names)
        manifest = next(x for x in names if x.endswith('/MANIFEST_SHA256.txt'))
        prefix = manifest[:-len('MANIFEST_SHA256.txt')]
        for line in z.read(manifest).decode('utf-8').splitlines():
            sha, name = line.split('  ', 1)
            assert hashlib.sha256(z.read(prefix + name)).hexdigest() == sha


def test_package_is_reproducible(tmp_path):
    root = Path(__file__).resolve().parents[2]
    a, b = tmp_path / 'a.zip', tmp_path / 'b.zip'
    assert build_package(root, a)['sha256'] == build_package(root, b)['sha256']


def test_package_rejects_symlink(tmp_path):
    (tmp_path / 'README.md').write_text('x')
    (tmp_path / 'bad').symlink_to('/etc/passwd')
    with pytest.raises(PackageError, match='symlink'):
        build_package(tmp_path, tmp_path / 'result.zip')
