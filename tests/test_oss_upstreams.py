"""Red/green tests for pinned OSS upstream ingestion and provenance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from tools.oss_upstreams import LockError, audit_lock, sync_sources, verify_sources


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _fixture(tmp_path: Path):
    upstream = tmp_path / 'fixtures' / 'example'
    upstream.mkdir(parents=True)
    _git(upstream, 'init', '-q')
    _git(upstream, 'config', 'user.email', 'test@omega.invalid')
    _git(upstream, 'config', 'user.name', 'OMEGA test')
    (upstream / 'LICENSE').write_text('MIT License\nCopyright OMEGA tests\n', encoding='utf-8')
    (upstream / 'engine.py').write_text('print("real source")\n', encoding='utf-8')
    _git(upstream, 'add', '.')
    _git(upstream, 'commit', '-qm', 'initial')
    sha = _git(upstream, 'rev-parse', 'HEAD')
    lock = tmp_path / 'upstreams.lock.json'
    lock.write_text(json.dumps({'schema': 1, 'sources': [
        {'id': 'example', 'repository': 'example/engine', 'commit': sha,
         'license': 'MIT', 'license_file': 'LICENSE', 'purpose': 'test engine'}
    ]}), encoding='utf-8')
    return lock, upstream, sha


def test_audit_accepts_pinned_repo_and_returns_source_count(tmp_path):
    lock, _, sha = _fixture(tmp_path)
    report = audit_lock(lock)
    assert report['status'] == 'PASS'
    assert report['count'] == 1
    assert report['sources'][0]['commit'] == sha


@pytest.mark.parametrize('mutation', [
    {'commit': 'main'}, {'repository': 'evil.invalid/repo'},
    {'repository': '../escape'}, {'id': '../escape'},
    {'license_file': '../outside'}, {'license_file': '/etc/passwd'},
    {'license_file': 'a\\b'}, {'license': ''},
])
def test_audit_rejects_unpinned_or_unsafe_manifest(tmp_path, mutation):
    lock, _, _ = _fixture(tmp_path)
    doc = json.loads(lock.read_text())
    doc['sources'][0].update(mutation)
    lock.write_text(json.dumps(doc))
    with pytest.raises(LockError):
        audit_lock(lock)


def test_audit_rejects_duplicate_entries(tmp_path):
    lock, _, _ = _fixture(tmp_path)
    doc = json.loads(lock.read_text())
    doc['sources'].append(dict(doc['sources'][0]))
    lock.write_text(json.dumps(doc))
    with pytest.raises(LockError):
        audit_lock(lock)


def test_sync_offline_pins_sha_and_checks_license(tmp_path):
    lock, upstream, sha = _fixture(tmp_path)
    vendor = tmp_path / 'vendor'
    report = sync_sources(lock, vendor, local_sources={'example': upstream})
    assert report['status'] == 'PASS'
    assert report['sources'][0]['commit'] == sha
    assert (vendor / 'example' / 'engine.py').read_text() == 'print("real source")\n'
    provenance = json.loads((vendor / 'example' / '.omega-source.json').read_text())
    assert provenance['commit'] == sha
    assert provenance['license_sha256'] == hashlib.sha256((upstream / 'LICENSE').read_bytes()).hexdigest()
    assert verify_sources(lock, vendor)['status'] == 'PASS'


def test_sync_fails_closed_when_commit_missing(tmp_path):
    lock, upstream, _ = _fixture(tmp_path)
    doc = json.loads(lock.read_text())
    doc['sources'][0]['commit'] = 'f' * 40
    lock.write_text(json.dumps(doc))
    vendor = tmp_path / 'vendor'
    with pytest.raises(LockError):
        sync_sources(lock, vendor, local_sources={'example': upstream})
    assert not (vendor / 'example').exists()


def test_sync_fails_closed_if_license_missing(tmp_path):
    lock, upstream, _ = _fixture(tmp_path)
    doc = json.loads(lock.read_text())
    doc['sources'][0]['license_file'] = 'NONEXISTENT'
    lock.write_text(json.dumps(doc))
    with pytest.raises(LockError):
        sync_sources(lock, tmp_path / 'vendor', local_sources={'example': upstream})


def test_sync_rejects_overwrite(tmp_path):
    lock, upstream, _ = _fixture(tmp_path)
    vendor = tmp_path / 'vendor'
    sync_sources(lock, vendor, local_sources={'example': upstream})
    with pytest.raises(LockError):
        sync_sources(lock, vendor, local_sources={'example': upstream})


def test_verify_detects_tampering(tmp_path):
    lock, upstream, _ = _fixture(tmp_path)
    vendor = tmp_path / 'vendor'
    sync_sources(lock, vendor, local_sources={'example': upstream})
    (vendor / 'example' / 'engine.py').write_text('print("tampered")\n')
    with pytest.raises(LockError):
        verify_sources(lock, vendor)


def test_sync_rejects_symlink_vendor_root(tmp_path):
    lock, upstream, _ = _fixture(tmp_path)
    root = tmp_path / 'real'
    root.mkdir()
    link = tmp_path / 'vendor'
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(LockError):
        sync_sources(lock, link, local_sources={'example': upstream})


def test_verify_detects_license_tampering(tmp_path):
    lock, upstream, _ = _fixture(tmp_path)
    vendor = tmp_path / 'vendor'
    sync_sources(lock, vendor, local_sources={'example': upstream})
    (vendor / 'example' / 'LICENSE').write_text('altered')
    with pytest.raises(LockError):
        verify_sources(lock, vendor)
