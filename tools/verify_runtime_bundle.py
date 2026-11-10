"""Strict structural gate for a package-prefix-compatible arm64 Termux runtime.

This is deliberately NOT an Android runtime test: structural verification alone
cannot establish that native binaries execute on the target phone.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import sys
import zipfile


class RuntimeBundleError(ValueError):
    """Release gate failure, with no automatic fallback to a mock runtime."""


_REQUIRED=('bash','python','git','llama-cli')
_PREFIX='bootstrap-prefix.txt'
_DIGEST='bootstrap-aarch64-v8a.sha256'
_ZIP='bootstrap-aarch64-v8a.zip'


def inspect_runtime_bundle(assets:Path, package_name:str)->dict:
    assets=Path(assets)
    if not re.fullmatch(r'[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+',package_name):
        raise RuntimeBundleError('Invalid Android package identifier')
    archive=assets/_ZIP
    if not archive.is_file() or not (assets/_DIGEST).is_file() or not (assets/_PREFIX).is_file():
        raise RuntimeBundleError('Missing compatible bootstrap archive, prefix or SHA-256 manifest')
    expected_prefix=f'/data/data/{package_name}/files/usr'
    if (assets/_PREFIX).read_text('utf-8').strip()!=expected_prefix:
        raise RuntimeBundleError('Bootstrap prefix does not match application ID')
    digest=(assets/_DIGEST).read_text('ascii').strip().split()[0]
    if not re.fullmatch('[a-fA-F0-9]{64}',digest):
        raise RuntimeBundleError('Invalid SHA-256 manifest')
    h=hashlib.sha256()
    with archive.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            h.update(block)
    if h.hexdigest().lower()!=digest.lower():
        raise RuntimeBundleError('Bootstrap SHA-256 mismatch')
    with zipfile.ZipFile(archive) as z:
        entries=z.infolist()
        if len(entries)>200000 or sum(x.file_size for x in entries)>2*1024**3:
            raise RuntimeBundleError('Bootstrap archive exceeds resource limits')
        names=set()
        for item in entries:
            path=PurePosixPath(item.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in item.filename or '\x00' in item.filename:
                raise RuntimeBundleError('Unsafe bootstrap archive path')
            if item.filename in names:
                raise RuntimeBundleError('Duplicate bootstrap path')
            names.add(item.filename)
        symlinks={}
        if 'SYMLINKS.txt' in names:
            raw=z.read('SYMLINKS.txt')
            if len(raw)>2*1024*1024:raise RuntimeBundleError('Symlink manifest too large')
            for line in raw.decode('utf-8').splitlines():
                if not line.strip():continue
                pair=line.split('←',1)
                if len(pair)!=2:raise RuntimeBundleError('Invalid symlink record')
                target,link=(p.strip() for p in pair)
                if link.startswith('/') or '..' in PurePosixPath(link).parts or not link:
                    raise RuntimeBundleError('Unsafe bootstrap symlink path')
                if link in symlinks:raise RuntimeBundleError('Duplicate symlink')
                symlinks[link]=target
        def get_entry(name:str,visited:set[str]|None=None)->bytes:
            visited=visited or set()
            if name in visited:raise RuntimeBundleError('Symlink cycle in runtime')
            visited.add(name)
            if name in names:return z.read(name)
            target=symlinks.get(name)
            if target is None:raise RuntimeBundleError('Missing runtime command: '+name)
            if target.startswith(expected_prefix+'/'):
                target=target[len(expected_prefix)+1:]
            elif target.startswith('/'):
                raise RuntimeBundleError('External symlink target in runtime')
            else:
                import posixpath
                target=posixpath.normpath(posixpath.join(posixpath.dirname(name),target))
            if target.startswith('../') or target=='..':raise RuntimeBundleError('Escaping runtime symlink')
            return get_entry(target,visited)
        for cmd in _REQUIRED:
            binary=get_entry('bin/'+cmd)
            if len(binary)<20 or binary[:4]!=b'\x7fELF' or binary[5]!=1:
                raise RuntimeBundleError('Runtime command is not a little-endian ELF: '+cmd)
            if struct.unpack_from('<H',binary,18)[0]!=183:
                raise RuntimeBundleError('Runtime command is not AArch64: '+cmd)
    return {'abi':'arm64-v8a','package_name':package_name,'required_commands':list(_REQUIRED),
            'verified_sha256':True,'bootstrap_sha256':digest.lower(),
            'execution_verified':False,'validation':'STRUCTURAL_ONLY'}


def main()->int:
    root=Path(__file__).resolve().parents[1]
    assets=root/'android/app/src/main/assets'
    try:
        result=inspect_runtime_bundle(assets,'org.omega.actions')
        print(json.dumps(result,indent=2))
        return 0
    except (RuntimeBundleError,OSError,zipfile.BadZipFile,UnicodeError) as exc:
        print(json.dumps({'status':'BLOCKED','reason':str(exc),'production_apk_ready':False},ensure_ascii=False))
        return 2


if __name__=='__main__':sys.exit(main())
