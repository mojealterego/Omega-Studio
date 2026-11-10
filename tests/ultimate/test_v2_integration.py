"""Integration tests for MCode research modules, API and native release artifacts."""
from pathlib import Path
import json
import struct
import subprocess
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from omega_actions.ultimate.code_swarm import analyze_source
from omega_actions.ultimate.router import create_ultimate_router
from omega_actions.ultimate.simulation import run_simulation


def test_code_swarm_reports_repair_as_review_required_not_automatic():
    bad = 'def f(x)\n    return x + 1\n'
    report = analyze_source(bad, mode='duo', suggest_repair=True)
    assert report['syntax_valid'] is False
    assert report['repair']['requires_human_review'] is True
    assert report['repair']['repaired'] == 'def f(x):\n    return x + 1\n'
    assert report['repair']['changed']
    assert report['verified'] is False


def test_code_swarm_ast_projection_reports_classical_scope():
    report = analyze_source('x = 1\n', mode='leak')
    assert report['ast_projection']['dimensions'] == 64
    assert report['ast_projection']['scope'] == 'CLASSICAL_CPU_HEURISTIC'
    assert report['syntax_valid']


def test_research_api_responds_to_ast_and_network_simulation(tmp_path: Path):
    app = FastAPI()
    app.include_router(create_ultimate_router(tmp_path))
    client = TestClient(app)
    ast_report = client.post('/api/ultimate/research/ast', json={'source':'x = 1\n'}).json()
    assert ast_report['scope'] == 'CLASSICAL_CPU_HEURISTIC'
    assert ast_report['dimensions'] == 64
    net_report = client.post('/api/ultimate/research/network', json={
        'seed':4,'packets':30,'loss_rate':0.2,'jitter_ms':15,'handoff_every':7}).json()
    assert net_report['packets_sent'] == 30
    assert net_report['scope'] == 'DETERMINISTIC_NETWORK_MODEL'
    assert client.post('/api/ultimate/research/network',json={'seed':4,'packets':0}).status_code == 422


def test_simulation_includes_real_bounded_research_invariants():
    report = run_simulation(seed=4, jobs=16)
    for key in ('ast_hilbert_embedding', 'holographic_bounded_cache',
                'self_healing_review', 'trs_aead_envelope',
                'neuromorphic_routing', 'mobile_network_handoffs',
                'ci_signed_approval'):
        assert report['invariants'][key], key
    assert report['status'] == 'PASS'
    assert report['scope'] == 'DETERMINISTIC_HOST_SIMULATION'


def test_native_arm64_library_is_real_elf_and_exports_gguf_validator():
    root = Path(__file__).resolve().parents[2]
    binary = root/'android/app/src/main/jniLibs/arm64-v8a/libomega_runtime.so'
    raw = binary.read_bytes()
    assert raw[:4] == b'\x7fELF'
    assert raw[4] == 2
    assert struct.unpack_from('<H', raw, 18)[0] == 183
    symbols = subprocess.check_output(['readelf','-Ws',str(binary)],text=True)
    assert 'omega_gguf_version' in symbols
    assert 'omega_runtime_abi_version' in symbols


def test_native_library_is_not_misrepresented_as_termux_runtime():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root/'RELEASE_STATUS.json').read_text())
    assert manifest['android']['embedded_native_gguf_probe'] is True
    assert manifest['android']['termux_python_git_llama_code_server_bundled'] is False
    assert manifest['android']['device_verified'] is False
