"""Deterministic simulation harness for external services; not device verification."""
from __future__ import annotations
import hashlib
import io
from pathlib import Path
import struct
import tempfile
import zipfile
import httpx
from fastapi.testclient import TestClient
from ..compiler import compile_workflow, load_workflow
from ..digital_twin import simulate_architecture
from ..model_studio import GGUFInspector
from .archives import extract_zip, pack_zip
from .crawler import GitHubOrgCrawler, RepositoryIndex
from .remote8080 import create_remote_app
from .seal import seal_python_source, verify_seal
from .swarm import DuoCoordinator, LoadBalancer, SwarmCoordinator
from .quantum_ast import ASTResonator
from .holographic_memory import HolographicMemoryWeaver
from .self_healing import repair_python_syntax
from .synapse import NeuromorphicRouter
from .mobile_network import NetworkScenario, simulate_mobile_link
from .ci_singularity import AdaptiveCIGate
from .trs_transport import SessionEnvelope


def run_simulation(*, seed: int = 20261110, jobs: int = 128) -> dict:
    if not 1 <= jobs <= 10_000 or not 0 <= seed < 2**32:
        raise ValueError('Invalid simulation parameters')
    pages = []

    def handler(request):
        page = int(request.url.params['page'])
        pages.append(page)
        return httpx.Response(200, json=[{
            'id': page, 'full_name': f'github/sim-{page}', 'default_branch': 'main',
            'description': 'Deterministic fixture', 'license': {'spdx_id': 'MIT'}, 'size': 1}])

    with tempfile.TemporaryDirectory(prefix='omega-simulation-') as work:
        root = Path(work)
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            repos = GitHubOrgCrawler(client).crawl('github', pages=20)
        with RepositoryIndex(root/'repos.sqlite3') as index:
            indexed = index.upsert(repos)
            count = index.count()
        gguf = root/'model.gguf'
        gguf.write_bytes(b'GGUF' + struct.pack('<IQQ', 3, 0, 0))
        gguf_info = GGUFInspector.inspect(gguf)
        workflow = compile_workflow(load_workflow('''name: Simulated CI\non: workflow_dispatch\njobs:\n  lint:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo lint\n  test:\n    needs: lint\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo test\n'''))
        with SwarmCoordinator(max_workers=4, max_pending=8) as swarm:
            results = swarm.map(lambda x: x*x, range(jobs))
            peak = swarm.peak_active
        duo = DuoCoordinator(max_rounds=3).run(lambda text, n: f'{text}:{n}',
                                               lambda value: value.endswith(':2'), 'validated')
        balanced = LoadBalancer([1,1,1,1],[(0,1),(1,2),(2,3)]).diffuse([100,0,0,0], steps=20)
        seal = seal_python_source('x = 1\n', secret=b'deterministic-sim-key')
        archive_root = root/'archive'; archive_root.mkdir()
        (archive_root/'hello.txt').write_text('OMEGA')
        packed = root/'bundle.zip'; pack_zip(archive_root, packed)
        unpacked = root/'unpacked'; extract_zip(packed, unpacked)
        app = create_remote_app(archive_root, username='omega', password='test-password-long')
        client = TestClient(app)
        unauth = client.get('/api/files').status_code
        import base64
        auth = 'Basic ' + base64.b64encode(b'omega:test-password-long').decode()
        authorized = client.get('/api/files', headers={'Authorization': auth}).status_code
        twin = simulate_architecture(seed=seed, jobs=jobs, worker_count=4, network_failure_rate=0.1)
        resonator = ASTResonator(64)
        state = resonator.embed('def f():\n    return 42\n')
        memory_file = root/'large-memory.bin'
        memory_file.write_bytes(b'A' * 16384)
        with HolographicMemoryWeaver(memory_file, block_size=4096, cache_blocks=2) as weaver:
            memory_ok = (weaver.read_at(4080, 32) == b'A' * 32
                         and weaver.cached_blocks <= 2 and len(weaver.phase_sketch(0)) == 32)
        repaired = repair_python_syntax('def f()\n    return 1\n')
        router = NeuromorphicRouter(('generator','verifier','reviewer'))
        router.feedback('generator','verifier',reward=1.0)
        synapse_ok = router.route('generator') == 'verifier'
        router.quarantine('verifier')
        synapse_ok &= router.route('generator') == 'reviewer'
        network = simulate_mobile_link(NetworkScenario(seed=seed, packets=jobs,
            loss_rate=0.1, jitter_ms=30, handoff_every=7))
        envelope = SessionEnvelope(master_key=b's' * 32, session_id=b'omega-session-001')
        encrypted = envelope.encrypt(b'confidential', context=b'api:8080')
        transport_ok = envelope.decrypt(encrypted, context=b'api:8080') == b'confidential'
        gate = AdaptiveCIGate(root, signing_key=b'omega-simulation-signing-key-32!!')
        proposal = gate.propose('lint', ['python','-m','compileall','.'])
        signed = gate.approve(proposal, approval='approve:lint')
        invariants = {
            'crawler_20_pages': pages == list(range(1,21)) and indexed == 20 and count == 20,
            'gguf_v3_header': gguf_info['version'] == 3 and gguf_info['tensor_count'] == 0,
            'workflow_dag': workflow.order == ('lint','test'),
            'bounded_swarm': results == [i*i for i in range(jobs)] and peak <= 4,
            'duo_verifier': duo == 'validated:2',
            'graph_load_conservation': abs(sum(balanced)-100) < 1e-7 and min(balanced) >= 0,
            'authenticated_8080_gateway': unauth == 401 and authorized == 200,
            'archive_integrity': (unpacked/'hello.txt').read_text() == 'OMEGA',
            'ast_seal': verify_seal('x = 1\n',seal,secret=b'deterministic-sim-key'),
            'external_twin': all(twin['invariants'].values()),
            'ast_hilbert_embedding':abs(sum(abs(v)**2 for v in state)-1.0)<1e-10,
            'holographic_bounded_cache':memory_ok,
            'self_healing_review':repaired.changed and repaired.requires_human_review,
            'trs_aead_envelope':transport_ok,
            'neuromorphic_routing':synapse_ok,
            'mobile_network_handoffs':network['packets_sent']==jobs and
                network['packets_delivered']+network['packets_lost']==jobs,
            'ci_signed_approval':gate.verify(signed),
        }
        return {'scope':'DETERMINISTIC_HOST_SIMULATION', 'seed': seed, 'jobs': jobs,
                'crawler': {'pages':len(pages),'indexed':count},
                'gguf': {'version':gguf_info['version'],'tensor_count':gguf_info['tensor_count']},
                'workflow': {'jobs':len(workflow.jobs),'order':list(workflow.order)},
                'swarm': {'jobs':jobs,'peak_active':peak,'sum_of_squares':sum(results)},
                'remote': {'unauthorized_status':unauth,'authorized_status':authorized},
                'external_twin':twin,'invariants':invariants,
                'status':'PASS' if all(invariants.values()) else 'FAIL'}
