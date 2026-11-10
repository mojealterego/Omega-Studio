"""Production APK must include verified ARM64 runtime; preview must never pass."""
from pathlib import Path
import zipfile
import pytest
from tools.verify_android_apk_release import inspect_apk, APKReleaseError


def test_preview_apk_rejected():
    apk=Path(__file__).resolve().parents[1]/'dist/OMEGA_STUDIO_APPBUILDER_UI_PREVIEW_v1.2.0.apk'
    assert apk.exists()
    with pytest.raises(APKReleaseError, match='bootstrap'):
        inspect_apk(apk)


def test_fake_bootstrap_cannot_pass(tmp_path):
    apk=tmp_path/'fake.apk'
    with zipfile.ZipFile(apk,'w') as z:
        z.writestr('AndroidManifest.xml',b'fake')
        z.writestr('classes.dex',b'fake')
        z.writestr('assets/bootstrap-aarch64-v8a.zip',b'fake')
        z.writestr('assets/bootstrap-aarch64-v8a.sha256',b'0'*64)
        z.writestr('assets/bootstrap-prefix.txt','/data/data/org.omega.actions/files/usr')
    with pytest.raises(APKReleaseError,match='(SHA-256|bootstrap)'):
        inspect_apk(apk)


def test_corrupt_apk_rejected(tmp_path):
    apk=tmp_path/'bad.apk'
    apk.write_bytes(b'not an APK')
    with pytest.raises(APKReleaseError):
        inspect_apk(apk)
