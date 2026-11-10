"""GitHub organization catalog and explicitly requested local source snapshots."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile
from urllib.parse import quote
import httpx
from .archives import extract_zip

IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z')
SHA = re.compile(r'[0-9a-fA-F]{40}\Z')


class CrawlerError(RuntimeError):
    pass


def _name(value: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value) or value in ('.', '..'):
        raise ValueError('Invalid repository or organization identifier')
    return value


class GitHubOrgCrawler:
    def __init__(self, client: httpx.Client | None = None, token: str | None = None):
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)
        self.owns_client = client is None
        self.headers = {'Accept': 'application/vnd.github+json',
                        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'OmegaStudioUltimate/1.0'}
        if token:
            if any(c in token for c in '\r\n'):
                raise ValueError('Invalid token')
            self.headers['Authorization'] = 'Bearer ' + token

    def close(self):
        if self.owns_client:
            self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def crawl(self, organization: str, *, pages: int = 20, per_page: int = 100) -> list[dict]:
        organization = _name(organization)
        if not 1 <= pages <= 1000 or not 1 <= per_page <= 100:
            raise ValueError('Invalid pagination limits')
        found: dict[str, dict] = {}
        for page in range(1, pages + 1):
            try:
                response = self.client.get('https://api.github.com/orgs/' + organization + '/repos',
                                           params={'per_page': per_page, 'page': page, 'type': 'public'},
                                           headers=self.headers)
            except httpx.HTTPError as exc:
                raise CrawlerError('GitHub connection failed') from exc
            if response.status_code in (403, 429) and response.headers.get('x-ratelimit-remaining') == '0':
                raise CrawlerError('GitHub API rate limit reached')
            if response.status_code != 200:
                raise CrawlerError('GitHub API returned HTTP ' + str(response.status_code))
            try:
                records = response.json()
            except ValueError as exc:
                raise CrawlerError('GitHub API returned invalid JSON') from exc
            if not isinstance(records, list) or len(records) > per_page:
                raise CrawlerError('Invalid GitHub repository response')
            for item in records:
                if not isinstance(item, dict):
                    raise CrawlerError('Invalid repository record')
                full = item.get('full_name', '')
                parts = full.split('/') if isinstance(full, str) else []
                if len(parts) != 2 or parts[0].lower() != organization.lower():
                    raise CrawlerError('Repository identity mismatch')
                try:
                    _name(parts[0]); _name(parts[1])
                except ValueError as exc:
                    raise CrawlerError('Invalid repository identity') from exc
                license_data = item.get('license') or {}
                record = {
                    'full_name': full, 'description': str(item.get('description') or '')[:2000],
                    'language': str(item.get('language') or '')[:100],
                    'license': str(license_data.get('spdx_id') or 'NOASSERTION')[:100]
                    if isinstance(license_data, dict) else 'NOASSERTION',
                    'default_branch': str(item.get('default_branch') or 'main')[:200],
                    'html_url': 'https://github.com/' + parts[0] + '/' + parts[1],
                    'size_kb': max(0, int(item.get('size') or 0)),
                }
                found[full.casefold()] = record
            # API returns an empty page at EOF. Continue through requested page count
            # only when a mocked backend supplies one item per page; for real API, EOF ends scan.
            if not records:
                break
        return list(found.values())

    def download_snapshot(self, organization: str, repository: str, revision: str, destination: Path,
                          *, max_archive_bytes: int = 256 * 1024 * 1024) -> dict:
        organization, repository = _name(organization), _name(repository)
        if not isinstance(revision, str) or not SHA.fullmatch(revision):
            raise ValueError('Revision must be pinned to a 40-character commit SHA')
        if not 1024 <= max_archive_bytes <= 8 * 1024**3:
            raise ValueError('Invalid archive byte limit')
        url = 'https://codeload.github.com/' + quote(organization) + '/' + quote(repository) + '/zip/' + revision
        destination = Path(destination).resolve(strict=False)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='omega-snapshot-') as tempdir:
            archive = Path(tempdir)/'source.zip'
            size = 0
            digest = hashlib.sha256()
            try:
                with self.client.stream('GET', url, headers={'User-Agent': 'OmegaStudioUltimate/1.0'}) as response:
                    if response.status_code != 200:
                        raise CrawlerError('Snapshot download failed: HTTP ' + str(response.status_code))
                    with archive.open('wb') as out:
                        for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                            size += len(chunk)
                            if size > max_archive_bytes:
                                raise CrawlerError('Snapshot exceeds configured size limit')
                            digest.update(chunk)
                            out.write(chunk)
            except httpx.HTTPError as exc:
                raise CrawlerError('Snapshot transfer failed') from exc
            result = extract_zip(archive, destination, max_total_bytes=4 * max_archive_bytes)
            result.update({'archive_sha256': digest.hexdigest(), 'archive_bytes': size,
                           'revision': revision, 'source': f'{organization}/{repository}'})
            return result


class RepositoryIndex:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.execute('''CREATE TABLE IF NOT EXISTS repositories (
            full_name TEXT PRIMARY KEY, description TEXT NOT NULL, language TEXT NOT NULL,
            license TEXT NOT NULL, default_branch TEXT NOT NULL, html_url TEXT NOT NULL,
            size_kb INTEGER NOT NULL)''')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.connection.close()

    def upsert(self, items: list[dict]) -> int:
        rows = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get('full_name'), str):
                raise ValueError('Invalid repository metadata')
            parts = item['full_name'].split('/')
            if len(parts) != 2:
                raise ValueError('Invalid repository full_name')
            _name(parts[0]); _name(parts[1])
            rows.append(tuple(item[key] for key in ('full_name', 'description', 'language', 'license',
                                                    'default_branch', 'html_url', 'size_kb')))
        with self.connection:
            self.connection.executemany('''INSERT INTO repositories VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(full_name) DO UPDATE SET description=excluded.description,
                language=excluded.language, license=excluded.license,
                default_branch=excluded.default_branch, html_url=excluded.html_url,
                size_kb=excluded.size_kb''', rows)
        return len(rows)

    def search(self, term: str, limit: int = 100) -> list[dict]:
        if not 1 <= limit <= 1000 or len(term) > 256:
            raise ValueError('Invalid search')
        escaped = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        cur = self.connection.execute('''SELECT full_name,description,language,license,default_branch,
            html_url,size_kb FROM repositories WHERE full_name LIKE ? ESCAPE '\\'
            OR description LIKE ? ESCAPE '\\' ORDER BY full_name LIMIT ?''',
            ('%' + escaped + '%', '%' + escaped + '%', limit))
        keys = ['full_name','description','language','license','default_branch','html_url','size_kb']
        return [dict(zip(keys, row)) for row in cur.fetchall()]

    def count(self) -> int:
        return self.connection.execute('SELECT COUNT(*) FROM repositories').fetchone()[0]
