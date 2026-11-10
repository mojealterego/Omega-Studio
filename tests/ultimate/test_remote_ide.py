"""Browser-based OMEGA IDE contract tests: real editor, authenticated file tree."""
import base64
from pathlib import Path
from fastapi.testclient import TestClient
from omega_actions.ultimate.remote8080 import create_remote_app


def auth():
    return {'Authorization': 'Basic ' + base64.b64encode(b'omega:long-secret-123').decode()}


def test_browser_editor_is_self_contained_and_authenticated(tmp_path):
    app = create_remote_app(tmp_path, username='omega', password='long-secret-123')
    client = TestClient(app)
    assert client.get('/').status_code == 401
    response = client.get('/', headers=auth())
    assert response.status_code == 200
    assert 'text/html' in response.headers['content-type']
    for required in ('id="file-tree"', 'id="editor"', 'id="save-file"', 'id="new-file"', 'id="status"'):
        assert required in response.text
    assert 'cdn.' not in response.text
    assert 'fetch(' in response.text
    assert '/api/tree' in response.text
    assert 'expected_sha256' in response.text


def test_tree_lists_directories_and_avoids_symlink_escape(tmp_path):
    (tmp_path/'src').mkdir()
    (tmp_path/'src'/'main.py').write_text('print(1)')
    (tmp_path/'escape').symlink_to(tmp_path.parent, target_is_directory=True)
    client = TestClient(create_remote_app(tmp_path, username='omega', password='long-secret-123'))
    response = client.get('/api/tree', headers=auth())
    assert response.status_code == 200
    assert response.json()['path'] == '.'
    assert response.json()['entries'] == [{'name': 'src', 'path': 'src', 'directory': True, 'bytes': None}]
    nested = client.get('/api/tree', params={'path': 'src'}, headers=auth())
    assert nested.json()['entries'] == [{'name': 'main.py', 'path': 'src/main.py', 'directory': False, 'bytes': 8}]
    assert client.get('/api/tree', params={'path': '../'}, headers=auth()).status_code == 403
    assert client.get('/api/tree', params={'path': 'escape'}, headers=auth()).status_code == 403
    assert client.get('/api/tree', params={'path': 'src/main.py'}, headers=auth()).status_code == 400


def test_browser_editor_api_creates_and_updates_file(tmp_path):
    (tmp_path/'src').mkdir()
    client = TestClient(create_remote_app(tmp_path, username='omega', password='long-secret-123'))
    created = client.put('/api/write', headers=auth(), json={'path': 'src/new.py', 'content': 'print("omega")'})
    assert created.status_code == 200
    loaded = client.get('/api/read', headers=auth(), params={'path': 'src/new.py'})
    assert loaded.json()['content'] == 'print("omega")'
    saved = client.put('/api/write', headers=auth(), json={'path': 'src/new.py', 'content': 'print(2)', 'expected_sha256': loaded.json()['sha256']})
    assert saved.status_code == 200
    assert (tmp_path/'src/new.py').read_text() == 'print(2)'
