"""Local-only authenticated OMEGA Ultimate API routes for existing FastAPI backend."""
from __future__ import annotations
import html
import io
from pathlib import Path
import shutil
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from .assets import make_svg, make_png, make_wav, make_gltf_animation, make_video
from .crawler import GitHubOrgCrawler, RepositoryIndex, CrawlerError
from .simulation import run_simulation
from .code_swarm import analyze_source
from .quantum_ast import ASTResonator
from .mobile_network import NetworkScenario, simulate_mobile_link
from .upstream_sources import default_catalog, UpstreamSourceManager, CatalogError, SourceSyncError


class AssetRequest(BaseModel):
    kind: str = Field(pattern='^(svg|png|wav|gltf|mp4)$')
    text: str = Field(default='OMEGA Studio', max_length=1000)


class SwarmRequest(BaseModel):
    source: str = Field(min_length=1, max_length=512 * 1024)
    mode: str = Field(default='leak', pattern='^(leak|duo)$')
    suggest_repair: bool = False


class UpstreamSyncRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    confirm_network: bool = False


class ASTResearchRequest(BaseModel):
    source: str = Field(min_length=1, max_length=2 * 1024 * 1024)


class NetworkResearchRequest(BaseModel):
    seed: int = Field(ge=0, lt=2**32)
    packets: int = Field(ge=1, le=1_000_000)
    loss_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    jitter_ms: int = Field(default=0, ge=0, le=60_000)
    handoff_every: int = Field(default=0, ge=0, le=1_000_000)


class NoCodeRequest(BaseModel):
    description: str = Field(min_length=1, max_length=4000)


def create_ultimate_router(home: Path) -> APIRouter:
    router = APIRouter(prefix='/api/ultimate', tags=['ultimate'])
    root = Path(home).resolve(strict=False)
    index_path = root / 'ultimate' / 'repositories.sqlite3'

    @router.post('/simulate')
    def simulate(seed: int = 20261110, jobs: int = 128):
        try:
            return run_simulation(seed=seed, jobs=jobs)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post('/analyze')
    def analyze(body: SwarmRequest):
        try:
            return analyze_source(body.source, mode=body.mode, suggest_repair=body.suggest_repair)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post('/research/ast')
    def research_ast(body: ASTResearchRequest):
        try:
            resonator = ASTResonator(64)
            embedding = resonator.embed(body.source)
            return {'scope':'CLASSICAL_CPU_HEURISTIC', 'dimensions':64,
                    'norm_squared':sum(abs(value)**2 for value in embedding),
                    'projection':resonator.project(embedding,embedding)}
        except (ValueError, SyntaxError) as exc:
            raise HTTPException(422, 'Invalid Python source or embedding configuration') from exc

    @router.post('/research/network')
    def research_network(body: NetworkResearchRequest):
        scenario = NetworkScenario(**body.model_dump())
        return simulate_mobile_link(scenario)

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
