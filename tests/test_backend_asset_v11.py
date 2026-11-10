import hashlib
from pathlib import Path
import zipfile
from tools.prepare_android_assets import package_backend


def test_backend_asset_contains_runtime_code_and_is_reproducible(tmp_path):
    source=Path(__file__).resolve().parents[1]/'backend'
    target=tmp_path/'assets';target.mkdir()
    first=package_backend(source,target)
    data=(target/'omega-backend.zip').read_bytes()
    assert first['sha256']==hashlib.sha256(data).hexdigest()
    with zipfile.ZipFile(target/'omega-backend.zip') as archive:
        names=set(archive.namelist())
        assert 'omega_actions/__main__.py' in names
        assert 'omega_actions/providers.py' in names
        assert not any('__pycache__' in name or name.endswith('.pyc') for name in names)
    second=package_backend(source,target)
    assert second['sha256']==first['sha256']
    assert data==(target/'omega-backend.zip').read_bytes()
