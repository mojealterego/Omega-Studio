"""Import verified, prefix-matched Termux bootstrap + Python/Git/llama/code-server.

No downloads, substitutions, fake ELF, or bypasses. All native assets are supplied
by a real Termux package build performed for the OMEGA application ID.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from tools.verify_runtime_bundle import RuntimeBundleError, inspect_runtime_bundle


def prepare_runtime_release(archive: Path, prefix_manifest: Path, assets: Path, package_name: str) -> dict:
    archive = Path(archive).resolve(strict=True)
    prefix_manifest = Path(prefix_manifest).resolve(strict=True)
    assets = Path(assets)
    if not archive.is_file() or not prefix_manifest.is_file():
        raise RuntimeBundleError('Input bootstrap or prefix manifest missing')
    digest = hashlib.sha256()
    with archive.open('rb') as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b''):
            digest.update(chunk)
    sha = digest.hexdigest()
    # Validate in a private temporary staging directory before touching assets.
    with tempfile.TemporaryDirectory(prefix='omega-runtime-stage-') as tmp:
        staged = Path(tmp)
        shutil.copyfile(archive, staged / 'bootstrap-aarch64-v8a.zip')
        shutil.copyfile(prefix_manifest, staged / 'bootstrap-prefix.txt')
        (staged / 'bootstrap-aarch64-v8a.sha256').write_text(sha + '\n', encoding='ascii')
        report = inspect_runtime_bundle(staged, package_name)
        (staged / 'runtime-integrity.json').write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8'
        )
        targets = ('bootstrap-aarch64-v8a.zip', 'bootstrap-prefix.txt', 'bootstrap-aarch64-v8a.sha256', 'runtime-integrity.json')
        if assets.exists() and any((assets / name).exists() for name in targets):
            raise RuntimeBundleError('Runtime already installed in assets; explicit removal is required before replacement')
        assets.mkdir(parents=True, exist_ok=True)
        for name in targets:
            # Each asset is a complete, immutable file. Manifest is published last.
            os.replace(staged / name, assets / name)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Import a fully built ARM64 Termux runtime into OMEGA Studio assets')
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--prefix-manifest', type=Path, required=True)
    parser.add_argument('--assets', type=Path, default=Path('android/app/src/main/assets'))
    parser.add_argument('--package', default='org.omega.actions')
    args = parser.parse_args()
    try:
        print(json.dumps(prepare_runtime_release(args.archive, args.prefix_manifest, args.assets, args.package), indent=2))
        return 0
    except (RuntimeBundleError, OSError, ValueError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(exc), 'production_apk_ready': False}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
