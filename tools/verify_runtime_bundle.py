"""Fail-closed structural verification of a self-contained Android/Termux runtime.

No structural test can prove that binaries actually run on Android. Production release
requires the separate device smoke test and signing verification.
"""
from __future__ import annotations

import hashlib
import json
import posixpath
from pathlib import Path, PurePosixPath
import re
import struct
import sys
import zipfile


class RuntimeBundleError(ValueError):
    """An archive cannot be used to claim a complete native runtime."""


_REQUIRED_ELF = ('bash', 'python', 'git', 'llama-cli', 'node')
_REQUIRED_SCRIPT = ('code-server',)
_REQUIRED = _REQUIRED_ELF + _REQUIRED_SCRIPT
_ZIP = 'bootstrap-aarch64-v8a.zip'
_DIGEST = 'bootstrap-aarch64-v8a.sha256'
_PREFIX = 'bootstrap-prefix.txt'
_MAX_ENTRIES = 200_000
_MAX_UNCOMPRESSED = 2 * 1024**3
_MAX_COMMAND_BYTES = 256 * 1024**2


def _valid_member(name: str) -> bool:
    p = PurePosixPath(name)
    return bool(name) and not p.is_absolute() and not name.startswith('./') and not name.startswith('\\') and not any(
        part in ('', '.', '..') for part in name.rstrip('/').split('/')
    ) and '\\' not in name and '\x00' not in name


def _read_elf(binary: bytes, name: str) -> None:
    if len(binary) < 4096 or binary[:4] != b'\x7fELF' or binary[4:7] != b'\x02\x01\x01':
        raise RuntimeBundleError('Invalid ELF64 little-endian program: ' + name)
    e_type, e_machine, e_version = struct.unpack_from('<HHI', binary, 16)
    if e_machine != 183:
        raise RuntimeBundleError('ELF is not AArch64: ' + name)
    if e_type != 3 or e_version != 1:
        raise RuntimeBundleError('Invalid ELF type: Android PIE ET_DYN required: ' + name)
    e_phoff = struct.unpack_from('<Q', binary, 32)[0]
    e_phentsize, e_phnum = struct.unpack_from('<HH', binary, 54)
    if e_phnum < 1 or e_phnum > 512 or e_phentsize < 56 or e_phoff < 64 or e_phoff + e_phnum * e_phentsize > len(binary):
        raise RuntimeBundleError('Invalid ELF program header table: ' + name)
    load_found = False
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, flags, p_offset, _vaddr, _paddr, p_filesz, _memsz, _align = struct.unpack_from('<IIQQQQQQ', binary, off)
        if p_offset > len(binary) or p_filesz > len(binary) - p_offset:
            raise RuntimeBundleError('Invalid ELF segment bounds: ' + name)
        if p_type == 1 and flags & 1:
            load_found = True
        if p_type == 3:
            interp = binary[p_offset:p_offset + p_filesz].rstrip(b'\0')
            if interp not in (b'/system/bin/linker64', b'/apex/com.android.runtime/bin/linker64'):
                raise RuntimeBundleError('ELF interpreter is not Android linker64: ' + name)
    if not load_found:
        raise RuntimeBundleError('ELF has no executable PT_LOAD segments: ' + name)


def _read_script(binary: bytes, name: str, prefix: str) -> None:
    if binary[:4] == b'\x7fELF':
        _read_elf(binary, name)
        return
    if not binary.startswith(b'#!'):
        raise RuntimeBundleError('code-server must be ELF or executable shebang script')
    first_line = binary.split(b'\n', 1)[0]
    try:
        interpreter = first_line[2:].decode('utf-8').strip().split(' ', 1)[0]
    except UnicodeError as exc:
        raise RuntimeBundleError('Invalid code-server shebang') from exc
    if not (interpreter.startswith(prefix + '/bin/') or interpreter == '/system/bin/sh'):
        raise RuntimeBundleError('code-server interpreter outside Android package prefix')


