"""Classical Hilbert-space AST embedding for deterministic structural comparisons.

This is a CPU vector-space heuristic, not quantum computation, formal verification,
or a vulnerability detector. It cannot replace parsing, tests or security analysis.
"""
from __future__ import annotations
import ast
from collections import Counter
import hashlib
import math


class ResonatorError(ValueError):
    pass


class ASTResonator:
    def __init__(self, dimensions: int = 128):
        if not 8 <= dimensions <= 4096 or dimensions & (dimensions - 1):
            raise ResonatorError('Dimensions must be a power of two between 8 and 4096')
        self.dimensions = dimensions

    def embed(self, source: str) -> tuple[complex, ...]:
        if not isinstance(source, str) or len(source.encode('utf-8')) > 2 * 1024 * 1024:
            raise ResonatorError('Source exceeds 2 MiB analysis bound')
        root = ast.parse(source)
        features: Counter[str] = Counter()
        stack: list[tuple[ast.AST, str]] = [(root, '')]
        while stack:
            node, parent = stack.pop()
            name = type(node).__name__
            features['node:' + name] += 1
            if parent:
                features['edge:' + parent + '>' + name] += 1
            # Constants and identifiers deliberately excluded: structural, not semantic.
            for child in ast.iter_child_nodes(node):
                stack.append((child, name))
        values = [0j] * self.dimensions
        for name, count in sorted(features.items()):
            h = hashlib.sha256(name.encode('utf-8')).digest()
            idx = int.from_bytes(h[:4], 'big') % self.dimensions
            phase = 2 * math.pi * int.from_bytes(h[4:8], 'big') / 2**32
            amplitude = math.log1p(count)
            values[idx] += complex(math.cos(phase), math.sin(phase)) * amplitude
        norm = math.sqrt(sum(abs(value) ** 2 for value in values))
        if norm == 0:
            raise ResonatorError('Zero-norm AST embedding')
        return tuple(value / norm for value in values)

    def similarity(self, a: tuple[complex, ...], b: tuple[complex, ...]) -> float:
        self._validate(a, b)
        return min(1.0, abs(sum(x.conjugate() * y for x, y in zip(a, b))))

    def project(self, a: tuple[complex, ...], b: tuple[complex, ...]) -> float:
        return self.similarity(a, b) ** 2

    def _validate(self, a: tuple[complex, ...], b: tuple[complex, ...]) -> None:
        if len(a) != self.dimensions or len(b) != self.dimensions:
            raise ResonatorError('Embedding dimension mismatch')
        if any(not math.isfinite(z.real) or not math.isfinite(z.imag) for z in (*a, *b)):
            raise ResonatorError('Nonfinite embedding')
