"""Local-only authenticated OMEGA Ultimate API routes for existing FastAPI backend."""
from __future__ import annotations
import html
import io
import os
from pathlib import Path
import shutil
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from .assets import make_svg, make_png, make_wav, make_gltf_animation, make_video
from .crawler import GitHubOrgCrawler, RepositoryIndex, CrawlerError
from .simulation import run_simulation
from .code_swarm import analyze_source
from .upstream_sources import default_catalog, UpstreamSourceManager, CatalogError, SourceSyncError
from .quantum_topology import QuantumASTResonator
from .self_healing_ast import repair_python_source
from .network_chaos import simulate_mobile_network
from .workspace_registry import WorkspaceRegistry, WorkspaceError
from .mcp_registry import MCPRegistry, MCPServer, MCPRegistryError
from .llm_provider import ChatCompletionProvider, ProviderConfig, ProviderError
from .chat_duo import DuoSession, DuoError
from dataclasses import asdict


class DuoChatRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=262144)


class AssetRequest(BaseModel):
    kind: str = Field(pattern='^(svg|png|wav|gltf|mp4)$')
    text: str = Field(default='OMEGA Studio', max_length=1000)


class SwarmRequest(BaseModel):
    source: str = Field(min_length=1, max_length=512 * 1024)
    mode: str = Field(default='leak', pattern='^(leak|duo)$')


class UpstreamSyncRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    confirm_network: bool = False


class ASTRequest(BaseModel):
    source: str = Field(min_length=1, max_length=512 * 1024)


class NetworkChaosRequest(BaseModel):
    seed: int = 20261110
    steps: int = Field(default=1000, ge=1, le=1000000)
    loss: float = Field(default=0.1, ge=0, le=1)
    jitter_ms: int = Field(default=50, ge=0, le=5000)


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]*$')


class MCPServerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    transport: str
    command: list[str] = Field(default_factory=list, max_length=32)
    url: str = Field(default='', max_length=4096)


class NoCodeRequest(BaseModel):
    description: str = Field(min_length=1, max_length=4000)


