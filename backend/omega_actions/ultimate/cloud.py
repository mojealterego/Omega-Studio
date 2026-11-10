"""Read-only cloud catalog endpoints. Fixed hosts prevent user-supplied SSRF targets."""
from __future__ import annotations
import httpx


class CloudError(RuntimeError):
    pass


class MultiCloudHub:
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)
        self.owns_client = client is None

    def close(self):
        if self.owns_client:
            self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _get(self, url: str, *, params: dict, token: str | None = None):
        headers = {'Accept': 'application/json', 'User-Agent': 'OmegaStudioUltimate/1.0'}
        if token:
            if '\n' in token or '\r' in token:
                raise ValueError('Invalid token')
            headers['Authorization'] = 'Bearer ' + token
        try:
            response = self.client.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise CloudError('Cloud provider connection failed') from exc
        if response.status_code != 200:
            raise CloudError('Cloud provider returned HTTP ' + str(response.status_code))
        try:
            return response.json()
        except ValueError as exc:
            raise CloudError('Invalid provider JSON') from exc

    def gitlab_projects(self, page: int = 1, per_page: int = 100, token: str | None = None) -> list[dict]:
        if not 1 <= page <= 10000 or not 1 <= per_page <= 100:
            raise ValueError('Invalid GitLab pagination')
        data = self._get('https://gitlab.com/api/v4/projects',
                         params={'page': page, 'per_page': per_page, 'simple': 'true'}, token=token)
        if not isinstance(data, list):
            raise CloudError('Invalid GitLab response')
        return data

    def hf_models(self, limit: int = 100, token: str | None = None) -> list[dict]:
        if not 1 <= limit <= 1000:
            raise ValueError('Invalid Hugging Face limit')
        data = self._get('https://huggingface.co/api/models', params={'limit': limit}, token=token)
        if not isinstance(data, list):
            raise CloudError('Invalid Hugging Face response')
        return data

    def drive_files(self, token: str, page_token: str | None = None, page_size: int = 100) -> dict:
        if not token or not token.strip() or not 1 <= page_size <= 1000:
            raise ValueError('Drive OAuth bearer token and valid page size required')
        if page_token is not None and (not isinstance(page_token, str) or len(page_token) > 4096):
            raise ValueError('Invalid Google Drive page token')
        params = {'pageSize': page_size, 'fields': 'nextPageToken,files(id,name,mimeType,size,modifiedTime)'}
        if page_token:
            params['pageToken'] = page_token
        data = self._get('https://www.googleapis.com/drive/v3/files', params=params, token=token)
        if not isinstance(data, dict) or not isinstance(data.get('files'), list):
            raise CloudError('Invalid Google Drive response')
        return data
