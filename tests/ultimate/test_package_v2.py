from __future__ import annotations
import hashlib
from pathlib import Path
import zipfile
from tools.package_v2 import package_release, verify_release


def test_package_manifest_covers_every_file_and_is_deterministic(tmp_path: Path):
    root = tmp_path / 'project'; root.mkdir()
    (root / 'README.md').write_text('Omega v2\n')
    (root / 'backend').mkdir(); (root / 'backend' / 'code.py').write_text('print(1)\n')
    source = tmp_path / 'upstream.zip'
    with zipfile.ZipFile(source, 'w') as z:
        z.writestr('source/README', 'upstream')
    first = tmp_path / 'one.zip'; second = tmp_path / 'two.zip'
    a = package_release(first, root, uploads=[source])
    b = package_release(second, root, uploads=[source])
    assert a['sha256'] == b['sha256']
    assert verify_release(first)['files_verified'] == 3
    with zipfile.ZipFile(first) as z:
        assert z.read('project/backend/code.py') == b'print(1)\n'
        assert z.read('upstream/user_supplied/upstream.zip') == source.read_bytes()
        assert 'project/MANIFEST_SHA256.txt' in z.namelist()
