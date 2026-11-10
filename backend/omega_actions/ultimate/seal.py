"""Reproducible AST topology metrics and authenticated source integrity seal.

Topology is diagnostic; an AST seal is not a formal proof of code correctness.
"""
from __future__ import annotations
import ast
import hashlib
import hmac
import json


def graph_invariants(vertices: int, edges: list[tuple[int, int]]) -> dict:
    if vertices < 0:
        raise ValueError('Negative vertex count')
    parent = list(range(vertices))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        if not 0 <= a < vertices or not 0 <= b < vertices:
            raise ValueError('Graph edge out of bounds')
        parent[find(a)] = find(b)
    components = len({find(i) for i in range(vertices)})
    beta1 = len(edges) - vertices + components
    if beta1 < 0:
        raise AssertionError('Invalid first Betti number')
    return {'vertices': vertices, 'edges': len(edges), 'components': components,
            'euler_characteristic': vertices - len(edges), 'beta1': beta1}


def _ast_graph(root: ast.AST) -> tuple[int, list[tuple[int, int]]]:
    edges: list[tuple[int, int]] = []
    count = 0

    def visit(node, parent_id=None):
        nonlocal count
        current = count
        count += 1
        if parent_id is not None:
            edges.append((parent_id, current))
        for child in ast.iter_child_nodes(node):
            visit(child, current)

    visit(root)
    return count, edges


def seal_python_source(source: str, *, secret: bytes) -> dict:
    if not secret or len(secret) < 8:
        raise ValueError('Seal requires an independent HMAC secret')
    tree = ast.parse(source)
    canonical = ast.dump(tree, annotate_fields=True, include_attributes=False)
    vertices, edges = _ast_graph(tree)
    graph = graph_invariants(vertices, edges)
    digest = hashlib.sha256(source.encode('utf-8')).hexdigest()
    canonical_digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    payload = {'version': 1, 'sha256': digest, 'ast_sha256': canonical_digest, **graph}
    wire = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    payload['hmac_sha3_256'] = hmac.new(secret, wire, hashlib.sha3_256).hexdigest()
    return payload


def verify_seal(source: str, seal: dict, *, secret: bytes) -> bool:
    if not isinstance(seal, dict):
        return False
    try:
        expected = seal_python_source(source, secret=secret)
        return hmac.compare_digest(json.dumps(expected, sort_keys=True), json.dumps(seal, sort_keys=True))
    except (ValueError, SyntaxError, TypeError):
        return False