def create_ultimate_router(home: Path) -> APIRouter:
    router = APIRouter(prefix='/api/ultimate', tags=['ultimate'])
    root = Path(home).resolve(strict=False)
    index_path = root / 'ultimate' / 'repositories.sqlite3'

    registry = WorkspaceRegistry(root)

    @router.get('/workspaces')
    def list_workspaces():
        return {'items': registry.list()}

    @router.post('/workspaces', status_code=201)
    def create_workspace(body: WorkspaceCreateRequest):
        try:
            path = registry.create(body.name)
            return {'name': body.name, 'created': True, 'path': str(path.relative_to(root))}
        except WorkspaceError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get('/workspaces/{name}')
    def get_workspace(name: str):
        try:
            path = registry.open(name)
            return {'name': name, 'path': str(path.relative_to(root))}
        except WorkspaceError as exc:
            raise HTTPException(404, str(exc)) from exc

    mcp_registry = MCPRegistry(root)

    @router.get('/mcp/servers')
    def list_mcp_servers():
        try:
            return {'items': [asdict(server) for server in mcp_registry.list()]}
        except MCPRegistryError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.put('/mcp/servers/{name}')
    def put_mcp_server(name: str, body: MCPServerRequest):
        if name != body.name:
            raise HTTPException(422, 'MCP server identity mismatch')
        try:
            server = MCPServer(name=body.name, transport=body.transport,
                               command=tuple(body.command), url=body.url)
            mcp_registry.put(server)
            return {'server': asdict(server), 'configured': True, 'executed': False}
        except MCPRegistryError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.delete('/mcp/servers/{name}')
    def delete_mcp_server(name: str):
        try:
            removed = mcp_registry.delete(name)
            if not removed:
                raise HTTPException(404, 'MCP server not found')
            return {'removed': True}
        except MCPRegistryError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post('/hyper/ast')
    def hyper_ast(body: ASTRequest):
        try:
            return QuantumASTResonator().analyze(body.source)
        except (SyntaxError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post('/hyper/heal')
    def hyper_heal(body: ASTRequest):
        try:
            return repair_python_source(body.source)
        except (SyntaxError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post('/hyper/network')
    def hyper_network(body: NetworkChaosRequest):
        return simulate_mobile_network(seed=body.seed, steps=body.steps,
                                       loss=body.loss, jitter_ms=body.jitter_ms)

    @router.post('/simulate')
    def simulate(seed: int = 20261110, jobs: int = 128):
        try:
            return run_simulation(seed=seed, jobs=jobs)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post('/chat/duo')
    def chat_duo(body: DuoChatRequest):
        author_endpoint = os.environ.get('OMEGA_DUO_AUTHOR_ENDPOINT')
        reviewer_endpoint = os.environ.get('OMEGA_DUO_REVIEWER_ENDPOINT')
        author_model = os.environ.get('OMEGA_DUO_AUTHOR_MODEL')
        reviewer_model = os.environ.get('OMEGA_DUO_REVIEWER_MODEL')
        if not all((author_endpoint, reviewer_endpoint, author_model, reviewer_model)):
            raise HTTPException(503, 'Two independent model providers must be configured')
        try:
            author = ChatCompletionProvider(ProviderConfig(
                endpoint=author_endpoint, model=author_model,
                api_key=os.environ.get('OMEGA_DUO_AUTHOR_KEY', '')))
            reviewer = ChatCompletionProvider(ProviderConfig(
                endpoint=reviewer_endpoint, model=reviewer_model,
                api_key=os.environ.get('OMEGA_DUO_REVIEWER_KEY', '')))
            result = DuoSession(author, reviewer).run(body.instruction)
            return {'proposal': result.proposal, 'review': result.review,
                    'approved': result.approved, 'executed': result.executed}
        except (ProviderError, DuoError) as exc:
            raise HTTPException(502, str(exc)) from exc

    @router.post('/analyze')
    def analyze(body: SwarmRequest):
        try:
            return analyze_source(body.source, mode=body.mode)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get('/status')
    def status():
        names = ('bash', 'python3', 'git', 'llama-cli', 'node', 'code-server')
        return {'features': {'repo_crawler': 'ready', 'streaming': 'ready',
                             'assets': 'procedural', 'swarm': 'bounded', 'nocode': 'template'},
                'runtime_executables_on_host': {name: bool(shutil.which(name)) for name in names},
                'scope': 'host-process-not-android-apk'}

    @router.get('/upstreams')
    def upstream_catalog():
        catalog = default_catalog()
        return {'sources': catalog.public_info(), 'pinned': True,
                'source_downloads_automatic': False,
                'license_acceptance_required': True}

    @router.post('/upstreams/sync')
    def upstream_sync(body: UpstreamSyncRequest):
        if not body.confirm_network:
            raise HTTPException(403, 'Explicit source download consent required')
        catalog = default_catalog()
        try:
            catalog.get(body.name)
            target = root / 'upstream-sources'
            target.mkdir(mode=0o700, parents=True, exist_ok=True)
            return UpstreamSourceManager(catalog, target).sync(body.name, consent=True)
        except (CatalogError, SourceSyncError, OSError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get('/repositories')
    def repositories(organization: str = 'github', pages: int = 20):
        try:
            with GitHubOrgCrawler() as crawler:
                items = crawler.crawl(organization, pages=pages)
            with RepositoryIndex(index_path) as index:
                indexed = index.upsert(items)
                total = index.count()
            return {'organization': organization, 'indexed': indexed, 'total': total, 'pages_requested': pages}
        except (ValueError, CrawlerError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get('/search')
    def search(q: str = '', limit: int = 50):
        try:
            with RepositoryIndex(index_path) as index:
                return {'items': index.search(q, limit=limit), 'total': index.count()}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post('/assets')
    def assets(body: AssetRequest):
        if body.kind == 'svg':
            return Response(make_svg(body.text).encode('utf-8'), media_type='image/svg+xml')
        if body.kind == 'png':
            return Response(make_png(512, 512, (7, 8, 10)), media_type='image/png')
        if body.kind == 'wav':
            return Response(make_wav(440, 1.0), media_type='audio/wav')
        if body.kind == 'mp4':
            import tempfile
            with tempfile.TemporaryDirectory(prefix='omega-video-') as tempdir:
                path = Path(tempdir) / 'video.mp4'
                make_video(path)
                return Response(path.read_bytes(), media_type='video/mp4')
        import json
        return Response(json.dumps(make_gltf_animation()), media_type='model/gltf+json')

    @router.post('/nocode')
    def nocode(body: NoCodeRequest):
        title = body.description.strip().splitlines()[0][:100]
        safe = html.escape(title, quote=True)
        document = (f'<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" '
                    f'content="width=device-width,initial-scale=1"><title>{safe}</title>'
                    '<style>body{background:#07080a;color:#f4f1ea;font:18px system-ui;margin:0;padding:5vw}'
                    'main{max-width:960px;margin:auto}h1{font:52px Georgia,serif;color:#d4af37}'
                    'article{padding:28px;border:1px solid #aa8222;border-radius:20px}</style>'
                    f'<main><h1>{safe}</h1><article>{html.escape(body.description)}</article></main></html>')
        return {'html': document, 'type': 'deterministic-html-template', 'requires_cloud_ai': False}

    return router
