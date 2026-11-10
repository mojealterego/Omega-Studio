"""Build a package-specific, reproducible Termux asset from REAL ARM64 prefix files.

No native executable is fabricated, downloaded, or substituted. Source must be
produced by a matching Termux cross-build and code-server installation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import tempfile
import zipfile


class RuntimePackagingError(ValueError):
    """Unsafe or incomplete Android runtime: never publish an APK from this."""


REQUIRED_COMMANDS = ('bash', 'python', 'git', 'llama-cli', 'node', 'code-server')
ELF_COMMANDS = frozenset(('bash', 'python', 'git', 'llama-cli', 'node'))
MAX_BYTES = 2 * 1024 ** 3
MAX_FILES = 200_000
PACKAGE_RE = re.compile(r'[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+')


def validate_elf(data: bytes, name: str) -> None:
    """Check ELF64/LE/AArch64 PIE with a valid executable PT_LOAD segment.

    Structural validation is NOT execution or signature attestation.
    """
    if len(data) < 4096 or data[:4] != b'\x7fELF' or data[4:7] != b'\x02\x01\x01':
        raise RuntimePackagingError(f'Invalid or truncated ELF64: {name}')
    e_type, machine, version = struct.unpack_from('<HHI', data, 16)
    if machine != 183:
        raise RuntimePackagingError(f'Not AArch64 ELF: {name}')
    if e_type != 3:
        raise RuntimePackagingError(f'ELF is not PIE ET_DYN: {name}')
    if version != 1:
        raise RuntimePackagingError(f'Invalid ELF version: {name}')
    phoff = struct.unpack_from('<Q', data, 32)[0]
    phentsize, phnum = struct.unpack_from('<HH', data, 54)
    if not 1 <= phnum <= 1024 or phentsize < 56 or phoff > len(data) or phnum * phentsize > len(data) - phoff:
        raise RuntimePackagingError(f'Invalid ELF program headers: {name}')
    has_executable_load = False
    for index in range(phnum):
        off = phoff + index * phentsize
        p_type, p_flags = struct.unpack_from('<II', data, off)
        p_offset, _, _, p_filesz, p_memsz, _ = struct.unpack_from('<QQQQQQ', data, off + 8)
        if p_type == 1:
            if p_filesz > len(data) or p_offset > len(data) - p_filesz or p_memsz < p_filesz:
                raise RuntimePackagingError(f'Invalid ELF PT_LOAD bounds: {name}')
            if p_flags & 1:
                has_executable_load = True
    if not has_executable_load:
        raise RuntimePackagingError(f'Missing executable ELF PT_LOAD: {name}')


def validate_command(data: bytes, name: str, prefix: str) -> None:
    if name in ELF_COMMANDS or data.startswith(b'\x7fELF'):
        validate_elf(data, f'bin/{name}')
        return
    if name != 'code-server':
        raise RuntimePackagingError(f'Command must be ELF: {name}')
    if not data.startswith(b'#!'):
        raise RuntimePackagingError('code-server must be an executable ELF or script with shebang')
    line = data.split(b'\n', 1)[0]
    try:
        shebang = line.decode('ascii')
    except UnicodeError as exc:
        raise RuntimePackagingError('Invalid code-server shebang') from exc
    if not (shebang.startswith('#!' + prefix + '/bin/') and len(shebang) <= 180):
        raise RuntimePackagingError('code-server shebang uses a different prefix')


def _rel(path: Path, root: Path) -> str:
    name = path.relative_to(root).as_posix()
    pure = PurePosixPath(name)
    if pure.is_absolute() or not name or any(x in ('', '.', '..') for x in pure.parts) or '\\' in name or '\x00' in name:
        raise RuntimePackagingError('Unsafe runtime file path')
    return name


def _file_bytes(path: Path, limit: int = MAX_BYTES) -> bytes:
    if path.stat().st_size > limit:
        raise RuntimePackagingError('Runtime file exceeds size limit')
    return path.read_bytes()


def package_prefix(source: Path, assets: Path, package_name: str = 'org.omega.actions') -> dict:
    """Produce assets/bootstrap-* with SHA256, strict path and symlink controls."""
    if not PACKAGE_RE.fullmatch(package_name):
        raise RuntimePackagingError('Invalid package identifier')
    root = Path(source).resolve(strict=True)
    if not root.is_dir():
        raise RuntimePackagingError('Source prefix must be a directory')
    prefix = f'/data/data/{package_name}/files/usr'
    files: dict[str, Path] = {}
    symlinks: dict[str, str] = {}
    total = 0
    for path in sorted(root.rglob('*')):
        name = _rel(path, root)
        if path.is_symlink():
            target = os.readlink(path)
            if target.startswith(prefix + '/'):
                actual = root / target[len(prefix) + 1:]
            elif target.startswith('/'):
                raise RuntimePackagingError(f'External absolute symlink: {name}')
            else:
                actual = path.parent / target
            try:
                actual.resolve(strict=True).relative_to(root)
            except (OSError, ValueError) as exc:
                raise RuntimePackagingError(f'Unsafe or broken symlink: {name}') from exc
            symlinks[name] = target
        elif path.is_file():
            size = path.stat().st_size
            total += size
            if total > MAX_BYTES:
                raise RuntimePackagingError('Runtime exceeds 2 GiB extraction limit')
            files[name] = path
        elif not path.is_dir():
            raise RuntimePackagingError(f'Special device/socket not allowed: {name}')
        if len(files) + len(symlinks) > MAX_FILES:
            raise RuntimePackagingError('Too many runtime files')
    for command in REQUIRED_COMMANDS:
        path = root / 'bin' / command
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise RuntimePackagingError(f'Missing or unsafe command: {command}') from exc
        if not resolved.is_file() or not os.access(resolved, os.X_OK):
            raise RuntimePackagingError(f'Missing executable command: {command}')
        validate_command(_file_bytes(resolved), command, prefix)
    if not any(name.startswith('share/code-server/') or name.startswith('lib/node_modules/code-server/')
               for name in files):
        raise RuntimePackagingError('Missing code-server application resources')
    if 'SYMLINKS.txt' in files or 'SYMLINKS.txt' in symlinks:
        raise RuntimePackagingError('Reserved symlink manifest path in runtime')
    symlink_manifest = ''.join(f'{target}←{name}\n' for name, target in sorted(symlinks.items())).encode('utf-8')
    if len(symlink_manifest) > 2 * 1024 * 1024:
        raise RuntimePackagingError('Symlink manifest too large')
    assets = Path(assets)
    assets.mkdir(parents=True, exist_ok=True)
    # Do not overwrite a valid release asset until all checks and ZIP CRC pass.
    with tempfile.TemporaryDirectory(prefix='omega-runtime-', dir=assets) as tmp:
        tmpdir = Path(tmp)
        archive = tmpdir / 'bootstrap-aarch64-v8a.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            for name, path in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o100755 if os.access(path, os.X_OK) else 0o100644) << 16
                with z.open(info, 'w', force_zip64=True) as out, path.open('rb') as inp:
                    shutil.copyfileobj(inp, out, length=1024 * 1024)
            info = zipfile.ZipInfo('SYMLINKS.txt', date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, symlink_manifest)
        with zipfile.ZipFile(archive) as z:
            bad = z.testzip()
            if bad:
                raise RuntimePackagingError(f'ZIP CRC mismatch: {bad}')
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        (tmpdir / 'bootstrap-aarch64-v8a.sha256').write_text(digest + '\n', encoding='ascii')
        (tmpdir / 'bootstrap-prefix.txt').write_text(prefix + '\n', encoding='utf-8')
        from tools.verify_runtime_bundle import inspect_runtime_bundle
        inspect_runtime_bundle(tmpdir, package_name)
        for name in ('bootstrap-aarch64-v8a.zip', 'bootstrap-aarch64-v8a.sha256', 'bootstrap-prefix.txt'):
            os.replace(tmpdir / name, assets / name)
    return {'commands': list(REQUIRED_COMMANDS), 'files': len(files), 'symlinks': len(symlinks),
            'sha256': digest, 'prefix': prefix, 'execution_verified': False, 'structural_validation': 'PASS'}


def main() -> int:
    p = argparse.ArgumentParser(description='Package a REAL package-prefix-compatible Termux runtime')
    p.add_argument('--prefix-root', type=Path, required=True)
    p.add_argument('--assets', type=Path, required=True)
    p.add_argument('--package', default='org.omega.actions')
    args = p.parse_args()
    try:
        print(json.dumps(package_prefix(args.prefix_root, args.assets, args.package), indent=2))
    except (OSError, RuntimePackagingError, ValueError) as exc:
        p.exit(2, f'BLOCKED: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
