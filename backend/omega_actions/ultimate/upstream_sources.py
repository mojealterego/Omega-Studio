"""Pin, acquire and audit official open-source source trees without executing them.

The catalog is a supply-chain input, not a license waiver or a binary distribution.
Only explicit, pinned, allowlisted Git repositories may be checked out. The
caller must confirm network access and accept upstream license obligations.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
from typing import Iterator
from urllib.parse import urlsplit


class CatalogError(ValueError):
    """Untrusted or malformed upstream source catalog."""


class SourceSyncError(RuntimeError):
    """Upstream source cannot be safely checked out or verified."""


_VALID_NAME = re.compile(r'[a-z][a-z0-9_.-]{0,63}\Z')
_VALID_SHA = re.compile(r'[a-f0-9]{40}\Z')
_VALID_LICENSE = re.compile(r'[A-Za-z0-9.+-]{2,64}\Z')
_VALID_REPO = re.compile(r'/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?\Z')
_ALLOWED_HOSTS = frozenset({'github.com', 'gitlab.com', 'huggingface.co'})
_ALLOWED_ROLES = frozenset({'android', 'runtime', 'editor', 'toolchain', 'integration', 'ci', 'terminal'})


def _validate_repository(value: str, *, allow_local: bool) -> str:
    if not isinstance(value, str) or len(value) > 300:
        raise CatalogError('Invalid repository URL')
    parts = urlsplit(value)
    if allow_local and parts.scheme == 'file':
        if parts.netloc or parts.query or parts.fragment or not parts.path.startswith('/'):
            raise CatalogError('Invalid local source URL')
        local = Path(parts.path)
        if not local.is_dir() or local.is_symlink():
            raise CatalogError('Local source must be an existing regular directory')
        return value
    if (parts.scheme != 'https' or parts.hostname not in _ALLOWED_HOSTS
            or parts.netloc != parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment or not _VALID_REPO.fullmatch(parts.path)
            or any(seg in ('.', '..') for seg in parts.path.split('/'))):
        raise CatalogError('Repository must be a canonical HTTPS URL on an allowlisted host')
    return value


def _validate_rel_path(value: str) -> str:
    if not isinstance(value, str) or len(value) > 200 or not value or '\\' in value or '\x00' in value:
        raise CatalogError('Invalid relative license path')
    parts = PurePosixPath(value)
    if parts.is_absolute() or any(x in ('.', '..', '') for x in value.split('/')):
        raise CatalogError('License path traversal is prohibited')
    return value


@dataclass(frozen=True)
class UpstreamSource:
    name: str
    repository: str
    commit: str
    license: str
    license_files: tuple[str, ...]
    role: str

    def public_info(self) -> dict:
        return {'name': self.name, 'repository': self.repository, 'commit': self.commit,
                'license': self.license, 'license_files': list(self.license_files), 'role': self.role}


@dataclass(frozen=True)
class SourceCatalog:
    sources: tuple[UpstreamSource, ...]

    @classmethod
    def load(cls, path: Path, *, allow_local: bool = False) -> 'SourceCatalog':
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise CatalogError('Cannot load source catalog') from exc
        if not isinstance(data, dict) or data.get('schema_version') != 1:
            raise CatalogError('Unsupported catalog schema')
        records = data.get('sources')
        if not isinstance(records, list) or not 1 <= len(records) <= 128:
            raise CatalogError('Source catalog requires 1..128 entries')
        names: set[str] = set()
        parsed = []
        for item in records:
            if not isinstance(item, dict) or set(item) != {'name', 'repository', 'commit', 'license', 'license_files', 'role'}:
                raise CatalogError('Unexpected source entry fields')
            name = item['name']
            if not isinstance(name, str) or not _VALID_NAME.fullmatch(name) or name in ('.', '..') or '..' in name:
                raise CatalogError('Invalid source name')
            if name in names:
                raise CatalogError('Duplicate source name: ' + name)
            names.add(name)
            repo = _validate_repository(item['repository'], allow_local=allow_local)
            commit = item['commit']
            if not isinstance(commit, str) or not _VALID_SHA.fullmatch(commit):
                raise CatalogError('Source commit must be an immutable 40-character lowercase SHA-1')
            license_id = item['license']
            if not isinstance(license_id, str) or not _VALID_LICENSE.fullmatch(license_id):
                raise CatalogError('Invalid declared SPDX license identifier')
            license_files = item['license_files']
            if not isinstance(license_files, list) or not 1 <= len(license_files) <= 8:
                raise CatalogError('At least one license file is required')
            licenses = tuple(_validate_rel_path(p) for p in license_files)
            if len(set(licenses)) != len(licenses):
                raise CatalogError('Duplicate license file')
            role = item['role']
            if role not in _ALLOWED_ROLES:
                raise CatalogError('Invalid upstream source role')
            parsed.append(UpstreamSource(name, repo, commit, license_id, licenses, role))
        return cls(tuple(parsed))

    def get(self, name: str) -> UpstreamSource:
        for item in self.sources:
            if item.name == name:
                return item
        raise CatalogError('Unknown upstream source')

    def public_info(self) -> list[dict]:
        return [x.public_info() for x in self.sources]


def default_catalog() -> SourceCatalog:
    return SourceCatalog.load(Path(__file__).with_name('upstream_sources.lock.json'))


class UpstreamSourceManager:
    """Offline-verifiable git checkout with an explicit opt-in network step."""

    def __init__(self, catalog: SourceCatalog, root: Path, *, allow_local: bool = False,
                 git_timeout_seconds: int = 1800):
        self.catalog = catalog
        self.root = Path(root)
        if not self.root.is_dir() or self.root.is_symlink():
            raise SourceSyncError('Source workspace must be a pre-existing non-symlink directory')
        self.root = self.root.resolve(strict=True)
        self.allow_local = allow_local
        if not 5 <= git_timeout_seconds <= 7200:
            raise SourceSyncError('Git timeout out of range')
        self.timeout = git_timeout_seconds

    @contextmanager
    def _exclusive(self) -> Iterator[None]:
        flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
        try:
            fd = os.open(self.root / '.omega-source-sync.lock', flags, 0o600)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise SourceSyncError('Source lock is not a regular file')
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        except OSError as exc:
            raise SourceSyncError('Cannot lock source workspace') from exc
        finally:
            if 'fd' in locals():
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

    def _git(self, args: list[str], *, cwd: Path | None = None, timeout: int | None = None) -> str:
        env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
               'HOME': str(self.root), 'GIT_CONFIG_NOSYSTEM': '1',
               'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_TERMINAL_PROMPT': '0',
               'GIT_LFS_SKIP_SMUDGE': '1', 'GIT_OPTIONAL_LOCKS': '0',
               'LC_ALL': 'C'}
        if self.allow_local:
            env['GIT_ALLOW_PROTOCOL'] = 'file:https'
        else:
            env['GIT_ALLOW_PROTOCOL'] = 'https'
        command = ['git', '-c', 'core.hooksPath=' + os.devnull,
                   '-c', 'submodule.recurse=false', *args]
        try:
            result = subprocess.run(command, cwd=cwd, env=env, text=True,
                                    capture_output=True, check=False, timeout=timeout or self.timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SourceSyncError('Git invocation failed or exceeded timeout') from exc
        if result.returncode:
            # Never forward upstream stderr, which can contain credentials or untrusted text.
            raise SourceSyncError('Git command failed (exit ' + str(result.returncode) + ')')
        return result.stdout.strip()

    @staticmethod
    def _validate_tree(target: Path) -> None:
        root = target.resolve(strict=True)
        for path in root.rglob('*'):
            if path.is_symlink():
                try:
                    path.resolve(strict=True).relative_to(root)
                except (ValueError, OSError, RuntimeError) as exc:
                    raise SourceSyncError('Upstream symlink escapes checkout') from exc

    def _license_digest(self, target: Path, source: UpstreamSource) -> tuple[str, str]:
        for name in source.license_files:
            path = target / name
            if path.is_file() and not path.is_symlink():
                raw = path.read_bytes()
                if not raw:
                    raise SourceSyncError('Upstream license file is empty')
                return name, hashlib.sha256(raw).hexdigest()
        raise SourceSyncError('Required upstream license file missing')

    def sync(self, name: str, *, consent: bool = False) -> dict:
        if not consent:
            raise SourceSyncError('Explicit consent is required before source download')
        source = self.catalog.get(name)
        _validate_repository(source.repository, allow_local=self.allow_local)
        target = self.root / source.name
        with self._exclusive():
            if target.exists() or target.is_symlink():
                raise SourceSyncError('Source destination already exists')
            with tempfile.TemporaryDirectory(prefix='.omega-upstream-', dir=self.root) as temp:
                staging = Path(temp) / 'source'
                staging.mkdir()
                self._git(['init', '-q', str(staging)])
                self._git(['-C', str(staging), 'fetch', '--no-tags', '--depth=1',
                           source.repository, source.commit])
                self._git(['-C', str(staging), 'checkout', '-q', '--detach', 'FETCH_HEAD'])
                actual = self._git(['-C', str(staging), 'rev-parse', 'HEAD'])
                if actual != source.commit:
                    raise SourceSyncError('Git checkout differs from pinned source commit')
                if self._git(['-C', str(staging), 'status', '--porcelain', '--untracked-files=all']):
                    raise SourceSyncError('Fresh checkout is modified')
                self._validate_tree(staging)
                license_file, license_sha = self._license_digest(staging, source)
                provenance = {**source.public_info(), 'license_file_verified': license_file,
                              'license_sha256': license_sha, 'checkout_sha': actual,
                              'upstream_source_executed': False, 'device_binary_verified': False}
                prov_dir = self.root / '.omega-provenance'
                if prov_dir.is_symlink():
                    raise SourceSyncError('Provenance directory cannot be a symlink')
                prov_dir.mkdir(mode=0o700, exist_ok=True)
                if not prov_dir.is_dir():
                    raise SourceSyncError('Invalid provenance directory')
                prov_path = prov_dir / (source.name + '.json')
                if prov_path.exists() or prov_path.is_symlink():
                    raise SourceSyncError('Provenance record already exists')
                staging.rename(target)
                try:
                    with prov_path.open('x', encoding='utf-8') as output:
                        json.dump(provenance, output, indent=2, sort_keys=True)
                        output.write('\n')
                except OSError as exc:
                    shutil.rmtree(target)
                    raise SourceSyncError('Cannot record upstream provenance') from exc
                return provenance

    def verify(self, name: str) -> dict:
        source = self.catalog.get(name)
        target = self.root / source.name
        if not target.is_dir() or target.is_symlink():
            raise SourceSyncError('Source checkout missing or unsafe')
        with self._exclusive():
            prov_path = self.root / '.omega-provenance' / (source.name + '.json')
            if not prov_path.is_file() or prov_path.is_symlink():
                raise SourceSyncError('Source provenance missing')
            try:
                provenance = json.loads(prov_path.read_text(encoding='utf-8'))
            except (OSError, ValueError) as exc:
                raise SourceSyncError('Invalid source provenance') from exc
            actual = self._git(['-C', str(target), 'rev-parse', 'HEAD'])
            if actual != source.commit or provenance.get('checkout_sha') != actual:
                raise SourceSyncError('Source commit differs from lockfile')
            if self._git(['-C', str(target), 'status', '--porcelain', '--untracked-files=all']):
                raise SourceSyncError('Source checkout was modified')
            self._validate_tree(target)
            license_file, digest = self._license_digest(target, source)
            if provenance.get('license_file_verified') != license_file or provenance.get('license_sha256') != digest:
                raise SourceSyncError('Upstream license digest changed')
            return {'name': name, 'commit': actual, 'license': source.license,
                    'license_sha256': digest, 'verified': True}
