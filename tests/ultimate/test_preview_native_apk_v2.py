from __future__ import annotations
from pathlib import Path
import zipfile
from tools.build_embedded_apk import build
from tools.apk_signing import verify_apk


def test_preview_apk_contains_real_arm64_elf_and_no_fake_bootstrap(tmp_path: Path):
    apk = tmp_path / 'preview.apk'
    report = build(apk)
    verify_apk(apk)
    with zipfile.ZipFile(apk) as archive:
        lib = archive.read('lib/arm64-v8a/libomega_runtime.so')
        assert lib[:4] == b'\x7fELF'
        assert int.from_bytes(lib[18:20], 'little') == 183
        assert 'assets/bootstrap-aarch64-v8a.zip' not in archive.namelist()
    assert report['signed_v2']
    assert report['runtime_complete'] is False
