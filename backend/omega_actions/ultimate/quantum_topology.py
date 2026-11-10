"""Classical complex Hilbert-space embedding of Python ASTs.

No quantum hardware, zero-time detection, formal verification or security proof is
claimed.  This is a deterministic, finite-dimensional static-analysis heuristic.
"""
from __future__ import annotations
import ast
import cmath
import math
from .seal import graph_invariants

FEATURES = (
    'FunctionDef', 'AsyncFunctionDef', 'ClassDef', 'Call', 'Assign', 'AnnAssign',
    'If', 'For', 'AsyncFor', 'While', 'Try', 'With', 'Return', 'Await',
    'Import', 'ImportFrom', 'Lambda', 'Compare', 'BinOp', 'BoolOp',
    'ListComp', 'DictComp', 'Subscript', 'Attribute',
)


class QuantumASTResonator:
    """Project AST feature counts onto a fixed orthonormal complex basis."""
    def __init__(self, max_source_bytes: int = 512 * 1024):
        if not 1024 <= max_source_bytes <= 16 * 1024 * 1024:
            raise ValueError('Invalid source quota')
        self.max_source_bytes = max_source_bytes

    def _parse(self, source: str) -> ast.AST:
        if not isinstance(source, str) or len(source.encode('utf-8')) > self.max_source_bytes:
            raise ValueError('Invalid source or source quota exceeded')
        return ast.parse(source)

    def _vector(self, tree: ast.AST) -> tuple[complex, ...]:
        counts = {feature: 0 for feature in FEATURES}
        for node in ast.walk(tree):
            name = type(node).__name__
            if name in counts:
                counts[name] += 1
        # Fixed phases distinguish feature axes; the transformation is unitary.
        raw = [math.sqrt(counts[name]) * cmath.exp(2j * math.pi * i / len(FEATURES))
               for i, name in enumerate(FEATURES)]
        norm = math.sqrt(sum(abs(x)**2 for x in raw))
        return tuple(x / norm for x in raw) if norm else tuple(0j for _ in raw)

    def similarity(self, left: str, right: str) -> float:
        a, b = self._vector(self._parse(left)), self._vector(self._parse(right))
        if not any(a) or not any(b):
            return float(a == b)
        projection = sum(x.conjugate() * y for x, y in zip(a, b))
        return max(0.0, min(1.0, abs(projection)**2))

    def analyze(self, source: str) -> dict:
        tree = self._parse(source)
        vector = self._vector(tree)
        findings: list[dict] = []
        definitions: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in definitions:
                    findings.append({'rule': 'duplicate_function_name', 'line': node.lineno})
                definitions.add(node.name)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('eval', 'exec'):
                findings.append({'rule': 'dynamic_execution', 'line': node.lineno})
        # An AST is a tree: E = V - 1, so beta_1 = 0, chi = 1.
        count = sum(1 for _ in ast.walk(tree))
        invariants = graph_invariants(count, [(i - 1, i) for i in range(1, count)])
        return {'model': 'classical-complex-hilbert', 'dimension': len(FEATURES),
                'norm_squared': sum(abs(x)**2 for x in vector),
                'nonzero_axes': sum(bool(x) for x in vector),
                'topology': invariants, 'findings': sorted(findings, key=lambda f: (f['line'], f['rule']))}