def inspect_runtime_bundle(assets: Path, package_name: str) -> dict:
    assets = Path(assets)
    if not re.fullmatch(r'[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+', package_name):
        raise RuntimeBundleError('Invalid Android package identifier')
    archive = assets / _ZIP
    if not archive.is_file() or not (assets / _DIGEST).is_file() or not (assets / _PREFIX).is_file():
        raise RuntimeBundleError('Missing compatible bootstrap archive, prefix or SHA-256 manifest')
    expected_prefix = f'/data/data/{package_name}/files/usr'
    if (assets / _PREFIX).read_text('utf-8').strip() != expected_prefix:
        raise RuntimeBundleError('Bootstrap prefix does not match application ID')
    manifest_text = (assets / _DIGEST).read_text('ascii').strip().split()
    if not manifest_text or not re.fullmatch('[a-fA-F0-9]{64}', manifest_text[0]):
        raise RuntimeBundleError('Invalid SHA-256 manifest')
    digest = manifest_text[0].lower()
    h = hashlib.sha256()
    with archive.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    if h.hexdigest() != digest:
        raise RuntimeBundleError('Bootstrap SHA-256 mismatch')

    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        if len(entries) > _MAX_ENTRIES or sum(x.file_size for x in entries) > _MAX_UNCOMPRESSED:
            raise RuntimeBundleError('Bootstrap archive exceeds resource limits')
        names = set()
        for item in entries:
            if not _valid_member(item.filename):
                raise RuntimeBundleError('Unsafe bootstrap archive path: ' + item.filename)
            if item.filename in names:
                raise RuntimeBundleError('Duplicate bootstrap path: ' + item.filename)
            names.add(item.filename)
        if 'SYMLINKS.txt' not in names:
            raise RuntimeBundleError('Bootstrap symlink manifest is required')
        if z.getinfo('SYMLINKS.txt').file_size > 2 * 1024**2:
            raise RuntimeBundleError('Symlink manifest too large')
        symlinks: dict[str, str] = {}
        for line in z.read('SYMLINKS.txt').decode('utf-8').splitlines():
            if not line.strip():
                continue
            pair = line.split('←', 1)
            if len(pair) != 2:
                raise RuntimeBundleError('Invalid symlink record')
            target, link = (p.strip() for p in pair)
            if not _valid_member(link) or not target or link in symlinks or link in names:
                raise RuntimeBundleError('Invalid or duplicate symlink path')
            if target.startswith('/'):
                if not (target.startswith(expected_prefix + '/') or target.startswith('/system/')):
                    raise RuntimeBundleError('External symlink target outside trusted Android prefixes')
            else:
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(link), target))
                if resolved.startswith('../') or resolved == '..' or resolved.startswith('/'):
                    raise RuntimeBundleError('Relative symlink escapes bootstrap prefix')
            symlinks[link] = target

        def get_entry(name: str, visited: set[str] | None = None) -> bytes:
            visited = set() if visited is None else visited
            if name in visited:
                raise RuntimeBundleError('Symlink cycle in runtime')
            visited.add(name)
            if name in names:
                info = z.getinfo(name)
                if info.file_size > _MAX_COMMAND_BYTES:
                    raise RuntimeBundleError('Runtime command too large: ' + name)
                return z.read(name)
            target = symlinks.get(name)
            if target is None:
                raise RuntimeBundleError('Missing runtime command: ' + name)
            if target.startswith(expected_prefix + '/'):
                target = target[len(expected_prefix) + 1:]
            elif target.startswith('/'):
                raise RuntimeBundleError('Runtime command resolves outside app prefix: ' + name)
            else:
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
            if not _valid_member(target):
                raise RuntimeBundleError('Runtime symlink escapes prefix: ' + name)
            return get_entry(target, visited)

        for command in _REQUIRED_ELF:
            _read_elf(get_entry('bin/' + command), command)
        for command in _REQUIRED_SCRIPT:
            _read_script(get_entry('bin/' + command), command, expected_prefix)

        editor_assets = any(
            name.startswith(('lib/node_modules/code-server/', 'share/code-server/', 'opt/code-server/', 'lib/code-server/'))
            and not name.endswith('/') and name != 'bin/code-server'
            for name in names
        )
        if not editor_assets:
            raise RuntimeBundleError('code-server editor payload missing from bootstrap')
        return {
            'abi': 'arm64-v8a',
            'package_name': package_name,
            'prefix': expected_prefix,
            'required_commands': list(_REQUIRED),
            'editor_payload_detected': True,
            'verified_sha256': True,
            'bootstrap_sha256': digest,
            'entry_sha256': {command: hashlib.sha256(get_entry('bin/' + command)).hexdigest() for command in _REQUIRED},
            'archive_entries': len(entries),
            'archive_uncompressed_bytes': sum(x.file_size for x in entries),
            'execution_verified': False,
            'validation': 'STRUCTURAL_ONLY',
        }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    assets = root / 'android/app/src/main/assets'
    try:
        result = inspect_runtime_bundle(assets, 'org.omega.actions')
        print(json.dumps(result, indent=2))
        return 0
    except (RuntimeBundleError, OSError, zipfile.BadZipFile, UnicodeError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(exc), 'production_apk_ready': False}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    sys.exit(main())
