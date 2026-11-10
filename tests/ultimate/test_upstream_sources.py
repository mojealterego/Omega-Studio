"""Contract tests for pinned upstream source acquisition (no network)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess

import pytest
from omega_actions.ultimate.upstream_sources import (
    CatalogError, SourceCatalog, SourceSyncError, UpstreamSourceManager,
)


def sample_source(tmp_path: Path) -> tuple[Path, str]:
    src = tmp_path / 'local-upstream'
    src.mkdir()
    subprocess.run(['git', 'init', '-q', str(src)], check=True)
    (src / 'LICENSE').write_text('MIT License\n', encoding='utf-8')
    (src / 'main.py').write_text('print("hello")\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(src), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(src), '-c', 'user.email=test@example.invalid',
                    '-c', 'user.name=Test', 'commit', '-qm', 'source'], check=True)
    sha = subprocess.check_output(['git', '-C', str(src), 'rev-parse', 'HEAD'], text=True).strip()
    return src, sha


def catalog_file(tmp_path: Path, source: Path, sha: str, *, name='sample', license_file='LICENSE') -> Path:
    path = tmp_path / 'catalog.json'
    path.write_text(json.dumps({'schema_version': 1, 'sources': [{
        'name': name, 'repository': source.as_uri(), 'commit': sha,
        'license': 'MIT', 'license_files': [license_file], 'role': 'runtime',
    }]}), encoding='utf-8')
    return path


def test_manifest_rejects_mutable_ref(tmp_path):
    src, _ = sample_source(tmp_path)
    with pytest.raises(CatalogError, match='commit'):
        SourceCatalog.load(catalog_file(tmp_path, src, 'main'), allow_local=True)


def test_manifest_rejects_host_userinfo_and_untrusted_schemes(tmp_path):
    src, sha = sample_source(tmp_path)
    path = catalog_file(tmp_path, src, sha)
    for url in ('https://attacker.example/a/b', 'https://evil@github.com/a/b',
                'http://github.com/a/b', 'https://github.com:443/a/b',
                'https://github.com/a/b.git?token=secret'):
        doc = json.loads(path.read_text())
        doc['sources'][0]['repository'] = url
        path.write_text(json.dumps(doc))
        with pytest.raises(CatalogError):
            SourceCatalog.load(path)


def test_manifest_rejects_duplicate_and_path_traversal(tmp_path):
    src, sha = sample_source(tmp_path)
    path = catalog_file(tmp_path, src, sha, name='../escape')
    with pytest.raises(CatalogError):
        SourceCatalog.load(path, allow_local=True)
    path = catalog_file(tmp_path, src, sha)
    doc = json.loads(path.read_text())
    doc['sources'].append(doc['sources'][0])
    path.write_text(json.dumps(doc))
    with pytest.raises(CatalogError, match='Duplicate'):
        SourceCatalog.load(path, allow_local=True)


def test_offline_checkout_exact_sha_and_provenance(tmp_path):
    src, sha = sample_source(tmp_path)
    catalog = SourceCatalog.load(catalog_file(tmp_path, src, sha), allow_local=True)
    dest = tmp_path / 'sources'
    dest.mkdir()
    manager = UpstreamSourceManager(catalog, dest, allow_local=True)
    result = manager.sync('sample', consent=True)
    assert result['commit'] == sha
    assert (dest / 'sample' / 'main.py').read_text() == 'print("hello")\n'
    assert (dest / 'sample' / 'LICENSE').is_file()
    assert result['license'] == 'MIT'
    assert (dest / '.omega-provenance' / 'sample.json').is_file()
    assert manager.verify('sample')['verified'] is True


def test_sync_requires_explicit_consent_and_never_overwrites(tmp_path):
    src, sha = sample_source(tmp_path)
    catalog = SourceCatalog.load(catalog_file(tmp_path, src, sha), allow_local=True)
    dest = tmp_path / 'sources'
    dest.mkdir()
    manager = UpstreamSourceManager(catalog, dest, allow_local=True)
    with pytest.raises(SourceSyncError, match='consent'):
        manager.sync('sample', consent=False)
    manager.sync('sample', consent=True)
    with pytest.raises(SourceSyncError, match='exists'):
        manager.sync('sample', consent=True)


def test_license_missing_fails_closed_without_partial_checkout(tmp_path):
    src, sha = sample_source(tmp_path)
    catalog = SourceCatalog.load(catalog_file(tmp_path, src, sha, license_file='COPYING'), allow_local=True)
    dest = tmp_path / 'sources'
    dest.mkdir()
    with pytest.raises(SourceSyncError, match='license'):
        UpstreamSourceManager(catalog, dest, allow_local=True).sync('sample', consent=True)
    assert not (dest / 'sample').exists()


def test_verify_detects_source_mutation(tmp_path):
    src, sha = sample_source(tmp_path)
    catalog = SourceCatalog.load(catalog_file(tmp_path, src, sha), allow_local=True)
    dest = tmp_path / 'sources'
    dest.mkdir()
    manager = UpstreamSourceManager(catalog, dest, allow_local=True)
    manager.sync('sample', consent=True)
    (dest / 'sample' / 'main.py').write_text('malicious\n')
    with pytest.raises(SourceSyncError, match='modified'):
        manager.verify('sample')


def test_upstream_lock_contains_expected_projects():
    root = Path(__file__).resolve().parents[2]
    catalog = SourceCatalog.load(root / 'config' / 'upstream_sources.lock.json')
    names = {x.name for x in catalog.sources}
    assert {'termux-app','termux-packages','code-server','vscode-1.85.1',
            'llama.cpp','git','cpython','nodejs','monaco-editor','xterm.js',
            'actions-runner','huggingface-hub'} <= names
    assert all(len(x.commit) == 40 for x in catalog.sources)


def test_api_catalog_is_authenticated(tmp_path):
    from fastapi.testclient import TestClient
    from omega_actions.api import create_app
    from omega_actions.config import Settings
    settings = Settings(home=tmp_path / 'home')
    app = create_app(settings)
    client = TestClient(app, base_url="http://localhost")
    assert client.get('/api/ultimate/upstreams').status_code == 401
    response = client.get('/api/ultimate/upstreams', headers={'X-OMEGA-Token': app.state.token})
    assert response.status_code == 200
    assert any(x['name']=='vscode-1.85.1' for x in response.json()['sources'])
    assert all('commit' in x for x in response.json()['sources'])


def test_upstream_api_rejects_unconsented_sync(tmp_path):
    from fastapi.testclient import TestClient
    from omega_actions.api import create_app
    from omega_actions.config import Settings
    app = create_app(Settings(home=tmp_path / 'home'))
    client = TestClient(app, base_url='http://localhost')
    headers = {'X-OMEGA-Token': app.state.token}
    response = client.post('/api/ultimate/upstreams/sync', headers=headers,
                           json={'name':'termux-app', 'confirm_network':False})
    assert response.status_code == 403
    assert not (tmp_path / 'home' / 'upstream-sources').exists()
    assert client.post('/api/ultimate/upstreams/sync',
                       json={'name':'termux-app', 'confirm_network':True}).status_code == 401


def test_upstream_cli_lists_locked_sources_without_network(tmp_path):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(['python3', str(root / 'tools/sync_upstream_sources.py'), 'list'],
                            cwd=root, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed['count'] == 14
    assert all('commit' in item for item in parsed['sources'])


def test_upstream_cli_sync_refuses_missing_consent(tmp_path):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(['python3', str(root / 'tools/sync_upstream_sources.py'),
                             '--root', str(tmp_path), 'sync', 'termux-app'],
                            cwd=root, capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert 'consent' in result.stderr.lower()
    assert not (tmp_path / 'termux-app').exists()


def test_catalog_is_packaged_with_python_wheel():
    import omega_actions.ultimate.upstream_sources as module
    root = Path(__file__).resolve().parents[2]
    resource = Path(module.__file__).with_name('upstream_sources.lock.json')
    assert resource.is_file()
    assert resource.read_bytes() == (root / 'config/upstream_sources.lock.json').read_bytes()
