"""Deterministic offline source archive with per-file SHA-256 integrity manifest.

This archive is NOT a production Android APK. Native runtime/device gates are separate.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile


class PackageError(ValueError):
    """Unsafe or incomplete OMEGA source delivery."""


DOCS = ('README.md', 'ARCHITECTURE.md', 'ENGINEERING_SPECIFICATION.md',
        'BEYOND_MAXIMUM_INNOVATIONS.md', 'MODULE_REFERENCE.md', 'API_REFERENCE.md',
        'SECURITY_ARCHITECTURE.md', 'BUILD_AND_DEPLOYMENT_GUIDE.md',
        'TESTING_AND_VALIDATION.md', 'DEPENDENCIES_AND_LICENSES.md',
        'DIGITAL_LIFE_COMPATIBILITY.md', 'INTEGRATION_BLUEPRINT.md',
        'PRODUCTION_READINESS_REPORT.md')
REQUIRED = set(DOCS) | {
    'backend/omega_actions/ultimate/upstream_sources.py',
    'backend/omega_actions/ultimate/upstream_sources.lock.json',
    'config/upstream_sources.lock.json',
    'docs/UPSTREAM_SOURCE_INTEGRATION.md',
    'tests/ultimate/test_upstream_sources.py',
    'tools/sync_upstream_sources.py',
    'tools/build_full_apk.sh',
    'android/app/src/main/AndroidManifest.xml',
}
EXCLUDED_DIRS = {'.git', '.pytest_cache', '__pycache__', '.venv', '.gradle',
                 '.mypy_cache', 'node_modules', 'upstream-sources', 'build',
                 'omega_actions_local.egg-info', 'browser_home'}
EXCLUDED_NAMES = {'MANIFEST_SHA256.txt', '.env', '.omega-source-sync.lock'}
EXCLUDED_SUFFIXES = {'.pyc', '.pyo', '.class', '.jks', '.keystore', '.gguf', '.part'}
PREFIX = 'OMEGA_STUDIO_OPEN_SOURCE_INTEGRATION_v1.2.0/'
MAX_BYTES = 512 * 1024 * 1024


def build_package(root: Path, output: Path) -> dict:
    root = Path(root).resolve(strict=True)
    output = Path(output).resolve(strict=False)
    if not root.is_dir():
        raise PackageError('Source root is not a directory')
    files: dict[str, bytes] = {}
    total = 0
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        if path.is_symlink():
            raise PackageError('Unsafe symlink in source archive: ' + rel.as_posix())
        if not path.is_file() or path.resolve() == output:
            continue
        if rel.name in EXCLUDED_NAMES or path.suffix in EXCLUDED_SUFFIXES:
            continue
        name = rel.as_posix()
        if name.startswith('/') or '..' in rel.parts or '\\' in name:
            raise PackageError('Invalid source archive path')
        data = path.read_bytes()
        total += len(data)
        if total > MAX_BYTES:
            raise PackageError('Source package exceeds 512 MiB quota')
        files[name] = data
    missing = REQUIRED.difference(files)
    if missing:
        raise PackageError('Mandatory source files missing: ' + ', '.join(sorted(missing)))
    manifest = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n'
                       for name, data in sorted(files.items())).encode('utf-8')
    files['MANIFEST_SHA256.txt'] = manifest
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as z:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(PREFIX + name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None or len(z.namelist()) != len(files):
            raise PackageError('Archive CRC or member count verification failed')
        for line in z.read(PREFIX + 'MANIFEST_SHA256.txt').decode('utf-8').splitlines():
            digest, name = line.split('  ', 1)
            if hashlib.sha256(z.read(PREFIX + name)).hexdigest() != digest:
                raise PackageError('Manifest mismatch for ' + name)
    return {'status': 'SOURCE_PACKAGE_VERIFIED', 'archive': str(output),
            'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
            'files': len(files), 'manifest_entries': len(files) - 1,
            'bytes': output.stat().st_size, 'mandatory_documents': len(DOCS),
            'android_arm64_binaries_included': False, 'physical_android_test': False,
            'zip_crc': 'PASS', 'sha256_manifest': 'PASS'}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_package(args.root, args.output), ensure_ascii=False, indent=2))
