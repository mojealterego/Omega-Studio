"""Deterministic, streaming ZIP64 source bundle with SHA-256 manifest.

Unmodified user-supplied upstream archives are references, not Android binaries.
The package does not claim production APK readiness.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import stat
import zipfile

STAMP = (2026, 11, 10, 0, 0, 0)
EXCLUDED = {'.git', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'node_modules', '.venv'}


def _entry(name: str, compressed: bool) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, STAMP)
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.compress_type = zipfile.ZIP_DEFLATED if compressed else zipfile.ZIP_STORED
    return info


def _iter_project(root: Path):
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if any(part in EXCLUDED for part in rel.parts):
            continue
        if path.is_symlink():
            raise ValueError('Symlink cannot be included in package: ' + str(rel))
        if path.is_file() and rel.as_posix() != 'MANIFEST_SHA256.txt':
            yield path, 'project/' + rel.as_posix(), path.suffix.lower() not in ('.zip', '.apk', '.png', '.jpg', '.pdf', '.so')


def package_release(output: Path, root: Path, *, uploads: list[Path] | None = None, pdf: Path | None = None) -> dict:
    root = Path(root).resolve(strict=True)
    output = Path(output).resolve(strict=False)
    if output.is_relative_to(root):
        raise ValueError('Output must be outside project tree')
    output.parent.mkdir(parents=True, exist_ok=True)
    files = list(_iter_project(root))
    seen = {name for _, name, _ in files}
    for source in uploads or []:
        source = Path(source)
        name = 'upstream/user_supplied/' + source.name
        if name in seen or source.is_symlink() or not source.is_file() or source.suffix.lower() != '.zip':
            raise ValueError('Unsafe or duplicate source archive')
        seen.add(name)
        files.append((source, name, False))
    if pdf is not None:
        pdf = Path(pdf)
        if pdf.is_symlink() or not pdf.is_file():
            raise ValueError('Invalid reference PDF')
        files.append((pdf, 'reference/MCode.pdf', False))
    files.sort(key=lambda entry: entry[1])
    lines = []
    with zipfile.ZipFile(output, 'w', allowZip64=True) as archive:
        for source, name, compressed in files:
            digest = hashlib.sha256()
            with source.open('rb') as stream, archive.open(_entry(name, compressed), 'w', force_zip64=True) as target:
                while True:
                    block = stream.read(1024 * 1024)
                    if not block:
                        break
                    digest.update(block)
                    target.write(block)
            lines.append(digest.hexdigest() + '  ' + name)
        archive.writestr(_entry('project/MANIFEST_SHA256.txt', True), ('\n'.join(lines) + '\n').encode('utf-8'))
    with output.open('rb') as stream:
        package_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'archive': str(output), 'sha256': package_digest,
            'files': len(files), 'size_bytes': output.stat().st_size,
            'release_class': 'source-with-preview-apk-and-unmodified-reference-archives'}


def verify_release(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or 'project/MANIFEST_SHA256.txt' not in names:
            raise ValueError('Invalid or duplicate ZIP entries')
        if archive.testzip() is not None:
            raise ValueError('ZIP CRC failure')
        manifest = archive.read('project/MANIFEST_SHA256.txt').decode('utf-8')
        records = {}
        for line in manifest.splitlines():
            if len(line) < 67 or line[64:66] != '  ':
                raise ValueError('Malformed manifest entry')
            digest, name = line[:64], line[66:]
            if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest) or name in records:
                raise ValueError('Invalid manifest digest or duplicate')
            records[name] = digest
        if set(records) != set(names) - {'project/MANIFEST_SHA256.txt'}:
            raise ValueError('Manifest does not cover every ZIP file')
        for name, expected in records.items():
            digest = hashlib.sha256()
            with archive.open(name) as stream:
                while block := stream.read(1024 * 1024):
                    digest.update(block)
            if digest.hexdigest() != expected:
                raise ValueError('SHA-256 mismatch: ' + name)
        return {'status': 'PASS', 'files_verified': len(records)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--include-user-archives', action='store_true')
    args = parser.parse_args()
    upstream = Path('/mnt/data')
    names = ['vscode-main.zip', 'vscode-droidscript-code-master.zip', 'vscode-droidscript-docs-master.zip',
             'termux-app-master.zip', 'llama.cpp-master.zip']
    uploads = [upstream / name for name in names] if args.include_user_archives else []
    pdf = upstream / 'MCode.pdf' if args.include_user_archives else None
    report = package_release(args.output, args.root, uploads=uploads, pdf=pdf)
    report['verification'] = verify_release(args.output)
    print(json.dumps(report, indent=2, ensure_ascii=False))
