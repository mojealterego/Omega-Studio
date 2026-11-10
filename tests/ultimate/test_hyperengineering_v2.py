"""Behavioral acceptance tests for bounded, classical implementations of MCode pages 6-9."""
from __future__ import annotations
import hashlib
from pathlib import Path
import pytest

from omega_actions.ultimate.quantum_topology import QuantumASTResonator
from omega_actions.ultimate.holographic_memory import HolographicMemoryWeaver
from omega_actions.ultimate.self_healing_ast import repair_python_source
from omega_actions.ultimate.neuromorphic_synapse import NeuromorphicSynapse
from omega_actions.ultimate.adaptive_ci import AdaptiveCI, PlanRejected
from omega_actions.ultimate.network_chaos import simulate_mobile_network
from omega_actions.ultimate.streamer import WindowedReader


def test_quantum_hilbert_projection_and_security_flags():
    engine = QuantumASTResonator()
    safe = 'def f(x):\n    return x + 1\n'
    report = engine.analyze(safe)
    assert report['dimension'] >= 12
    assert report['norm_squared'] == pytest.approx(1, abs=1e-9)
    assert engine.similarity(safe, safe) == pytest.approx(1)
    assert 0 <= engine.similarity(safe, 'a = 3\n') <= 1
    assert engine.analyze('eval("2+2")\n')['findings'][0]['rule'] == 'dynamic_execution'


def test_self_healing_is_limited_and_requires_parseable_result():
    bad = 'def f(x)\n    return x + 1\n'
    result = repair_python_source(bad)
    assert result['repaired'] is True
    assert result['source'] == 'def f(x):\n    return x + 1\n'
    assert result['changes'] == [{'line': 1, 'rule': 'missing_header_colon'}]
    assert repair_python_source('x = 1\n')['repaired'] is False
    with pytest.raises(SyntaxError):
        repair_python_source('def f(:\n pass\n')
    with pytest.raises(ValueError):
        repair_python_source('x' * (512 * 1024 + 1))


def test_holographic_index_is_disk_backed_and_detects_mutation(tmp_path: Path):
    source = tmp_path / 'large.dat'
    source.write_bytes(bytes(range(256)) * 800)
    engine = HolographicMemoryWeaver(tmp_path / 'index.sqlite3', block_size=65536)
    report = engine.index(source)
    assert report['blocks'] == 4
    assert report['sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert engine.read_verified(source, 65530, 30) == source.read_bytes()[65530:65560]
    source.write_bytes(b'x' * 204800)
    with pytest.raises(ValueError, match='changed'):
        engine.read_verified(source, 0, 10)


def test_sparse_gigabyte_random_access_stays_bounded(tmp_path: Path):
    source = tmp_path / 'sparse.gguf'
    with source.open('wb') as stream:
        stream.seek(3 * 1024**3)
        stream.write(b'GGUF')
    with WindowedReader(source, window_size=4096) as reader:
        assert reader.read_at(3 * 1024**3, 4) == b'GGUF'
        assert reader.read_at(0, 4) == b'\x00' * 4


def test_neuromorphic_stdp_and_bounds():
    s = NeuromorphicSynapse(['generator', 'validator'], max_weight=2)
    s.spike('generator', tick=10)
    s.spike('validator', tick=12)
    assert s.weight('generator', 'validator') > 1.0
    s.spike('validator', tick=30)
    s.spike('generator', tick=31)
    assert 0 <= s.weight('generator', 'validator') <= 2
    assert s.route('generator', {'validator': 0}, tick=32) == 'validator'
    with pytest.raises(ValueError):
        s.spike('generator', tick=0)


def test_adaptive_ci_is_fail_closed_and_runs_only_approved_plan(tmp_path: Path):
    (tmp_path / 'main.py').write_text('print(1)\n', encoding='utf-8')
    ci = AdaptiveCI(tmp_path, secret=b'local-approval-key-32-bytes-strong')
    proposal = ci.propose_python_compile()
    with pytest.raises(PlanRejected):
        ci.execute(proposal, approval='wrong')
    token = ci.approve(proposal, operator_confirmed=True)
    result = ci.execute(proposal, approval=token, timeout=10)
    assert result['returncode'] == 0
    assert result['verified_plan_sha256'] == proposal['sha256']
    with pytest.raises(PlanRejected):
        ci.execute({**proposal, 'argv': ['sh', '-c', 'curl evil']}, approval=token)


def test_mobile_network_simulation_reproducible_and_bounded():
    first = simulate_mobile_network(seed=123, steps=1000, loss=0.2, jitter_ms=70)
    assert first == simulate_mobile_network(seed=123, steps=1000, loss=0.2, jitter_ms=70)
    assert first['sent'] == 1000
    assert first['delivered'] + first['lost'] == 1000
    assert first['reconnects'] >= 1
    with pytest.raises(ValueError):
        simulate_mobile_network(seed=1, steps=100, loss=1.1)


def test_hyperengineering_http_api(tmp_path: Path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from omega_actions.ultimate.router import create_ultimate_router
    app = FastAPI()
    app.include_router(create_ultimate_router(tmp_path))
    client = TestClient(app)
    result = client.post('/api/ultimate/hyper/ast', json={'source': 'eval("x")\n'})
    assert result.status_code == 200
    assert result.json()['findings'][0]['rule'] == 'dynamic_execution'
    repaired = client.post('/api/ultimate/hyper/heal', json={'source': 'def f()\n    return 1\n'})
    assert repaired.status_code == 200
    assert repaired.json()['repaired']
    assert client.post('/api/ultimate/hyper/ast', json={'source': 'def f(:\n'}).status_code == 422
    chaos = client.post('/api/ultimate/hyper/network', json={'seed': 2, 'steps': 100})
    assert chaos.status_code == 200 and chaos.json()['sent'] == 100


def test_hyperengineering_cli(tmp_path: Path):
    import os
    import subprocess
    import sys
    source = tmp_path / 'file.py'
    source.write_text('def f(x):\n    return x\n', encoding='utf-8')
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2] / 'backend')}
    for command in [('quantum', str(source)), ('network-chaos', '--seed', '11', '--steps', '100')]:
        result = subprocess.run([sys.executable, '-m', 'omega_actions.ultimate', *command],
                                env=env, text=True, capture_output=True, timeout=20)
        assert result.returncode == 0, result.stderr
        assert 'model' in result.stdout
