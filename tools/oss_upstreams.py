"""Pinned, auditable acquisition of upstream OSS source trees.

A source lock is NOT a substitute for a compiled Android runtime.  The tool
performs an actual git checkout and checks commit identity and license presence.
It never executes source code, install hooks or git submodules.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from typing import Mapping, Sequence


class LockError(ValueError):
    """Unsafe lock, missing dependency, checkout mismatch or integrity failure."""


_ID = re.compile(r'^[a-z][a-z0-9_-]{0,63}$')
_REPO = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9_.-]+$')
_SHA = re.compile(r'^[0-9a-f]{40}$')
_LICENSE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9.+() -]{0,95}$')


@dataclass(frozen=True)
class Source:
    id: str
    repository: str
    commit: str
    license: str
    license_file: str
    purpose: str

    @property
    def url(self) -> str:
        return f'https://github.com/{self.repository}.git'


def _relpath(value: str) -> bool:
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(x not in ('', '.', '..') for x in value.split('/'))


def load_lock(lock: Path) -> tuple[Source, ...]:
    try:
        raw = Path(lock).read_bytes()
        if len(raw) > 256 * 1024:
            raise LockError('Source lock exceeds 256 KiB')
        document = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LockError(f'Cannot read source lock: {exc}') from exc
    if not isinstance(document, dict) or document.get('schema') != 1 or not isinstance(document.get('sources'), list):
        raise LockError('Invalid source lock schema')
    entries = document['sources']
    if not 1 <= len(entries) <= 64:
        raise LockError('Source count outside 1..64')
    sources: list[Source] = []
    seen_ids: set[str] = set()
    seen_repos: set[str] = set()
    required = {'id', 'repository', 'commit', 'license', 'license_file', 'purpose'}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != required:
            raise LockError('Invalid source entry fields')
        if not isinstance(entry['id'], str) or not _ID.fullmatch(entry['id']):
            raise LockError('Invalid source id')
        if not isinstance(entry['repository'], str) or not _REPO.fullmatch(entry['repository']):
            raise LockError('Invalid GitHub repository')
        if not _SHA.fullmatch(str(entry['commit'])):
            raise LockError('Source revision must be a lowercase 40-character SHA')
        if not isinstance(entry['license'], str) or not _LICENSE.fullmatch(entry['license']):
            raise LockError('Missing or invalid license identifier')
        if not _relpath(entry['license_file']):
            raise LockError('Unsafe license path')
        if not isinstance(entry['purpose'], str) or not 1 <= len(entry['purpose']) <= 240:
            raise LockError('Missing source purpose')
        if entry['id'] in seen_ids or entry['repository'].lower() in seen_repos:
            raise LockError('Duplicate source identifier or repository')
        seen_ids.add(entry['id'])
        seen_repos.add(entry['repository'].lower())
        sources.append(Source(**entry))
    return tuple(sources)


def audit_lock(lock: Path) -> dict:
    sources = load_lock(lock)
    return {'status': 'PASS', 'count': len(sources),
            'sources': [dict(id=x.id, repository=x.repository, commit=x.commit,
                             license=x.license, purpose=x.purpose) for x in sources]}


def _run_git(args: Sequence[str], *, cwd: Path | None = None, timeout: int = 240,
             allow_local: bool = False) -> str:
    env = dict(os.environ)
    env.update(GIT_TERMINAL_PROMPT='0', GIT_LFS_SKIP_SMUDGE='1', GIT_CONFIG_NOSYSTEM='1',
               GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS='0')
    cmd = ['git', '-c', 'core.hooksPath=/dev/null', '-c',
           'protocol.file.allow=' + ('always' if allow_local else 'never'),
           '-c', 'protocol.ext.allow=never', *args]
    try:
        result = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True,
                                timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LockError(f'Git operation failed: {type(exc).__name__}') from exc
    if result.returncode:
        # Do not leak potentially credential-bearing Git stderr into reports.
        raise LockError(f'Git command {args[0]} failed (exit {result.returncode})')
    return result.stdout.strip()


def _vendor_root(root: Path, *, create: bool) -> Path:
    root = Path(root)
    if root.is_symlink():
        raise LockError('Vendor root cannot be a symlink')
    if create:
        root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir():
        raise LockError('Vendor root must be a directory')
    return root.resolve(strict=True)


def _source_report(source: Source, path: Path) -> dict:
    if path.is_symlink() or not path.is_dir():
        raise LockError('Missing or symlinked checkout')
    actual = _run_git(['rev-parse', 'HEAD'], cwd=path)
    if actual != source.commit:
        raise LockError(f'Commit mismatch for {source.id}')
    license_path = path / source.license_file
    if license_path.is_symlink() or not license_path.is_file() or not license_path.resolve().is_relative_to(path.resolve()):
        raise LockError(f'License file missing or unsafe for {source.id}')
    if not license_path.read_bytes().strip():
        raise LockError(f'Empty license file for {source.id}')
    _run_git(['ls-files', '--error-unmatch', '--', source.license_file], cwd=path)
    status = _run_git(['status', '--porcelain=v1', '--untracked-files=all'], cwd=path)
    unexpected = [x for x in status.splitlines() if x != '?? .omega-source.json']
    if unexpected:
        raise LockError(f'Checkout contains uncommitted modifications: {source.id}')
    return {'id': source.id, 'repository': source.repository, 'commit': actual,
            'license': source.license, 'license_sha256': hashlib.sha256(license_path.read_bytes()).hexdigest()}


def sync_sources(lock: Path, destination: Path, *, local_sources: Mapping[str, Path] | None = None,
                 ids: set[str] | None = None, allow_network: bool = False) -> dict:
    sources = load_lock(lock)
    if ids is not None and (not ids or ids - {x.id for x in sources}):
        raise LockError('Requested unknown or empty source selection')
    chosen = [x for x in sources if ids is None or x.id in ids]
    if local_sources is None and not allow_network:
        raise LockError('Network source acquisition requires explicit --allow-network')
    root = _vendor_root(destination, create=True)
    for source in chosen:
        if (root / source.id).exists() or (root / source.id).is_symlink():
            raise LockError(f'Checkout already exists: {source.id}')
    completed: list[dict] = []
    for source in chosen:
        temp = Path(tempfile.mkdtemp(prefix=f'.{source.id}-', dir=root))
        try:
            local = local_sources is not None and source.id in local_sources
            if local_sources is not None and not local:
                raise LockError(f'Offline source not supplied: {source.id}')
            origin = str(Path(local_sources[source.id]).resolve(strict=True)) if local else source.url
            options = ['clone', '--no-checkout', '--no-recurse-submodules']
            if not local:
                options.append('--filter=blob:none')
            _run_git([*options, origin, str(temp)], timeout=900, allow_local=local)
            _run_git(['checkout', '--detach', source.commit], cwd=temp, timeout=900, allow_local=local)
            report = _source_report(source, temp)
            (temp / '.omega-source.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n', encoding='utf-8')
            os.rename(temp, root / source.id)
            completed.append(report)
        except Exception:
            shutil.rmtree(temp, ignore_errors=True)
            raise
    return {'status': 'PASS', 'count': len(completed), 'sources': completed}


def verify_sources(lock: Path, destination: Path, *, ids: set[str] | None = None) -> dict:
    sources = load_lock(lock)
    root = _vendor_root(destination, create=False)
    chosen = [x for x in sources if ids is None or x.id in ids]
    if not chosen or (ids is not None and len(chosen) != len(ids)):
        raise LockError('Unknown or empty verification selection')
    reports = []
    for source in chosen:
        path = root / source.id
        if path.is_symlink() or not path.exists():
            raise LockError(f'Missing checkout {source.id}')
        report = _source_report(source, path)
        try:
            recorded = json.loads((path / '.omega-source.json').read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise LockError(f'Missing provenance for {source.id}') from exc
        if recorded != report:
            raise LockError(f'Provenance mismatch for {source.id}')
        reports.append(report)
    return {'status': 'PASS', 'count': len(reports), 'sources': reports}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Pinned OSS source audit, sync and verification')
    parser.add_argument('command', choices=('audit', 'sync', 'verify', 'resolve'))
    parser.add_argument('--lock', type=Path, default=Path(__file__).resolve().parents[1] / 'config' / 'upstreams.lock.json')
    parser.add_argument('--destination', type=Path, default=Path('vendor/upstreams'))
    parser.add_argument('--id', action='append', dest='ids')
    parser.add_argument('--allow-network', action='store_true')
    args = parser.parse_args(argv)
    try:
        ids = set(args.ids) if args.ids else None
        if args.command == 'audit':
            result = audit_lock(args.lock)
        elif args.command == 'resolve':
            if not ids or len(ids) != 1:
                raise LockError('Resolve requires exactly one --id')
            found = [x for x in load_lock(args.lock) if x.id in ids]
            if not found:
                raise LockError('Unknown source')
            print(found[0].commit)
            return 0
        elif args.command == 'sync':
            result = sync_sources(args.lock, args.destination, ids=ids, allow_network=args.allow_network)
        else:
            result = verify_sources(args.lock, args.destination, ids=ids)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (LockError, OSError, ValueError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(exc)}, sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
