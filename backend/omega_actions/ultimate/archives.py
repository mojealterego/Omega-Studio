"""Deterministic ZIP and optional native RAR with strict extraction boundaries."""
from __future__ import annotations
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tempfile
import zipfile


class ArchiveError(ValueError):
    pass


def _relative_member(name: str) -> Path:
    if not name or '\\' in name or '\x00' in name or name.startswith('/'):
        raise ArchiveError('Invalid archive member name')
    parts = PurePosixPath(name).parts
    if any(p in ('.', '..') for p in parts) or (parts and ':' in parts[0]):
        raise ArchiveError('Archive path traversal rejected')
    return Path(*parts)


def pack_zip(source: Path, destination: Path, max_files: int = 100_000) -> dict:
    source = Path(source).resolve(strict=True)
    destination = Path(destination).resolve(strict=False)
    if not source.is_dir() or destination.is_relative_to(source):
        raise ArchiveError('Source must be a directory and archive must be outside it')
    files = sorted(p for p in source.rglob('*') if p.is_file() or p.is_symlink())
    if len(files) > max_files:
        raise ArchiveError('Archive entry count exceeds quota')
    if any(p.is_symlink() for p in files):
        raise ArchiveError('Symlinks are not permitted in export')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.omega-zip-', delete=False) as f:
            temporary = Path(f.name)
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            for path in files:
                relative = path.relative_to(source).as_posix()
                _relative_member(relative)
                info = zipfile.ZipInfo(relative, date_time=(2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                with path.open('rb') as reader, archive.open(info, 'w', force_zip64=True) as writer:
                    shutil.copyfileobj(reader, writer, length=1024 * 1024)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ArchiveError('ZIP CRC mismatch')
        os.replace(temporary, destination)
        temporary = None
        return {'files': len(files), 'bytes': destination.stat().st_size}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def extract_zip(source: Path, destination: Path, *, max_files: int = 100_000,
                max_total_bytes: int = 8 * 1024**3, max_ratio: int = 1000) -> dict:
    source = Path(source).resolve(strict=True)
    destination = Path(destination).resolve(strict=False)
    if destination.exists():
        raise ArchiveError('Extraction destination already exists')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        if len(entries) > max_files:
            raise ArchiveError('Too many archive entries')
        seen: set[str] = set()
        total = 0
        for entry in entries:
            rel = _relative_member(entry.filename)
            if not rel.parts:
                raise ArchiveError('Invalid empty path')
            key = str(rel).casefold()
            if key in seen:
                raise ArchiveError('Duplicate archive path')
            seen.add(key)
            kind = (entry.external_attr >> 16) & 0o170000
            if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ArchiveError('Archive contains a special file or symlink')
            total += entry.file_size
            if total > max_total_bytes or (entry.file_size > max_ratio * max(1, entry.compress_size)):
                raise ArchiveError('Archive decompression quota exceeded')
        staging = Path(tempfile.mkdtemp(prefix='.omega-extract-', dir=destination.parent))
        try:
            for entry in entries:
                path = staging / _relative_member(entry.filename)
                if entry.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry, 'r') as reader, path.open('xb') as writer:
                    shutil.copyfileobj(reader, writer, length=1024 * 1024)
            os.replace(staging, destination)
            return {'files': sum(not e.is_dir() for e in entries), 'uncompressed_bytes': total,
                    'destination': str(destination)}
        finally:
            if staging.exists():
                shutil.rmtree(staging)


def pack_rar(source: Path, destination: Path, *, timeout: int = 1800) -> dict:
    """Use installed licensed RAR encoder; fail closed when absent."""
    binary = shutil.which('rar')
    if binary is None:
        raise ArchiveError('RAR creation requires a licensed local RAR encoder')
    src = Path(source).resolve(strict=True)
    dst = Path(destination).resolve(strict=False)
    if not src.is_dir() or dst.is_relative_to(src):
        raise ArchiveError('Unsafe RAR source or destination')
    dst.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([binary, 'a', '-idq', '-r', str(dst), '.'], cwd=src,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    if result.returncode != 0 or not dst.is_file():
        raise ArchiveError('RAR encoder failed: ' + result.stderr.decode('utf-8', 'replace')[-400:])
    return {'bytes': dst.stat().st_size, 'destination': str(dst)}



def extract_rar(source: Path, destination: Path, *, max_files: int = 100_000,
                max_total_bytes: int = 8 * 1024**3) -> dict:
    """Bounded RAR extraction using rarfile; compressed RAR requires compatible decoder."""
    try:
        import rarfile
    except ImportError as exc:
        raise ArchiveError('RAR decoding requires rarfile and a compatible decompressor') from exc
    source = Path(source).resolve(strict=True)
    destination = Path(destination).resolve(strict=False)
    if destination.exists():
        raise ArchiveError('RAR destination already exists')
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with rarfile.RarFile(source) as archive:
            entries = archive.infolist()
            if len(entries) > max_files:
                raise ArchiveError('RAR entry quota exceeded')
            total = 0
            seen = set()
            for item in entries:
                rel = _relative_member(item.filename)
                key = str(rel).casefold()
                if key in seen:
                    raise ArchiveError('Duplicate RAR member')
                seen.add(key)
                if getattr(item, 'is_symlink', lambda: False)():
                    raise ArchiveError('RAR symlink rejected')
                total += item.file_size
                if total > max_total_bytes:
                    raise ArchiveError('RAR extraction byte quota exceeded')
            staging = Path(tempfile.mkdtemp(prefix='.omega-rar-', dir=destination.parent))
            try:
                for item in entries:
                    target = staging / _relative_member(item.filename)
                    if item.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as reader, target.open('xb') as writer:
                        copied = 0
                        while True:
                            block = reader.read(1024 * 1024)
                            if not block:
                                break
                            copied += len(block)
                            if copied > item.file_size:
                                raise ArchiveError('RAR member size mismatch')
                            writer.write(block)
                        if copied != item.file_size:
                            raise ArchiveError('RAR member truncated')
                os.replace(staging, destination)
                return {'files': sum(not e.isdir() for e in entries), 'uncompressed_bytes': total,
                        'destination': str(destination)}
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
    except ArchiveError:
        raise
    except (rarfile.Error, OSError, EOFError) as exc:
        raise ArchiveError('RAR archive cannot be decoded or is corrupted') from exc
