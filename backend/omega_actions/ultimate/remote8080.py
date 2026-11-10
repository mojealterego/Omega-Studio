"""Opt-in authenticated remote workspace server with TLS required outside loopback."""
from __future__ import annotations
import base64
from dataclasses import dataclass
import hashlib
import hmac
import os
import re
from pathlib import Path
import tempfile
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field


class RemoteError(ValueError):
    pass


@dataclass(frozen=True)
class RemoteConfig:
    bind: str = '127.0.0.1'
    port: int = 8080
    username: str = 'omega'
    password: str = ''
    tls_cert: Path | None = None
    tls_key: Path | None = None

    def __post_init__(self):
        if not 1 <= self.port <= 65535 or not self.username or len(self.password) < 12:
            raise RemoteError('Valid port, username and 12+ character password required')
        if self.bind not in ('127.0.0.1', '::1', 'localhost'):
            if not self.tls_cert or not self.tls_key or not self.tls_cert.is_file() or not self.tls_key.is_file():
                raise RemoteError('Remote network exposure requires TLS certificate and private key')


class WriteRequest(BaseModel):
    path: str = Field(min_length=1, max_length=2048)
    content: str = Field(max_length=1024 * 1024)
    expected_sha256: str | None = Field(default=None, min_length=64, max_length=64)


def create_remote_app(workspace: Path, *, username: str, password: str) -> FastAPI:
    RemoteConfig(username=username, password=password)
    root = Path(workspace).resolve(strict=True)
    if not root.is_dir():
        raise RemoteError('Workspace must be a directory')
    app = FastAPI(title='OMEGA Studio Remote Workspace', docs_url=None, redoc_url=None, openapi_url=None)

    def authorized(header: str | None) -> bool:
        if not header or not header.startswith('Basic '):
            return False
        try:
            decoded = base64.b64decode(header[6:], validate=True).decode('utf-8')
            user, candidate = decoded.split(':', 1)
        except (ValueError, UnicodeError):
            return False
        return hmac.compare_digest(user, username) and hmac.compare_digest(candidate, password)

    def within(path: str) -> Path:
        if not path or Path(path).is_absolute() or '\x00' in path or '\\' in path:
            raise HTTPException(403, 'Workspace path denied')
        candidate = (root / path).resolve(strict=False)
        if not candidate.is_relative_to(root) or candidate == root:
            raise HTTPException(403, 'Workspace path denied')
        return candidate

    @app.middleware('http')
    async def authentication(request: Request, call_next):
        if not authorized(request.headers.get('authorization')):
            return JSONResponse({'detail': 'Authentication required'}, status_code=401,
                                headers={'WWW-Authenticate': 'Basic realm="OMEGA Studio"',
                                         'Cache-Control': 'no-store'})
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"
        return response

    @app.get('/', response_class=HTMLResponse)
    async def index():
        page = Path(__file__).with_name('remote_ide.html').read_text(encoding='utf-8')
        script = re.search(r'<script>(.*?)</script>', page, re.DOTALL)
        if script is None:
            raise HTTPException(500, 'Editor script unavailable')
        script_hash = base64.b64encode(hashlib.sha256(script.group(1).encode('utf-8')).digest()).decode('ascii')
        return HTMLResponse(page, headers={
            'Content-Security-Policy':
                "default-src 'none'; script-src 'sha256-" + script_hash +
                "'; connect-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; "
                "form-action 'none'; frame-ancestors 'none'"
        })

    @app.get('/api/tree')
    async def tree(path: str = '.'):
        if path == '.':
            directory = root
        else:
            directory = within(path)
        if not directory.is_dir():
            raise HTTPException(400, 'Directory required')
        entries = []
        for item in sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold()))[:1000]:
            if item.is_symlink():
                continue
            rel = item.relative_to(root).as_posix()
            try:
                directory_entry = item.is_dir()
                entries.append({'name': item.name, 'path': rel, 'directory': directory_entry,
                                'bytes': None if directory_entry else item.stat().st_size})
            except OSError:
                continue
        return {'path': path, 'entries': entries}

    @app.get('/api/files')
    async def files():
        files = []
        for item in sorted(root.iterdir(), key=lambda p:p.name)[:1000]:
            if item.is_symlink():
                continue
            files.append({'name': item.name, 'directory': item.is_dir(),
                          'bytes': item.stat().st_size if item.is_file() else None})
        return {'files': files}

    @app.get('/api/read')
    async def read(path: str):
        file = within(path)
        if not file.is_file() or file.stat().st_size > 1024 * 1024:
            raise HTTPException(413, 'Only text files up to 1 MiB may be edited')
        raw = file.read_bytes()
        try:
            content = raw.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise HTTPException(415, 'Binary file') from exc
        return {'path': path, 'content': content, 'sha256': hashlib.sha256(raw).hexdigest()}

    @app.put('/api/write')
    async def write(body: WriteRequest):
        file = within(body.path)
        if not file.parent.is_dir():
            raise HTTPException(404, 'Parent directory does not exist')
        if file.exists() and not file.is_file():
            raise HTTPException(403, 'Not a regular file')
        if file.exists():
            current = hashlib.sha256(file.read_bytes()).hexdigest()
            if not body.expected_sha256 or not hmac.compare_digest(current, body.expected_sha256):
                raise HTTPException(409, 'Concurrent modification detected')
        elif body.expected_sha256:
            raise HTTPException(409, 'File no longer exists')
        raw = body.content.encode('utf-8')
        if len(raw) > 1024 * 1024:
            raise HTTPException(413, 'UTF-8 payload exceeds 1 MiB')
        temp = None
        try:
            with tempfile.NamedTemporaryFile(dir=file.parent, prefix='.omega-write-', delete=False) as output:
                temp = Path(output.name)
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp, file)
            temp = None
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
        return {'path': body.path, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}

    @app.websocket('/ws')
    async def websocket(ws: WebSocket):
        if not authorized(ws.headers.get('authorization')):
            raise WebSocketException(code=1008)
        await ws.accept()
        await ws.send_json({'type': 'hello', 'protocol': 'omega-remote-v1'})
        try:
            while True:
                message = await ws.receive_json()
                if message == {'type': 'ping'}:
                    await ws.send_json({'type': 'pong'})
                else:
                    await ws.send_json({'type': 'error', 'reason': 'Unsupported message'})
        except Exception as exc:
            from starlette.websockets import WebSocketDisconnect
            if not isinstance(exc, WebSocketDisconnect):
                raise
    return app


def serve(workspace: Path, config: RemoteConfig) -> None:
    import uvicorn
    uvicorn.run(create_remote_app(workspace, username=config.username, password=config.password),
                host=config.bind, port=config.port,
                ssl_certfile=str(config.tls_cert) if config.tls_cert else None,
                ssl_keyfile=str(config.tls_key) if config.tls_key else None,
                access_log=False)
