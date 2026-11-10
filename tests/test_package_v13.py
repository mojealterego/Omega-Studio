"""Source delivery is reproducible and never masquerades as a complete APK."""
import hashlib
from pathlib import Path
import zipfile

from tools.package_v13 import build_source_package, REQUIRED


def test_source_package_is_deterministic_and_explicitly_not_apk(tmp_path):
    root=tmp_path/'src';root.mkdir()
    (root/'README.md').write_text('Omega\n')
    (root/'android').mkdir();(root/'android/Main.java').write_text('class Main {}\n')
    for name in REQUIRED:
        file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('test source\n')
    (root/'dist').mkdir();(root/'dist/fake.apk').write_bytes(b'FAKE')
    (root/'__pycache__').mkdir();(root/'__pycache__/x.pyc').write_bytes(b'FAKE')
    first=build_source_package(root,tmp_path/'first.zip')
    second=build_source_package(root,tmp_path/'second.zip')
    assert first['sha256']==second['sha256']
    assert first['binary_release_ready'] is False
    with zipfile.ZipFile(tmp_path/'first.zip') as z:
        names=z.namelist()
        assert 'OMEGA_STUDIO_v1.3.0/README.md' in names
        assert 'OMEGA_STUDIO_v1.3.0/dist/fake.apk' not in names
        assert 'OMEGA_STUDIO_v1.3.0/RELEASE_STATUS.json' in names
        assert 'OMEGA_STUDIO_v1.3.0/MANIFEST_SHA256.txt' in names
        for line in z.read('OMEGA_STUDIO_v1.3.0/MANIFEST_SHA256.txt').decode().splitlines():
            sha,path=line.split('  ',1)
            assert hashlib.sha256(z.read('OMEGA_STUDIO_v1.3.0/'+path)).hexdigest()==sha
