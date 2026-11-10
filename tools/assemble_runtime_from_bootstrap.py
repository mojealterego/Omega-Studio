"""Import an upstream custom-prefix Termux bootstrap and prebuilt code-server.

Offline assembly. This module never downloads binaries or treats host ELF as Android.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import tempfile
import zipfile

from tools.runtime_supply_chain import MAX_BYTES, MAX_FILES, RuntimePackagingError, package_prefix


class RuntimeImportError(ValueError):
    pass


def _valid_rel(name: str) -> bool:
    p=PurePosixPath(name)
    return bool(name) and not p.is_absolute() and '..' not in p.parts and '\\' not in name and '\x00' not in name


def _symlink_target(target: str, link: str, prefix: str) -> str:
    if target.startswith(prefix + '/'):
        resolved=target[len(prefix) + 1:]
    elif target.startswith('/'):
        raise RuntimeImportError('External symlink target')
    else:
        resolved=posixpath.normpath(posixpath.join(posixpath.dirname(link),target))
    if not _valid_rel(resolved) or resolved in ('.','..'):
        raise RuntimeImportError('Unsafe symlink target')
    return resolved


def unpack_bootstrap(archive: Path, target: Path, package_name: str) -> Path:
    archive=Path(archive)
    target=Path(target)
    prefix=f'/data/data/{package_name}/files/usr'
    if not target.parent.is_dir() or target.exists() or target.is_symlink():
        raise RuntimeImportError('Target prefix exists or parent missing')
    with tempfile.TemporaryDirectory(prefix='omega-bootstrap-',dir=target.parent) as temp:
        root=Path(temp)/'usr';root.mkdir()
        try:
            with zipfile.ZipFile(archive) as z:
                infos=z.infolist()
                if len(infos)>MAX_FILES or sum(i.file_size for i in infos)>MAX_BYTES:
                    raise RuntimeImportError('Bootstrap exceeds size limits')
                names=set()
                for entry in infos:
                    name=entry.filename
                    if not _valid_rel(name):
                        raise RuntimeImportError('Unsafe archive path')
                    if name in names:
                        raise RuntimeImportError('Archive duplicate entry')
                    names.add(name)
                if 'SYMLINKS.txt' not in names:
                    raise RuntimeImportError('Missing SYMLINKS.txt')
                symlink_raw=z.read('SYMLINKS.txt')
                if len(symlink_raw)>2*1024*1024:
                    raise RuntimeImportError('Symlink manifest exceeds limit')
                pairs={}
                for line in symlink_raw.decode('utf-8').splitlines():
                    if not line.strip():continue
                    if line.count('←')!=1:
                        raise RuntimeImportError('Invalid symlink record')
                    raw_target,link=line.split('←',1)
                    if not _valid_rel(link) or link in names or link in pairs:
                        raise RuntimeImportError('Symlink collision or unsafe path')
                    pairs[link]=_symlink_target(raw_target,link,prefix)
                for entry in infos:
                    if entry.filename=='SYMLINKS.txt':continue
                    dest=root/entry.filename
                    if entry.is_dir():
                        dest.mkdir(parents=True,exist_ok=True)
                        continue
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(entry) as inp,dest.open('xb') as out:
                        shutil.copyfileobj(inp,out,length=1024*1024)
                    if entry.filename.startswith(('bin/','libexec/','lib/apt/')):
                        dest.chmod(0o700)
                for link,resolved in pairs.items():
                    dest=root/link
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    if dest.exists() or dest.is_symlink():
                        raise RuntimeImportError('Symlink collision with file')
                    rel=os.path.relpath(root/resolved,dest.parent)
                    dest.symlink_to(rel)
                for link in pairs:
                    dest=root/link
                    try:dest.resolve(strict=True).relative_to(root)
                    except (OSError,ValueError,RuntimeError) as exc:
                        raise RuntimeImportError('Broken or escaping symlink') from exc
            root.rename(target)
        except (OSError,UnicodeError,zipfile.BadZipFile) as exc:
            raise RuntimeImportError(f'Bootstrap import failed: {exc}') from exc
    return target


def overlay_editor(prefix_root: Path, editor_root: Path) -> None:
    """Overlay an independently built, same-prefix code-server tree; no binaries fetched."""
    prefix_root=Path(prefix_root).resolve(strict=True)
    editor_root=Path(editor_root).resolve(strict=True)
    if not editor_root.is_dir():
        raise RuntimeImportError('Editor prefix must be a directory')
    for path in sorted(editor_root.rglob('*')):
        name=path.relative_to(editor_root).as_posix()
        if not _valid_rel(name):raise RuntimeImportError('Unsafe editor path')
        dest=prefix_root/name
        if path.is_symlink():
            try:resolved=path.resolve(strict=True);rel=resolved.relative_to(editor_root)
            except (OSError,ValueError,RuntimeError) as exc:
                raise RuntimeImportError('Editor symlink escapes prefix') from exc
            if dest.exists() or dest.is_symlink():
                raise RuntimeImportError('Editor symlink collision')
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.symlink_to(os.path.relpath(prefix_root/rel,dest.parent))
        elif path.is_dir():dest.mkdir(parents=True,exist_ok=True)
        elif path.is_file():
            if dest.exists() or dest.is_symlink():
                raise RuntimeImportError('Editor overwrites an existing runtime file')
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,dest)
        else:raise RuntimeImportError('Unsupported editor file type')


def main() -> int:
    p=argparse.ArgumentParser(description='Offline import custom Termux and code-server for OMEGA APK')
    p.add_argument('--bootstrap',type=Path,required=True)
    p.add_argument('--editor-prefix',type=Path,required=True)
    p.add_argument('--assets',type=Path,required=True)
    p.add_argument('--package',default='org.omega.actions')
    args=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='omega-assemble-') as tmp:
        root=Path(tmp)/'usr'
        try:
            unpack_bootstrap(args.bootstrap,root,args.package)
            overlay_editor(root,args.editor_prefix)
            print(json.dumps(package_prefix(root,args.assets,args.package),indent=2))
        except (RuntimeImportError,RuntimePackagingError,OSError,ValueError) as exc:
            p.exit(2,f'BLOCKED: {exc}\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
