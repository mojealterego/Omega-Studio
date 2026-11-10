"""Fail-closed APK artifact gate: embedded ARM64 runtime and APK signature.

Archive checks do not prove execution on a physical Android device.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from tools.verify_runtime_bundle import inspect_runtime_bundle, RuntimeBundleError


class APKReleaseError(ValueError):
    """APK does not meet release artifact requirements."""


ASSETS = ('bootstrap-aarch64-v8a.zip', 'bootstrap-aarch64-v8a.sha256', 'bootstrap-prefix.txt')
MAX_BOOTSTRAP_BYTES = 2 * 1024**3


def _digest_file(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inspect_apk(path: Path, package_name: str = 'org.omega.actions') -> dict:
    path = Path(path).resolve(strict=True)
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise APKReleaseError('APK CRC mismatch')
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if len(set(names)) != len(names):
                raise APKReleaseError('Duplicate APK entry')
            if not {'AndroidManifest.xml', 'classes.dex'}.issubset(names):
                raise APKReleaseError('Android manifest or DEX missing')
            if any('assets/' + item not in names for item in ASSETS):
                raise APKReleaseError('Compatible bootstrap assets missing from APK')
            if archive.getinfo('assets/' + ASSETS[0]).file_size > MAX_BOOTSTRAP_BYTES:
                raise APKReleaseError('Bootstrap size exceeds release quota')
            with tempfile.TemporaryDirectory(prefix='omega-apk-gate-') as temp:
                assets = Path(temp)
                for name in ASSETS:
                    with archive.open('assets/' + name) as source, (assets / name).open('wb') as dest:
                        shutil.copyfileobj(source, dest, 1024 * 1024)
                report = inspect_runtime_bundle(assets, package_name)
    except (OSError, zipfile.BadZipFile, RuntimeBundleError, UnicodeError) as exc:
        raise APKReleaseError('Invalid bootstrap or APK: ' + str(exc)) from exc
    return {'status': 'STRUCTURAL_PASS', 'apk': str(path),
            'apk_sha256': _digest_file(path),
            'runtime': report, 'android_device_execution_verified': False}


def verify_signed_apk(path: Path) -> None:
    apksigner = shutil.which('apksigner')
    if not apksigner:
        raise APKReleaseError('Android SDK apksigner not installed')
    result = subprocess.run([apksigner, 'verify', '--verbose', '--print-certs', str(path)],
                            capture_output=True, text=True, timeout=120, check=False)
    if result.returncode != 0:
        raise APKReleaseError('APK signature verification failed: ' + result.stderr[-600:])


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate embedded Android ARM64 runtime and APK signature')
    parser.add_argument('apk', type=Path)
    parser.add_argument('--package', default='org.omega.actions')
    args = parser.parse_args()
    try:
        report = inspect_apk(args.apk, args.package)
        verify_signed_apk(args.apk)
        report['apk_signature'] = 'VERIFIED'
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (APKReleaseError, OSError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(exc), 'device_verified': False}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
